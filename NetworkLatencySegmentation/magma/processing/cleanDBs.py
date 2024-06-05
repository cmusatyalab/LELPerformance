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
    This program deletes the data in the various databases either en masse or measurement by measurement
'''
LOGNAME=__name__
LOGLEV = logging.DEBUG

def main():
    global logger
    kwargs = configure()
    
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
            dfclient = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=db)
            wtclient = InfluxDBClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=db)
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

def configure():
    global seg_client;global df_seg_client; global df_cloudlet_icmp_client
    global df_magma_icmp_client;global df_ue_icmp_client
    global TZ; global CLOUDLET_IP; global EPC_IP;
    global INFLUXDB_IP; global INFLUXDB_PORT; global measuredict
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
            wcnf = cnf['MAGMA']
    ''' General '''
    key = "epc_ip"; EPC_IP = gcnf[key] if key in gcnf else "192.168.25.4"
    key = "lelgw_ip"; LELGW_IP = gcnf[key] if key in gcnf else "128.2.212.53"
    key = "cloudlet_ip" ; CLOUDLET_IP = gcnf[key] if key in gcnf else "128.2.208.248"
    key = "ue_ip"; UE_IP = gcnf[key] if key in gcnf else "172.26.21.132"
    key = "influxdb_port"; INFLUXDB_PORT = gcnf[key] if key in gcnf else 8086
    key = "influxdb_ip"; INFLUXDB_IP = gcnf[key] if key in gcnf else CLOUDLET_IP
    key = "timezone"; TZ = gcnf[key] if key in gcnf else "America/New_York"
    key = "seg_db"; SEG_DB = gcnf[key] if key in gcnf else "segmentation"
    key = "offset_db"; OFFSET_DB = gcnf[key] if key in gcnf else "winoffset"
    
    ''' necessary node specific '''
    LOGFILE= "database_cleanup.log"
    key = "icmp_db"; CLOUDLET_ICMP_DB = ccnf[key] if key in ccnf else "cloudleticmp"
    key = "icmp_db"; MAGMA_ICMP_DB = wcnf[key] if key in wcnf else "magmaicmp"
    key = "icmp_db"; UE_ICMP_DB = ucnf[key] if key in ucnf else "ueicmp"
    
    measuredict = {CLOUDLET_ICMP_DB:['latency'],UE_ICMP_DB:['latency'],MAGMA_ICMP_DB:['latency']
               ,SEG_DB:['segments'],OFFSET_DB:['winoffset']}
     
    ''' Get all the clients '''
    seg_client = InfluxDBClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=SEG_DB)
    df_seg_client = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=SEG_DB)
    df_cloudlet_icmp_client = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=CLOUDLET_ICMP_DB)
    df_magma_icmp_client = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=MAGMA_ICMP_DB)
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