#!/usr/bin/env python3
from DIGIPythonHandler import DIGIPythonHandler

rpt = 10

def main():
    dh = DIGIPythonHandler()
    for ii in range(0,rpt):
        currsim = dh.getCurrentSIM(output=True)
        print(f"Running on {currsim[1]}")
        if currsim[0] == "2":
            modemstat,stdoutclean = dh.getModemStatus()
            print(modemstat)
            connected = dh.waitForConnect(output=False)
            if not connected: 
                dh.toggleSIM()
        elif currsim[0] == "1":
            modemstat,stdoutclean = dh.getModemStatus()
            dh.waitForConnect(output=False)
            print(modemstat)
        
if __name__ == '__main__': main()