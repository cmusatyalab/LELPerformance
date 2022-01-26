"""
Routines to compute the latency of each segment from the stored DB values
"""
from influxdb import InfluxDBClient
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import time

# Hardcode cloudlet IP and port for DB
CLOUDLET_IP = '128.2.208.248'
CLOUDLET_PORT = 8086

CLOUDLET_ICMP_DB = 'cloudleticmp'
WATERSPOUT_ICMP_DB = 'waterspouticmp'
UE_ICMP_DB = 'ueicmp'

cloudlet_icmp_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=CLOUDLET_ICMP_DB)
waterspout_icmp_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=WATERSPOUT_ICMP_DB)
ue_icmp_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=UE_ICMP_DB)

def retrieve_timestamp(client, src, dst, limit, is_ue, timestamp=None):
    if timestamp is not None:
      query = "SELECT src, dst, data_time, identifier, epoch FROM latency WHERE time > '%s' ORDER BY time DESC LIMIT %s" % (timestamp, limit)
    else: 
      query = "SELECT src, dst, data_time, identifier, epoch FROM latency ORDER BY time DESC LIMIT %s" % (limit)

    entries = client.query(query).get_points()

    uplink_values = []
    downlink_values = []

    # Note that the query occurs in reverse order
    for entry in entries:

      if (is_ue):
        # Changing UE src destination so disregard that value
        if (entry['dst'] == dst):
          uplink_values.append([entry['data_time'], entry['identifier'], (entry['epoch'] * 1000), entry['time']])

        if (entry['src'] == dst):
          downlink_values.append([entry['data_time'], entry['identifier'], (entry['epoch'] * 1000), entry['time']])
      
      else:
        if (entry['src'] == src) and (entry['dst'] == dst):
          uplink_values.append([entry['data_time'], entry['identifier'], (entry['epoch'] * 1000), entry['time']])

        if (entry['src'] == dst) and (entry['dst'] == src):
          downlink_values.append([entry['data_time'], entry['identifier'], (entry['epoch'] * 1000), entry['time']])
      
    return (uplink_values, downlink_values)


def join_timestamps(cloudlet_measurements, xran_measurements, epc_measurements, ue_measurements):
    # Extract uplink, downlink dataframes from input tuples and convert into dataframes

    cloudlet_uplink_df = pd.DataFrame(cloudlet_measurements[0], columns=['Data Time', 'Identifier', 'Epoch', 'Time'])
    cloudlet_uplink_df.drop_duplicates(inplace=True, keep='first', subset=['Data Time', 'Identifier'])
    cloudlet_downlink_df = pd.DataFrame(cloudlet_measurements[1], columns=['Data Time', 'Identifier', 'Epoch', 'Time'])
    cloudlet_downlink_df.drop_duplicates(inplace=True, keep='first', subset=['Data Time','Identifier'])

    xran_uplink_df = pd.DataFrame(xran_measurements[0], columns=['Data Time', 'Identifier', 'Epoch', 'Time'])
    xran_uplink_df.drop_duplicates(inplace=True, keep='first', subset=['Data Time', 'Identifier'])
    xran_downlink_df = pd.DataFrame(xran_measurements[1], columns=['Data Time', 'Identifier', 'Epoch', 'Time'])
    xran_downlink_df.drop_duplicates(inplace=True, keep='first', subset=['Data Time','Identifier'])

    epc_uplink_df = pd.DataFrame(epc_measurements[0], columns=['Data Time', 'Identifier', 'Epoch', 'Time'])
    epc_uplink_df.drop_duplicates(inplace=True, keep='first', subset=['Data Time','Identifier'])
    epc_downlink_df = pd.DataFrame(epc_measurements[1], columns=['Data Time', 'Identifier', 'Epoch', 'Time'])
    epc_downlink_df.drop_duplicates(inplace=True, keep='first', subset=['Data Time', 'Identifier'])

    ue_uplink_df = pd.DataFrame(ue_measurements[0], columns=['Data Time', 'Identifier', 'Epoch', 'Time'])
    ue_uplink_df.drop_duplicates(inplace=True, keep='first', subset=['Data Time','Identifier'])
    ue_downlink_df = pd.DataFrame(ue_measurements[1], columns=['Data Time', 'Identifier', 'Epoch', 'Time'])
    ue_downlink_df.drop_duplicates(inplace=True, keep='first', subset=['Data Time', 'Identifier'])

    xran_epc_uplink_df = pd.merge(
        left=xran_uplink_df, right=epc_uplink_df, how='inner', on=['Data Time', 'Identifier']
    )

    xran_epc_cloudlet_df = pd.merge(
        left=xran_epc_uplink_df, right=cloudlet_uplink_df, how='inner', on=['Data Time', 'Identifier']
    )

    xran_epc_cloudlet_df.rename(
        columns={"Epoch_x":"xran_time", "Epoch_y":"epc_time", "Epoch":"cloudlet_time", "Time_x":"xran_timestamp", "Time_y":"epc_timestamp", "Time":"cloudlet_timestamp"}, 
        inplace=True
    )

    # Join with the UE DB
    uplink_df = pd.merge(
        left=ue_uplink_df, right=xran_epc_cloudlet_df, how='inner', on=['Data Time', 'Identifier']
    )

    uplink_df.rename(columns={"Epoch":"ue_time"}, inplace=True)
    uplink_segments = pd.concat([(uplink_df['xran_time'] - uplink_df['ue_time']), (uplink_df['epc_time'] - uplink_df['xran_time']), (uplink_df['cloudlet_time'] - uplink_df['epc_time'])], axis=1, keys=['ue_xran', 'xran_epc', 'epc_cloudlet'])

    xran_epc_downlink_df = pd.merge(
        left=xran_downlink_df, right=epc_downlink_df, how='inner', on=['Data Time', 'Identifier']
    )

    xran_epc_cloudlet_downlink_df = pd.merge(
        left=xran_epc_downlink_df, right=cloudlet_downlink_df, how='inner', on=['Data Time', 'Identifier']
    )

    xran_epc_cloudlet_downlink_df.rename(
        columns={"Epoch_x":"xran_time", "Epoch_y":"epc_time", "Epoch":"cloudlet_time", "Time_x":"xran_timestamp", "Time_y":"epc_timestamp", "Time":"cloudlet_timestamp"}, 
        inplace=True
    )

    # Join with the UE DB
    downlink_df = pd.merge(
        left=ue_downlink_df, right=xran_epc_cloudlet_downlink_df, how='inner', on=['Data Time', 'Identifier']
    )

    downlink_df.rename(
        columns={"Epoch":"ue_time"}, inplace=True
    )

    downlink_segments = pd.concat([(downlink_df['ue_time'] - downlink_df['xran_time']), (downlink_df['xran_time'] - downlink_df['epc_time']), (downlink_df['epc_time'] - downlink_df['cloudlet_time'])], axis=1, keys=['ue_xran', 'xran_epc', 'epc_cloudlet'])

    # Update the timestamps to query based on latest downlink timestamps
    cloudlet_timestamp_retrieved = downlink_df['cloudlet_timestamp'].max()
    xran_timestamp_retrieved = downlink_df['xran_timestamp'].max()
    epc_timestamp_retrieved = downlink_df['epc_timestamp'].max()
    ue_timestamp_retrieved = downlink_df['Time'].max()

    return uplink_segments, downlink_segments, (cloudlet_timestamp_retrieved, xran_timestamp_retrieved, epc_timestamp_retrieved, ue_timestamp_retrieved)

