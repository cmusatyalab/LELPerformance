import os
import sys
import subprocess
import shutil
from time import sleep, time
from jinja2 import Environment, FileSystemLoader
from pprint import pprint
import json

from digidevice import cli
from digidevice import config
from digidevice import datapoint

TIMEOUTCT=40
TIMEOUTWT=10
simdict = {'2':"Living Edge Lab",'1':"T-Mobile"}
localcfgfile = "configfile.txt"
DEFAULT_DATAPOINT_TAG = "LELMonitor"

'''
    
    DIGIPythonHandler uses the DIGI python interface locally on the device shell to
    manipulate the device. This can only be accessed through a local client connected to the DIGI 
    or through the Remote Manager command line shell interface.

'''
     
def main():
    print(cmd_all("ls"))
    dh = DIGIPythonHandler()
    dh.pingTest()
    dh.getDIGIconfig()
    dh.getCurrentSIM(output=True, debug=False)    
    dh.getModemStatus(output=False, debug=False)
    # dh.toggleSIM(output=False)
    dh.waitForConnect(output=False)
    dh.pingTest()
    pass


class DIGIPythonHandler(object):
    ''' For Digi local command line access '''
    def __init__(self,pw=None, user = None, mode = None):
        self.datapoint_tag = DEFAULT_DATAPOINT_TAG
        # self.DIGIPW = pw
        # self.DIGIUSER = user
        # self.mode = mode
        return

    def runDIGIcmd(self,icmd, output = True,debug=False):
        ''' Run a command line command on the DIGI Gateway '''
        output = False
        if output: print(f"Command: {icmd}")
        outp = {}
        outp['stdout'] = cli.execute(icmd).split("\n")
        outp['stderr'] = [""]
        return outp
    
    def getDIGIvalue(self,key,output = True,debug=False):
        ''' Get a parameter value on the DIGI Gateway '''
        cfg = config.load()
        value = cfg.get(key)
        if output: print(f"key={key} value={value}")
        return value 

    def setDIGIvalue(self,key,value, output = True,debug=False):
        ''' set a parameter value on the DIGI Gateway '''
        if output: print(f"key={key} value={value}")
        cfg = config.load(writable=True)
        cfg.set(key,value)
        outp = {}
        outp['stdout'] = cfg.set(key,value)
        outp['stderr'] = [""]
        cfg.commit()
        return outp
    
    def getDIGIvalue(self,key,output = True,debug=False):
        ''' Get a parameter value on the DIGI Gateway '''
        cfg = config.load()
        value = cfg.get(key)
        if output: print(f"key={key} value={value}")
        return value
    
    def getDIGIconfig(self,output = True,debug=False,save=False):
        cfg = config.load()
        cfglines = cfg.dump().splitlines()
        if output: pprint(cfglines)
        if save:
            cfglines = [line + '\n' for line in cfglines]
            with open(localcfgfile,"w") as f:
                f.writelines(cfglines)
        return cfg
    
    def searchDIGIconfig(self,searchstr,output=False):
        cfg = config.load()
        cfglines = cfg.dump().splitlines()
        matchlines = [line for line in cfglines if searchstr in line]
        if output: pprint(matchlines)
        return matchlines
    
    def sendDIGIdatapoint(self,stream = "Test", value = 0, units = "NA", timestamp = None, geo_location = (0,0,0), description = "NA", quality = -1):
        if timestamp is None: timestamp = time()
        stream = f"{self.datapoint_tag}/{stream}"
        datapoint.upload(stream, value, units=units, timestamp=timestamp, geo_location=geo_location, description=description, quality=quality)
        
    def getDIGIsystem(self,output = True,debug=False, verbose = True):
        cmd = "show system"
        if verbose: cmd = cmd + " verbose"
        outp = self.runDIGIcmd(cmd,output=output,debug=debug)
        if output: pprint(outp)
        return outp
    
    def getModemStatus(self,output=True,debug = False):
        ''' Get (and parse) the WWAN1 Modem Status '''
        res = self.runDIGIcmd("show modem verbose",output=output,debug=debug)
        modemstat = None
        stdoutclean = [line.strip() for line in res['stdout'] if line.startswith("Modem") 
                                                               or line.startswith(" wwan1")]
        if debug: print(f"stdoutclean: {stdoutclean}")
        if len(stdoutclean) < 2:
            modemstat = 'not_connected'
        elif 'disabl' in stdoutclean[1]:
            modemstat = 'disabled'
        elif 'found' in stdoutclean[1]:
            modemstat = 'not_found'
        elif 'enabl' in stdoutclean[1]:
            modemstat = 'enabling'
        elif 'No Signal' in stdoutclean[1]:
            modemstat = 'no_signal'
        elif 'registered' in stdoutclean[1]:
            modemstat = 'registered'
        elif 'connecting' in stdoutclean[1]:
            modemstat = 'connecting'
        else:
            data = [fld for fld in stdoutclean[1].split(' ') if fld != '']
            dbm = data[-2].replace("(","")
            try:
                modemstat = f"{data[3]}_SIM:{data[1]}_DBM:{dbm}"
            except:
                if output: print(data)
                modemstat = "unknown"
            if output: print(f"{modemstat} {data}")
        return modemstat,stdoutclean
    
    def toggleSIM(self,output=False,debug = False):
        SIMSLOTSETTING="network.modem.wwan1.sim_slot"        
        # sim_slot,_ = self.getCurrentSIM(output=output,debug=debug)
        sim_slot = self.getDIGIvalue(SIMSLOTSETTING)
        if output: print(f"Sim slot is {sim_slot}")
        nsim_slot = "2" if sim_slot == "1" else "1"
        self.setDIGIvalue(SIMSLOTSETTING,nsim_slot)
        sim_slot,_ = self.getCurrentSIM(output=output,debug=debug)
        if output: print(f"Sim slot is {sim_slot}")
        sleep(5)
        
    
    def waitForConnect(self,output=True,timeoutct = TIMEOUTCT, timeoutwt = TIMEOUTWT):
        print(f"Waiting through {timeoutct} attempts of {timeoutwt} seconds ")
        for ii in range(0,timeoutct):
            mstat, output = self.getModemStatus(output=False)
            nonstatelst = ['not_connected','not_found','disabled','enabling','disabling',
                           'unknown','no_signal','registered','connecting']
            if (mstat not in nonstatelst):
                if output: print(f"{ii} {humandatenow()} {mstat}:{output[-1]}:{self.getCurrentSIM()[-1]}")
                break
            else:
                if output: print(f"{ii} {humandatenow()} {mstat}:{output[-1]}:{self.getCurrentSIM()[-1]}")
            sleep(timeoutwt)
        connected = True if ii < timeoutct else False
        return connected
    
    def pingTest(self, dest="8.8.8.8", c=1, output=True):
        cmd=f"ping -c {c} {dest}"
