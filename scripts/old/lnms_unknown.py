#!/usr/bin/python

"""
This code will return a pdf file that represents the data of our network,
automatically generated from cdp & lldp data.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import argparse
from Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient
import graphviz
import csv

lnms = LibreNMSAPIClient()
devices = lnms.list_devices()
links = lnms.list_links()
ports = lnms.get_all_ports()


# making log file
log_dir = os.environ['log_dir']
if not os.path.exists(log_dir): 
    os.makedirs(log_dir)

def get_argument(index):
    if len(sys.argv) > index:
        return sys.argv[index]
    else:
        return None

log_file = log_dir + "librenms_config_downloader.log"

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



def get_a_list_of_unknow_neighbours(_devices, _links):
    reply = []
    remote_match =[]
    local_match = [i['sysName'].lower().split('.', 1)[0] for i in _devices if isinstance(i, dict)]
    
    for value in _links:
        if isinstance(value, dict):
            remote_list = value['remote_hostname']
            try:
                start_index = remote_list.index("(")
                end_index = remote_list.rindex(")")
                remote_list = remote_list[:start_index] + remote_list[end_index + 1:]
            except:
                pass
            remote_match.append(remote_list.lower().split('.', 1)[0])
    
    for value in sorted(list(set(remote_match))):
        if value not in local_match:
            reply.append(value)

    return(reply)

def get_device_name_by_id(device_id):
    for device in devices:
        if device['device_id'] == device_id:
            return(device['sysName'])

def get_port_by_id(port_id):
    for port in ports:
        if port['port_id'] == port_id:
            return(port['ifName'])

def get_sorted_port_list():
    reply = []
    for value in links:
        if get_argument(1) in value['remote_hostname']:
            reply.append((
                value['remote_hostname'].split('.', 1)[0], 
                get_device_name_by_id(value['local_device_id']), 
                get_port_by_id(value['local_port_id'])
            ))
    reply = list(set(reply))
    reply = [list(item) for item in reply]
    return reply

def print_help():
    if not get_argument(1):
        print()
        print("Add hostname to narrow list")
        print("Examples:")
        print("     ./lnms_unknown 'partial-or-full-hostname'")


neighbour = get_a_list_of_unknow_neighbours(devices, links)

for value in neighbour:
    if not get_argument(1):
        print(value)
    elif value == get_argument(1):
        for i in get_sorted_port_list():
            print(f"{i[0]} --> {i[1]} ({i[2]})")
    elif value.startswith(get_argument(1)):
        print(value)
    
print_help()

