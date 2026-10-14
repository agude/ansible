#!/usr/bin/python3
"""Keep a direct home LAN route only while the home router is on-link."""

import argparse
import fcntl
import ipaddress
import json
import re
import subprocess
from pathlib import Path

# These identifiers belong exclusively to this helper, including legacy rules.
RULE_PRIORITY = 2500
ROUTE_TABLE = 2500
CONFIG_PATH = Path("/etc/tailscale-lan-direct.json")
LOCK_PATH = Path("/run/tailscale-lan-direct.lock")


def run(*arguments, check=True):
    return subprocess.run(arguments, check=check, text=True, stdout=subprocess.PIPE, timeout=10)


def read_ip(*arguments):
    return json.loads(run("/usr/sbin/ip", "-4", "-json", *arguments).stdout)


def find_home_interface(config):
    if not config["gateway"] or not config["gateway_mac"]:
        return None

    subnet = ipaddress.IPv4Network(config["subnet"])
    gateway = ipaddress.IPv4Address(config["gateway"])
    if gateway not in subnet:
        raise ValueError("Home gateway must be inside home_lan_subnet")

    routes = read_ip("route", "show", "table", "main")
    for route in sorted(routes, key=lambda route: route.get("metric", 0)):
        if (
            route.get("dst") != str(subnet)
            or route.get("scope") != "link"
            or "linkdown" in route.get("flags", [])
        ):
            continue

        # Probe each link: a cached neighbor can belong to the previous network.
        probe = run(
            "/usr/bin/arping",
            "-f",
            "-c",
            "2",
            "-w",
            "2",
            "-I",
            route["dev"],
            str(gateway),
            check=False,
        )
        addresses = re.findall(r"\[([0-9a-fA-F:]{17})\]", probe.stdout)
        if probe.returncode == 0 and config["gateway_mac"].lower() in (
            address.lower() for address in addresses
        ):
            return route["dev"]

    return None


def reconcile(config=None):
    interface = find_home_interface(config) if config else None
    rules = read_ip("rule", "show", "priority", str(RULE_PRIORITY))
    routes = [
        route
        for route in read_ip("route", "show", "table", "all")
        if str(route.get("table")) == str(ROUTE_TABLE)
    ]

    if interface and len(rules) == 1 and len(routes) == 1:
        rule = rules[0]
        destination = rule.get("dst", "all")
        if "dstlen" in rule:
            destination += f"/{rule['dstlen']}"
        if (
            destination == config["subnet"]
            and str(rule.get("table")) == str(ROUTE_TABLE)
            and routes[0].get("dst") == config["subnet"]
            and routes[0].get("dev") == interface
        ):
            return False

    for _ in rules:
        run("/usr/sbin/ip", "-4", "rule", "del", "priority", str(RULE_PRIORITY))
    if routes:
        run("/usr/sbin/ip", "-4", "route", "flush", "table", str(ROUTE_TABLE))
    if interface:
        # A dedicated table keeps another interface's overlapping route out.
        run(
            "/usr/sbin/ip",
            "-4",
            "route",
            "add",
            config["subnet"],
            "dev",
            interface,
            "table",
            str(ROUTE_TABLE),
        )
        run(
            "/usr/sbin/ip",
            "-4",
            "rule",
            "add",
            "to",
            config["subnet"],
            "lookup",
            str(ROUTE_TABLE),
            "priority",
            str(RULE_PRIORITY),
        )
    return bool(rules or routes or interface)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clear", action="store_true", help="Remove owned routing state")
    arguments = parser.parse_args()
    # Serialize the boot service, dispatcher events, and Ansible reconciliation.
    with LOCK_PATH.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            config = None if arguments.clear else json.loads(CONFIG_PATH.read_text())
            changed = reconcile(config)
        except (OSError, ValueError, subprocess.SubprocessError):
            # Detection or config failures must not leave a bypass on a foreign LAN.
            if not arguments.clear:
                reconcile()
            raise
        if changed:
            print("changed")


if __name__ == "__main__":
    main()
