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
from base64 import b64encode
from jinja2 import Environment, FileSystemLoader

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
remotemgrurl="https://remotemanager.digi.com/ws/v1/"

''' 
    This file contains two different API interfaces
    
    DIGIHandler uses the DIGI command line interface locally on the device to
    manipulate the device. This can only be accessed through a local client connected to the DIGI.
    
    DIGIAPIHandler uses the DIGI Remote Manager API to access the DIGI device. 
    It works from anywhere when the device is accessible by the Remote Manager. 
    API user must have a Remote Manager Login.
    
    A third interface, the local device API is not yet implemented.
    
'''
     
def main():
    # # dh.getModemStatus(output=True)
    # dh.toggleSIM()
    # dh.waitForConnect()
    digicred = "../../../digicred.json"
    with open(digicred) as f: cred = json.load(f)

    dh = DIGIHandler(user=cred['user'], pw=cred['pw'], mode = "DIGIDEVICE")
    dah = DIGIAPIHandler(user=cred['user'], pw=cred['pw'])
    # dah.setAuthentication()
    # dah.query("devices/inventory")
    inventory = dah.getInventory()
    dah.parseInventory(inventory)
    dah.getCurrentSIM()
    dah.toggleSIM()

    pass


class DIGIHandler(object):
    ''' For Digi local command line access '''
    def __init__(self,pw=None, user = None, mode = None):
        self.DIGIPW = pw
        self.DIGIUSER = user
        self.mode = mode
        if mode == "DIGIDEVICE":
            from digidevice import cli
        return

    def runDIGIcmd(self,icmd, output = True):
        ''' Run a command line command on the DIGI Gateway '''
        if self.mode != "DIGIDEVICE": # from host
            if self.DIGIPW is None: self.setPassword()
            basecmd = f"sshpass -p {self.DIGIPW} ssh admin@{DIGIIP}"
            cmd=f"{basecmd} {DIGI_TESTCMD}"
            cmd=f"{basecmd} {icmd}"
            return cmd_all(cmd, output=output)
        # else: # from device
            
    
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
    
    def toggleSIM(self,output=False):
        ''' Toggle the current SIM: SIM1=T-Mobile SIM2=LEL '''
        res = self.runDIGIcmd(DIGI_TESTCMD,output=output)
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
        res = self.runDIGIcmd("config network modem wwan1 sim_slot",output=output)
        curSIM = res['stdout'][0]
        curSIMName = self.getSIMName(curSIM)
        if output: print(f"Current SIM: {curSIM} {curSIMName}")
        return curSIM, curSIMName
    
    def setPassword(self,inpw = None):
        if inpw is not None:
            self.DIGIPW=inpw
            return
        pw = input("Enter your DIGI gateway command line password: ")
        if pw is not None:
            self.DIGIPW = pw
        else:
            print("Password not updated")

