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

OUTPUT_FILENAME = "MergedOutput.kml"
TOUTPUT_FILENAME = "MergedOutput.csv"
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
        EXPDIR=os.path.join(*[DATADIR,"2024-10-04-JMA-Testing","LEL-UE1"])
        filename = 'MadeOutput' + "_".join(EXPDIR.split("\\")[-2:]) + '.kml'
    DIRCHECKLIST=[DATADIR,EXPDIR]
    for DIR in DIRCHECKLIST:
        mconsole(f"{DIR} exists") if os.path.isdir(DIR) else print(f"{DIR} does not exist")
    kc = KMLCombiner()
    # kc.setFiles(rxlevfiles)
    kc.findFiles(EXPDIR)
    kc.combine(ftype='merge')
    kc.inflate()
    kc.labelsOn()
    kc.filter(filterin = True, filtervalue="Living_Edge_Lab")
    kc.writeKMLFile(filename=filename)
    # kmltask = kwargs['kmltask']
    # kmlc = KMLCombiner()
    # kmlc.findFiles(EXPDIR)
    # # kmlc.combine(ftype = 'kml')
    # # kmlc.combine(ftype = 'txt')
    # kmlc.combine(ftype = 'merge')
    # kmlc.filter(filterin = True, filtervalue="Living_Edge_Lab")
    # # kmlc.removeNoSignal()
    # kmlc.rescale(original="0.3",new="0.7",style="IconStyle")
    # kmlc.rescale(original="0.0",new="0.7",style="LabelStyle")
    # kmlc.inflate()
    # kmlc.writeKMLFile(filename="MadeOutput_2024-10-03.kml")

    
