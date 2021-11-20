import pyshark
import time
import sys
from pyshark.capture.pipe_capture import PipeCapture

# InfluxDB related initialization
from influxdb import InfluxDBClient

CLOUDLET_IP = '128.2.208.248'
CLOUDLET_PORT = 8086

TCP_DB = 'cloudlettcp'
ICMP_DB = 'cloudleticmp'

tcp_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=TCP_DB)
tcp_client.alter_retention_policy("autogen", database=TCP_DB, duration="30d", default=True)

icmp_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=ICMP_DB)
icmp_client.alter_retention_policy("autogen", database=ICMP_DB, duration="30d", default=True)

pipecap = PipeCapture(pipe=sys.stdin, debug=True)

# Acceptable IP addresses to track at cloudlet
IP_ADDR = ['128.2.208.248', '128.2.212.53']

def log_packet(pkt):

    if "TCP" in pkt:

        # Skip the packet if not related to cloudlet
        if (pkt.ip.src not in IP_ADDR) or (pkt.ip.dst not in IP_ADDR):
            return
    
        try:
            tcp_timestamp = pkt.tcp.options_timestamp_tsval
        except:
            tcp_timestamp = 0

        try:
            tcp_ack = float(pkt.tcp.ack_raw)
        except:
            tcp_ack = 0
        
        pkt_entry = {"measurement":"latency", "tags":{"dst":pkt.ip.dst, "src":pkt.ip.src}, "fields":{"seqnum": int(pkt.tcp.seq_raw), "timestamp": int(tcp_timestamp), "acknum": float(tcp_ack), "epoch": float(pkt.frame_info.time_epoch)}}

        packets = []
        packets.append(pkt_entry)

        # Write to TCP database
        tcp_client.write_points(packets)
        

    elif "ICMP" in pkt:

        try:
            icmp_timestamp = str(pkt.icmp.data_time)
        except:
            return

        try:
            icmp_id = int(pkt.icmp.seq_le)
        except:
            return

        pkt_entry = {"measurement":"latency", "tags":{"dst":pkt.ip.dst, "src":pkt.ip.src}, "fields":{"data_time": icmp_timestamp, "epoch": float(pkt.frame_info.time_epoch), "identifier": icmp_id}}

        packets = []
        packets.append(pkt_entry)

        # Write to ICMP database
        icmp_client.write_points(packets)


        
pipecap.apply_on_packets(log_packet, timeout=1000)


