#!/usr/bin/env python
import os
import sys
import platform
# print(sys.path)
sys.path.append("../lib")
import subprocess
import shutil
import pandas as pd
import numpy as np
import calendar
import traceback
import json
from pyutils import *
from pdutils import *
from pdpltutils import *
from gputils import *
from iputils import *
import xmltodict
import re

from optparse import OptionParser
from simlogging import *
from config import *

cnf = initConfig()
LOGNAME=__name__

def main():
    global logger
    LOGFILE="network_study.log"
    logger = configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,coloron=False)
    try:
        mconsole(f"Starting {__file__}")
        reverse = False
        if(cnf['USENAMESPACES']): 
            for NS in cnf['NETWORKS']: deleteNetworkNamespace(NS)
        while True:
            reverse = False if reverse else True
            for NS in cnf['NETWORKS']:
                if(cnf['USENAMESPACES']): addNetworkNamespace(NS)
                for DEST in cnf['DESTINATIONS']:
                    mconsole(f"TEST {DEST} over {NS}")
                    pingdf, iperfdf,tracertdf= runTestRound(cnf[DEST]['IP'],cnf[NS],cnf[DEST]['IPERFPORT'], reverse = reverse)
                    saveDF(pingdf, iperfdf,tracertdf)
                    pass
                if(cnf['USENAMESPACES']): deleteNetworkNamespace(NS)
            mconsole(f"Sleeping for {cnf['SLEEPTIME']} minutes")
            time.sleep(cnf['SLEEPTIME']*60)
    except KeyboardInterrupt:
        mconsole(f"Interrupting {__file__}")
        sys.exit(0)
    mconsole(f"Ending {__file__}")
        

def runTestRound(dest, ns, port,reverse = False):
    if cnf['PINGON']: pingdf = nping(dest,ns)
    else: pingdf = None
    if cnf['IPERFON']: perfdf = niperf(dest,ns,port,reverse=reverse)
    else: perfdf = None
    if cnf['TRACEROUTEON']: tracertdf = ntraceroute(dest,ns)
    else: tracertdf = None
    return pingdf, perfdf,tracertdf
        
def nping(dest, ns):
    ifc = ns['IFC']
    mconsole(f"Pinging {dest} via {ifc}")
    if(cnf['USENAMESPACES']): pref=f"sudo ip netns exec {ns['NAMESPACE']}"
    else: pref=""
    # pref=""
    cmd = f"{pref} {cnf['PINGPATH']} -I {ifc} -c {cnf['PINGCOUNT']} -i {cnf['PINGINTERVAL']} {dest}"
    result = cmd_all(cmd)
    console_stderr(result)
    tdfx = parsePing(result)
    tdfx['DEST'] = dest
    tdfx['IFC'] = ifc
    tdfx['PINGINTERVAL'] = cnf['PINGINTERVAL']
    if tdfx.shape[0] == 0: mconsole("No ping data received",level="ERROR")
    else: mconsole(f"Ping returned: {tdfx.shape[0]} measurements")
    return tdfx

def niperf(dest, ns, port,reverse=False):
    ifc = ns['IFC']
    tns = ns['NAMESPACE']
    mconsole(f"Running iperf3 to {dest} via {ifc} reverse={reverse}")
    if(cnf['USENAMESPACES']): pref=f"sudo ip netns exec {tns}"
    else: pref=""
    cmd = f"{pref} {cnf['IPERF3PATH']} -c {dest} -p {port}"
    if reverse: cmd = cmd + " -R"
    result = cmd_all(cmd)
    console_stderr(result)
    tdfx = parseIperf(result)
    if tdfx.shape[0] == 0: mconsole("No iperf data received",level="ERROR")
    else: mconsole(f"Iperf returned: {tdfx.shape[0]} measurements")
    tdfx['DEST'] = dest
    tdfx['IFC'] = ifc
    tdfx['DIRECTION'] = "DOWN" if reverse else "UP"
    return tdfx

def ntraceroute(dest, ns):
    ifc = ns['IFC']
    mconsole(f"Running traceroute to {dest} via {ifc}")
    if(cnf['USENAMESPACES']): pref=f"sudo ip netns exec {ns['NAMESPACE']}"
    else: pref=""
    cmd = f"{pref} {cnf['TRACEROUTEPATH']} -i {ifc} {dest}"
    result = cmd_all(cmd)
    console_stderr(result)
    tdfx = parseTraceroute(result)
    if tdfx.shape[0] == 0: mconsole("No traceroute data received",level="ERROR")
    else: mconsole(f"Traceroute returned: {tdfx.shape[0]} measurements")
    tdfx['DEST'] = dest
    tdfx['IFC'] = ifc
    return tdfx

