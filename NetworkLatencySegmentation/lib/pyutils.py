#!/usr/bin/env python3
import json
import os
import sys,platform
import shlex, subprocess
import time, datetime
from subprocess import PIPE
import logging, logging.config

def cd(path):
    os.chdir(path)

def oscmd(cmdstr): # Prints out to console and returns exit status
    return os.system(cmdstr)

def cmd(cmdstr,removeblank=False): # Returns the output of the command as a list
    output = os.popen(cmdstr).read().split("\n")
    if len(output) > 0 and removeblank:
        output = [ln for ln in output if ln != ""]
    return output

def cmd0(cmdstr): # Returns first line of output as a string
    retlst = cmd(cmdstr)
    return retlst[0].strip()

def cmds(cmdstr): # Returns all output  of the command as a string
    output = os.popen(cmdstr).read()
    return output

def cmd_subp(cmdstr):
    args = shlex.split(cmdstr)
    procdata = subprocess.Popen(args)
    return procdata

def prtlines(lines):
    devnull = [print(line) for line in lines]
    
def cmd_all(cmdstr,output=False):
    args = shlex.split(cmdstr)
    procdata = subprocess.run(args,stdout=PIPE,stderr=PIPE)
    stdout = procdata.stdout.decode('utf-8').split('\n')
    stderr = procdata.stderr.decode('utf-8').split('\n')
    if output:
        print("STDOUT")
        prtlines(stdout)
        print("STDERR")
        prtlines(stderr)
    return {'stdout':stdout,'stderr':stderr }

def walkDir(dn):
    fnlst = []
    for root, subdirs, files in os.walk(dn):
        if len(files) > 0:
            for fn in files:
                ffn = os.path.join(root,fn)
                if os.path.exists(ffn): fnlst.append(ffn)
    return fnlst

def creationDate(path_to_file):
    if platform.system() == 'Windows':
        return os.path.getmtime(path_to_file)
    else:
        stat = os.stat(path_to_file)
        try:
            return stat.st_birthtime
        except AttributeError:
            # We're probably on Linux. No easy way to get creation dates here,
            # so we'll settle for when its content was last modified.
            return stat.st_mtime

def humandate(unixtime):
    retstr = datetime.datetime.fromtimestamp(unixtime).strftime('%Y-%m-%d-%H-%M-%S-%f')
    return retstr

def humandatenow():
    retstr = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
    return retstr

def printhumandatenow(prstr=""): print(humandatenow(),prstr)

def getFreeMem(): return int(cmd("free -m")[1].split(" ")[-1])

def getMemUsage(dirlst):
    # needs to be called with getMemUsage(dir())
    # These are the usual ipython objects, including this one you are creating
    ipython_vars = ['In', 'Out', 'exit', 'quit', 'get_ipython', 'ipython_vars']
    # Get a sorted list of the objects and their sizes
    retlst = sorted([(x, sys.getsizeof(globals().get(x))) for x in dirlst if not x.startswith('_') and \
            x not in sys.modules and x not in ipython_vars], key=lambda x: x[1], reverse=True)
    return retlst

def getLastLine(fn): # Faster than running a commandline
    with open(fn,'rb') as f:
        f.seek(-2, os.SEEK_END)
        while f.read(1) != b'\n':
            f.seek(-2,os.SEEK_CUR)
        last_line = f.readline().decode()
#         print(last_line)
    return last_line

from timeit import timeit
def timefunc(func,*args,nexp=10,**kwargs):
    ''' time a function with *args and **kwargs '''
    def wrapper(func, *args, **kwargs):
        def wrapped():
            return func(*args, **kwargs)
        return wrapped
    wrapped = wrapper(func,*args,**kwargs)
    timeret = timeit(wrapped,number=nexp)
    return timeret

''' JSON '''
def readJSON(fn):
    retdict = {}
    if os.path.isfile(fn):
        with open(fn,"r") as f:
            retdict = json.load(f)
    else:
        writeJSON(fn,retdict)
    return retdict

def writeJSON(fn,injson):
    with open(fn,"w") as f:
        json.dump(injson,f,indent=4)

       
def configureLogging(LOGNAME=__name__,loglev = logging.DEBUG):
    class CustomFormatter(logging.Formatter):
        """Logging Formatter to add colors and count warning / errors"""
    
        grey = "\033[37;40m"
        bold_yellow = "\033[33;1m"
        red = "\033[31;40m"
        bold_red = "\033[31;1m"
        bold_green = "\033[32;1m"
        reset = "\033[0m"
        format = "%(asctime)s [%(levelname)s] %(message)s"
    
        FORMATS = {
            logging.DEBUG: grey + format + reset,
            logging.INFO: bold_green + format + reset,
            logging.WARNING: bold_yellow + format + reset,
            logging.ERROR: bold_red + format + reset,
            logging.CRITICAL: bold_red + format + reset
        }
    
        def format(self, record):
            log_fmt = self.FORMATS.get(record.levelno)
            formatter = logging.Formatter(log_fmt)
            return formatter.format(record)
    logging.config.dictConfig({'version':1,'disable_existing_loggers':True})
    
    selflogger = logging.getLogger(LOGNAME)
    selflogger.propagate = False
    fh = logging.FileHandler(LOGNAME+'.log')
    fh.setLevel(loglev)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(loglev)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh.setFormatter(formatter)
    # ch.setFormatter(formatter)
    ch.setFormatter(CustomFormatter())
    selflogger.addHandler(fh)
    selflogger.addHandler(ch)
    selflogger.setLevel(loglev)
    return selflogger

