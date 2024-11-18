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
import itertools


from optparse import OptionParser
from simlogging import *
from config import *



FILEMERGING = False
FILEREPORTING = False
PRO=True
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
        DATADIR="P:\\My Drive\\CMU-LEL\\Mill19\\Coverage and Performance"
        EXPDIR=os.path.join(*[DATADIR,"2024-10-10-Mill19-Testing","LEL-UE1"])
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
    kc.filter(filterin = True, filtervalue="314737")
    kc.filter(filterin = True, filtername="PHONE STATE", filtervalue="D")
    tdfx = kc.kmlToDF(filename="tmp.csv")
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
        self.PRO = PRO
    
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
                for ii,srow in enumerate(sdata):
                    sdata[ii] = srow + ["" for jj in range(0,len(columns) - len(srow))] # Pad
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
            pm0 = kmldict['kml']['Folder']['Placemark'][0]['ExtendedData']['Data']
            eddict = {dd['@name']:ii for ii,dd in enumerate(pm0)}
            tsindex = eddict['TIME']
            for pm in kmldict['kml']['Folder']['Placemark']:
                # if pm['ExtendedData'][style]['scale'] == original:
                    try:
                        ts = pm['ExtendedData']['Data'][tsindex]['value']
                        tdfx = txtdf[txtdf.Timestamp == ts]
                        ''' Add operator from text file '''
                        if len(tdfx) > 0:
                            operator = tdfx.Operatorname.iloc[0]
                        else:
                            operator = "UNKNOWN"
                    except:
                        operator = "UNKNOWN"
                    pm['ExtendedData']['Data'].append({'@name':'OPERATOR','value':operator})
                    newpmlst.append(pm)
            kmldict['kml']['Folder']['Placemark'] = newpmlst
            self.kresult = kmldict
   
    def rescale(self,kmldict = None, original="0.3",new="0.7",style="IconStyle", force = False ):
        ''' Changes the size of the icon from original to new. If force is true, set all to new '''
        kmldict = kmldict if kmldict is not None else self.kresult 
        ''' Style can be IconStyle or LabelStyle '''
        for pm in kmldict['kml']['Folder']['Placemark']:
            if force or pm['Style'][style]['scale'] == original:
                pm['Style'][style]['scale'] = new
        self.kresult = kmldict
        return kmldict
    
    def inflate(self,key = "RSRP",type=int, kmldict = None, min=0.1, max=1.2,style="IconStyle" ):
        ''' Changes the size of the icon based on value of the key '''
        kmldict = kmldict if kmldict is not None else self.kresult
        ''' Style must be IconStyle '''
        style = 'IconStyle'
        threshold = 200
        siglevlst = []
        tdfx = self.getDataKeyValue(key,kmldict=kmldict)
        tdfx['fvalue'] = tdfx[key].map(lambda xx: int(xx.replace("-","").replace(" dBm","")) 
                                        if xx is not None else xx)
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
        ''' Filters out Placemarks if the name starts with -200 (no signal) '''
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
        ''' Filters the Placemark based on ExtendedData/Data @name and value; filterin picks between keeping or dropping '''
        kmldict = kmldict if kmldict is not None else self.kresult
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
        ''' Replaces the ExtendedData dictionaries with the contents of extdatalst '''
        kmldict = kmldict if kmldict is not None else self.kresult
        newpmlst = []
        for ii, pm in enumerate(kmldict['kml']['Folder']['Placemark']):
            pm['ExtendedData']['Data'] = extdatalst[ii]
            newpmlst.append(pm)
        kmldict['kml']['Folder']['Placemark'] = newpmlst
        self.kresult = kmldict
        return kmldict

    def getDataKeyValue(self,key,kmldict=None):
        ''' Returns 1-column DataFrame with the values for the key '''
        kmldict = kmldict if kmldict is not None else self.kresult
        # self.result['kml']['Folder']['Placemark'][0]['ExtendedData']['Data'].append({'@name':'OPERATOR','value':'314737'})
        matchlst = []
        for pm in kmldict['kml']['Folder']['Placemark']:
            foundmatch = False
            for edata in pm['ExtendedData']['Data']:
                if edata['@name'] == key:
                    foundmatch = True
                    matchlst.append(edata['value'])
                    continue                   
            if not foundmatch:
                matchlst.append(None)
        return pd.DataFrame(matchlst,columns=[key])
    
    def getDataKeyValueDF(self,key,extralst):
        for edata in extralst['Data']:
            if edata['@name'] == key:
                return edata['value']
        return None
    ''' KML to DF Utilities '''
    def kmlToDF(self, kmldict = None,filename=None):
        kmldict = kmldict if kmldict is not None else self.kresult
        fdf = pd.DataFrame(kmldict['kml']['Folder']['Placemark'])
        fdf = self.getEDataFields(fdf)
        fdf = self.getStyleFields(fdf)
        fdf = self.getStyleFields(fdf)
        fdf = self.getCoordinates(fdf)
        fdf = drp_lst(fdf,['ExtendedData','Style','Point'])
        if filename is not None:
            writejoin(fdf.set_index('TIME'),"",filename)
        return fdf
    
    def getEDataFields(self,fdf):
        retdf = fdf.copy()
        edatadf = fdf.ExtendedData.map(lambda xx: xx['Data'])
        fielddf = edatadf.map(lambda xx: [subdict['@name'] for subdict in xx])
        flst = list(set(itertools.chain.from_iterable(list(fielddf))))
        for fld in flst:
           retdf[fld] = retdf.ExtendedData.map(lambda xx: self.getDataKeyValueDF(fld,xx))
        return retdf

    def getStyleFields(self, fdf):
        retdf = fdf.copy()
        retdf['LabelScale'] = fdf.Style.map(lambda xx: xx['LabelStyle']['scale'])
        retdf['IconScale'] = fdf.Style.map(lambda xx: xx['IconStyle']['scale'])
        retdf['IconColor'] = fdf.Style.map(lambda xx: xx['IconStyle']['color'])
        retdf['Icon'] = fdf.Style.map(lambda xx: xx['IconStyle']['Icon']['href'])
        return retdf
    
    def getCoordinates(self, fdf):
        retdf = fdf.copy()
        retdf[['Latitude','Longitude','Elevation']] = retdf.apply(lambda xx: xx.Point['coordinates'].split(","),  axis=1, result_type="expand")
        return retdf
    
    ''' Map and Apply Methods '''
    def parseXML(self,filedata):
        ''' Parse the KML Data into XML Dictionary '''
        fd = '\n'.join(filedata)
        if not fd.endswith("</Folder></kml>"):
            mconsole("File not properly closed")
            fd += "</Folder></kml>"
        return xmltodict.parse(fd)
    
    def addDataKeyValue(self,row,inkey=None):
        ''' Returns row (e.g., from apply) function with the value in the 
            inkey column inserted in the ExtendedData dictionary '''
        val = row[inkey]
        # print(row.ExtendedData)
        # print(val)
        exists = False
        for ii,item in enumerate(row.ExtendedData['Data']):
            if item['@name'] == inkey:
                row.ExtendedData['Data'][ii]['value'] = val
                exists = True
        if not exists:
            row.ExtendedData['Data'].append({'@name':inkey,'value':val})
        # print(row.ExtendedData)
        return row

    ''' General Methods '''
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

if __name__ == '__main__': main()