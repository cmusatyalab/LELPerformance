# The DIGI Gateway API Utility
This set of tools is meant to be used with a DIGI IX40 or (eventually) TX40. It has lightly tested code for the Remote Manager API, direct access to the command line, and the local interface for Python scripts on-board the device. The command line interface code is currently broken with the addition of the admin vs. shell option to support python execution. As a result, the command line code is deprecated. 

```
Access selection menu:

    a: Admin CLI
    s: Shell
    q: Quit

Select access or quit [admin] :
```
The Admin CLI is used for the command line code and for direct command line access. The Shell is used for python scripts.

The remote manager API is still functional. But, due to our expected usage, this documentation focuses on the python script access.

## Python API
For info on DIGI python API, see the IX40 user manual. Any python code should be run directly on the target device.

The  `DIGIPythonHandler.py` file contains the `DIGIPythonHandler` class which interfaces with the digidevice package. Scripts should be run from `/etc/config/scripts` which will contain and `pip install` libraries required.

The `ConnectivityManager.py` file shows an example use of the DIGIPythonHandler. This script (shown below) iteratively runs the following steps.

1. Get the current active SIM card (*1* or *2*).
2. If sim 2 is active, get the connectivity status and send a datapoint to the Remote Manager.
3. Check if sim 2 is connected. If not, wait for it, then send another datapoint.
4. If it is not connected switch to sim 1.
5. If sim 1 is active, get the connectivity status and send a datapoint to the Remote Manager.
6. Check if sim 1 is connected. If not, wait for it, then send another datapoint.
7. Sleep for 5 seconds and repeat 10 times

```
def sendDataPoint(dh,sim,value):
    try:
        dh.sendDIGIdatapoint(stream=f"Connection-SIM{sim}",value=value)
    except digidevice.datapoint.DataPointException:
        print("Not Connected -- Datapoint not sent")

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
```

The `DIGIPythonHandler` class has primitives for:
* Sending pings to an end point from the DIGI
* Getting the current SIM
* Toggling the current SIM
* Getting the current SIM status
* Waiting for the SIM to connect
* Getting and setting the DIGI settings
* Getting the DIGI system information
* Getting the DIGI config
* Searching the DIGI config
* Running a DIGI command line command
* Sending datapoints to the Remote Manager (this primitive requires the device to be network connected).

Additional primitives should be relatively easy to add from using the manual and the existing code.
