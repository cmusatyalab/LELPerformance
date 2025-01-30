#!/usr/bin/env python3
from DIGIPythonHandler import DIGIPythonHandler
import digidevice

from time import sleep
rpt = 10
slp = 5

def main():
    dh = DIGIPythonHandler()
    for ii in range(0,rpt):
        currsim = dh.getCurrentSIM(output=True)
        print(f"Running on {currsim[1]}")
        if currsim[0] == "2":
            modemstat,stdoutclean = dh.getModemStatus(output=False)
            sendDataPoint(dh,currsim[0],f"{ii}/{modemstat}")
            connected = dh.waitForConnect(output=False)
            bconnected = 1 if connected else 0
            sendDataPoint(dh,currsim[0],f"{ii}/{modemstat}")
            if not connected: dh.toggleSIM()
        elif currsim[0] == "1":
            modemstat,stdoutclean = dh.getModemStatus(output=False)
            sendDataPoint(dh,currsim[0],f"{ii}/{modemstat}")
            dh.waitForConnect(output=False)
            sendDataPoint(dh,currsim[0],f"{ii}/{modemstat}")
            # print(modemstat)
        sleep(slp)

def sendDataPoint(dh,sim,value):
    try:
        dh.sendDIGIdatapoint(stream=f"Connection-SIM{sim}",value=value)
    except digidevice.datapoint.DataPointException:
        print("Not Connected -- Datapoint not sent")
    
if __name__ == '__main__': main()