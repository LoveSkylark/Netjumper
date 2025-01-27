#!/bin/bash




# Install network tools
sudo apt update
sudo apt install -y mtr tcpdump iperf nmap dnsutils arp-scan whois netcat

# Install Python-related packages
sudo apt install -y python-is-python3 python3-pip python3-dotenv

# Install Python packages using pip
sudo pip install certifi python-hosts graphviz dotenv


mkdir -p /data/scripts
sudo git clone https://github.com/LoveSkylark/Netjumper.git /data/scripts/

mkdir -p /data/scripts/Libs/LibreNMSAPIClient
sudo git clone https://github.com/electrocret/LibreNMSAPIClient.git /data/scripts/Libs/LibreNMSAPIClient
#
# from Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient
#