def parsePing(res):
    fnlines = res['stdout']    
    fnlines = [fn.replace("<","=") for fn in fnlines[1:]]
    rec = re.compile("time=.* ")
    timelines=[line for line in fnlines if rec.search(line)]
    times = [float(rec.findall(line)[0].strip()[5:-2]) for line in timelines]
    fdf = pd.DataFrame(times,columns=["TIME"])
    nowtime = datetime.datetime.now();
    fdf['TIMESTAMP'] = nowtime
    fdf['HDATE'] = nowtime.strftime('%Y-%m-%d-%H-%M-%S-%f')
    fdf['TEST'] = "ping"
    return fdf

def parseIperf(res):
    fnlines = res['stdout']
    rec = re.compile(" \d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3} ")
    iplines = [line for line in fnlines if rec.search(line)]
    rec = re.compile("sec .* MBytes .* Mbits/sec")
    bwlines =[line for line in fnlines if rec.search(line)]
    datalines = [float(rec.findall(line)[0].split()[3]) for line in bwlines]
    fdf = pd.DataFrame(datalines,columns=["THROUGHPUT"])
    nowtime = datetime.datetime.now();
    fdf['TIMESTAMP'] = nowtime
    fdf['HDATE'] = nowtime.strftime('%Y-%m-%d-%H-%M-%S-%f')
    fdf['TEST'] = "iperf"
    return fdf

def parseTraceroute(res):
    fnlines = res['stdout']
    rec = re.compile("\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
    iplines = [line for line in fnlines if rec.search(line)]
    fdf = pd.DataFrame(iplines,columns=['TXT'])
    fdf['IP'] = fdf.TXT.map(lambda line: rec.findall(line)[0])
    fdf = drp_lst(fdf, ['TXT'])
    nowtime = datetime.datetime.now();
    fdf['TIMESTAMP'] = nowtime
    fdf['HDATE'] = nowtime.strftime('%Y-%m-%d-%H-%M-%S-%f')
    fdf['TEST'] = "traceroute"
    return fdf

def saveDF(pdf,idf,tdf):
    dd = cnf['DATADIR']
    mconsole(f"Saving test results in {dd}")
    ''' ping '''
    if pdf is not None and pdf.shape[0] > 0:
        rr = pdf.iloc[0]
        fn = f"{rr.TEST}-{rr.HDATE}-{rr.DEST}-{rr.IFC}.csv"
        writejoin(pdf,dd,fn, index=False)
    ''' iperf '''
    if idf is not None and idf.shape[0] > 0:
        rr = idf.iloc[0]
        fn = f"{rr.TEST}-{rr.HDATE}-{rr.DEST}-{rr.IFC}.csv"
        writejoin(idf,dd,fn, index=False)
    ''' traceroute '''
    if tdf is not None and tdf.shape[0] > 0:
        rr = tdf.iloc[0]
        fn = f"{rr.TEST}-{rr.HDATE}-{rr.DEST}-{rr.IFC}.csv"
        writejoin(tdf,dd,fn, index=False)
    pass
    
''' Utilities '''
def getIfcIP(ifc):
    rec = re.compile(" \d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
    cmd = "ip a"
    ip = None
    res = cmd_all(cmd)
    try:
        for ii,line in enumerate(res['stdout']):
            if ifc in line:
                ifcline = line
                ipline = res['stdout'][ii+2]
                ip = rec.findall(ipline)[0]
                break;
    except:
        mconsole("Could not get interface IP",level=ERROR)
    return ip

def addNetworkNamespace(ns):
    if isNetworkNamespace(ns): return
    tns = ns
    cmd=f"sudo bash ./add_network_namespace.sh {tns}"
    result = cmd_all(cmd)
    console_stderr(result)
    isNetworkNamespace(ns)
    pref=f"sudo ip netns exec {tns}"
    cmd = f"{pref} ip a"
    result = cmd_all(cmd)
    console_stdout(result)

def deleteNetworkNamespace(ns):
    if not isNetworkNamespace(ns): return
    cmd=f"sudo bash -c 'bash ./del_network_namespace.sh {ns} && sudo netplan apply'"
    result = cmd_all(cmd)
    console_stderr(result)
    
def isNetworkNamespace(ns):
    retbool = False
    rec = re.compile(f"{ns}")                    
    cmd="ip netns list"
    results = cmd_all(cmd)
    console_stdout(results)
    console_stderr(results)
    for line in results['stdout']:
        if rec.match(line): return True
    return retbool
    
def console_stdout(res):  devnull=[mconsole(f"{line}") for line in res['stdout']]
def console_stderr(res):  devnull=[mconsole(f"{line}",level="ERROR") for line in res['stderr']]

''' Graveyard '''


if __name__ == '__main__': main()
