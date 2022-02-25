import pyshark
import time
import sys
import os
from pyshark.capture.pipe_capture import PipeCapture

# InfluxDB related initialization
from influxdb import InfluxDBClient
from optparse import OptionParser

ECLIPSE_DEBUG = True

CLOUDLET_IP = '128.2.208.248'
CLOUDLET_PORT = 8086

TCP_DB = 'cloudlettcp'
ICMP_DB = 'cloudleticmp'
FIFO_NAME = 'clfifo'

# Initialize clients to access Cloudlet TCP and ICMP databases

parser = OptionParser(usage="usage: %prog [options]")
parser.add_option("-f", "--fifo",
    action="store_true", dest="fifo", default=False,
    help="Use a named pipe (fifo) instead of stdin")
parser.add_option("-O", "--tcpoff",
    action="store_true", dest="tcpoff", default=False,
    help="Turn off tcp capture")

(options,args) = parser.parse_args()
kwargs = options.__dict__.copy()

tcp_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=TCP_DB)
tcp_client.alter_retention_policy("autogen", database=TCP_DB, duration="30d", default=True)

icmp_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=ICMP_DB)
icmp_client.alter_retention_policy("autogen", database=ICMP_DB, duration="30d", default=True)

# Receive input from STDIN (piped on terminal)

if kwargs['fifo']:
    clfifo = os.open(FIFO_NAME, os.O_RDONLY) # Get from fifo
    pipecap = PipeCapture(pipe=clfifo, debug=True)
else:
    pipecap = PipeCapture(pipe=sys.stdin, debug=True) # Get from stdin

# Acceptable IP addresses to track at cloudlet
IP_ADDR = ['128.2.208.248', '128.2.212.53','172.26.25.174']

def log_packet(pkt):
    """
    Routine to execute for each packet received on the interface STDIN

    Extracts fields needed to correlate packets across each probe and insert into
    TCP or ICMP database
    """
    
    if "TCP" in pkt and not kwargs['tcpoff']:

        # Skip the packet if not related to cloudlet
        if (pkt.ip.src not in IP_ADDR) or (pkt.ip.dst not in IP_ADDR):
            return
        
        # print("TCP SRC IP: {} DST IP: {}".format(pkt.ip.src,pkt.ip.dst)) 
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
        print("ICMP SRC IP: {} DST IP: {}".format(pkt.ip.src,pkt.ip.dst))
        try:
            icmp_timestamp = str(pkt.icmp.data_time)
        except:
            return

        try:
            icmp_id = int(pkt.icmp.seq_le)
        except:
            return

        try:
            epoch = float(pkt.frame_info.time_epoch)
        except:
            return

        pkt_entry = {"measurement":"latency", "tags":{"dst":pkt.ip.dst, "src":pkt.ip.src}, "fields":{"data_time": icmp_timestamp, "epoch": epoch, "identifier": icmp_id}}
        print(pkt_entry)
        packets = []
        packets.append(pkt_entry)

        # Write to ICMP database
        icmp_client.write_points(packets)


        
pipecap.apply_on_packets(log_packet)


