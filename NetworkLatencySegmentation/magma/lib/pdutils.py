#!/usr/bin/env python3
import json
import os
import shlex, subprocess
import time, datetime
import pandas as pd
import pytz


''' Data frame functions '''
def dumpdf(df, rows=5):
    print(df.shape)
    print(df.head(rows))
    print(df.dtypes)

def getColumns(fn):
    for fdf in pd.read_csv(fn, chunksize=1):
        return list(fdf.columns)
    
def getHead(fn,chunksize=5):
    for fdf in pd.read_csv(fn, chunksize=chunksize):
        return fdf

def display_all(df):
    print(df.shape)
    pd.set_option('display.max_rows',None)
    display(df)
    
def drp_unnamed(df):
    drplst = [c for c in df.columns if 'Unnamed' in c]
    return df.drop(drplst,axis=1)

def drp_lst(df,lst):
    drplst = [c for c in df.columns for col in lst if col == c]
    return df.drop(drplst,axis=1)

def renamecol(fdf,col=None,newname=None):
    return fdf.rename(columns={col:newname}) if col in fdf.columns and newname is not None else fdf

def listof(fdf, col):
    retlst = list(fdf[col].drop_duplicates().sort_values())
    return retlst

import datetime
def exceldt2datetime(fdate):
    temp = datetime.datetime(1899, 12, 30)
    delta = datetime.timedelta(days=fdate)
    rettime = (temp+delta).replace(microsecond=0)
    return rettime

# def to_ts(df,fmt):
#     import pandas as pd
#     df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'],format=fmt,errors='coerce')
#     return df

def to_ts(df,col='TIMESTAMP', origtz=None, newtz=None,**kwargs):
    if 'fmt' in kwargs: format = kwargs['fmt'] # deprecated option
    df[col] = pd.to_datetime(df[col],errors='coerce',**kwargs)
    if not origtz is None:
        df[col] = df[col].dt.tz_localize(pytz.timezone(origtz))
    if not newtz is None:
        df[col] = df[col].dt.tz_convert(pytz.timezone(newtz))    
    return df

def changeTZ(df,col='TIMESTAMP',origtz=None, newtz=None):
    import pandas as pd
    if not origtz is None:
        df[col] = df[col].dt.tz_convert(pytz.timezone(origtz))
    if not newtz is None:
        df[col] = df[col].dt.tz_convert(pytz.timezone(newtz))    
    return df

def localizeTZ(fdf,col='TIMESTAMP', newtz=None):
    if not newtz is None:
        fdf[col] = fdf[col].dt.tz_localize(pytz.timezone(newtz))    
    return fdf

def getMidnight(tz='America/New_York'):
    today = pd.Timestamp.today(tz=tz)
    midnight = pd.Timestamp(today.year,today.month,today.day).tz_localize(pytz.timezone(tz))
    return midnight

def print_tz(): print(pytz.all_timezones)

def to_ts_dh(df,dcol,hcol,fmt="%m/%d/%Y %H:%M"):
    import pandas as pd
    df['tmphr'] = pd.to_numeric(df[hcol],errors='coerce')
    df = df.dropna(subset=['tmphr'])
    df['tmphr'] = df['tmphr'].apply(lambda row: int(round(row))-1)
    df['dtstr'] = df.apply(lambda row: "{} {:02d}:00".format(row[dcol],row['tmphr']), axis=1)
    df['TIMESTAMP'] = pd.to_datetime(df['dtstr'],format=fmt,errors='coerce')
    return df.drop(columns=['tmphr','dtstr'])

