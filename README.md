

# Network Latency Segmentation Project

## Introduction
This repository contains the implementation of the  [Living Edge Lab](https://www.cmu.edu/scs/edgecomputing/index.html)  Network Latency Segmentation project by Sophie Smith and Ishan Darwhekar in the CMU Mobile and Pervasive Computing 15-821/18-843 course. The project was mentored by Jim Blakley. The video and poster for the project are [here](https://www.cs.cmu.edu/~15-821/archive/#2021). A CMU Technical Report, *"Segmenting Latency in a Private 4G LTE Network"*, is available here<link when published>. This work and the code associated with it are very specific to the network used. As a result, this code will not be directly useable on other networks without modifications.

The aim of this project is to determine the latency of each segment in the round-trip path of the [Living Edge Lab](https://www.cmu.edu/scs/edgecomputing/index.html) network. To determine segment latency, we inserted probes into the network at the User Equipment (UE aka *laptop*), XRAN, EPC and the Cloudlet. Probes between the XRAN, EPC and Cloudlet were captured by an **Intra-CN** server, *"waterspout"*, that mirrored the ports between the systems.

The `processing` folder contains scripts to run for real-time segment latency analysis. The `preprocessing` folder contains the scripts used to collect and store latency measurements for preliminary experiments to analyze the effect of different factors on the segment latency. 

## Collecting Latency Measurements
We receive and inspect each incoming packet using [Pyshark](https://github.com/KimiNewt/pyshark), a Python wrapper for Wireshark. From this, we can extract fields necessary to correlate packets at each probe. 

We use the source and destination IP addresses to identify whether the packet is uplink or downlink and to determine which segment (UE-XRAN, XRAN-EPC, EPC-Cloudlet) they correspond to. To correlate ICMP data, we use the sequence number, ICMP identifier and ICMP timestamp. To correlate the TCP data, we use the sequence number, TCP timestamp and acknowledgement number We use the differences in epoch time to calculate the segment latency. 

The scripts `cloudlet_measure.py`, `laptop_measure.py` and `waterspout_measure.py` handle extracting and storing these fields in an InfluxDB database. To run these scripts, run these commands on the Cloudlet, Waterspout, and the UE respectively:

```
sudo tcpdump -s 0 -U -w - -i enp179s0f1 | python3 cloudlet_measure.py

sudo tcpdump -s 0 -U -w - -i eno1 | python3 waterspout_measure.py

sudo tcpdump -s 0 -U -w - -i enx0016083656d3 | python3 laptop_measure.py
```

The interface names will be specific to the network used. They can be obtained with the `ip a` command on linux systems. We used a Multitech USB dongle to connect the laptop to our CBRS network. Configuring that dongle on Linux required adding it to the `netplan` configuration. (See the dongle.cfg file for more details.)

Note that adding ```not tcp and not sctp``` to the *tcpdump* command helps to filter out the overwhelming amount of  TCP and SCTP traffic that is spurious if you're only interested in ICMP ping data.

To monitor from within the XRAN server itself, you'd need xran credentials. For our xran,

```
sshpass -p <XRANIP> ssh <XRANLOGIN>@<XRANIP> "sudo tcpdump -s 0 -U -w - -i any not port 22" | python xran_measure.py
```

## Latency Segmentation Calculations
We use the `query_measurements.py` script to calculate segment latency from extracted fields for each probe and upload them to a separate database. The commands to run this script are: 

```
python3 query_measurements.py 
```

## InfluxDB

To store all values above, InfluxDB must be running on the Cloudlet. The Cloudlet is the location where all databases are stored. To run InfluxDB, run the following command on the Cloudlet:

```
docker run -it -p 8086:8086 -p 8088:8088 -v influxdb:/var/lib/influxdb influxdb:1.8
```

However, if your cloudlet does not run continuously, you may want to run influxdb natively on the cloudlet to avoid loss of data.

```
sudo apt install influxdb
sudo systemctl start influxdb
sudo systemctl enable influxdb
```
There are two utilities for managing the databases, `cleanDBs.py` for selectively or completely deleting the data, and `backupDBs.py` which will create a backup of the full database and export the data as `.csv` files.

## Grafana Dashboard
To enable the grafana dashboard, grafana must be running on the Cloudlet. To run Grafana, run the following command on the Cloudlet:

```
docker run -d -p 3000:3000 grafana/grafana-enterprise
```
Connect to grafana at http://localhost:3000/, login with admin, pw=admin, and import processing `dashboard.json` or one of the other dashboards in the grafana folder. Within grafana, add a datasource for InfluxDB. In the datasource, use the IP or domain name of the Cloudlet, not *localhost*. Now, edit each of the panels in the dashboard to use that datasource. Even though the InfluxDB datasource is the default in the imported json, you need to reconnect the datasource to the dashboard for it to access the data.

An example of the *Network Latency Segmentation Summary* dashboard is below.
![dashboard](grafana/DashboardScreenshot.png)

# Synchronization
To provide accurate segmentation all timing elements -- UE (laptop), Intra-CN Probe (waterspout) and the cloudlet -- must be synchronized to the same timing source. We used an NTP timing source within our lab to synchronize the UE and Intra-CN Probe. The cloudlet was synced using a PTP server on the same clock as the NTP source.

We used `chrony` on the UE for synchronization and for measuring offsets between UE and the other elements. To run the offset measurement collector on the UE:
``` 
python3 laptop_offset.py
```

We did not have success running the synchronization setup on a Windows UE (either with `chrony` or `w32tm /stripchart`). 

# OpenRTiST

To run experiments with OpenRTiST (https://github.com/cmusatyalab/openrtist), for TCP measurements, run the following command on the cloudlet:

```
docker run --rm -it -p 9099:9099 cmusatyalab/openrtist:stable
```
