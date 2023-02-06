#!/usr/bin/python

##
# update_hosts.php
#
# API LibreNMS Script to retrive the serials for all devices.
##

import json
import csv
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
    try:
        devices = lnms.devices.all()
        response = []
        host = []
        ip = []
        for i in devices:
            host = (getattr(i, 'sysName'))
            ip = (getattr(i, 'hostname'))
            response.append((host ,ip))
        return response
    except Exception as LibreNMSStatusNotOKException:
        logging.exception(LibreNMSStatusNotOKException)
        print(LibreNMSStatusNotOKException)


lnms_devices = get_data_list()

# opening the csv file in 'w+' mode
file = open('serial.csv', 'w+', newline ='')

# writing the data into the file
with file:   
    write = csv.writer(file)
    write.writerows(lnms_devices)