def to_ts_dhm(idf,dcol,hcol,intcol=None, mincol=None,fmt="%m/%d/%Y %H:%M:%S"):
    df = idf.copy()
    tmphr = 'tmphr'
    if mincol is None: mincol = 'tmpmn'
    if intcol != None: df[mincol] = pd.to_numeric((df[intcol]-1) * 15,errors='coerce')
    df[tmphr] = pd.to_numeric(df[hcol]-1,errors='coerce') 
    df = df.dropna(subset=[tmphr,mincol])
    df['dtstr'] = df.apply(lambda row: "{} {:02.0f}:{:02.0f}:00".format(row[dcol],row[tmphr],row[mincol]), axis=1)
    df['TIMESTAMP'] = pd.to_datetime(df['dtstr'],format=fmt,errors='coerce')
    return df.drop(columns=[tmphr,mincol,'dtstr'])

def to_ts_std(df,**kwargs):
    return to_ts(df,format = '%Y-%m-%d %H:%M:%S',**kwargs)

def add_quarters(y,q,dq):
    dt = datetime.date(yr,qtrmap[qtr][0],1)
    ndt = dt + DateOffset(months=dq*3)
    fdf = pd.DataFrame([[dt,ndt]],columns=['TIMESTAMP','QTIMESTAMP'])
    return fdf.QTIMESTAMP.dt.quarter.iloc[0],fdf.QTIMESTAMP.dt.year.iloc[0]

def ts_matchymd(fdf,fyr,fmn,fday):
    return fdf[(fdf.TIMESTAMP.dt.year == fyr) & (fdf.TIMESTAMP.dt.month == fmn) & (fdf.TIMESTAMP.dt.day == fday)]

def ts_matchym(fdf,fyr,fmn):
    return fdf[(fdf.TIMESTAMP.dt.year == fyr) & (fdf.TIMESTAMP.dt.month == fmn)]

def time2hour(srs):
    ''' srs is series with a string datetime'''
    return pd.to_datetime(srs).apply(lambda x: x.hour).values
def time2month(srs):
    ''' srs is series with a string datetime'''
    return pd.to_datetime(srs).apply(lambda x: x.month).values

def convTS(fdf):  # InfluxDB timestamps to a pandas timestamp
    fdf = renamecol(fdf.reset_index(),col='index',newname='TIMESTAMP')
    fdf['TIMESTAMP'] = fdf['TIMESTAMP'].map(lambda cell: cell.replace(microsecond=0))
    return fdf

def epochToTS(fdf,epochcol='epoch',newtz='America/New_York',tscol = 'TIMESTAMP'):
    ''' Linux epoch in seconds to Timestamp '''
    fdf[tscol] = pd.to_datetime(fdf[epochcol],unit='s',utc=True)
    fdf = changeTZ(fdf,col=tscol,origtz='UTC', newtz=newtz)
    return fdf

def writejoin(df,dn,fn):
    df.to_csv(os.path.join(dn,fn))

def readjoin(dn,fn,**kwargs):
    ffn = os.path.join(dn,fn)
    if not os.path.isfile(ffn):
        print("%s does not exist" % ffn)
    return pd.read_csv(ffn,**kwargs)

def readjoin_ts(dn,fn):
    return to_ts_std(readjoin(dn,fn))

def indaterange(df,startdt,enddt,key):
    ''' Start and end date as string ala '2011-01-01'; key as datetime '''
    return df[(df[key] >= startdt) & (df[key] <=  enddt)]

def explodeColumn(fdf,col,colnameprepend=True,printshape=True):
    ''' Converts a column with a dictionary into columns for each key '''
    fdfx = pd.DataFrame(fdf[fdf[col].notna()][col].tolist())
    colst = fdfx.columns
    if colnameprepend:
        colst = [col + "_" + ncol for ncol in colst ]
    fdf[colst] = fdfx
    if printshape: print(fdf.shape)
    return fdf

def writePQT(epp,pdf,basefname):
#     epp.writePdfParquet(pdf,os.path.join(PARQDIR,basefname+".pqt"))
    try:
        epp.writePdfParquet(pdf,os.path.join(PARQDIR,basefname+".pqt"))
    except:
        print("Could not write parquet for: %s" % basefname)

