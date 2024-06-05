from influxdb import InfluxDBClient
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Hardcode cloudlet IP and port for DB
CLOUDLET_IP = '128.2.208.248'
CLOUDLET_PORT = 8086

CLOUDLET_DB = 'experimentcloudlet'
WATERSPOUT_DB = 'experimentwaterspout'
DEVICE_DB = 'experimentdevice'

# Define clients to access each database 
cloudlet_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=CLOUDLET_DB)
waterspout_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=WATERSPOUT_DB)
device_client = InfluxDBClient(host=CLOUDLET_IP, port=CLOUDLET_PORT, database=DEVICE_DB)


def retrieve_rtts(experiment_number):
  # Retrieves the RTTs for a specific experiment

  query = "SELECT src, dst, experiment, timestamp, rtt FROM latency WHERE experiment = '%d'" % (experiment_number)
  cloudlet_entries = cloudlet_client.query(query).get_points()

  cloudlet_values = []

  # Note that the query occurs in reverse order
  for entry in cloudlet_entries:
    cloudlet_values.append([entry['timestamp'], entry['rtt']])

  xran_values = []
  epc_values = []

  waterspout_entries = waterspout_client.query(query).get_points()
  for entry in waterspout_entries:
    # Since src corresponds to who sends the ACK back
    if (entry['src'] == '192.168.25.4'):
      xran_values.append([entry['timestamp'], entry['rtt']])

    else:
      epc_values.append([entry['timestamp'], entry['rtt']])

  # Join the databases to get all non-device RTTs
  cloudlet_df = pd.DataFrame(cloudlet_values, columns=['Timestamp', 'RTT'])
  xran_df = pd.DataFrame(xran_values, columns=['Timestamp', 'RTT'])
  epc_df = pd.DataFrame(epc_values, columns=['Timestamp', 'RTT'])

  xran_epc_df = pd.merge(
      left=xran_df, right=epc_df, how='inner', on=['Timestamp']
  )

  xran_epc_cloudlet_df = pd.merge(
      left=xran_epc_df, right=cloudlet_df, how='inner', on=['Timestamp']
  )

  xran_epc_cloudlet_df.rename(
      columns={"RTT_x":"xran_rtt", "RTT_y":"epc_rtt", "RTT":"cloudlet_rtt", "Timestamp_x":"xran_timestamp", "Timestamp_y":"epc_timestamp", "Timestamp":"cloudlet_timestamp"}, 
      inplace=True
  )


  # Query the device database for experiment RTTs
  device_query = 'SELECT rtt FROM latency WHERE experiment = %d' % (experiment_number)
  device_entries = device_client.query(query).get_points()

  device_values = []

  for entry in device_entries:
    device_values.append([entry['rtt']])

  device_df = pd.DataFrame(device_values, columns=['device_rtt'])

  # Print lengths to ensure properly parsed
  print("Device %d XRAN %d EPC %d Cloudlet %d" % (len(device_df), len(xran_df), len(epc_df), len(cloudlet_df)))

  # Concatenate all values to produce final dataframe of RTTs
  rtts = pd.concat([device_df['device_rtt'] - xran_epc_cloudlet_df['xran_rtt'], xran_epc_cloudlet_df['xran_rtt'] - xran_epc_cloudlet_df['epc_rtt'], xran_epc_cloudlet_df['epc_rtt'] - xran_epc_cloudlet_df['cloudlet_rtt']], axis=1, keys=['Device RTT', 'XRAN RTT', 'EPC RTT', 'Cloudlet RTT'])
  
  return rtts

standstill_hunt = retrieve_rtts(0)
print(rtt_0.head())

standstill_gates = retrieve_rtts(3)

standstill_schenley = retrieve_rtts(8)




