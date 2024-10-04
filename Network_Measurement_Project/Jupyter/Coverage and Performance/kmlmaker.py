#!/usr/bin/env python
import os
import sys
import platform
# print(sys.path)
sys.path.append("../../")
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



FILEMERGING = False
FILEREPORTING = False
TMP = True

OUTPUT_FILENAME = "MadeOutput.kml"
TOUTPUT_FILENAME = "MadeOutput.csv"
KMLTEMPLATEFN = "kmltemplate.kml"
DFTEMPLATEFN = "pdtemplate.csv"
NAMESPACE = "http://earth.google.com/kml/2.1"
cnf = initConfig()
LOGNAME=__name__

def main():
    LOGFILE=f"{LOGNAME}.log"
    logger = configureLogging(LOGNAME=LOGNAME,LOGFILE=LOGFILE,coloron=False)
    kwargs = cmdOptions(cnf)
    
    if sys.platform == "linux":
        DATADIR="/home/jblake1/Downloads/Network_Measurements"
    else:
        DATADIR="P:\\My Drive\\CMU-LEL\\Mill19\\Images\\Coverage and Performance"
        EXPDIR=os.path.join(*[DATADIR,"2024-10-03-JMA-Testing","PXL4-UE1"])
    
    DIRCHECKLIST=[DATADIR,EXPDIR]
    for DIR in DIRCHECKLIST:
        mconsole(f"{DIR} exists") if os.path.isdir(DIR) else print(f"{DIR} does not exist")
    
    # kmltask = kwargs['kmltask']
    indf = readjoin(EXPDIR,"JMA-2024-10-03-processed.csv")
    kmlm = KMLMaker()
    # kmlm.findFiles(EXPDIR)
    kmlm.makeKML(indf)
    kmlm.writeKMLFile()
    pass
    
class KMLMaker(object):
    def __init__(self):
        with open(KMLTEMPLATEFN, "r") as f:
            lines = f.readlines()
        self.kmlheader = lines[0]
        self.kmlnamespace = lines[1]
        self.kmlend = lines[3]
        self.templatedata = xmltodict.parse('\n'.join(lines))
        self.placemarktemplate = self.templatedata['kml']['Folder']['Placemark']
        self.kmldataframe = None
        self.dfc = None
        self.kresult = None

    def findFiles(self,rootdir):
        ''' Basic File Selection '''
        ffnlst = walkDir(rootdir)
        csvfiles =  [fn for fn in ffnlst if fn.endswith(".csv") ]
        csvfiles.sort()
        tdfc = pd.DataFrame(csvfiles,columns=['FFN'])
        tdfc['type'] = 'csv'
        tdfc['FILEDATA'] = tdfc.FFN.map(self.readCSV)
        self.dfc = tdfc.copy()
    
    def makeKML(self):
        tdfc = self.dfc.copy()
        kmltmp = self.templatedata.copy()
        tdfc = tdfc.FILEDATA.iloc[0]
        tdfc = tdfc.dropna(subset=['LONGITUDE','LATITUDE'])
        pmdf = tdfc.apply(self.makePM,axis =1)
        kmltmp['kml']['Folder']['Placemark'] = list(pmdf)
        self.kresult = kmltmp.copy()
        
    def makeKML(self,indf,lng="LONGITUDE",lat="LATITUDE"):
        tdfc = indf.copy()
        tdfc = tdfc.dropna(subset=[lng,lat])
        kmltmp = self.templatedata.copy()
        pmdf = tdfc.apply(self.makePM,axis =1)
        kmltmp['kml']['Folder']['Placemark'] = list(pmdf)
        self.kresult = kmltmp.copy()
        
    def makePM(self,row):
        collst = ['RSRP','PTMEAN','PTMIN','PTMAX','PTSD','PSLOSS','SNR','DOWNLOAD','UPLOAD','CELLID','LONGITUDE','LATITUDE']
        rowlst = list(row.index)
        iterlst = [col for col in collst if col in rowlst]
        pmtmp = self.placemarktemplate.copy()
        for col in iterlst:
            if np.isnan(row[col]):
                continue 
            if col == "PTMEAN":
                pmtmp = self.updatePMData(pmtmp,"name",f"{row[col]} ms")
            elif col == "LONGITUDE" or col == "LATITUDE":
                pmtmp = self.updatePMData(pmtmp,"coordinates",f"{row.LONGITUDE}, {row.LATITUDE}, 0")
                continue
            pmtmp = self.updatePMData(pmtmp,col,f"{row[col]}")
        pmtmp = self.removePMTBData(pmtmp)
        retpm = json.loads(json.dumps(pmtmp)) # Strange way to remove obscure call by reference issues
        return retpm
    
    def updatePMData(self,pmin,name,value):
        pm = pmin.copy()
        if name == "name":
            pm['name'] = value
        elif name == "coordinates":
            pm['Point']['coordinates'] = value
        else:
            namelst = [item['@name'] for item in pm['ExtendedData']['Data']]
            if name in namelst:
                for ii,pmname in enumerate(namelst):
                    if pmname == name:
                        pm['ExtendedData']['Data'][ii]['value'] = value
            else:
                pm['ExtendedData']['Data'].append({"@name":name,"value":value})
        return pm
    
    def removePMTBData(self,pm):
        namelst = [item['@name'] for item in pm['ExtendedData']['Data']]
        edatalst = []
        for ii,pmname in enumerate(namelst):
            if pm['ExtendedData']['Data'][ii]['value'] != "TBD":
                edatalst.append({'@name':pm['ExtendedData']['Data'][ii]['@name'],
                        'value':pm['ExtendedData']['Data'][ii]['value']})
        pm['ExtendedData']['Data'] = edatalst
        return pm
    
    def readCSV(self,ffn):
        return readjoin("",ffn)
    
    def readFile(self,fn,prepend = False):
        lines = []
        with open(fn,"r") as f:
            lines = f.readlines()
        if prepend:
            fnlabel = os.path.basename(fn).replace(".txt","")
            lines = [f"{fnlabel}\t{line}" for line in lines]
        return lines

    def writeKMLFile(self,filename = OUTPUT_FILENAME):
        filedata = self.kresult
        with open(filename, 'w') as f:
                f.write(xmltodict.unparse(filedata))
                
def cmdOptions(tmpcnf):
    parser = OptionParser(usage="usage: %prog [options]")
    parser.add_option("-d", "--debug",
                  action="store_true", dest="debug", default=False,
                  help="Debugging mode")
    parser.add_option("-T", "--kmltask",
                  dest="kmltask", default='fasttrack',
                  help="Specify which task to run ('fasttrack','filemerge','filereport'")
    parser.add_option("-C", "--csvfile",
                  dest="csvfile", 
                  help="Path to csv file containing data for kmlfile")
    options,_ = parser.parse_args()
    tmpcnf.update(options.__dict__.copy())
    return  tmpcnf

def console_stdout(res):  devnull=[mconsole(f"{line}") for line in res['stdout']]
def console_stderr(res):  devnull=[mconsole(f"{line}",level="ERROR") for line in res['stderr']]

''' Graveyard '''

if __name__ == '__main__': main()