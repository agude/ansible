"""Exercise home detection and routing migration without changing host networking."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HELPER_PATH = Path(__file__).resolve().parents[1] / "roles/tailscale/files/tailscale-lan-direct.py"
HOME_MAC = "70:a7:41:99:46:36"
HOME_CONFIG = {
    "subnet": "192.168.1.0/24",
    "gateway": "192.168.1.1",
    "gateway_mac": HOME_MAC,
}


def connected_route(interface, subnet="192.168.1.0/24", metric=100):
    return {"dst": subnet, "dev": interface, "scope": "link", "metric": metric}


class Network:
    def __init__(self):
        self.connected_routes = []
        self.rules = []
        self.direct_routes = []
        self.router_macs = {}
        self.commands = []
        self.mutations = []

    def run(self, *arguments, check=True):
        self.commands.append(arguments)
        if arguments[0] == "/usr/bin/arping":
            interface = arguments[arguments.index("-I") + 1]
            mac = self.router_macs.get(interface)
            output = f"Unicast reply from {arguments[-1]} [{mac}] 1ms\n" if mac else ""
            return subprocess.CompletedProcess(arguments, 0 if mac else 1, output)

        if arguments[:3] == ("/usr/sbin/ip", "-4", "-json"):
            query = arguments[3:]
            if query == ("route", "show", "table", "main"):
                output = self.connected_routes
            elif query == ("rule", "show", "priority", "2500"):
                output = self.rules
            elif query == ("route", "show", "table", "all"):
                output = [
                    *self.connected_routes,
                    *self.direct_routes,
                    {"dst": "192.168.1.0/24", "dev": "tailscale0", "table": 52},
                ]
            else:
                raise AssertionError(f"Unexpected query: {arguments}")
            return subprocess.CompletedProcess(arguments, 0, json.dumps(output))

        self.mutations.append(arguments)
        action = arguments[2:4]
        if action == ("rule", "del"):
            assert arguments[4:] == ("priority", "2500")
            self.rules.pop(0)
        elif action == ("route", "flush"):
            assert arguments[4:] == ("table", "2500")
            self.direct_routes.clear()
        elif action == ("route", "add"):
            assert arguments[5] == "dev" and arguments[7:] == ("table", "2500")
            self.direct_routes.append({"dst": arguments[4], "dev": arguments[6], "table": 2500})
        elif action == ("rule", "add"):
            assert arguments[4] == "to"
            assert arguments[6:] == ("lookup", "2500", "priority", "2500")
            self.rules.append({"dst": arguments[5], "table": 2500, "priority": 2500})
        else:
            raise AssertionError(f"Unexpected mutation: {arguments}")
        return subprocess.CompletedProcess(arguments, 0, "")


@pytest.fixture
def helper():
    specification = importlib.util.spec_from_file_location("lan_direct", HELPER_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def network(helper, monkeypatch):
    network = Network()
    monkeypatch.setattr(helper, "run", network.run)
    return network


@pytest.mark.parametrize("interface", ["eth0", "wlan0"])
def test_home_ethernet_and_wifi_install_direct_route(helper, network, interface):
    network.connected_routes = [connected_route(interface)]
    network.router_macs[interface] = HOME_MAC.upper()

    assert helper.reconcile(HOME_CONFIG)
    assert network.direct_routes == [
        {"dst": HOME_CONFIG["subnet"], "dev": interface, "table": 2500}
    ]
    assert network.rules == [{"dst": HOME_CONFIG["subnet"], "table": 2500, "priority": 2500}]


def test_foreign_overlapping_network_removes_legacy_rule(helper, network):
    network.connected_routes = [connected_route("eth0")]
    network.router_macs["eth0"] = "00:11:22:33:44:55"
    network.rules = [{"dst": "192.168.1.0", "dstlen": 24, "table": "main"}]

    assert helper.reconcile(HOME_CONFIG)
    assert not network.rules
    assert not network.direct_routes
    assert len(network.mutations) == 1


def test_home_wifi_uses_its_own_table_with_foreign_ethernet(helper, network):
    network.connected_routes = [
        connected_route("eth0", metric=100),
        connected_route("wlan0", metric=600),
    ]
    network.router_macs = {"eth0": "00:11:22:33:44:55", "wlan0": HOME_MAC}

    assert helper.reconcile(HOME_CONFIG)
    assert network.direct_routes[0]["dev"] == "wlan0"


def test_switching_between_home_ethernet_and_wifi_replaces_route(helper, network):
    ethernet = connected_route("eth0", metric=100)
    wifi = connected_route("wlan0", metric=600)
    network.connected_routes = [ethernet, wifi]
    network.router_macs = {"eth0": HOME_MAC, "wlan0": HOME_MAC}
    helper.reconcile(HOME_CONFIG)

    for routes, expected_interface in [([wifi], "wlan0"), ([ethernet, wifi], "eth0")]:
        network.connected_routes = routes
        assert helper.reconcile(HOME_CONFIG)
        assert len(network.rules) == len(network.direct_routes) == 1
        assert network.direct_routes[0]["dev"] == expected_interface


def test_unchanged_home_network_does_not_rewrite_routes(helper, network):
    network.connected_routes = [connected_route("eth0")]
    network.router_macs["eth0"] = HOME_MAC
    helper.reconcile(HOME_CONFIG)
    network.mutations.clear()
    # iproute2 versions also print the prefix length as a separate JSON field.
    network.rules[0].update(dst="192.168.1.0", dstlen=24)

    assert not helper.reconcile(HOME_CONFIG)
    assert not network.mutations


def test_subnet_change_removes_old_state_by_priority(helper, network):
    network.connected_routes = [connected_route("eth0")]
    network.router_macs["eth0"] = HOME_MAC
    helper.reconcile(HOME_CONFIG)
    network.mutations.clear()
    network.connected_routes = [connected_route("eth0", "192.168.2.0/24")]
    new_config = {**HOME_CONFIG, "subnet": "192.168.2.0/24", "gateway": "192.168.2.1"}

    assert helper.reconcile(new_config)
    assert network.mutations[0][2:] == ("rule", "del", "priority", "2500")
    assert network.rules[0]["dst"] == "192.168.2.0/24"
    assert network.direct_routes[0]["dst"] == "192.168.2.0/24"


@pytest.mark.parametrize("router_available", [True, False])
def test_leaving_home_or_losing_router_clears_state(helper, network, router_available):
    network.connected_routes = [connected_route("eth0")]
    network.router_macs["eth0"] = HOME_MAC
    helper.reconcile(HOME_CONFIG)
    if router_available:
        network.connected_routes.clear()
    else:
        network.router_macs.clear()

    assert helper.reconcile(HOME_CONFIG)
    assert not network.rules
    assert not network.direct_routes


def test_clear_removes_duplicate_rules_without_home_config(helper, network):
    network.rules = [
        {"dst": "192.168.1.0/24", "table": "main"},
        {"dst": "192.168.2.0/24", "table": 2500},
    ]
    network.direct_routes = [{"dst": "192.168.2.0/24", "dev": "eth0", "table": 2500}]

    assert helper.reconcile()
    assert not network.rules
    assert not network.direct_routes
    assert all(command[0] != "/usr/bin/arping" for command in network.commands)
    assert not helper.reconcile()


def test_unconfigured_identity_keeps_tailscale_routing(helper, network):
    network.connected_routes = [connected_route("eth0")]
    network.router_macs["eth0"] = HOME_MAC

    assert not helper.reconcile({**HOME_CONFIG, "gateway_mac": ""})
    assert not network.mutations
    assert all(command[0] != "/usr/bin/arping" for command in network.commands)


def test_stop_does_not_read_missing_config(helper, network, monkeypatch, tmp_path):
    monkeypatch.setattr(helper, "CONFIG_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(helper, "LOCK_PATH", tmp_path / "lock")
    monkeypatch.setattr(sys, "argv", ["tailscale-lan-direct", "--clear"])
    network.rules = [{"dst": "192.168.1.0/24", "table": "main"}]

    helper.main()
    assert not network.rules


def test_failed_detection_clears_bypass_and_reports_error(helper, network, monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(HOME_CONFIG))
    monkeypatch.setattr(helper, "CONFIG_PATH", config_path)
    monkeypatch.setattr(helper, "LOCK_PATH", tmp_path / "lock")
    monkeypatch.setattr(sys, "argv", ["tailscale-lan-direct"])
    network.rules = [{"dst": "192.168.1.0/24", "table": "main"}]

    def fail_detection(config):
        raise subprocess.TimeoutExpired("arping", 10)

    monkeypatch.setattr(helper, "find_home_interface", fail_detection)
    with pytest.raises(subprocess.TimeoutExpired):
        helper.main()
    assert not network.rules


def test_disconnected_link_is_not_probed(helper, network):
    network.connected_routes = [{**connected_route("eth0"), "flags": ["linkdown"]}]
    network.router_macs["eth0"] = HOME_MAC

    assert not helper.reconcile(HOME_CONFIG)
    assert all(command[0] != "/usr/bin/arping" for command in network.commands)
