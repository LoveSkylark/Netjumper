#!/usr/bin/python
import os
import logging
from logging.handlers import RotatingFileHandler
import argparse
from Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient

lnms = LibreNMSAPIClient()
devices = lnms.list_devices()
links = lnms.list_links()
ports = lnms.get_all_ports()

log_dir = os.environ.get('log_dir', 'logs/')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, "librenms_config_downloader.log")

parser = argparse.ArgumentParser(description="Script to download LibreNMS configuration")
parser.add_argument("hostname", nargs="?", help="Hostname to filter on")
args = parser.parse_args()

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=10)
handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s - %(message)s"))
logger.addHandler(handler)

def get_unknown_neighbors(devices, links):
    # Create a set of all local and remote device names in lowercase
    local_match = set(i['sysName'].lower().split('.', 1)[0] for i in devices if isinstance(i, dict))
    remote_match = set(i['remote_hostname'].lower().split('(', 1)[0].split('.', 1)[0] for i in links if isinstance(i, dict))
    # Compute the set difference between the two sets to find remote hostnames that don't have a matching local device name
    reply = sorted(list(remote_match - local_match))
    return reply

def get_sorted_port_list(hostname):
    reply = []
    for value in links:
        # Check if the remote hostname of the link matches the specified hostname
        if hostname in value['remote_hostname'].lower().split('.', 1)[0]:
            # Retrieve the device name associated with the local device ID of the link
            device_name = next((device['sysName'] for device in devices if device['device_id'] == value['local_device_id']), None)
            # Retrieve the port name associated with the local port ID of the link
            port_name = next((port['ifName'] for port in ports if port['port_id'] == value['local_port_id']), None)
            reply.append((device_name, port_name))
    # Sort the 'reply' list by the device name in ascending order (case-insensitive)
    reply.sort(key=lambda x: x[0].lower() if x[0] else '')
    return reply

def print_help():
    if not args.hostname:
        print()
        print("Add hostname to narrow list")
        print("Examples:")
        print("     ./lnms_unknown 'partial-or-full-hostname'")

def print_unknown_neighbors():
    # Get the list of unknown neighbors
    neighbours = get_unknown_neighbors(devices, links)
    for neighbour in neighbours:
        # If no hostname argument is given, print all unknown neighbors
        if not args.hostname:
            print(neighbour)
        # If a hostname argument is given, print matching neighbors and their port information
        elif neighbour.startswith(args.hostname):
            print(neighbour)
            for device_name, port_name in get_sorted_port_list(neighbour):
                print(f"                  > {device_name} ({port_name})")

print_unknown_neighbors()
print_help()
