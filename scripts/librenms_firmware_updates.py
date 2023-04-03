#!/usr/bin/python3

# This Script Gather infromation need for device list

import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from  Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient

lnms = LibreNMSAPIClient()

# mmaking file location
log_dir = os.environ['log_dir']
if not os.path.exists(log_dir): 
    os.makedirs(log_dir)

log_file = log_dir + "librenms_device_inventory.log"

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

# file location
output_dir = os.environ['info_dir']
if not os.path.exists(output_dir): 
    os.makedirs(output_dir)

#API connect to LibreNMS
lnms = LibreNMSAPIClient()

def get_list(_value, _list) -> list:
    result = []
    [result.append(i[_value]) for i in _list if i[_value] not in result]
    return result

#device table
device_list = lnms.list_devices()

#list of types
list_hardware = get_list('hardware', device_list)

#list of versions?

for device in device_list:
    if device['hardware'] in list_hardware:
        print(device['sysName']," ",device['hardware']," ",device['version'])
