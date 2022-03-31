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

import simlogging
from simlogging import mconsole
''' 
    This program collects latency measurements from the UE, waterspout and cloudlet influxdb databases,
    aggregates them and writes them back into the segmentation database for later analysis and dashboard dataset
'''
LOGNAME=__name__

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

legdict = {1: 'ue_xran',2:'xran_epc',3:'epc_cloudlet',
           7: 'ue_xran',6:'xran_epc',5:'epc_cloudlet',0:'start',4:'cloudlet_proc'}

def main():
    global logger
    LOGFILE="query_measurments.log"
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = logging.INFO,coloron=False)

    def noMeasurements(fdf):
        if len(fdf) == 0:
            mconsole("No measurements available for the segmentation database")
            return True
        else: return False
    seg_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=SEG_DB)
    firsttime = True
    while True:
        if not firsttime: time.sleep(5)
        firsttime = False
        try:
            latencydf = getLatencyData()
        except:
            mconsole("Did not get any latency data",level = "ERROR")
            continue
        latencydf = checkAgainstCurrent(latencydf)
        if noMeasurements(latencydf): continue
        ''' Group the sequences and clean up '''
        tdfz = latencydf.copy().sort_values(['sequence','TIMESTAMP'])
        # Make a small df that has just the number of times a sequence appears in the df
        tdfz = renamecol(tdfz.groupby(by='sequence') \
                .agg('count').reset_index()[['sequence','TIMESTAMP']],col='TIMESTAMP',newname='COUNT')
        # Join the small df with bigger
        tdfz = tdfz.set_index('sequence').join(latencydf.set_index('sequence')) \
                .reset_index().sort_values(['sequence','STEP'])
        tdfz = tdfz.drop_duplicates(subset = ['sequence','NAME','epoch'])
        
        tdfz = tdfz[tdfz.COUNT >= 8] # remove partial data
        if noMeasurements(tdfz): continue
        
        ''' Calculate difference between each step ; save the epoch for the start of the sequence '''
        tdfz['DELTA'] = tdfz.epoch - tdfz.epoch.shift(1)
        tdfz['DELTA'] = tdfz.apply(lambda row: row['epoch'] if 'ue' in row.NAME and 'uplink' in row.direction else row.DELTA, axis=1)
        '''RTT and STEPSUM should be the same; RTT is the (end - start) at the UE; STEPSUM is the sum of the DELTAS '''
        tdfz['RTT'] =  tdfz.epoch - tdfz.epoch.shift(7)
        tdfz['RTT'] = tdfz.apply(lambda row: row['RTT'] \
                        if 'ue' in row.NAME and 'downlink' in row.direction else np.nan, axis=1).fillna(method='bfill')
        tdfz['STEPSUM'] = tdfz.DELTA.rolling(min_periods=1, window=7).sum()
        tdfz['STEPSUM'] = tdfz.apply(lambda row: row['STEPSUM'] \
                        if 'ue' in row.NAME and 'downlink' in row.direction else np.nan, axis=1).fillna(method='bfill')

        ''' Convert for storage in the segmentation database '''
        indlst = ['sequence','direction','RTT','STEPSUM']
        
        keepcol = ['sequence','epoch','TIMESTAMP','NAME','direction','DELTA','STEP','LEGNAME','STEPSUM','RTT']
        tdfx = tdfz.copy()[tdfz.COUNT >= 8][keepcol].sort_values(['sequence','STEP']) \
                        .reset_index(drop=True).drop_duplicates()

        ''' Pivot the data '''
        tdfx = tdfx.drop_duplicates(subset = indlst + ['LEGNAME'])
        tdfx = tdfx.pivot(index=indlst, columns=['LEGNAME'], values=['DELTA']).reset_index()

        ''' Get rid of multilevel index '''
        tdfx.columns = ["".join(a).replace("DELTA","") for a in tdfx.columns.to_flat_index()]
        if noMeasurements(tdfx): continue
        ''' Propagate the start time to the downlink '''
        tdfx = tdfx.sort_values(['sequence','direction'],ascending=[True,False])        
        tdfx['start'] = tdfx.start.fillna(method='ffill')
        
        ''' Find the offset '''
        # tdfx['offset'] = getOffset(startts = tdfx.start.min(),endts = tdfx.start.max())
        tdfx['offset'] = getOffset()
        ''' adjust the ue_xran latencies '''
        tdfx['ue_xran_adjust'] = tdfx.apply(lambda row: row.ue_xran - row.offset \
                                            if row.direction == 'uplink' else row.ue_xran + row.offset, \
                                            axis=1)
        
        ''' Cleanup the cloudlet processing time '''
        tdfx['cloudlet_proc'] = tdfx.cloudlet_proc.map(lambda col: col if not np.isnan(col) else 0)
        
        ''' Write to the segmentation database '''

        tdfx = tdfx.dropna()
        mconsole("Writing {} measurements to the segmentation database".format(len(tdfx)))

        tdfx[:].apply(writePkt,client = seg_client, axis=1)
    