class DIGIAPIHandler(object):
    ''' For Remote Manager Access API '''
    def __init__(self,user=None, pw=None,digiauth=None):
        self.DIGIPW = pw
        self.DIGIUSER = user
        self.DIGIAUTH=digiauth
        self.dev0 = None # Assuming only one DIGI for now
        self.Inventory = None
        self.templateFactory = TemplateFactory()
        return
    
    ''' General Remote Manager Commands '''
 
    def getInventory(self, requery = True):
        if requery: 
            self.Inventory = self.query("devices/inventory")
        return self.Inventory
    
    def parseInventory(self,jinventory):
        if jinventory['count'] > 0 and len(jinventory['list']) > 0:
            dev0 = jinventory['list'][0]  # Only handle the first device
            if len(jinventory['list']) > 1:
                print(f"Ignoring devices:")
                _ = [print(f"\t{dev['name']}" for dev in jinventory['list'][1:])]
            
            self.parseDev(dev0)
        pass
    
    ''' Dev0 Commands '''
   
    def parseDev(self,jdevicedata):
        ''' Create and initialize the device '''
        self.dev0 = self.DIGIDevice(self,jdevicedata = jdevicedata)
        self.dev0.initDevice()
        pass
   
    def getDeviceID(self):
        if self.dev0 is not None:
            return self.dev0.getID()

    def getCurrentSIM(self):
        sim = self.dev0.getCurrentSIM()
        
    def setCurrentSIM(self,simvalue):
        self.dev0.setCurrentSIM(simvalue=simvalue)
        
    def toggleSIM(self):
        sim = self.getCurrentSIM()
        newsim = "_1" if sim == "_2" else "_1"
        print(f"Toggle sim from {sim} to {newsim}")
        self.setCurrentSIM(simvalue=newsim)
        
    
    def setAuthentication(self,user=None, pw = None,):
        if self.DIGIAUTH != None:
            update = input(f"Update authorization: {self.DIGIAUTH}? [Y/n]: ")
            if update != "Y":
                print("Not updating")
                return            
        if user is None: user = input("Enter your DIGI Remote Manager username: ")
        self.DIGIUSER = user
        if pw is None: pw = input("Enter your DIGI Remote Manager password: ")
        self.DIGIPW = pw
        b64 = b64encode(f"{login}:{pw}".encode('utf-8'))
        self.DIGIAUTH = f"Authorization: Basic {b64}"
    
    def query(self,qry,qtype='requests'):
        joutput = None
        r = requests.get(f"{remotemgrurl}/{qry}", auth=(self.DIGIUSER,self.DIGIPW))
        joutput = r.json()
        return joutput
    
    def getTemplatedXML(self,fn,tmpdict):
        return self.templateFactory.applyTemplate(fn,tmpdict)
    
    def querySCI(self,data):
        lremotemgrurl = remotemgrurl.replace('v1','sci')
        headers = {'Content-Type': 'application/xml'}
        r = requests.post(f"{lremotemgrurl}", data = data, headers=headers, auth=(self.DIGIUSER,self.DIGIPW))
        rdict = self.unwrapRCIpost(r)
        return rdict
    
    def dicttoxml(self,dictin):
        xmlout = xmltodict.unparse(dictin).replace('<?xml version="1.0" encoding="utf-8"?>','')
        return xmlout
    
    def testSCIPost(self):
        testfile = "SCITestMessage.xml"
        print(f"{testfile} exists? {os.path.isfile(testfile)}")
        with open(testfile,"rb") as f: data = f.read()
        lremotemgrurl = remotemgrurl.replace('v1','sci')
        headers = {'Content-Type': 'application/xml'}
        r = requests.post(f"{lremotemgrurl}", data = data, headers=headers, auth=(self.DIGIUSER,self.DIGIPW))
        rdict = self.unwrapRCIpost(r)
        pass
    
    def unwrapRCIpost(self,r):
        rdict = xmltodict.parse(r.text)['sci_reply']['send_message']['device']
        return rdict
    
    class DIGIDevice(object):
        def __init__(self,parent,jdevicedata=None):
            self.jdevicedata = jdevicedata
            self.id = jdevicedata['id']
            self.currsim = None
            self.parent = parent
            self.settings = None
            self.root_descriptor = None
            self.state_descriptor = None
            self.CurrentSIM = None
            # self.inventory = None
            # self.getInventory()
        
        def initDevice(self):
            self.root_descriptor = self.getDescriptors("")
            self.state_descriptor = self.getDescriptors("query_state")
            self.settings = self.getSettings()
            self.CurrentSIM = self.getCurrentSIM()
            # self.setCurrentSIM(simvalue="_2")
                
        def getInventory(self):
            self.inventory = self.parent.query(f"devices/inventory/{self.id}")
        
        def setSettings(self,settings):
            self.settings = settings
            
        def setCurrentSIM(self,simvalue="_2"):
            settingdict = {"set_setting":{"network":{"modem":{"wwan1":{"sim_slot":simvalue}}}}}
            try:
                tmpsettings = self.setSettings(settingdict = settingdict)
                sim = tmpsettings['network']['modem']['wwan1']['sim_slot']
                self.settings['network']['modem']['wwan1']['sim_slot'] = sim
            except:
                return None
            return sim

        def getCurrentSIM(self):
            settingdict = {"query_setting":{"network":{"modem":{"wwan1":"sim_slot"}}}}
            try:
                tmpsettings = self.getSettings(settingdict = settingdict)
                sim = tmpsettings['network']['modem']['wwan1']['sim_slot']
                self.settings['network']['modem']['wwan1']['sim_slot'] = sim
            except:
                return None
            return sim
        
        def getDescriptors(self,descriptor):
            descriptordict = {"query_descriptor":descriptor}
            rdict = self.runRCICommand(rcidict = descriptordict)
            # if descriptor != "": descriptor = f"<{descriptor} />"
            # commandxml = self.parent.getTemplatedXML("SCIGetDescriptor.xml.j2",
            #         {"devid":self.id,"descriptor":descriptor})
            rdict = rdict['query_descriptor']['descriptor']
            return rdict
        
        def getSettings(self,settingdict = {"query_setting":""}):
            rdict = self.runRCICommand(rcidict = settingdict)
            rdict = rdict['query_setting']
            return rdict
        
        def runRCICommand(self,rcidict = {"query_setting":""}):
            commandxml = self.parent.getTemplatedXML("SCIRunRCIQuery.xml.j2",
                    {"devid":self.id,"settingxml":self.parent.dicttoxml(rcidict)})
            rdict = self.parent.querySCI(commandxml)['rci_reply']
            return rdict
        
        def setSettings(self,settingdict):
            self.runRCICommand(rcidict = settingdict)
        
        def getDeviceID(self):
            return self.id
        
    
class TemplateFactory():
    def __init__(self):
        self.env = Environment(loader=FileSystemLoader('templates'))
        pass
     
    def applyTemplate(self,tmpltfn,data):
        template = self.env.get_template(tmpltfn)
        rendered_template = template.render(data)
        print(rendered_template)
        return rendered_template
         
if __name__ == '__main__': main()