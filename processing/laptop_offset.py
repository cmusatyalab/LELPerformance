import time
import sys
import os
import re
import time
# from datetime import datetime

sys.path.append("../lib")
from influxdb import InfluxDBClient, DataFrameClient
import numpy as np
import pandas as pd
from optparse import OptionParser

from pyutils import *
from pdutils import *
from pdpltutils import *

import logging
import simlogging
from simlogging import mconsole

if os.name == 'nt':
    OSNAME='WINDOWS'
elif os.name == 'posix':
    OSNAME='LINUX'
else:
    OSNAME='OTHER'
    
LOGNAME=__name__
LOGLEV = logging.INFO

# Hardcode cloudlet IP and port for DB
CLOUDLET_IP = '128.2.208.248'
CLOUDLET_PORT = 8086
NTPSERVER = "0.north-america.pool.ntp.org"
NTPSERVER = "north-america.pool.ntp.org"
NTPSERVER = "labgw.elijah.cs.cmu.edu"
BATCHSIZE = 20
SLEEPTIME = 3
DBNAME = 'winoffset'
MEASURENAME = 'winoffset'

TZ = pytz.timezone('America/New_York')


''' Regular expression matching '''
offrestr = 'o\:.*s'
dtrerstr = '^.*,'
offre = re.compile(offrestr)
dtre = re.compile(dtrerstr)

def main():
    global logger
    LOGFILE="{}_offset.log".format(OSNAME)
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = LOGLEV,coloron=False)
    (options,_) = cmdOptions()
    kwargs = options.__dict__.copy()
    offset_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=DBNAME)
    mconsole("Starting offset measurements against {} with batchsize={} and {} seconds between batches" \
             .format(NTPSERVER,kwargs['batchsize'],kwargs['querytime']))
    while True:
        ''' This command must be run as administrator '''
        batch = getBatch(batchsize = kwargs['batchsize'])
        batch = parseBatch(batch)
        mconsole("Writing {} offset measurements".format(len(batch)))
        batch.reset_index().apply(writeInfluxDB,client=offset_client, axis=1)
        time.sleep(int(kwargs['querytime']))
    pass

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

def getBatch(ntpserver = NTPSERVER, batchsize = BATCHSIZE,output = False):
    ''' This command must be run as administrator in windows '''
    if OSNAME == 'WINDOWS':
        cmdstr = "w32tm.exe /stripchart /computer:{} /samples:{}".format(ntpserver,batchsize)
        ret = cmd_all(cmdstr,output=output)
        btch = ret['stdout'][-batchsize-1:-1] # Blank line at end
    elif OSNAME == 'LINUX':
        cmdstr = "./chronyoffset.sh {} {}".format(ntpserver,batchsize)
        ret = cmd_all(cmdstr,output=output)
        btch = ret['stdout']
    return btch

def parseBatch(btch,ntpserver = NTPSERVER):
    retdict = {}
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    ''' Parse windows (w32tm /stripchart) '''
    if OSNAME == "WINDOWS":
        for line in btch:
            if 'error' in line: continue
            o = float(offre.findall(line)[0][2:-1])
            d = dtre.findall(line)[0][:-1]
            ds = TZ.localize(datetime.datetime.strptime("{} {}".format(today,d),"%Y-%m-%d %H:%M:%S"))
            retdict[ds] = o
            pass
    elif OSNAME == "LINUX":
        for line in btch:
            lnlst = line.split()
            if len(lnlst) < 9:
                # mconsole("Bad offset line: {}".format(line),level="ERROR")
                continue
            o = lnlst[7]
            if o.endswith("ns"): oo = float(o[:-2]) * 1e-9
            elif o.endswith("us"): oo = float(o[:-2]) * 1e-6
            elif o.endswith("ms"): oo = float(o[:-2]) * 1e-3
            d = lnlst[0][:-6]
            ds = TZ.localize(datetime.datetime.strptime(d,"%Y-%m-%dT%H:%M:%S"))
            retdict[ds] = oo
            pass
    retdf = pd.DataFrame.from_dict(retdict,orient='index',columns=['OFFSET'])
    retdf.index.name = 'TIMESTAMP'
    retdf['NTPSERVER'] = ntpserver
    
    return retdf
    
def writeInfluxDB(row,client = None):
    mconsole("Writing measurement -- offset={} TIMESTAMP={} ntpserver={} ostype={}" \
             .format(row.OFFSET,row.TIMESTAMP,row.NTPSERVER,OSNAME), level="DEBUG") 
    pkt_entry = {"measurement":MEASURENAME,
                 "tags": {"ntpserver": row['NTPSERVER'],'TIMESTAMP':row.TIMESTAMP,'ostype':OSNAME}, 
                 "fields":{"offset": row['OFFSET']},"time":int(row.TIMESTAMP.timestamp())}
    client.write_points([pkt_entry], time_precision = 's')

if __name__ == '__main__': main()