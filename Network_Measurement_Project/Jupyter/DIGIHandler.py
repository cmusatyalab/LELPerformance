import os
import sys
import subprocess
import shutil
import pandas as pd
import numpy as np
import xmltodict
import json
import hashlib
import requests
import getpass
from requests import Response
from time import sleep

sys.path.append("../../lib")
print(sys.path)
from pyutils import *

from optparse import OptionParser

DIGIIP="192.168.2.1"
DIGI_TESTCMD="config network modem wwan1 sim_slot"
DIGIIFC="enx0050b623c78d"
TIMEOUTCT=40
TIMEOUTWT=10
simdict = {'2':"Living Edge Lab",'1':"T-Mobile"}

def main():
    dh = DIGIHandler()
    # dh.getModemStatus(output=True)
    dh.toggleSIM()
    dh.waitForConnect()


class DIGIHandler(object):
    def __init__(self):
        self.DIGIPW = None
        return

    def runDIGIcmd(self,icmd, output = True):
        ''' Run a command line command on the DIGI Gateway '''
        if self.DIGIPW is None: self.setPassword()
        basecmd = f"sshpass -p {self.DIGIPW} ssh admin@{DIGIIP}"
        cmd=f"{basecmd} {DIGI_TESTCMD}"
        cmd=f"{basecmd} {icmd}"
        return cmd_all(cmd, output=output)
    
    def getModemStatus(self,output=True):
        ''' Get (and parse) the WWAN1 Modem Status '''
        res = self.runDIGIcmd("show modem verbose",output=output)
        modemstat = None
        stdoutclean = [line.strip() for line in res['stdout'] if line.startswith(" Modem") 
                                                               or line.startswith(" wwan1")]
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
                print(data)
                modemstat = "unknown"
            if output: print(data)
        return modemstat,stdoutclean
    
    def toggleSIM(self):
        ''' Toggle the current SIM: SIM1=T-Mobile SIM2=LEL '''
        res = self.runDIGIcmd(DIGI_TESTCMD,output=False)
        curSIM = res['stdout'][0]
        newSIM = '1' if curSIM == '2' else '2'
        print(f"Changing SIM {curSIM} to SIM {newSIM} -- {simdict[newSIM]}")
        self.runDIGIcmd(DIGI_TESTCMD + " " + newSIM,output=False)
        sleep(5)
        
    def waitForConnect(self):
        for ii in range(0,TIMEOUTCT):
            mstat, output = self.getModemStatus(output=False)
            nonstatelst = ['not_connected','not_found','disabled','enabling','disabling',
                           'unknown','no_signal','registered','connecting']
            if (mstat not in nonstatelst):
                print(f"{ii} {humandatenow()} {mstat}:{output[-1]}:{self.getCurrentSIM()[-1]}")
                break
            else:
                print(f"{ii} {humandatenow()} {mstat}:{output[-1]}:{self.getCurrentSIM()[-1]}")
            sleep(TIMEOUTWT)
    
    def pingTest(self, dest="8.8.8.8", c=1, output=True):
        cmd=f"ping -c {c} -I {DIGIIFC} {dest}"
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
        
    def getCurrentSIM(self,output=False):
        res = self.runDIGIcmd("config network modem wwan1 sim_slot",output=False)
        curSIM = res['stdout'][0]
        curSIMName = self.getSIMName(curSIM)
        if output: print(f"Current SIM: {curSIM} {curSIMName}")
        return curSIM, curSIMName
    
    def setPassword(self,inpw = None):
        if inpw is not None:
            self.DIGIPW=inpw
            return
        pw = input("Enter your DIGI gateway command line password")
        if pw is not None:
            self.DIGIPW = pw
        else:
            print("Password not updated")
            
        
        

if __name__ == '__main__': main()