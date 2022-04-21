#!/usr/bin/env python

import sys

sys.path.append("../lib")
import os
from influxdb import InfluxDBClient, DataFrameClient
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import time
from pyutils import *
from pdutils import *
from pdpltutils import *

from optparse import OptionParser
import simlogging
from simlogging import mconsole
''' 
    This program deletes the data in the various databases either en masse or measurement by measurement
'''
LOGNAME=__name__
LOGLEV = logging.DEBUG

# Hardcode cloudlet IP and port for DB
CLOUDLET_IP = '128.2.208.248'
EPC_IP = '192.168.25.4'
CLOUDLET_PORT = 8086
TZ = 'America/New_York'
''' Obtain clients for ICMP databases ''' 
CLOUDLET_ICMP_DB = 'cloudleticmp'
WATERSPOUT_ICMP_DB = 'waterspouticmp'
UE_ICMP_DB = 'ueicmp'
SEG_DB = 'segmentation'
OFFSET_DB = 'winoffset'
measuredict = {CLOUDLET_ICMP_DB:['latency'],UE_ICMP_DB:['latency'],WATERSPOUT_ICMP_DB:['latency']
               ,SEG_DB:['uplink','downlink'],OFFSET_DB:['winoffset']}

def main():
    global logger
    LOGFILE="database_clean.log"
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = LOGLEV,coloron=False)
    (options,_) = cmdOptions()
    kwargs = options.__dict__.copy()
    mconsole("Warning: this program will delete information from your database.")
    entry = input("Do you want to continue? [y/N] ") or "n"
    if entry in ['Y','y']:
        entry = input("VERY DANGEROUS: Do you want to delete all of the data? [y/N] ") or "n"
        if entry in ['Y','y']:
            mconsole("Deleting all of the data")
            kwargs['DELETEALL'] = True
        else:
            mconsole("OK, walking you through each measurement")
            kwargs['DELETEALL'] = False
        for db in measuredict.keys():
            dfclient = DataFrameClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=db)
            wtclient = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=db)
            for measure in measuredict[db]:
                try:
                    tdfx = dfclient.query("select * from {}".format(measure))[measure]
                except:
                    mconsole("{}.{} has no measurements; continuing".format(db,measure))
                    continue
                mconsole("{}.{} has {} measurements".format(db,measure,len(tdfx)))
                mdel = kwargs['DELETEALL']
                if not mdel:
                    mconsole("NO RETURN: Do you want to drop all {} measurements from {}.{}".format(len(tdfx),db,measure))
                    entry = input("[y/N] ") or "n"
                    if entry in ['Y','y']: mdel = True
                if mdel: deleteMeasure(db,measure,wtclient)

def deleteMeasure(db,measure,wtclient):
    mconsole("Dropping {}.{}".format(db,measure))
    wtclient.drop_measurement(measure)
    
    

def cmdOptions():
    parser = OptionParser(usage="usage: %prog [options]")
    parser.add_option("-d", "--debug",
                  action="store_true", dest="debug", default=False,
                  help="Debugging mode")
    return  parser.parse_args()

if __name__ == '__main__': main()