# Create client to be used for writing to segmentation DB
SEGMENTATION_DB = 'segmentation'
segmentation_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=SEGMENTATION_DB)
segmentation_client.alter_retention_policy("autogen", database=SEGMENTATION_DB, duration="30d", default=True)

def upload_measurements(df, is_uplink):
  packets = []
  count = 0
  for _, row in df.iterrows():
  
    # Create new entry to write to segmentation database
    if (is_uplink):
      pkt_entry = {"measurement":"uplink", "fields":{"ue_xran": row['ue_xran'], "xran_epc": row['xran_epc'], "epc_cloudlet": row['epc_cloudlet']}}
    else:
      pkt_entry = {"measurement":"downlink", "fields":{"ue_xran": row['ue_xran'], "xran_epc": row['xran_epc'], "epc_cloudlet": row['epc_cloudlet']}}


    # Handle potential synchronization error 
    if (row['ue_xran'] < 0) or (row['xran_epc'] < 0) or (row['epc_cloudlet'] < 0):
        print("Potential synchronization error. Segment has latencies: %f %f %f" % (row['ue_xran'], row['xran_epc'], row['epc_cloudlet']))
        continue

    packets.append(pkt_entry)
    print(count)
    segmentation_client.write_points(packets)
    packets.clear()

    count += 1

cloudlet_timestamp = None
xran_timestamp = None
epc_timestamp = None
ue_timestamp = None

while (True):
    cloudlet_measurements = retrieve_timestamp(cloudlet_icmp_client, '128.2.212.53', '128.2.208.248', 2000, False, cloudlet_timestamp)
    xran_measurements = retrieve_timestamp(waterspout_icmp_client, '192.168.25.2', '192.168.25.4', 2000, False, xran_timestamp)
    epc_measurements = retrieve_timestamp(waterspout_icmp_client, '192.168.25.4', '128.2.208.248', 2000, False, epc_timestamp)
    
    # Irrelevant what we specify for UE src address (filtered out since changes each session)
    ue_measurements = retrieve_timestamp(ue_icmp_client, '192.168.25.57', '128.2.208.248', 2000, True, ue_timestamp)

    uplink_segments, downlink_segments, timestamps = join_timestamps(cloudlet_measurements, xran_measurements, epc_measurements, ue_measurements)

    # Set the timestamps to updated values (if join was successful)
    if (len(downlink_segments) > 0):
      cloudlet_timestamp = timestamps[0]
      xran_timestamp = timestamps[1]
      epc_timestamp = timestamps[2]
      ue_timestamp = timestamps[3]

    print(len(uplink_segments))
    print(len(downlink_segments))

    # Upload results to segmentation database
    upload_measurements(uplink_segments, True)
    upload_measurements(downlink_segments, False)

    time.sleep(5)