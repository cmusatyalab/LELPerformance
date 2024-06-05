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
sudo ip -n ${NS} addr del ${IP}/32 dev ${IFC}
sudo ip netns exec ${NS} sysctl net.ipv4.ip_forward=0
sudo ip netns exec ${NS} sysctl net.ipv4.conf.${IFC}.forwarding=0
sudo ip netns exec ${NS} iptables -t nat -D POSTROUTING -s ${IP} -j MASQUERADE
sudo ip netns exec ${NS} ip addr del 127.0.0.1/8 dev lo
sudo ip netns exec ${NS} ip route del default via ${GW} dev ${IFC} proto dhcp src ${IP} metric 100
sudo ip netns del ${NS}


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