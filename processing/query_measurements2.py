#!/usr/bin/env python

import sys

sys.path.append("../lib")
import os
import json
import traceback
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
from local_common import *


''' 
    This program collects latency measurements from the UE, magma and cloudlet influxdb databases,
    aggregates them and writes them back into the segmentation database for later analysis and dashboard dataset
'''

def main():
    ''' INITIALIZATION '''
    global blacklist
    blacklist = []
    kwargs = configure()
    ''' Logging '''
    loglev = LOGLEV if not kwargs['debug'] else logging.DEBUG
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = loglev,coloron=False)
    
    firsttime = True
    
    
    ''' END INITIALIZATION '''
    
    mconsole("Starting querying")
    
    ''' Now keep looping '''
    while True:
        if not firsttime: time.sleep(int(kwargs['sleeptime']))
        else: createDB(seg_client,SEG_DB) # Only creates if it doesn't already exist 
        firsttime = False
        
        ''' Pull the data from the cloudlet, magma and ue databases '''
        try:
            latencydf,newblacklist = getLatencyData()
            blacklist += newblacklist
        except Exception as e:
            mconsole("Did not get any latency data: {}".format(e),level = "ERROR")
            continue
        
        preseq = list(set(latencydf.sequence))
        
        tdfz = cleanLatencyData(latencydf)
        if tdfz is None: continue
       
        ''' Add partial sequences to the blacklist '''
        if noMeasurements(tdfz,tag="partial data"): 
            mconsole(f"Sequence(s) {preseq} added to blacklist",level = "DEBUG")
            blacklist += preseq
            continue
        compseq = list(set(tdfz.sequence));
        mconsole(f"Retrieved {len(compseq)} possibly complete sequences (Sequence Nos: {compseq})" \
                       ,level="DEBUG") # 2 for uplink and downlink
        
        ''' Pivot the data '''
        tdfx = tdfz.copy()
        tdfx = tdfx.pivot_table(index='sequence', columns='STEP', values=['epoch'])
        tdfx.columns = [ "".join([str(x) for x in a]).replace("epoch","") \
                        for a in tdfx.columns.to_flat_index()] # Flatten and clean up index
        
        lastcol = None
        for ii,col in enumerate(tdfx.columns): # TODO more pandas way
            scol = legdict[col]
            if ii == 0:
                tdfx[scol] = tdfx[col]
                lastcol = col
                continue
            tdfx[scol] = tdfx[col] - tdfx[lastcol]
            lastcol = col
        tdfx['end'] = tdfx[col] # last column
        tdfx['rtt'] = tdfx['end'] - tdfx['start']
        debugDF(tdfx,"debug2")
        if noMeasurements(tdfx,tag="nothing after pivot") or "start" not in tdfx.columns: continue
        tdfx['DTDATE'] = tdfx.start.map(lambda cell: datetime.datetime.fromtimestamp(cell,tz=pytz.timezone(TZ)))
        tdfx['STRDATE'] = tdfx.DTDATE.map(lambda x: x.strftime("%Y-%m-%d %H:%M:%S.%f"))
        
        ''' Find the offset '''
        tdfx['offset'] = getOffset(startts = tdfx.start.min(),endts = tdfx.start.max(),filteroffset=kwargs['filteroffset'])

        ''' adjust the ue_xran latencies to correct for offset'''
        tdfx['ue_xran_adjust'] = tdfx.apply(lambda row: row.ue_xran - row.offset, axis=1)
        tdfx['xran_ue_adjust'] = tdfx.apply(lambda row: row.xran_ue + row.offset,axis=1)
               
        ''' Write to the segmentation database '''
        tdfx = tdfx.dropna().reset_index()
        # blacklist += list(set(fullseqlst) - set(tdfx.sequence) - set(blacklist)) # TODO fix blacklist
        mconsole("Writing {} measurements to the segmentation database  (Sequence Nos: {})" \
                 .format(len(tdfx),list(set(tdfx.sequence))))
        tdfx[:].apply(writePkt,client = seg_client, axis=1)
        
