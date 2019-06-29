#!/bin/bash

# Exit if any errors or if any needed variables are unset
set -e
set -u

#Save time and temperature
time=$(date +%s)
temp=$(</sys/class/thermal/thermal_zone0/temp)

# Write to db
echo "Writing time: $time, temp: $temp"
sqlite3 /home/agude/data/data.sqlite3 "INSERT INTO temperature (datetime_id, temperate) VALUES ($time, $temp);"
