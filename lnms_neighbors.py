#!/usr/bin/python
import os
import logging.handlers
import argparse
from Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient

lnms = LibreNMSAPIClient()
devices = lnms.list_devices()
links = lnms.list_links()
ports = lnms.get_all_ports()

### Logger
log_dir = os.environ.get('log_dir', '/var/log/')
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, 'librenms_device_inventory.log')

logging.basicConfig(
level=logging.INFO,
format='%(asctime)s:%(levelname)s - %(message)s',
datefmt='%Y-%m-%d %H:%M:%S',
handlers=[
    logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5*1024*1024,
        backupCount=10
    )
]
)

### Parser
parser = argparse.ArgumentParser(description="Script to download LibreNMS configuration")
parser.add_argument("hostname", nargs="?", help="Hostname to filter on")
args = parser.parse_args()


def get_unknown_neighbors(devices, links):

    # Create a set of all local and remote device short names in lowercase
    local_match = set(i['sysName'].lower().split('.', 1)[0] for i in devices if isinstance(i, dict))
    remote_match = set(i['remote_hostname'].lower().split('(', 1)[0].split('.', 1)[0] for i in links if isinstance(i, dict))
    
    # Compute the set difference between the two sets to find remote hostnames that don't have a matching local device name
    reply = sorted(list(remote_match - local_match))
    
    return reply

def get_sorted_port_list(hostname):

    reply = []
    
    for link in links:

        # Check if the remote hostname of the link matches the specified hostname
        if hostname in link['remote_hostname'].lower().split('.', 1)[0]:
        
            # Retrieve the device name associated with the local device ID of the link
            device_name = next((device['sysName'] for device in devices if device['device_id'] == link['local_device_id']), None)
        
            # Retrieve the port name associated with the local port ID of the link
            port_name = next((port['ifName'] for port in ports if port['port_id'] == link['local_port_id']), None)
            reply.append((device_name, port_name))
    
    # Sort the 'reply' list by the device name in ascending order (case-insensitive)
    reply.sort(key=lambda x: x[0].lower() if x[0] else '')
    return reply

def print_unknown_neighbors():
    
    # Get the list of unknown neighbors
    neighbours = get_unknown_neighbors(devices, links)
    for neighbour in neighbours:
        logging.info(f"Neighbour {neighbour} discovered")
        # If no hostname argument is given, print all unknown neighbors
        if not args.hostname:
            print(neighbour)
                
        # If a hostname argument is given, print matching neighbors and their port information
        elif neighbour.startswith(args.hostname):
            print(neighbour)
            for device_name, port_name in get_sorted_port_list(neighbour):
                print(f"  -> {device_name} ({port_name})")

def print_help():
    if not args.hostname:
        print()
        print("Add hostname to narrow list")
        print("Examples:")
        print("     ./lnms_unknown 'partial-or-full-hostname'")

print_unknown_neighbors()
print_help()