def debugDF(fdf,name):
    try:
        writejoin(fdf,".",f"{name}.csv")
    except:
        mconsole(f"Couldn't write {name}.csv")


def getLatencyData():            
    ''' Query the different network nodes' data '''
    measure = 'latency'
    cloudlet_icmp_df = df_cloudlet_icmp_client.query("select * from {}".format(measure))[measure]
    magma_icmp_df = df_magma_icmp_client.query("select * from {}".format(measure))[measure]
    ue_icmp_df = df_ue_icmp_client.query("select * from {}".format(measure))[measure]
    
    ''' Get list of sequences in all three dataframes '''
    seqminset = list(set(ue_icmp_df.sequence) \
        .intersection((set(cloudlet_icmp_df.sequence) \
        .intersection(set(magma_icmp_df.sequence)))))
        
    ''' Combine the nodes '''
    dflst = [(cloudlet_icmp_df,'cloudlet'),(magma_icmp_df,'magma'),(ue_icmp_df,'ue')]
    tdfy = pd.DataFrame()
    for tup in dflst:
        tdfx = tup[0]
        tdfx['NAME'] = tup[1]
        tdfy = pd.concat([tdfy,tdfx],sort=True)
        
    ''' TIMESTAMP '''
    tdfy['TIMESTAMP']= pd.to_datetime(tdfy['epoch'],unit='s',utc=True) # convenience
    tdfy = changeTZ(tdfy,col='TIMESTAMP',origtz='UTC', newtz=TZ)
    tdfy = tdfy[tdfy.TIMESTAMP >= getMidnight()] # TODO Parameterize
    
    ''' Only keep sequences that are in all three dataframes '''
    newblacklist = list(set(tdfy.sequence[~tdfy.sequence.isin(seqminset)]))
    
    tdfy = tdfy[tdfy.sequence.isin(seqminset)]
    ''' Only keep sequences that are not on blacklist '''
    tdfy = checkAgainstBlacklist(tdfy)
    
    ''' Label the segments in what remains '''

    
    tdfy = tdfy.drop_duplicates(['NAME','src','dst','sequence'])
    try:
        writejoin(tdfy,".","tdfy.csv")
    except:
        mconsole("Can't write to tdfy.csv")
        
    
    tdfy = renamecol(tdfy.reset_index().copy(),col='index',newname='influxts')

    return tdfy,newblacklist

def cleanLatencyData(fdf):
    ''' Is it already in the segmentation database? '''
    fdf,newblacklist = checkAgainstCurrent(fdf)
    if noMeasurements(fdf,tag="no new"): return None
    fullseqlst = list(set(fdf.sequence))
    mconsole(f"Retrieved {len(fullseqlst)} possible sequences (Sequence Nos: {fullseqlst})" \
                   ,level="DEBUG")
    ''' Group the sequences and clean up '''
    tdfz = fdf.copy().sort_values(['sequence','TIMESTAMP'])
    
    ''' Make a small df that has just the number of times a sequence appears in the df '''
    tdfz = renamecol(tdfz.groupby(by='sequence') \
            .agg('count').reset_index()[['sequence','TIMESTAMP']],col='TIMESTAMP',newname='COUNT')
    
    ''' Join the small df with bigger '''
    tdfz = tdfz.set_index('sequence').join(fdf.set_index('sequence')) \
            .reset_index().sort_values(['sequence'])
    tdfz = tdfz.drop_duplicates(subset = ['sequence','NAME','epoch']) # pure duplicates
    
    writejoin(tdfz,".","tdfz.csv")
    ''' Check for complete sequence data from all probes '''
    
    ''' Remove partial and duplicate sequences '''
    tdfz = tdfz[(tdfz.COUNT == 8)]
    tdfz[['direction','STEP','LEGNAME']] = tdfz.apply(lookupLeg,axis=1, result_type='expand')
    return tdfz