#         print(cmd)
        res =  cmd_all(cmd)
        if output and 'stdout' in res:
            _ = [print(line) for line in res['stdout']]
        return res
        
    def getSIMName(self,simstr):
        if simstr in simdict.keys():
            return simdict[simstr]
        else:
            return "UNKNOWN"
        
    def getCurrentSIM(self,output=False,debug=False):
        res = self.runDIGIcmd("config network modem wwan1 sim_slot",output=output,debug=debug)
        curSIM = res['stdout'][0]
        curSIMName = self.getSIMName(curSIM)
        if output: print(f"Current SIM: {curSIM} {curSIMName}")
        return curSIM, curSIMName
    
    def setDataPointTag(self,dptag):
        self.datapoint_tag = dptag

''' Utilities '''
import datetime
import shlex, subprocess
from subprocess import PIPE

def humandatenow():
    retstr = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
    return retstr


def cmd_all(cmdstr,output=False):
    args = shlex.split(cmdstr)
    procdata = subprocess.run(args,stdout=PIPE,stderr=PIPE)
    stdout = procdata.stdout.decode('utf-8').split('\n')
    stderr = procdata.stderr.decode('utf-8').split('\n')    
    stderr = [line for line in stderr if line != ""]
    
    if output:
        print("STDOUT")
        prtlines(stdout)
        print("STDERR")
        prtlines(stderr)
    return {'stdout':stdout,'stderr':stderr }

if __name__ == '__main__': main()