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
    global cnf
    global ifc_ip_map,gw_ip_map
    global verbose
    
    LOGFILE="network_study.log"
    logger = configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,coloron=False)
    cnf = cmdOptions(cnf)
    verbose = cnf['verbose']
    try:
        mconsole(f"Starting {__file__}")
        reverse = False
        deleteAllNetworkNamespaces()
        ifc_ip_map,gw_ip_map = getIfcIP()
        addAllNetworkNamespaces()
        while True:
            reverse = False if reverse else True
            for NS in cnf['NETWORKS']:
                IFC = cnf[NS]['IFC']
                # if(cnf['USENAMESPACES']): addNetworkNamespace(NS)
                for DEST in cnf['DESTINATIONS']:
                    mconsole(f"TEST {DEST} over {NS}")
                    pingdf, iperfdf,tracertdf= runTestRound(cnf[DEST]['IP'],cnf[NS],cnf[DEST]['IPERFPORT'], reverse = reverse)
                    saveDF(pingdf, iperfdf,tracertdf)
                    pass
                # deleteAllNetworkNamespaces()
            mconsole(f"Sleeping for {cnf['SLEEPTIME']} minutes")
            time.sleep(cnf['SLEEPTIME']*60)
    except KeyboardInterrupt:
        exitSmoothly()

    mconsole(f"Ending {__file__}")

def exitSmoothly():
    mconsole(f"Interrupting {__file__} -- exit smoothly")
    if(cnf['USENAMESPACES']): 
        for NS in cnf['NETWORKS']: deleteNetworkNamespace(NS)
    sys.exit(0)

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
    if(cnf['USENAMESPACES']): 
        pref=f"echo '{cnf['sudopw']}' |sudo -S ip netns exec {ns['NAMESPACE']}"
    else: pref=""
    # pref=""
    cmd = f"{pref} {cnf['PINGPATH']} -I {ifc} -c {cnf['PINGCOUNT']} -i {cnf['PINGINTERVAL']} {dest}"
    result = cmd_all_pipe(cmd)
    console_stderr(result)
    tdfx = parsePing(result)
    tdfx['DEST'] = dest
    tdfx['IFC'] = ifc
    tdfx['PINGINTERVAL'] = cnf['PINGINTERVAL']
    if tdfx.shape[0] == 0: 
        mconsole("No ping data received",level="ERROR")
        if verbose: console_stdout(result)
    else: mconsole(f"Ping returned: {tdfx.shape[0]} measurements")
    return tdfx

