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


def main():
    global logger
    LOGFILE="epc_startup.log"
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = LOGLEV,coloron=False)
    kwargs = configure()
    tcpdumpcmd = "gnome-terminal -- bash -c 'tcpdump -s 0 -U -w - -i any | python3 magma_measure.py -O -S MAGMA'"
    mconsole("Starting epc processes")
    
    cmdlst = [tcpdumpcmd]
    for cmdstr in cmdlst:
        oscmd(cmdstr)

    pass



def configure():
    (options,_) = cmdOptions()
    cmdopts = options.__dict__.copy()
    configfn = "config-jit.json"
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