def checkAgainstCurrent(newdf):
    df_seg_client = DataFrameClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=SEG_DB)
    measure = 'uplink'
    try:
        seg_ul_df = df_seg_client.query("select * from {}".format(measure))[measure]
    except:
        return newdf
    seqlst = list(set(seg_ul_df.sequence))
    return newdf[~newdf.sequence.isin(seqlst)]
    

def getLatencyData():
    ''' Get all the clients '''
    df_cloudlet_icmp_client = DataFrameClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=CLOUDLET_ICMP_DB)
    df_waterspout_icmp_client = DataFrameClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=WATERSPOUT_ICMP_DB)
    df_ue_icmp_client = DataFrameClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=UE_ICMP_DB)
                                        
    ''' Query the different network nodes' data '''
    measure = 'latency'
    cloudlet_icmp_df = df_cloudlet_icmp_client.query("select * from {}".format(measure))[measure]
    waterspout_icmp_df = df_waterspout_icmp_client.query("select * from {}".format(measure))[measure]
    ue_icmp_df = df_ue_icmp_client.query("select * from {}".format(measure))[measure]
    
    ''' Get list of sequences in all three dataframes '''
    seqminset = list(set(ue_icmp_df.sequence) \
        .intersection((set(cloudlet_icmp_df.sequence) \
        .intersection(set(waterspout_icmp_df.sequence)))))
    
    ''' Combine the nodes '''
    dflst = [(cloudlet_icmp_df,'cloudlet'),(waterspout_icmp_df,'waterspout'),(ue_icmp_df,'ue')]
    tdfy = pd.DataFrame()
    for tup in dflst:
        tdfx = tup[0]
        tdfx['NAME'] = tup[1]
        tdfy = tdfy.append(tdfx)
    
    ''' Only keep sequences that are in all three dataframes '''
    tdfy = tdfy[tdfy.sequence.isin(seqminset)]
    
    ''' Label the segments in what remains '''
    
    tdfy['TIMESTAMP']= pd.to_datetime(tdfy['epoch'],unit='s',utc=True) # convenience
    tdfy = changeTZ(tdfy,col='TIMESTAMP',origtz='UTC', newtz=TZ)
    tdfy[['direction','STEP','LEGNAME']] = tdfy.apply(lookupLeg,axis=1, result_type='expand')
    tdfy = renamecol(tdfy.reset_index().copy(),col='index',newname='influxts')
    
    return tdfy

def getOffset(startts = None, endts = None, measure = 'winoffset'):
    TZ = 'America/New_York'
    df_offset_client = DataFrameClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=OFFSET_DB)
    offset_df = to_ts_std(df_offset_client.query("select * from {}".format(measure))[measure],newtz='America/New_York')
    ''' Filter by ts boundaries '''
    tdfx = offset_df.copy()
    ''' convert from epoch to datetime '''
    startdt = datetime.datetime.fromtimestamp(startts,tz=pytz.timezone(TZ)) if startts is not None else None
    enddt = datetime.datetime.fromtimestamp(endts,tz=pytz.timezone(TZ)) if endts is not None else None
    ''' remove out of bounds '''
    tdfx = tdfx[tdfx.TIMESTAMP >= startdt] if startts is not None else tdfx
    tdfx = tdfx[tdfx.TIMESTAMP <= enddt] if endts is not None else tdfx
    if len(tdfx) < len(offset_df):
        mconsole("Filtered offset to boundaries: {} to {}".format(startdt,enddt))
    median_offset = tdfx.offset.median()
    return median_offset


''' Label the legs '''
def lookupLeg(row):
    src = row.src
    dst = row.dst
    name = row.NAME
    ddir = np.nan
    step = np.nan
    if dst == CLOUDLET_IP:
        ddir = "uplink"        
    elif src == CLOUDLET_IP:
        ddir = "downlink"
    elif dst == EPC_IP:
        ddir = "uplink"
    elif src == EPC_IP:
        ddir = "downlink"
    if ddir == 'uplink':
        if name == 'ue': step = 0
        elif name == 'cloudlet': step = 3
        elif name == 'waterspout': step = 1 if dst == EPC_IP else 2                
    elif ddir == 'downlink':
        if name == 'ue': step = 7
        elif name == 'cloudlet': step = 4
        elif name == 'waterspout': step = 5 if dst == EPC_IP else 6
    legname = legdict[step]
    return (ddir,step,legname)

''' Write into influxdb '''
def writePkt(row, client):
    # try:
        pkt_entry = {"measurement":row['direction'], 
                     "tags": {"sequence": row['sequence'],"direction": row['direction']}, 
                     "fields":{"ue_xran": row['ue_xran'], 'ue_xran_adjust':row['ue_xran_adjust'],
                               'offset':row['offset'],"xran_epc": row['xran_epc'], 
                                "epc_cloudlet": row['epc_cloudlet'], "start": row['start'],
                                "cloudlet_proc": row['cloudlet_proc'],
                                'rtt':row.RTT,'stepsum':row.STEPSUM},"time":int(row['start']*1e6)}
        client.write_points([pkt_entry], time_precision = 'u')
    # except:
    #     mconsole("Bad measurement: {}".format(row),level="ERROR")

if __name__ == '__main__': main()