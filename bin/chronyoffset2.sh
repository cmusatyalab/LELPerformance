#!/bin/bash
# Simple helper to run chrony sourcestats multiple time
NTPSERVER=$1
BATCHSIZE=$2
II=0
SLEEPTIME=1
while [ $II -lt $BATCHSIZE ]
do
	LN=$(chronyc sources|grep "$NTPSERVER")
	DT=$(date -Iseconds)
	echo "$DT $LN"
	II=$(expr $II + 1)
	sleep $SLEEPTIME
done