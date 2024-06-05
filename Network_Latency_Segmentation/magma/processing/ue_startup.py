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

if os.name == 'nt':
    OSNAME='WINDOWS'
elif os.name == 'posix':
    OSNAME='LINUX'
else:
    OSNAME='OTHER'
    
LOGNAME=__name__
LOGLEV = logging.INFO


def main():
    global logger
    LOGFILE="{}_iperf.log".format(OSNAME)
    logger = simlogging.configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,loglev = LOGLEV,coloron=False)
    kwargs = configure()
    tcpdumpcmd = f"gnome-terminal -- bash -c 'tcpdump -s 0 -U -w - -i {kwargs['ue_interface']} | python3 magma_measure.py -O -S UE'"
    offsetcmd = "gnome-terminal -- bash -c 'python ue_offset.py'"
    iperfcmd = "gnome-terminal -- bash -c 'python ue_iperf.py'"
    pingcmd = f"gnome-terminal -- bash -c 'ping {kwargs['cloudlet_ip']}'"
    mconsole("Starting ue processes")
    
    cmdlst = [tcpdumpcmd, offsetcmd,iperfcmd,pingcmd]
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