def configure():
    global seg_client;global df_seg_client; global df_cloudlet_icmp_client
    global df_magma_icmp_client;global df_ue_icmp_client;global df_offset_client
    global TZ; 
    global INFLUXDB_IP; global INFLUXDB_PORT; global SEG_DB
    global LOGFILE; global LOGNAME; global LOGLEV
    global legdict; global leghashmap
    global S1_IP; global SG1_IP; global CLOUDLET_IP; global EPC_IP; global UE_IP; global LEGW_IP; global ENB_IP

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
            mcnf = cnf['MAGMA']
    cnf.update(cnf['GENERAL'])
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
    key = "timezone";       TZ = gcnf[key] if key in gcnf else DEFAULTS[key]
    key = "seg_db";         SEG_DB = gcnf[key] if key in gcnf else DEFAULTS[key]
    key = "offset_db";      OFFSET_DB = gcnf[key] if key in gcnf else DEFAULTS[key]
    
    ''' necessary node specific '''
    key = "logfile";        LOGFILE= qcnf[key] if key in qcnf else "query_measurments.log"
    key = "icmp_db";        CLOUDLET_ICMP_DB = ccnf[key] if key in ccnf else "cloudleticmp"
    key = "icmp_db";        MAGMA_ICMP_DB = mcnf[key] if key in mcnf else "magmaicmp"
    key = "icmp_db";        UE_ICMP_DB = ucnf[key] if key in ucnf else "ueicmp"
    
    ''' Get all the clients '''
    seg_client = InfluxDBClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=SEG_DB)
    df_seg_client = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=SEG_DB)
    df_cloudlet_icmp_client = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=CLOUDLET_ICMP_DB)
    df_magma_icmp_client = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=MAGMA_ICMP_DB)
    df_ue_icmp_client = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=UE_ICMP_DB)
    df_offset_client = DataFrameClient(host=INFLUXDB_IP, port=INFLUXDB_PORT, database=OFFSET_DB)
    
    leghashmap = makeLegHashDict()
    legdict = {'0':'start', '1': 'ue_xran','2':'xran_epc','3':'epc_cloudlet',
           '7': 'xran_ue','6':'epc_xran','5':'epc_cloudlet','4':'cloudlet_epc'}
    
    (options,_) = cmdOptions()
    kwargs = options.__dict__.copy()
    return kwargs
        
def cmdOptions():
    parser = OptionParser(usage="usage: %prog [options]")
    parser.add_option("-D", "--delay", dest="sleeptime",
              help="Delay between queries", metavar="INT",default=5)
    parser.add_option("-d", "--debug",
                  action="store_true", dest="debug", default=False,
                  help="Debugging mode")
    parser.add_option("-f", "--filteroffset",
                  action="store_true", dest="filteroffset", default=False,
                  help="Filter out data without nearby offset values")
    return  parser.parse_args()
    
def noMeasurements(fdf,tag='no info'):
    if len(fdf) == 0:
        mconsole("No measurements available for the segmentation database: {}".format(tag))
        return True
    else: return False

def checkAgainstCurrent(newdf):
    ''' Is the sequence already in the database '''
    measure = 'segments'
    try:
        seg_df = df_seg_client.query("select * from {}".format(measure))[measure]
    except:
        return newdf
    seqlst = list(set(seg_df.sequence))
    return newdf[~newdf.sequence.isin(seqlst)],seqlst

def checkAgainstBlacklist(indf):
    retdf = indf[~indf.sequence.isin(blacklist)]
    return retdf

