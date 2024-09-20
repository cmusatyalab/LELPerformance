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
        EXPDIR=os.path.join(*[DATADIR,"2024-09-18-Mill19-PTC-Coverage","LEL-UE1"])
    
    DIRCHECKLIST=[DATADIR,EXPDIR]
    for DIR in DIRCHECKLIST:
        mconsole(f"{DIR} exists") if os.path.isdir(DIR) else print(f"{DIR} does not exist")
    
    kmltask = kwargs['kmltask'] 
    if kmltask == 'kmlmerge':
        ffnlst = walkDir(EXPDIR)
        rxlevfiles =  [fn for fn in ffnlst if "rxlev.kml" in fn ]
        rxlevfiles.sort()
        kmlc = KMLCombiner(rxlevfiles[:])
        newdata = kmlc.combine()
        newdata = kmlc.rescale(newdata)
        newdata = kmlc.rescale(newdata,original="0.0",new="0.7",style="LabelStyle")
        kmlc.writeKMLFile(newdata)
    if kmltask == 'txtmerge':
        ffnlst = walkDir(EXPDIR)
        txtfiles =  [fn for fn in ffnlst if fn.endswith(".txt") and not fn.startswith("Screenshot")]
        txtfiles.sort()
        txtc = KMLCombiner(txtfiles)
        newdata = txtc.combine()
        txtc.writeKMLFile(newdata)
    if kmltask == 'fullmerge':
        ffnlst = walkDir(EXPDIR)
        ''' KML Files '''
        rxlevfiles =  [fn for fn in ffnlst if "rxlev.kml" in fn ]
        rxlevfiles.sort()
        kmlc = KMLCombiner(rxlevfiles)
        newdata = kmlc.combine()
        newdata = kmlc.rescale(newdata)
        kmldata = kmlc.rescale(newdata,original="0.0",new="0.7",style="LabelStyle")
        ''' TXT Files '''
        txtfiles =  [fn for fn in ffnlst if fn.endswith(".txt") ]
        txtfiles.sort()
        txtc = KMLCombiner(txtfiles)
        txtdata = txtc.combine()
        newdata = kmlc.mergeKML_TXT(txtdata,filteroperator = "314737")
        kmlc.writeKMLFile(newdata)
        
    if kmltask == 'filereport':
        kmlc = KMLCombiner([OUTPUT_FILENAME])
        kmldicts = kmlc.getFilesDict()        
        # TODO Generate File Report
    if kmltask == 'fasttrack':
        kmlc = KMLCombiner([OUTPUT_FILENAME])
        newdata = kmlc.removeNoSignal(kmlc.getFilesDict()[0])
        kmlc.writeKMLFile(newdata)
    pass
    
class KMLCombiner(object):
    def __init__(self, filenames):
        assert len(filenames) > 0, 'No filenames!'
        self.fnames = filenames
        self.filesdata = [self.readFile(fn) for fn in filenames]
        self.result = None
        self.filesdf = None
        self.filesdict = None
        if filenames[0].endswith(".kml"):
            self.type = 'kml'
            self.filesdict = [xmltodict.parse('\n'.join(filedata)) for filedata in self.filesdata]
        elif filenames[0].endswith(".txt"):
            self.type='txt'

    def getFilesDict(self):
        return self.filesdict
    
    def getFilesDF(self):
        return self.filesdf
    
    def combine(self):
        if self.type == "kml":
            ''' Turn the kml files into dictionary '''
            retdict = self.filesdict[0]
            retdict['kml']['Folder'] = self.filesdict[1]['kml']['Folder']
            mconsole(f"{len(retdict['kml']['Folder']['Placemark'])}")
            for kdict in self.filesdict[2:]:
                retdict['kml']['Folder']['Placemark'] += kdict['kml']['Folder']['Placemark']
            mconsole(f"{len(retdict['kml']['Folder']['Placemark'])}")
            self.result = retdict
            return retdict
        elif self.type == "txt":
            ''' Turn the txt files into dataframe '''
            fdatalst = []
            columns = self.filesdata[0][0].strip("\n").split("\t")
            for fdata in self.filesdata:
                for line in fdata[1:]:
                    fdatalst.append(line.strip("\n").split("\t"))
            self.filesdf = pd.DataFrame(fdatalst, columns=columns)
            return self.filesdf
    
    def rescale(self,kmldict, original="0.3",new="0.7",style="IconStyle" ):
        ''' Style can be IconStyle or LabelStyle '''
        for pm in kmldict['kml']['Folder']['Placemark']:
            if pm['Style'][style]['scale'] == original:
                pm['Style'][style]['scale'] = new
        self.result = kmldict
        return kmldict
    
    def removeNoSignal(self,kmldict):
        pmlst = kmldict['kml']['Folder']['Placemark']
        newpmlst = []
        for pm in pmlst:
            if not pm['name'].startswith("-200"): # No Signal
                newpmlst.append(pm)
        kmldict['kml']['Folder']['Placemark'] = newpmlst
        self.result = kmldict
        return kmldict
    
    def mergeKML_TXT(self,txtdf,filteroperator = None):
        # self.result['kml']['Folder']['Placemark'][0]['ExtendedData']['Data'].append({'@name':'OPERATOR','value':'314737'})
        newpmlst = []
        kmldict = self.result
        for pm in kmldict['kml']['Folder']['Placemark']:
            # if pm['ExtendedData'][style]['scale'] == original:
                ts = pm['ExtendedData']['Data'][4]['value']
                tdfx = txtdf[txtdf.Timestamp == ts]
                if len(tdfx) > 0:
                    operator = tdfx.Operatorname.iloc[0]
                else:
                    operator = "UNKNOWN"
                if filteroperator is not None and operator != filteroperator:
                    continue
                pm['ExtendedData']['Data'].append({'@name':'OPERATOR','value':operator})
                
                newpmlst.append(pm)
        kmldict['kml']['Folder']['Placemark'] = newpmlst
        self.result = kmldict
        return kmldict

    def readFile(self,fn,prepend = False):
        lines = []
        with open(fn,"r") as f:
            lines = f.readlines()
        if prepend:
            fnlabel = os.path.basename(fn).replace(".txt","")
            lines = [f"{fnlabel}\t{line}" for line in lines]
        return lines

    def writeKMLFile(self,filedata,filename = OUTPUT_FILENAME):
        if self.type == 'kml':
            with open(filename, 'w') as f:
                    f.write(xmltodict.unparse(filedata))
        elif self.type == 'txt':
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