class KMLCombiner(object):
    def __init__(self):
        self.fnames = None
        self.kresult = None
        self.tresult = None
        self.txtdf = None
        self.rxlevdf = None
    
    def setFiles(self, filenames):  self.fnames = filenames
        
    def getFiles(self): return self.fnames
    
    def findFiles(self,rootdir):
        ''' Basic File Selection '''
        ffnlst = walkDir(rootdir)
        rxlevfiles =  [fn for fn in ffnlst if fn.endswith("rxlev.kml")]
        rxlevfiles.sort()
        tdfr = pd.DataFrame(rxlevfiles,columns=['FFN'])
        tdfr['type'] = 'kml'
        txtfiles =  [fn for fn in ffnlst if fn.endswith(".txt") if "Screenshot" not in fn]
        txtfiles.sort()
        tdft = pd.DataFrame(txtfiles,columns=['FFN'])
        tdft['type'] = 'txt'
        
        ''' File Reading and Parsing '''
        # KML
        tdfr['FILEDATA'] = tdfr.FFN.map(self.readFile)
        tdfr['FILEDICT'] = tdfr.FILEDATA.map(self.parseXML)
        # TXT
        tdft['FILEDATA'] = tdft.FFN.map(self.readFile)
        
        ''' Saving as class variables '''
        self.rxlevdf = tdfr.copy()
        self.txtdf = tdft.copy()
        self.fnames = rxlevfiles + txtfiles
    
    def combine(self,ftype ='merge'):
        if ftype == 'merge' or ftype == "kml":
            ''' Turn the kml files into dictionary '''
            tdfr = self.rxlevdf.copy()
            retdict = tdfr.FILEDICT.iloc[0]
            if len(tdfr) > 1:
                for kdict in tdfr.FILEDICT.iloc[1:]:
                    retdict['kml']['Folder']['Placemark'] += kdict['kml']['Folder']['Placemark']
                # mconsole(f"{len(retdict['kml']['Folder']['Placemark'])}")
                mconsole(f"Number of Placemarks: {len(retdict['kml']['Folder']['Placemark'])}")
            self.kresult = retdict
            # return retdict
        if ftype == 'merge' or ftype == "txt":
            ''' Turn the txt files into dataframe '''
            fdatalst = []
            tdft = self.txtdf.copy()
            columns = tdft.FILEDATA.iloc[0][0].strip("\n").split("\t")
            tdfx = pd.DataFrame(columns = columns)
            for fdata in list(tdft.FILEDATA):
                sdata = [dline.strip("\n").split("\t") for dline in fdata[1:]]
                try:
                    tdfy = pd.DataFrame(sdata,columns = columns)
                    tdfx = pd.concat([tdfx, tdfy],axis=0)
                except:
                    continue
            self.tresult = tdfx.copy()
        if ftype == 'merge':
            newpmlst = []
            kmldict = self.kresult
            txtdf = self.tresult
            for pm in kmldict['kml']['Folder']['Placemark']:
                # if pm['ExtendedData'][style]['scale'] == original:
                    ts = pm['ExtendedData']['Data'][4]['value']
                    tdfx = txtdf[txtdf.Timestamp == ts]
                    ''' Add operator from text file '''
                    if len(tdfx) > 0:
                        operator = tdfx.Operatorname.iloc[0]
                    else:
                        operator = "UNKNOWN"
                    pm['ExtendedData']['Data'].append({'@name':'OPERATOR','value':operator})
                    newpmlst.append(pm)
            kmldict['kml']['Folder']['Placemark'] = newpmlst
            self.kresult = kmldict
   
    def rescale(self,kmldict = None, original="0.3",new="0.7",style="IconStyle" ):
        kmldict = kmldict if kmldict is not None else self.kresult 
        ''' Style can be IconStyle or LabelStyle '''
        for pm in kmldict['kml']['Folder']['Placemark']:
            if pm['Style'][style]['scale'] == original:
                pm['Style'][style]['scale'] = new
        self.kresult = kmldict
        return kmldict
    
    def inflate(self,kmldict = None, min=0.1, max=1.2,style="IconStyle" ):
        kmldict = kmldict if kmldict is not None else self.kresult
        ''' Style can be IconStyle '''
        style = 'IconStyle'
        threshold = 200
        siglevlst = []
        for pm in kmldict['kml']['Folder']['Placemark']:
            siglevlst.append([pm['ExtendedData']['Data'][1]['@name'], pm['ExtendedData']['Data'][1]['value']])
        tdfx = pd.DataFrame(siglevlst, columns = ['name','value'])
        tdfx['fvalue'] = tdfx.value.map(lambda xx: int(xx.replace("-","").replace(" dBm","")))
        tdfx['fnorm'] = (tdfx.fvalue - tdfx.fvalue.min())/(tdfx.fvalue.max() - tdfx.fvalue.min())
        tdfx['fscale'] = (1 - tdfx.fnorm) * (max-min) + min
        tdfx['scale'] = tdfx.fscale.map(lambda xx: str(xx))
        scalelst = list(tdfx['scale'])
        for scale,pm in zip(scalelst, kmldict['kml']['Folder']['Placemark']):
            pm['Style'][style]['scale'] = scale
        self.kresult = kmldict
        return kmldict
    
    def labelsOn(self):
        self.rescale(original="0.0",new="0.7",style="LabelStyle")

    def removeNoSignal(self,kmldict = None):
        kmldict = kmldict if kmldict is not None else self.kresult
        pmlst = kmldict['kml']['Folder']['Placemark']
        newpmlst = []
        for pm in pmlst:
            if not pm['name'].startswith("-200"): # No Signal
                newpmlst.append(pm)
        kmldict['kml']['Folder']['Placemark'] = newpmlst
        self.kresult = kmldict
        return kmldict
    
    def filter(self,kmldict = None, filtername = "OPERATOR", filtervalue = "314737", filterin = True):
        kmldict = kmldict if kmldict is not None else self.kresult
        # self.result['kml']['Folder']['Placemark'][0]['ExtendedData']['Data'].append({'@name':'OPERATOR','value':'314737'})
        newpmlst = []
        for pm in kmldict['kml']['Folder']['Placemark']:
            foundmatch = False
            for edata in pm['ExtendedData']['Data']:
                if edata['@name'] == filtername and edata['value'] == filtervalue:
                    foundmatch = True
                    continue
            if filterin:
                if foundmatch:               
                    newpmlst.append(pm)
            else:
                if not foundmatch:
                    newpmlst.append(pm)
        kmldict['kml']['Folder']['Placemark'] = newpmlst
        self.kresult = kmldict
        return kmldict
    
    def replaceExtendedData(self,extdatalst,kmldict = None):
        kmldict = kmldict if kmldict is not None else self.kresult
        newpmlst = []
        for ii, pm in enumerate(kmldict['kml']['Folder']['Placemark']):
            pm['ExtendedData']['Data'] = extdatalst[ii]
            newpmlst.append(pm)
        kmldict['kml']['Folder']['Placemark'] = newpmlst
        self.kresult = kmldict
        return kmldict
    
    def getDataKeyValue(self,key,kmldict=None):
        kmldict = kmldict if kmldict is not None else self.kresult
        # self.result['kml']['Folder']['Placemark'][0]['ExtendedData']['Data'].append({'@name':'OPERATOR','value':'314737'})
        matchlst = []
        for pm in kmldict['kml']['Folder']['Placemark']:
            foundmatch = False
            for edata in pm['ExtendedData']['Data']:
                if edata['@name'] == key:
                    foundmatch = True
                    continue
                if foundmatch:               
                    matchlst.append(edata['value'])
                if not foundmatch:
                    matchlst.append(None)
        return pd.DataFrame(matchlst)
    ''' Map and Apply Methods '''
   

        
        
    def parseXML(self,filedata):
        return xmltodict.parse('\n'.join(filedata))

    def readFile(self,fn,prepend = False):
        lines = []
        with open(fn,"r") as f:
            lines = f.readlines()
        if prepend:
            fnlabel = os.path.basename(fn).replace(".txt","")
            lines = [f"{fnlabel}\t{line}" for line in lines]
        return lines

    def writeKMLFile(self,filedata=None,ftype = 'kml', filename = OUTPUT_FILENAME):
        filedata = filedata if filedata is not None else self.kresult
        if ftype == 'kml':
            with open(filename, 'w') as f:
                    f.write(xmltodict.unparse(filedata))
        elif ftype == 'txt':
            writejoin(filedata.set_index(filedata.columns[0],TOUUTPUT_FILENAME))
                