def niperf(dest, ns, port,reverse=False):
    ifc = ns['IFC']
    mconsole(f"Running iperf3 to {dest} via {ifc} reverse={reverse}")
    if(cnf['USENAMESPACES']): pref=f"echo '{cnf['sudopw']}' |sudo -S ip netns exec {ns['NAMESPACE']}"
    else: pref=""
    cmd = f"{pref} {cnf['IPERF3PATH']} -c {dest} -p {port}"
    if reverse: cmd = cmd + " -R"
    result = cmd_all_pipe(cmd)
    if verbose: console_stdout(result)
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
    if(cnf['USENAMESPACES']): pref=f"echo '{cnf['sudopw']}' |sudo -S ip netns exec {ns['NAMESPACE']}"
    else: pref=""
    # cmd = f"{pref} {cnf['TRACEROUTEPATH']} -i {ifc} {dest}"
    cmd = f"{pref} {cnf['TRACEROUTEPATH']} -m {cnf['TRACEROUTEMAXHOPS']} {dest}"
    result = cmd_all_pipe(cmd)
    console_stderr(result)
    tdfx = parseTraceroute(result)
    if tdfx.shape[0] == 0: 
        mconsole("No traceroute data received",level="ERROR")
    elif tdfx.IP.iloc[0] != tdfx.IP.iloc[-1]: 
        mconsole(f"Traceroute did not reach destination ({dest}); dropping data", level="ERROR")
        tdfx = pd.DataFrame()
    else: mconsole(f"Traceroute returned: {tdfx.shape[0]} hops")
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
    rec = re.compile("sec .* .*Bytes .* .*bits/sec")
    bwlines =[line for line in fnlines if rec.search(line)]
    datalines = [float(rec.findall(line)[0].split()[3]) for line in bwlines]
    unitlines = [rec.findall(line)[0].split()[4] for line in bwlines]
    fdf = pd.DataFrame(list(zip(datalines,unitlines)),columns=["THROUGHPUT","UNITS"])
    fdf['THROUGHPUT'] = fdf.apply(lambda row: row.THROUGHPUT*1000 if row.UNITS.startswith("G") else row.THROUGHPUT,axis=1)
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
def getIfcIP():
    ''' Execute with no namespaces active '''
    ipdict={}
    gwdict={}
    ''' Get the interface IPs '''
    rec1 = re.compile(" \d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
    rec2 = re.compile("[^\s]+")
    cmd = "ip --brief a"
    ip = None
    res = cmd_all(cmd)
    for ii,line in enumerate(res['stdout']):
        try:
                ip = rec1.findall(line)[0]
                ifc = rec2.findall(line)[0]
                ipdict[ifc] = ip.strip()
        except:
            mconsole(f"Could not get interface IP from {line}",level="ERROR")
    ''' Get the interface gateways '''
    cmd = "ip r"
    res = cmd_all(cmd)
    iplst = [ipdict[ifc] for ifc in ipdict.keys()]
    for ii,line in enumerate(res['stdout']):
        for ip in iplst:
            try:
                if ip in line and "default via" in line:
                    gw = rec1.findall(line)[0].strip()
                    gwdict[ip] = gw
            except:
                mconsole(f"Could not get gateway from {line}",level="ERROR")
    if verbose:
        _ = [mconsole(f"interface={key} IP={ipdict[key]}") for key in ipdict.keys()]
        _ = [mconsole(f"IP={key} GW={gwdict[key]}") for key in gwdict.keys()]
    return ipdict,gwdict

def addNetworkNamespace(ns):
    if isNetworkNamespace(ns): return
    mconsole(f"Adding network namespace {ns}")
    NS = cnf[ns]
    ifc = NS['IFC']
    ip = ifc_ip_map[ifc]
    gw = gw_ip_map[ip]
    cmd=f"echo '{cnf['sudopw']}' | sudo -S bash ./add_network_namespace.sh {ns} {ifc} {ip} {gw}"
    result = cmd_all_pipe(cmd)
    if verbose: console_stdout(result)
    console_stderr(result)
    if verbose:
        isNetworkNamespace(ns)
        pref=f"sudo ip netns exec {ns}"
        cmd = f"{pref} ip a"
        result = cmd_all(cmd)
        console_stdout(result)
    # getActiveNetworkNamespaces()
    
def addAllNetworkNamespaces():
    for NS in cnf['NETWORKS']: 
        addNetworkNamespace(NS)

def deleteNetworkNamespace(ns):
    if not isNetworkNamespace(ns):
        if verbose: mconsole(f"Network namespace {ns} does not exist") 
        return
    mconsole(f"Deleting network namespace {ns}")
    NS = cnf[ns]
    ifc = NS['IFC']
    # ip = ifc_ip_map[ifc]
    cmd=f"echo '{cnf['sudopw']}' | sudo -S bash -c 'bash ./del_network_namespace.sh {ns} {ifc} && sudo netplan apply'"
    result = cmd_all_pipe(cmd)
    console_stderr(result)
    time.sleep(2)
    # getActiveNetworkNamespaces()

def deleteAllNetworkNamespaces():
        for NS in cnf['NETWORKS']: 
            deleteNetworkNamespace(NS)
            
def getActiveNetworkNamespaces():
    cmd = "ip netns list"
    result = cmd_all(cmd)
    namespaces = [xx[0:xx.find(" ")] for xx in result['stdout']]
    if verbose:
        mconsole(f"Active namespaces: {namespaces}")
    console_stderr(result)
    return namespaces
    
def isNetworkNamespace(ns):
    retbool = False
    rec = re.compile(f"{ns}")                    
    namespaces = getActiveNetworkNamespaces()
    for line in namespaces:
        if rec.match(line): return True
    return retbool

def cmdOptions(tmpcnf):
    parser = OptionParser(usage="usage: %prog [options]")
    parser.add_option("-d", "--debug",
                  action="store_true", dest="debug", default=False,
                  help="Debugging mode")
    parser.add_option("-v", "--verbose",
                  action="store_true", dest="verbose", default=False,
                  help="Verbose Mode")
    parser.add_option("-S", "--sudopw", dest="sudopw", default = None,
        help="Allow sudo commands", metavar="STRING")
    (options,_) = parser.parse_args()
    tmpcnf.update(options.__dict__.copy())
    return  tmpcnf

def cmd_all_pipe(cmdstr,output=False):
    ps = subprocess.Popen(cmdstr,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    outp = ps.communicate()
    if outp[0] is not None:
        stdout = outp[0].decode('utf-8').split('\n')
        stdout = [line for line in stdout if line != ""]
    else:
        stdout = []
    if outp[1] is not None:
        stderr = outp[1].decode('utf-8').split('\n')    
        stderr = [line for line in stderr if line != ""]
    else:
        stderr = []

    if output:
        print("STDOUT")
        prtlines(stdout)
        print("STDERR")
        prtlines(stderr)
    return {'stdout':stdout,'stderr':stderr }

def console_stdout(res):  _=[mconsole(f"{line}") for line in res['stdout'] if line != ""]
def console_stderr(res):  _=[mconsole(f"{line}",level="ERROR") for line in res['stderr'] if line != ""]

''' Graveyard '''


if __name__ == '__main__': main()
