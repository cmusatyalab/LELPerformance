import pyshark
import time
import sys
from pyshark.capture.pipe_capture import PipeCapture
import csv

# InfluxDB related initialization
from influxdb import InfluxDBClient

CLOUDLET_IP = '128.2.208.248'
CLOUDLET_PORT = 8086

DB = 'experimentwaterspout'

client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=DB)
client.alter_retention_policy("autogen", database=DB, duration="30d", default=True)

pipecap = PipeCapture(pipe=sys.stdin, debug=True, display_filter="ip.addr == 128.2.208.248")

# Acceptable IP addresses to track for xran or epc
# TODO: determine if 192.168.25.76 is ever present
IP_ADDR = ['192.168.25.4', '192.168.25.2', '128.2.208.248']

# Unique identifier for experiment
EXPERIMENT_NUMBER = 0

def log_packet(pkt):

    if "ICMP" in pkt:

        # Skip the packet if not related to xran or epc
        if (pkt.ip.src not in IP_ADDR) or (pkt.ip.dst not in IP_ADDR):
            return

        # If contains response time, keep (gives RTT)

        try:
            icmp_rtt = float(pkt.icmp.resptime)
        except:
            # Don't care about packet otherwise
            return

        try:
            icmp_timestamp = str(pkt.icmp.data_time)
        except:
            return

        pkt_entry = {"measurement":"latency", "tags":{"dst":pkt.ip.dst, "src":pkt.ip.src, "experiment":EXPERIMENT_NUMBER}, "fields":{"timestamp": icmp_timestamp, "rtt": icmp_rtt}}

        packets = []
        packets.append(pkt_entry)

        client.write_points(packets)


pipecap.apply_on_packets(log_packet)