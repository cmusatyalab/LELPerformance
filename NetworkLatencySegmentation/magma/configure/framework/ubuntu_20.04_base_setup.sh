#!/bin/bash

# Set up Network Latency Segmentation Base Ubuntu 20.04 Configuration
# Tested on:
#	Azure Stack VM

HOST_IP=128.2.222.37

# Add root user in cases stuff happens
sudo adduser jblake1
sudo usermod -aG sudo jblake1

# Initial Configuration
sudo apt update && sudo apt upgrade -y

# Preliminary installs
sudo apt install -y wireguard resolvconf tshark

#------------------------------------------------------------------------------------
# WIREGUARD

VPN_NUM=3
SELF_ENDPOINT=${HOST_IP}
LISTEN_PORT=5001${VPN_NUM}
SELF_PEER_LABEL="AZURE_STACK"
SELF_IP_ADDR=192.168.25.51
DNS="128.2.208.222, 8.8.8.8"
ALLOWED="$SELF_IP_ADDR/32"

PRIV_KEY_FN=wg${VPN_NUM}_private.key
PUB_KEY_FN=wg${VPN_NUM}_public.key
CONF_FN=wg${VPN_NUM}.conf
PEER_FN=wg${VPN_NUM}.peer
PWD=$(pwd)

test -d ~/wgd || mkdir ~/wgd
#	Generate a wireguard key pair
cd ~/wgd
wg genkey | sudo tee $PRIV_KEY_FN
sudo chmod go= $PRIV_KEY_FN
sudo cat $PRIV_KEY_FN | wg pubkey | sudo tee $PUB_KEY_FN
sudo cp wg${VPN_NUM}_*.key /etc/wireguard/

(echo "[Interface]
PrivateKey = $(sudo cat $PRIV_KEY_FN)
# PublicKey = $(sudo cat $PUB_KEY_FN)
Address = $SELF_IP_ADDR
ListenPort = $LISTEN_PORT
SaveConfig = true
DNS = $DNS") > ${CONF_FN}

(echo "[Peer]
PublicKey = $(sudo cat $PUB_KEY_FN)
AllowedIPs = $ALLOWED
Endpoint = $SELF_ENDPOINT:$LISTEN_PORT") > ${PEER_FN}

# Add peer file to other peers and other peers to conf file
# Stop wireguard before changing config -- else overwritten

sudo cp $CONF_FN /etc/wireguard
sudo systemctl enable wg-quick@wg${VPN_NUM}.service # Server Only
sudo systemctl start wg-quick@wg${VPN_NUM}.service # Server Only
sudo wg-quick up wg${VPN_NUM}
sudo wg show

# ---------------------------------------------------------------------------------------------

