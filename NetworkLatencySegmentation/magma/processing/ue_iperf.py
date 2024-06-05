import time
import sys
import os
import re
import time

sys.path.append("../lib")
from influxdb import InfluxDBClient, DataFrameClient
import numpy as np
import pandas as pd
import iperf3
from optparse import OptionParser

from pyutils import *
from pdutils import *
from pdpltutils import *

import logging
import simlogging
from simlogging import mconsole
from local_common import *

  
LOGNAME=__name__
LOGLEV = logging.INFO

# Hardcode cloudlet IP and port for DB
CLOUDLET_IP = '192.168.8.153'
CLOUDLET_PORT = 8086
BATCHSIZE = 1
SLEEPTIME = 1
DBNAME = 'iperf'
MEASURENAME = 'throughput'

TZ = pytz.timezone('America/New_York')

def main():
    global logger
    LOGFILE="iperf.log"
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = LOGLEV,coloron=False)
    kwargs = configure()
    influx_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=DBNAME)
    
    createDB(influx_client,DBNAME)
    mconsole("Starting iperf measurements")
    reverse = False # Start with client to server
    direction = "uplink"
    while True:
        iperf_client = getIperfClient(reverse = reverse, **kwargs)
        results = getIperf(client = iperf_client,**kwargs)
        if results is not None:
            batch = parseIperf(results = results, direction = direction, **kwargs)
            mconsole("Writing {} iperf measurements".format(len(batch)))
            batch.reset_index().apply(writeInfluxDB, client=influx_client, axis=1)
        del iperf_client
        reverse = False if reverse else True # Toggle
        direction = "downlink" if direction == "uplink" else "uplink"
        time.sleep(int(kwargs['querytime']))
    pass

def getIperf(client = None, **kwargs):
    try:
        results = client.run()
        mconsole(f"Received Mbps={results.received_Mbps}")
    except:
        mconsole("Iperf run failed", level="ERROR")
        return None
    return results

def parseIperf(results = None, direction = None, timezone = None, **kwargs):
    tdfx = pd.DataFrame(results.__dict__)[IPERFIELDS + IPERFTAGS]
    # for col in tdfx.columns:
    #     mconsole(f"columns={col}, val={tdfx[col]} type = {type(tdfx[col].iloc[0])}", level="DEBUG")
    tdfx['direction'] = direction
    tdfx['TIMESTAMP']= pd.to_datetime(tdfx['timesecs'],unit='s',utc=True) # convenience
    tdfx = changeTZ(tdfx,col='TIMESTAMP',origtz='UTC', newtz=timezone)
    tdfx = renamecol(tdfx,col='time',newname='humantime')
    tdfx = renamecol(tdfx,col='received_Mbps',newname='throughput')
    mconsole(f"Mbps={list(tdfx.throughput)}",level="DEBUG")
    return tdfx[-1:]

def getIperfClient(port = 5201, cloudlet_ip = None, reverse = False, ue_ip = None, **kwargs):
    client = iperf3.Client()
    client.duration = 1
    client.bind_address = ue_ip
    client.server_hostname = cloudlet_ip
    client.port = port
    # client.blksize = 1234
    client.num_streams = 3
    client.zerocopy = True
    client.verbose = False
    client.reverse = reverse
    return client

def configure():
    (options,_) = cmdOptions()
    cmdopts = options.__dict__.copy()
    configfn = "config.json"
    cnf = {}; ccnf = {};gcnf = {}
    if configfn is not None and os.path.isfile(configfn):
        with open(configfn) as f:
            cnf = json.load(f)
        cnf.update(cmdopts)
        cnf.update(cnf['GENERAL'])
        cnf.update(cnf['QUERY'])
    else:
        cnf = cmdopts
    return cnf

def cmdOptions():
    parser = OptionParser(usage="usage: %prog [options]")
    parser.add_option("-d", "--debug",
                  action="store_true", dest="debug", default=False,
                  help="Debugging mode")
    parser.add_option("-B", "--batchsize", dest="batchsize", type = 'int',
                  help="How many measurements per query", metavar="INT",default=BATCHSIZE)
    parser.add_option("-T", "--querytime", dest="querytime", type = 'int',
                  help="How long to wait between batches (s)", metavar="INT",default=SLEEPTIME)
    return  parser.parse_args()

    
def writeInfluxDB(row, client = None):
    mconsole(f"Writing measurement -- mbps={row.throughput} direction = {row.direction} TIME={row.humantime}", level="INFO")
    tagdict = {k:str(row[k]) for k in FIPERFTAGS}
    fielddict = {k:row[k] for k in FIPERFIELDS}
    pkt_entry = {"measurement":MEASURENAME,
                 "tags": tagdict,
                 "fields":fielddict,"time":int(row.TIMESTAMP.timestamp())}
    client.write_points([pkt_entry], time_precision = 's')

IPERFCOLS = ['text', 'json', 'error', 'time', 'timesecs', 'system_info', 'version',
       'local_host', 'local_port', 'remote_host', 'remote_port',
       'tcp_mss_default', 'protocol', 'num_streams', 'blksize', 'omit',
       'duration', 'local_cpu_total', 'local_cpu_user', 'local_cpu_system',
       'remote_cpu_total', 'remote_cpu_user', 'remote_cpu_system',
       'sent_bytes', 'sent_bps', 'received_bytes', 'received_bps', 'sent_kbps',
       'sent_Mbps', 'sent_kB_s', 'sent_MB_s', 'received_kbps', 'received_Mbps',
       'received_kB_s', 'received_MB_s', 'retransmits']

IPERFIELDS = ['timesecs','received_Mbps']
IPERFTAGS = ['time','local_host', 'remote_host']
FIPERFTAGS = ['humantime','local_host', 'remote_host','direction']
FIPERFIELDS = ['timesecs','throughput']


if __name__ == '__main__': main()