# Processing script for ping RTT at device measurements

import pyshark
import time
import sys
import csv
from pyshark.capture.pipe_capture import PipeCapture
import re

# InfluxDB related initialization
from influxdb import InfluxDBClient

CLOUDLET_IP = '128.2.208.248'
CLOUDLET_PORT = 8086

DB = 'experimentdevice'

client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=DB)

# File Name
FILENAME = '../logs/11-25-21-device-0.txt'
EXPERIMENT_NUMBER = 0

with open(FILENAME, 'r') as f:

    lines = f.readlines()

    # Parse each line according to regex to extract the RTT and the ICMP timestamp 
    for line in lines:
        regex_matches = re.match(".*time=([0-9.]*) ms", line)
        if regex_matches:

            parsed_rtt = []

            # Write to DB here 
            parsed_rtt.append(regex_matches[1])

            pkt_entry = {"measurement":"latency", "tags":{"experiment":EXPERIMENT_NUMBER}, "fields":{"rtt": float(regex_matches[1])}}

            packets = []
            packets.append(pkt_entry)

            client.write_points(packets)
