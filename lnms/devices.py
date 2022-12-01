#!/usr/bin/python

import json
import certifi
import logging
import subprocess
from logging.handlers import RotatingFileHandler
import configparser
from python_hosts import Hosts, HostsEntry
from lnmsAPI import LibreNMSAPI

config = configparser.ConfigParser()
config.read('config.ini')

lnms_api      = config['librenms']['api_host']
lnms_token    = config['librenms']['api_token']
log_file      = config['other']['log_file']
file_path     = config['other']['file_path']
hosts_dir     = config['other']['hosts_dir']

logging.basicConfig (
    level = logging.INFO,
    format = "%(asctime)s:%(levelname)s - %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
    handlers = [
        RotatingFileHandler(
        log_file,
        maxBytes = 5*1024*1024,
        backupCount = 10
        )
    ]
)

# Connect API

lnms = LibreNMSAPI(
    access_token = lnms_token, 
    base_url= lnms_api+"/api/v0"
)

# GET device list from Librenms
def get_data_list():
    response = []
    host = []
    ip = []
    for i in lnms.devices.all():
        host = (getattr(i, 'sysName'))
        ip = (getattr(i, 'hostname'))
        response.append((host ,ip))
    return response

# ADD device list to hosts
def add_devices_to_hosts(data, path=hosts_dir):
    hosts = Hosts(path=path)
    for i in data:
        new_entry = HostsEntry(entry_type='ipv4', address=i[1], names=[i[0]])
        hosts.add([new_entry])
        hosts.write()
    return

# ADD device list to autocomplete
def create_autocomplete_list(data):
    device_list = []
    for i in data:
        device_list.append(i[0])
    return (' '.join(device_list))

# REMOVE host by IP
def remove_ip_from_hosts(ip, path=hosts_dir):
    host = Hosts(path=path)
    host.remove_all_matching(address=ip)

# REMOVE host by name
def remove_ip_from_hosts(name, path=hosts_dir):
    host = Hosts(path=path)
    host.remove_all_matching(name=name)


lnms_devices = get_data_list()

add_devices_to_hosts(lnms_devices)
add_devices_to_hosts(lnms_devices, 'hosts.new')

