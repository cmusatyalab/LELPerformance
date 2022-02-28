import pyshark
import time
import sys
from pyshark.capture.pipe_capture import PipeCapture

# InfluxDB related initialization
from influxdb import InfluxDBClient

CLOUDLET_IP = '128.2.208.248'
CLOUDLET_PORT = 8086

UE_IP = '192.168.25.4'

TCP_DB = 'waterspouttcp'
ICMP_DB = 'waterspouticmp'

tcp_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=TCP_DB)
tcp_client.alter_retention_policy("autogen", database=TCP_DB, duration="30d", default=True)

icmp_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=ICMP_DB)
icmp_client.alter_retention_policy("autogen", database=ICMP_DB, duration="30d", default=True)

# Filter for cloudlet packets to limit traffic to parse
pipecap = PipeCapture(pipe=sys.stdin, debug=True, display_filter="ip.addr == 128.2.208.248")

# Acceptable IP addresses to track for xran or epc
# TODO: determine if 192.168.25.76 is ever present
IP_ADDR = [UE_IP, '192.168.25.2', CLOUDLET_IP]

def log_packet(pkt):
    """
    Routine to execute for each packet received on the interface STDIN

    Extracts fields needed to correlate packets across each probe and insert into
    TCP or ICMP database
    """

    if "TCP" in pkt:

        # Skip the packet if not related to xran or epc
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

        
        # Adjust the packets if XRAN -> EPC packet
        pkt_entry = {"measurement":"latency", "tags":{"dst":pkt.ip.dst, "src":pkt.ip.src}, 
                     "fields":{"seqnum": int(pkt.tcp.seq_raw), "timestamp": int(tcp_timestamp), 
                               "acknum": float(tcp_ack), "epoch": float(pkt.frame_info.time_epoch)}}

        packets = []
        packets.append(pkt_entry)

        # Write to TCP database
        tcp_client.write_points(packets)
        

    elif "ICMP" in pkt:
        print("1: ICMP SRC IP: {} DST IP: {}".format(pkt.ip.src,pkt.ip.dst))
        try:
            icmp_timestamp = str(pkt.icmp.data_time)
        except:
            icmp_timestamp = "0"

        try:
            icmp_id = int(pkt.icmp.seq_le)
            icmp_seq = "{}/{}".format(str(pkt.icmp.seq),str(pkt.icmp.seq_le))
        except:
            return

        try:
            epoch = float(pkt.frame_info.time_epoch)
        except:
            return
        
        try:
            icmp_humantime = str(pkt.frame_info.time)
        except:
            return
        
        # print("2: ICMP SRC IP: {} DST IP: {}".format(pkt.ip.src,pkt.ip.dst))
        pkt_entry = {"measurement":"latency", "tags":{"dst":pkt.ip.dst, "src":pkt.ip.src}, 
                     "fields":{"data_time": icmp_timestamp, "epoch": epoch, 
                               "identifier": icmp_id, "sequence": icmp_seq, "htime": icmp_humantime}}

        packets = []
        packets.append(pkt_entry)

        # Write to ICMP database
        icmp_client.write_points(packets)


        
pipecap.apply_on_packets(log_packet)


