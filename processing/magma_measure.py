#!/usr/bin/env python
import pyshark
import time
import sys
import os
import datetime
import json
from ipaddress import ip_address
sys.path.append("../lib")

from pyshark.capture.pipe_capture import PipeCapture

# InfluxDB related initialization
from influxdb import InfluxDBClient
from optparse import OptionParser
# Logging
import simlogging
from simlogging import mconsole, logging

from local_common import createDB,getDBs

def main():
    global IP_ADDR
    global icmp_client
    global kwargs
    
    configfn = "config.json"
    cnf = {}; mcnf = {};gcnf = {}
    if configfn is not None and os.path.isfile(configfn):
        with open(configfn) as f:
            cnf = json.load(f)
            mcnf = cnf['MAGMA']
            gcnf = cnf['GENERAL']
    LOGNAME=__name__
    LOGLEV = logging.INFO
    ''' Assure values for all parameters '''
    ''' Magma related '''
    key = "logfile"; LOGFILE= mcnf[key] if key in mcnf else "magma_measure.log"
    key = "tcp_db"; TCP_DB = mcnf[key] if key in mcnf else "magmatcp"
    key = "icmp_db"; ICMP_DB = mcnf[key] if key in mcnf else "magmaicmp"

    
    ''' General '''
    key = "epc_ip"; EPC_IP = gcnf[key] if key in gcnf else "192.168.25.4"
    key = "lelgw_ip"; LELGW_IP = gcnf[key] if key in gcnf else "128.2.212.53"
    key = "cloudlet_ip" ; CLOUDLET_IP = gcnf[key] if key in gcnf else "128.2.208.248"
    key = "ue_ip"; UE_IP = gcnf[key] if key in gcnf else "172.26.21.132"
    key = "influxdb_port"; INFLUXDB_PORT = gcnf[key] if key in gcnf else 8086
    key = "influxdb_ip"; INFLUXDB_IP = gcnf[key] if key in gcnf else CLOUDLET_IP
    
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = LOGLEV,coloron=False)
    
    parser = OptionParser(usage="usage: %prog [options]")
    parser.add_option("-O", "--tcpoff",
        action="store_true", dest="tcpoff", default=False,
        help="Turn off tcp capture")
    parser.add_option("-F", "--filename", dest="filename",
        help="take input from pcap file instead of stdin", metavar="FILE")
    
    (options,args) = parser.parse_args()
    kwargs = options.__dict__.copy()
    
    ''' Initialize clients to access Cloudlet TCP and ICMP databases '''
    mconsole("Connecting to influxdb on cloudlet {}:{}".format(INFLUXDB_IP,INFLUXDB_PORT))
    tcp_client = InfluxDBClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=TCP_DB)
    if createDB(tcp_client, TCP_DB):   
        tcp_client.alter_retention_policy("autogen", database=TCP_DB, duration="30d", default=True)
    
    icmp_client = InfluxDBClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=ICMP_DB)
    if createDB(icmp_client, ICMP_DB):
        icmp_client.alter_retention_policy("autogen", database=ICMP_DB, duration="30d", default=True)
    
    # Receive input from STDIN (piped on terminal)        
    pipecap = PipeCapture(pipe=sys.stdin, debug=True) # Get from stdin
    
    # Acceptable IP addresses to track at cloudlet
    IP_ADDR = [CLOUDLET_IP, UE_IP,LELGW_IP,EPC_IP]
    
    pipecap.apply_on_packets(log_packet)

def log_packet(pkt):
    def timeconv(sstr):
        return datetime.datetime.strptime(sstr, '%Y-%m-%d %H:%M:%S.%f') \
            .strftime('%b %d, %Y %H:%M:%S.%f000 UTC')
    """
    Routine to execute for each packet received on the interface STDIN

    Extracts fields needed to correlate packets across each probe and insert into
    TCP or ICMP database
    """
    # print("LOG_PACKET-- {}".format(pkt))
    if "TCP" in pkt and not kwargs['tcpoff']:

        # Skip the packet if not related to magma
        print(f"ipsrc={pkt.ip.src} ipdst={pkt.ip.dst}")
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
        print("0: CMP SRC IP: {} DST IP: {} -- IP_ADDR: {}".format(pkt.ip.src,pkt.ip.dst,IP_ADDR))
        if (pkt.ip.src not in IP_ADDR) or (pkt.ip.dst not in IP_ADDR):
            return
        print("1: CMP SRC IP: {} DST IP: {}".format(pkt.ip.src,pkt.ip.dst))
        
        try:
            icmp_timestamp = str(pkt.icmp.data_time)
            mconsole("Has data_time: {} frame_info.time: {} {} {}" \
                  .format(icmp_timestamp,pkt.frame_info.time,pkt.ip.src,pkt.ip.dst), level="DEBUG")
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
        mconsole("Writing magma ICMP measurement -- SRC IP: {} DST IP: {} SEQUENCE: {}".format(pkt.ip.src,pkt.ip.dst,icmp_id))       
        pkt_entry = {"measurement":"latency", "tags":{"dst":pkt.ip.dst, "src":pkt.ip.src}, 
                     "fields":{"data_time": icmp_timestamp, "epoch": epoch, 
                               "identifier": icmp_id, "sequence": icmp_seq, "htime": icmp_humantime}}
        # print(pkt_entry)
        packets = []
        packets.append(pkt_entry)

        # Write to ICMP database
        icmp_client.write_points(packets)

        
        

if __name__ == '__main__': main()
