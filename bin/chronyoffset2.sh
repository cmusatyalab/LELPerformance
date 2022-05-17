#!/bin/bash
# Simple helper to run chrony sourcestats multiple time
NTPSERVER=$1
BATCHSIZE=$2
II=0
SLEEPTIME=1
while [ $II -lt $BATCHSIZE ]
do
	LN1=$(chronyc sources|grep "$NTPSERVER")
	LN2=$(chronyc sourcestats|grep "$NTPSERVER")
	DT=$(date -Iseconds)
	echo "$DT $LN2 $LN1"
	II=$(expr $II + 1)
	sleep $SLEEPTIME
done