def getOffset(startts = None, endts = None, measure = 'winoffset',filteroffset = True):
    TZ = 'America/New_York'
    try:
        offset_df = to_ts_std(df_offset_client.query("select * from {}".format(measure))[measure],newtz='America/New_York')
    except:
        mconsole("No offset data available -- returning 0",level="ERROR")
        return 0
    
    ''' Filter by ts boundaries '''
    tdfx = offset_df.copy()
    ''' convert from epoch to datetime '''
    startdt = datetime.datetime.fromtimestamp(startts,tz=pytz.timezone(TZ)) if startts is not None else None
    enddt = datetime.datetime.fromtimestamp(endts,tz=pytz.timezone(TZ)) if endts is not None else None
    ''' remove out of bounds '''
    if filteroffset:
        tdfx = tdfx[tdfx.TIMESTAMP >= startdt] if startts is not None else tdfx
        tdfx = tdfx[tdfx.TIMESTAMP <= enddt] if endts is not None else tdfx
    if len(tdfx) < len(offset_df):
        mconsole("Filtered offset to boundaries: {} to {}".format(startdt,enddt))
    median_offset = tdfx.offset.median()
    return median_offset


''' Label the legs '''
def lookupLeg(row):
    ''' For labeling segments '''
    src = row.src
    dst = row.dst
    name = row.NAME
    ddir = np.nan
    step = np.nan
    legname = "unknown"
    
    try:
        ddir,step,legname = leghashmap[makeHashString(name,src,dst)]
    except:
        mconsole(f"Bad step: {name} {src} {dst}")
    return (ddir,step,legname)

def makeHashString(name,src,dst):
    return f"{name}/{src}/{dst}"
def makeLegHashDict():
    leghashdict = {}
    ueup = makeHashString("ue",UE_IP,CLOUDLET_IP); leghashdict[ueup] = ("uplink",0,"start")
    epcups1 = makeHashString("magma", ENB_IP,S1_IP); leghashdict[epcups1] = ("uplink",1,"xran_epc")
    epcupsg1 = makeHashString("magma", SG1_IP,CLOUDLET_IP); leghashdict[epcupsg1] = ("uplink",2,"epc_cloudlet")
    cloudletup = makeHashString("cloudlet", EPC_IP,CLOUDLET_IP); leghashdict[cloudletup] = ("uplink",3,"cloudlet_in")
    
    cloudletdown = makeHashString("cloudlet",CLOUDLET_IP, EPC_IP); leghashdict[cloudletdown] = ("downlink",4,"cloudlet_out")
    xrandownsg1 = makeHashString("magma", CLOUDLET_IP,SG1_IP); leghashdict[xrandownsg1] = ("downlink",5,"epc_cloudlet")
    xrandown = makeHashString("magma", S1_IP,ENB_IP); leghashdict[xrandown] = ("downlink",6,"xran_epc")
    uedown = makeHashString("ue",CLOUDLET_IP,UE_IP); leghashdict[uedown] = ("downlink",7,"ue_xran")
    
    return leghashdict
    
    # s1up = f"magma/{"
    

''' Write into influxdb '''
def writePkt(row, client):
        mconsole(f"Writing measurement -- sequence={row.sequence} start={row.DTDATE}",level="DEBUG")
    # try:
        pkt_entry = {"measurement":"segments", 
                     "tags": {"sequence": row.sequence}, 
                     "fields":{"ue_xran": row.ue_xran, 'ue_xran_adjust':row.ue_xran_adjust,
                               "xran_ue": row.xran_ue, 'xran_ue_adjust':row.xran_ue_adjust,
                               "epc_xran": row.epc_xran,"xran_epc": row.xran_epc,
                               "epc_cloudlet": row.epc_cloudlet,"cloudlet_epc": row.cloudlet_epc,
                               'offset':row.offset, "start": row.start,
                                "end": row.end,
                                'rtt':row.rtt,"time":int(row.start*1e6),"HTIME":row.STRDATE}
                     }
        client.write_points([pkt_entry], time_precision = 'u')
    # except:
    #     mconsole("Bad measurement: {}".format(row),level="ERROR")

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
    "ue_ip":"192.168.128.22",
    "seg_db":"segmentation",
    "offset_db":"winoffset"
}
if __name__ == '__main__': main()