def cmdOptions(tmpcnf):
    parser = OptionParser(usage="usage: %prog [options]")
    parser.add_option("-d", "--debug",
                  action="store_true", dest="debug", default=False,
                  help="Debugging mode")
    parser.add_option("-T", "--kmltask",
                  dest="kmltask", default='fasttrack',
                  help="Specify which task to run ('fasttrack','filemerge','filereport'")
    options,_ = parser.parse_args()
    tmpcnf.update(options.__dict__.copy())
    return  tmpcnf

def console_stdout(res):  devnull=[mconsole(f"{line}") for line in res['stdout']]
def console_stderr(res):  devnull=[mconsole(f"{line}",level="ERROR") for line in res['stderr']]





''' Graveyard '''

# class XMLCombiner(object):
#     def __init__(self, filenames):
#         assert len(filenames) > 0, 'No filenames!'
#         self.fnames = filenames
#         eT.register_namespace('', NAMESPACE)
#         # save all the roots, in order, to be processed later
#         self.trees = [eT.parse(f) for f in filenames]
#         self.roots = [t.getroot() for t in self.trees]
#
#     def combine(self):
#         rootcoordinate = self.roots[0].findall(".//{"+NAMESPACE+"}coordinates")
#         for ii,r in enumerate(self.trees[1:]):
#             print(f"{ii} {os.path.basename(self.fnames[ii])} {r}")
#             othercoordinate = r.findall(".//{"+NAMESPACE+"}coordinates")
#             # try:
#             newcoordinate = str(rootcoordinate[0].text) + str(othercoordinate[0].text)
#             filtered = "\n".join([ll.rstrip() for ll in newcoordinate.splitlines() if ll.strip()])
#             rootcoordinate[0].text = str(filtered)
#             self.trees[0].write(OUTPUT_FILENAME)
#             # except:
if __name__ == '__main__': main()