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
SESSIONNAME="CLOUDLET"

def main():
    global logger
    LOGFILE="cloudlet_startup.log"
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = LOGLEV,coloron=False)
    kwargs = configure()
    cloudlet_interface = kwargs['cloudlet_interface']
    
    tmuxstartcmd = "tmux start-server"
    tcpdumpcmd = f'tmux new-session -d -s {SESSIONNAME} -n cloudletstartup -d "bash -c \'tcpdump -s 0 -U -w - -i {cloudlet_interface} | python3 magma_measure.py -O -S CLOUDLET\'"'
    querycmd = f'tmux split-window -t {SESSIONNAME}:0 "bash -c \'python query_measurements.py\'"'
    tmuxtiled = f'tmux select-layout -t {SESSIONNAME}:0 tiled'
    tmuxattach = f'tmux attach -t {SESSIONNAME}'
    mconsole("Starting ue processes")
    
    cmdlst = [tmuxstartcmd,tcpdumpcmd,tmuxtiled,querycmd, tmuxattach]
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
        cnf.update(cnf['CLOUDLET'])
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