import time
import sys
import os
import re
# from datetime import datetime

sys.path.append("../lib")
from influxdb import InfluxDBClient, DataFrameClient
import numpy as np
import pandas as pd

from pyutils import *
from pdutils import *
from pdpltutils import *

import logging
import simlogging
from simlogging import mconsole

if os.name == 'nt':
    OSNAME='WINDOWS'
else:
    OSNAME='OTHER'
    
LOGNAME=__name__

# Hardcode cloudlet IP and port for DB
CLOUDLET_IP = '128.2.208.248'
CLOUDLET_PORT = 8086
NTPSERVER = "0.north-america.pool.ntp.org"
NTPSERVER = "north-america.pool.ntp.org"
NTPSERVER = "labgw.elijah.cs.cmu.edu"
BATCHSIZE = 20
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
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = logging.INFO,coloron=False)
    offset_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=DBNAME)
    while True:
        ''' This command must be run as administrator '''
        batch = getBatch()
        batch = parseBatch(batch)
        mconsole("Writing {} offset measurements".format(len(batch)))
        batch.reset_index().apply(writeInfluxDB,client=offset_client, axis=1)
    pass

def getBatch(ntpserver = NTPSERVER, batchsize = BATCHSIZE,output = False):
    ''' This command must be run as administrator '''
    cmdstr = "w32tm.exe /stripchart /computer:{} /samples:{}".format(ntpserver,batchsize)
    ret = cmd_all(cmdstr,output=output)
    btch = ret['stdout'][-BATCHSIZE-1:-1] # Blank line at end
    return btch

def parseBatch(btch,ntpserver = NTPSERVER):
    retdict = {}
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    for line in btch:
        if 'error' in line: continue
        o = float(offre.findall(line)[0][2:-1])
        d = dtre.findall(line)[0][:-1]
        ds = TZ.localize(datetime.datetime.strptime("{} {}".format(today,d),"%Y-%m-%d %H:%M:%S"))
        retdict[ds] = o
        pass
    retdf = pd.DataFrame.from_dict(retdict,orient='index',columns=['OFFSET'])
    retdf.index.name = 'TIMESTAMP'
    retdf['NTPSERVER'] = ntpserver
    
    return retdf
    
def writeInfluxDB(row,client = None):
    
    pkt_entry = {"measurement":MEASURENAME,
                 "tags": {"ntpserver": row['NTPSERVER'],'TIMESTAMP':row.TIMESTAMP}, 
                 "fields":{"offset": row['OFFSET']},"time":int(row.TIMESTAMP.timestamp())}
    client.write_points([pkt_entry], time_precision = 's')

if __name__ == '__main__': main()