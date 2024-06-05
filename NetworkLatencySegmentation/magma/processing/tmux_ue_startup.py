import time
import sys
import os
import re
import time

sys.path.append("../lib")

import numpy as np
import pandas as pd
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
SESSIONNAME="UE"

def main():
    global logger
    LOGFILE="ue_startup.log"
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = LOGLEV,coloron=False)
    kwargs = configure()
    cloudlet_ip = kwargs['cloudlet_ip']
    ue_interface = kwargs['ue_interface']
    
    tmuxstartcmd = "tmux start-server"
    offsetcmd = f'tmux new-session -d -s {SESSIONNAME} -n uestartup -d "bash -c \'python ue_offset.py\'"'
    iperfcmd = f'tmux split-window -t {SESSIONNAME}:0 "bash -c \'python ue_iperf.py\'"'
    pingcmd = f'tmux split-window -t {SESSIONNAME}:0 "bash -c \'ping {cloudlet_ip}\'"'
    tcpdumpcmd = f'tmux split-window -t {SESSIONNAME}:0 "bash -c \'tcpdump -s 0 -U -w - -i {ue_interface} | python3 magma_measure.py -O -S UE\'"'
    tmuxtiled = f'tmux select-layout -t {SESSIONNAME}:0 tiled'
    tmuxattach = f'tmux attach -t {SESSIONNAME}'
    mconsole("Starting ue processes")
    
    cmdlst = [tmuxstartcmd, offsetcmd,iperfcmd,pingcmd,tcpdumpcmd,tmuxtiled,tmuxattach]
    for cmdstr in cmdlst:
        oscmd(cmdstr)

    pass

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
        cnf.update(cnf['UE'])
    else:
        cnf = cmdopts
    return cnf

def cmdOptions():
    parser = OptionParser(usage="usage: %prog [options]")
    parser.add_option("-d", "--debug",
                  action="store_true", dest="debug", default=False,
                  help="Debugging mode")
    return  parser.parse_args()



if __name__ == '__main__': main()