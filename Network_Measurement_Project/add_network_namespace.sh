#!/bin/bash
test -z "$1" && NS="LOCAL" || NS="$1"
test -z "$2" && IFC="eno2" || IFC="$2"
test -z "$3" && IP="128.2.208.222"  || IP="$3"
IPMTCHR='((1?[0-9][0-9]?|2[0-4][0-9]|25[0-5])\.){3}(1?[0-9][0-9]?|2[0-4][0-9]|25[0-5])'
GW=$(ip r|grep $IP|grep -oE "default via $IPMTCHR"|sed 's/default via //')

echo Adding NS=$NS IFC=$IFC IP=$IP GW=$GW
# GW=$IP

sudo ip netns add ${NS}                                                                              
sudo ip link set dev ${IFC} netns ${NS}                                                     
sudo ip -n ${NS} link set dev ${IFC} up
sudo ip -n ${NS} addr add ${IP}/24 dev ${IFC}
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