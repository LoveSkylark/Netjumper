#!/usr/bin/python3

# This Script Gather infromation need for device list

import logging
from logging.handlers import RotatingFileHandler

from  Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient
import os

lnms = LibreNMSAPIClient()

# mmaking file location

from logging.handlers import RotatingFileHandler

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


def make_device_list(name):
    f=open(output_dir + name,"w")
    try:
        f.write("NAME, IP, HARDWARE, VERSION, SERIAL"+"\n")
        for device in lnms.list_devices():
            device['short_name'] = device['sysName'].split(".")[0]
            logging.info(f"device added to list: {device['short_name']}")
            if device['serial'] == None:
                logging.warning(f"Unable to get serialnumber from {device['short_name']}")
            f.write(f"{device['short_name']}, {device['hostname']}, {device['hardware']}, {device['version']}, {device['serial']}"+"\n")
        f.close()
    except:
        print("fail")


devices_w_serial = []
_devices_wo_serial = []
try:
    for device in lnms.list_devices():
        device['short_name'] = device['sysName'].split(".")[0]
        if device['serial'] != None:
            devices_w_serial.append(device)
        else: 
            _devices_wo_serial.append(device)
except:
    print("fail")


print("\n"+"Devices with a serial number:")
for device in devices_w_serial:
    print(f"  {device['short_name']}  S:{device['serial']}")

# print("\n"+"Devices without a serial number:")
# for device in devices_w_serial:
#     print(f"  {device['short_name']} ({device['hostname']})")




make_device_list("device-list.csv")

print("\n"+f"Done, detailed list can be found under: ./{output_dir}"+"\n")
