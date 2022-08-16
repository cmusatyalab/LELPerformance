import pyshark
import time
import sys
from pyshark.capture.pipe_capture import PipeCapture
sys.path.append("../lib")

# InfluxDB related initialization
from influxdb import InfluxDBClient

# Logging
import simlogging
from simlogging import mconsole, logging

def main():
    global IP_ADDR
    global icmp_client
    
    configfn = "config.json"
    cnf = {}; ccnf = {};gcnf = {}
    if configfn is not None and os.path.isfile(configfn):
        with open(configfn) as f:
            cnf = json.load(f)
            wcnf = cnf['WATERSPOUT']
            gcnf = cnf['GENERAL']
    LOGNAME=__name__
    LOGLEV = logging.INFO
    
    ''' Waterspout related '''
    key = "logfile"; LOGFILE= wcnf[key] if key in wcnf else "waterspout_measure.log"
    key = "tcp_db"; TCP_DB = wcnf[key] if key in wcnf else "waterspouttcp"
    key = "icmp_db"; ICMP_DB = wcnf[key] if key in wcnf else "waterspouticmp"

    ''' General '''
    key = "epc_ip"; EPC_IP = gcnf[key] if key in gcnf else "192.168.25.4"
    key = "lelgw_ip"; LELGW_IP = gcnf[key] if key in gcnf else "128.2.212.53"
    key = "cloudlet_ip" ; CLOUDLET_IP = gcnf[key] if key in gcnf else "128.2.208.248"
    key = "ue_ip"; UE_IP = gcnf[key] if key in gcnf else "172.26.21.132"
    key = "influxdb_port"; INFLUXDB_PORT = gcnf[key] if key in gcnf else 8086

    LOGFILE="waterspout_measure.log"
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = LOGLEV,coloron=False)
    
    mconsole("Connecting to influxdb on cloudlet {}:{}".format(CLOUDLET_IP,INFLUXDB_PORT))
    tcp_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=TCP_DB)
    if createDB(tcp_client, TCP_DB): tcp_client.alter_retention_policy("autogen", database=TCP_DB, duration="30d", default=True)
    
    icmp_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=ICMP_DB)
    if createDB(icmp_client, ICMP_DB): icmp_client.alter_retention_policy("autogen", database=ICMP_DB, duration="30d", default=True)
    
    # Filter for cloudlet packets to limit traffic to parse
    pipecap = PipeCapture(pipe=sys.stdin, debug=True, display_filter="ip.addr == {}".format(CLOUDLET_IP))
    
    # Acceptable IP addresses to track for xran or epc
    IP_ADDR = [CLOUDLET_IP, UE_IP,LELGW_IP,EPC_IP]
    
    pipecap.apply_on_packets(log_packet)

def log_packet(pkt):
    """
    Routine to execute for each packet received on the interface STDIN

    Extracts fields needed to correlate packets across each probe and insert into
    TCP or ICMP database
    """
    print("LOG_PACKET-- {}".format(pkt))
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
        
        mconsole("Writing waterspout ICMP measurement -- SRC IP: {} DST IP: {} SEQUENCE: {}".format(pkt.ip.src,pkt.ip.dst,icmp_id)) 
        pkt_entry = {"measurement":"latency", "tags":{"dst":pkt.ip.dst, "src":pkt.ip.src}, 
                     "fields":{"data_time": icmp_timestamp, "epoch": epoch, 
                               "identifier": icmp_id, "sequence": icmp_seq, "htime": icmp_humantime}}

        packets = []
        packets.append(pkt_entry)

        # Write to ICMP database
        icmp_client.write_points(packets)


def getDBs(client):
    response = client.query("show databases")
    try:
        dbs = [db[0] for db in response.raw['series'][0]['values']]
        return dbs
    except:
        mconsole("Could not parse influxdb database list: {}".format(response),level="ERROR")
    return None

def createDB(client,dbname):
    dbs = getDBs(client)
    if dbs is not None and len(dbs) > 0 and dbname in dbs:
        ''' Check openrtistdb influxdb '''
        mconsole("Database {} exists in influxdb".format(dbname))
        return True
    else:
        mconsole("Creating database {} in influxdb".format(dbname))
        client.create_database(dbname)
        client.alter_retention_policy("autogen", database=dbname, duration="30d", default=True)
        client.create_retention_policy('DefaultRetentionPolicy', '365d', "3", database = dbname, default=True)
        dbs = getDBs(client)
        if not dbname in dbs:
            mconsole("Could not create: {}".format(DBNAME),level="ERROR")
            return False
    return True

if __name__ == '__main__': main()

