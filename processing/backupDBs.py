#!/usr/bin/env python

import sys

sys.path.append("../lib")
import os
from influxdb import InfluxDBClient, DataFrameClient
import numpy as np
import pandas as pd
import time
from pyutils import *
from pdutils import *

from optparse import OptionParser
import simlogging
from simlogging import mconsole
''' 
    This program backups the various databases as an influxdb portable backup and/or as individual csvs
'''
LOGNAME=__name__
LOGLEV = logging.DEBUG

def main():
    global logger
    kwargs = configure()
    
     # override
    
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = LOGLEV,coloron=False)
    if not os.path.exists(INFLUXDB_BACKUP_ROOT): 
        os.makedirs(INFLUXDB_BACKUP_ROOT)
    budir = os.path.join(INFLUXDB_BACKUP_ROOT,humandatenow())
    os.makedirs(budir)
    mconsole("Begin backups to {}".format(budir))
    entry = input("Do you want to do an influxdb portable backup? [y/N] ") or "n"
    if entry in ['Y','y']:       
        cmd = "influxd backup -portable -host {}:{} {}" \
            .format(INFLUXDB_IP,INFLUXDB_ADMINPORT,budir)
        oscmd(cmd)
    entry = input("Do you want to a csv file of each measurement? [y/N] ") or "n"
    if entry in ['Y','y']:
        for db in measuredict.keys():
            dfclient = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=db)
            wtclient = InfluxDBClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=db)
            for measure in measuredict[db]:
                measuretag = "{}.{}".format(db,measure)
                try:
                    tdfx = dfclient.query("select * from {}".format(measure))[measure]
                except:
                    mconsole("{} has no measurements; continuing".format(measuretag))
                    continue
                fn = "{}.csv".format(measuretag)
                mconsole("Writing {} with {} measurements".format(fn,len(tdfx)))
                writejoin(tdfx,budir,fn)

def configure():
    global seg_client;global df_seg_client; global df_cloudlet_icmp_client
    global df_waterspout_icmp_client;global df_ue_icmp_client
    global INFLUXDB_IP; global INFLUXDB_PORT;global INFLUXDB_ADMINPORT; global INFLUXDB_BACKUP_ROOT; global measuredict
    global LOGFILE; global LOGNAME; global LOGLEV

    LOGNAME=__name__
    LOGLEV = logging.INFO
    
    configfn = "config.json"
    cnf = {}; ccnf = {};gcnf = {}
    if configfn is not None and os.path.isfile(configfn):
        with open(configfn) as f:
            cnf = json.load(f)
            qcnf = cnf['QUERY']
            gcnf = cnf['GENERAL']
            ucnf = cnf['UE']
            ccnf = cnf['CLOUDLET']
            wcnf = cnf['WATERSPOUT']
    ''' General '''
    key = "influxdb_port"; INFLUXDB_PORT = gcnf[key] if key in gcnf else 8086
    key = "influxdb_adminport"; INFLUXDB_ADMINPORT = gcnf[key] if key in gcnf else 8088
    key = "influxdb_backup_root"; INFLUXDB_BACKUP_ROOT = gcnf[key] if key in gcnf else "~/influxdb_backup"
    INFLUXDB_BACKUP_ROOT = os.path.expanduser(INFLUXDB_BACKUP_ROOT)
    key = "influxdb_ip"; INFLUXDB_IP = gcnf[key] if key in gcnf else CLOUDLET_IP
    key = "seg_db"; SEG_DB = gcnf[key] if key in gcnf else "segmentation"
    key = "offset_db"; OFFSET_DB = gcnf[key] if key in gcnf else "winoffset"
    
    ''' necessary node specific '''
    LOGFILE = "database_backup.log"
    key = "icmp_db"; CLOUDLET_ICMP_DB = ccnf[key] if key in ccnf else "cloudleticmp"
    key = "icmp_db"; WATERSPOUT_ICMP_DB = wcnf[key] if key in wcnf else "cloudleticmp"
    key = "icmp_db"; UE_ICMP_DB = ucnf[key] if key in ucnf else "ueicmp"
    
    measuredict = {CLOUDLET_ICMP_DB:['latency'],UE_ICMP_DB:['latency'],WATERSPOUT_ICMP_DB:['latency']
               ,SEG_DB:['uplink','downlink'],OFFSET_DB:['winoffset']}
     
    ''' Get all the clients '''
    seg_client = InfluxDBClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=SEG_DB)
    df_seg_client = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=SEG_DB)
    df_cloudlet_icmp_client = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=CLOUDLET_ICMP_DB)
    df_waterspout_icmp_client = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=WATERSPOUT_ICMP_DB)
    df_ue_icmp_client = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=UE_ICMP_DB)
    df_offset_client = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=OFFSET_DB)
    (options,_) = cmdOptions()
    kwargs = options.__dict__.copy()
    return kwargs

def cmdOptions():
    parser = OptionParser(usage="usage: %prog [options]")
    parser.add_option("-d", "--debug",
                  action="store_true", dest="debug", default=False,
                  help="Debugging mode")
    return  parser.parse_args()

if __name__ == '__main__': main()