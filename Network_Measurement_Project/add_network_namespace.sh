#!/bin/bash
test -z "$1" && NS="CBRS" || NS="$1"

if [ "$NS" == "CBRS" ]
then
	NS=CBRS
	IFC=enx0016083656d3
	IP=192.168.128.88
	GW=$IP
else
	NS=TMOB
	IFC=enx0050b623c78d
	IP=192.168.0.57
	GW=$IP
fi
# sudo ip netns del ${NS}
sudo ip netns add ${NS}                                                                              
sudo ip link set dev ${IFC} netns ${NS}                                                     
sudo ip -n ${NS} link set dev ${IFC} up
sudo ip -n ${NS} addr add ${IP} dev ${IFC}
sudo ip netns exec ${NS} sysctl net.ipv4.ip_forward=1
sudo ip netns exec ${NS} sysctl net.ipv4.conf.${IFC}.forwarding=1
sudo ip netns exec ${NS} iptables -t nat -A POSTROUTING -s ${IP} -j MASQUERADE
sudo ip netns exec ${NS} ip addr add 127.0.0.1/8 dev lo
sudo ip netns exec ${NS} ip route add default via ${GW} dev ${IFC} proto dhcp src ${IP} metric 100

# T-Mobile Namespace


# Diagnostics
# sudo ip netns exec ${NS} ping -I ${IFC} 8.8.8.8
# sudo ip netns exec ${NS} iptables -v -L -t nat
# sudo ip netns exec ${NS} ip a
# sudo ip netns exec ${NS} ip route
# sudo ip netns exec ${NS} wireshark
# sudo ip netns exec ${NS} ls /proc/sys/net/ipv4/conf/${IFC}

# Remove from namespace
# sudo ip netns exec ${NS} ip link set dev ${IFC} netns 1