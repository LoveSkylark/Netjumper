#!/usr/bin/python

##
# update_hosts.php
#
# API LibreNMS Script to retrive device and add them to the host file
##

import os
import sys
import logging.handlers
from dotenv import load_dotenv
from python_hosts import Hosts, HostsEntry

from Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient

def setup_logging(log_file):

    log_dir = os.path.join('..', os.environ.get('log_dir', 'var/log/'))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, log_file)

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

# -------
def get_api_data(lnms):
    try:
        devices = lnms.list_devices()
    except Exception as e:
        logging.error(f"Error calling API: {e}")
        sys.exit(1)
        
    logging.info("API call succeeded")
    return devices

def get_data_list(devices):
    try:
        response = []
        host = []
        ip = []
        for i in devices:
            host = i['sysName'].lower().split('.', 1)[0]
            ip = i['hostname']
            response.append((host ,ip))
        return response
    except Exception as LibreNMSStatusNotOKException:
        logging.exception(LibreNMSStatusNotOKException)
        print(LibreNMSStatusNotOKException)


def add_devices_to_hosts(data, path):
    try:
        hosts = Hosts(path=path)
        for i in data:
            new_entry = HostsEntry(entry_type='ipv4', address=i[1], names=[i[0]])
            hosts.add([new_entry])
            hosts.write()
        return
    except:
        logging.exception(f'error')


def main():
    load_dotenv()
    hosts_dir = os.environ.get('hosts_dir')
    info_dir = os.environ.get('info_dir')

    # Setup logging
    log_file = "update_hosts.log"
    setup_logging(log_file)

    # Create API client
    logging.info(f'Connecting to LibreNMS')
    lnms = LibreNMSAPIClient()

    # Get data from API
    devices = get_api_data(lnms)

    # GET device list from Librenms
    logging.info(f'Gathering LibreNMS device list')
    lnms_devices = get_data_list(devices)

    # ADD device list to hosts
    logging.info(f'Adding device list to /etc/hosts')
    add_devices_to_hosts(lnms_devices, hosts_dir)

    # ADD device list to info
    host_file = os.environ['info_dir'] + "hosts.list"
    logging.info(f'Adding device list to "hosts.list"')
    add_devices_to_hosts(lnms_devices, host_file)

    # Print help text
    print("Done!")


if __name__ == "__main__":
    main()
