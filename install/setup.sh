#!/bin/bash

# Install network tools
sudo apt update
sudo apt install -y mtr tcpdump iperf nmap dnsutils arp-scan whois netcat

# Install Python
sudo apt install -y python-is-python3 python3-pip

# Install Python dependencies
sudo pip install -r /data/scripts/requirements.txt

# Clone Netjumper
mkdir -p /data/scripts
sudo git clone https://github.com/LoveSkylark/Netjumper.git /data/scripts/

# Copy environment config
cp /data/scripts/.env.example /data/scripts/.env
