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
from pyshark.capture.file_capture import FileCapture

# InfluxDB related initialization
from influxdb import InfluxDBClient
from optparse import OptionParser
# Logging
import simlogging
from simlogging import mconsole, logging

from local_common import createDB,getDBs

DEFAULTS = {}

def main():
    # global kwargs
    global cnf
    global logger
    global systemname

    ''' Configuration '''
    configfn = "config.json"
    cnf = {}
    if configfn is not None and os.path.isfile(configfn):
        with open(configfn) as f:
            cnf = json.load(f)  
    (options,_) = cmdOptions()
    kwargs = options.__dict__.copy()
    cnf.update(kwargs)
    systemnamekey = cnf['SYSTEM']
    systemname = systemnamekey.lower()
    cnf.update(cnf['GENERAL'])
    cnf.update(cnf[systemnamekey])
    
    ''' Logging '''
    LOGNAME=__name__
    LOGLEV = logging.INFO

    key = "logfile"; LOGFILE= cnf[key] if key in cnf else f"{systemname}_measure.log"
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = LOGLEV,coloron=False)   
    retcode = job_execute(**cnf)
    
def job_execute(**cnf):
    global IP_ADDR
    global icmp_client
    
    ''' Assure values for all parameters '''

    ''' System specific related '''
    key = "tcp_db"; TCP_DB = cnf[key] if key in cnf else f"{systemname}tcp"
    key = "icmp_db"; ICMP_DB = cnf[key] if key in cnf else f"{systemname}icmp"
    
    ''' General '''
    key = "epc_ip";         EPC_IP = cnf[key] if key in cnf else DEFAULTS[key]
    key = "s1_ip";          S1_IP = cnf[key] if key in cnf else DEFAULTS[key]
    key = "sg1_ip";         SG1_IP = cnf[key] if key in cnf else DEFAULTS[key]
    key = "enb_ip";         ENB_IP = cnf[key] if key in cnf else DEFAULTS[key]
    key = "lelgw_ip";       LELGW_IP = cnf[key] if key in cnf else DEFAULTS[key]
    key = "cloudlet_ip" ;   CLOUDLET_IP = cnf[key] if key in cnf else DEFAULTS[key]
    key = "ue_ip";          UE_IP = cnf[key] if key in cnf else DEFAULTS[key]
    key = "influxdb_port";  INFLUXDB_PORT = cnf[key] if key in cnf else DEFAULTS[key]
    key = "influxdb_ip";    INFLUXDB_IP = cnf[key] if key in cnf else DEFAULTS[key]
    
    ''' Initialize clients to access Cloudlet TCP and ICMP databases '''
    mconsole(f"Connecting to influxdb on cloudlet {INFLUXDB_IP}:{INFLUXDB_PORT}")
    tcp_client = InfluxDBClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=TCP_DB)
    if createDB(tcp_client, TCP_DB):   
        tcp_client.alter_retention_policy("autogen", database=TCP_DB, duration="30d", default=True)
    
    icmp_client = InfluxDBClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=ICMP_DB)
    if createDB(icmp_client, ICMP_DB):
        icmp_client.alter_retention_policy("autogen", database=ICMP_DB, duration="30d", default=True)
       
    # Acceptable IP addresses to track at system
    IP_ADDR = [CLOUDLET_IP, UE_IP,LELGW_IP,SG1_IP,S1_IP,ENB_IP]
    
    if ('filename' in cnf and cnf['filename'] is not None and os.path.isfile(cnf['filename'])):
        ''' Receive input from pcap file '''
        pipecap = FileCapture(cnf['filename'], debug=True)
    else:
        ''' Receive input from STDIN (piped on terminal) '''        
        pipecap = PipeCapture(pipe=sys.stdin, debug=True) # Get from stdin
 
    pipecap.apply_on_packets(log_packet)
    
def cmdOptions():
    parser = OptionParser(usage="usage: %prog [options]")
    parser.add_option("-d", "--debug",
                  action="store_true", dest="debug", default=False,
                  help="Debugging mode")
    parser.add_option("-O", "--tcpoff",
        action="store_true", dest="tcpoff", default=False,
        help="Turn off tcp capture")
    parser.add_option("-F", "--filename", dest="filename",
        help="take input from pcap file instead of stdin", metavar="FILE")
    parser.add_option("-S", "--system", dest="SYSTEM", default="MAGMA",
        help="System to run on SYSTEM (MAGMA, CLOUDLET,UE)", metavar="SYSTEM")
    
    return  parser.parse_args()

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
    if "TCP" in pkt and not cnf['tcpoff']:

        # Skip the packet if not related to magma
        # print(f"ipsrc={pkt.ip.src} ipdst={pkt.ip.dst}")
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
        mconsole(f"0: CMP SRC IP: {pkt.ip.src} DST IP: {pkt.ip.dst} -- IP_ADDR: {IP_ADDR}", level="DEBUG")
        if (pkt.ip.src not in IP_ADDR) or (pkt.ip.dst not in IP_ADDR):
            return
        mconsole(f"1: CMP SRC IP: {pkt.ip.src} DST IP: {pkt.ip.dst}", level="DEBUG")
        
        try:
            icmp_timestamp = str(pkt.icmp.data_time)
            mconsole(f"Has data_time: {icmp_timestamp} frame_info.time: {pkt.frame_info.time} {pkt.ip.src} {pkt.ip.dst}", \
                  level="DEBUG")
        except:
            icmp_timestamp = "0"

        try:
            icmp_id = int(pkt.icmp.seq_le)
            icmp_seq = f"{pkt.icmp.seq}/{pkt.icmp.seq_le}"
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
        mconsole(f"Writing {systemname} ICMP meas -- SRC: {pkt.ip.src} DST: {pkt.ip.dst} SEQ: {icmp_seq} {icmp_humantime}")       
        pkt_entry = {"measurement":"latency", "tags":{"dst":pkt.ip.dst, "src":pkt.ip.src}, 
                     "fields":{"data_time": icmp_timestamp, "epoch": epoch, 
                               "identifier": icmp_id, "sequence": icmp_seq, "htime": icmp_humantime}}
        # print(pkt_entry)
        packets = []
        packets.append(pkt_entry)

        # Write to ICMP database
        icmp_client.write_points(packets)
        
    else:
        pass

    
    DEFAULTS =    {    
        "lelgw_ip":"128.2.212.53",
        "epc_ip":"128.2.211.195",
        "cloudlet_ip":"128.2.208.222",
        "influxdb_ip":"128.2.211.195",
        "influxdb_port":"8086",
        "enb_ip":"192.168.25.13",
        "s1_ip":"192.168.25.116",
        "sg1_ip":"192.168.122.47",
        "influxdb_adminport":"8088",
        "influxdb_backup_root":"~/influxdb_backup",
        "timezone":"America/New_York" ,
        "ue_ip":"192.168.128.13",
    } 
        

if __name__ == '__main__': main()
