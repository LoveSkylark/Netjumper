#!/usr/bin/python3


import os
import logging
import requests
import certifi
import pprint
import json
from dotenv import load_dotenv
from dictdiffer import diff
import pprint
from logging.handlers import RotatingFileHandler

import pynetbox
from  Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient

def connect_to_netbox(netbox_url=None, api_token=None):
    if api_token is None and netbox_url is None:
            load_dotenv()
            netbox_url = os.environ['Netbox_URL']
            api_token = os.environ['Netbox__APIToken']
    return(pynetbox.api(url=netbox_url, token=api_token))

lnms = LibreNMSAPIClient()
nb = connect_to_netbox()
nb.http_session.verify = False



# making log file
log_dir = os.environ['log_dir']
if not os.path.exists(log_dir): 
    os.makedirs(log_dir)

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

# file location
output_dir = os.environ['info_dir']
if not os.path.exists(output_dir): 
    os.makedirs(output_dir)

def get_normalized_librenms() -> dict:
    result = {}
    for device in lnms.list_devices():
        name = str(device["sysName"]).split(".")[0]
        name = name.casefold()
        result[name] = {
                    "full_name": device["sysName"],
                    #"libre_id": device["device_id"],
                    "mgmt_ip": device["hostname"],
                    "platform_type": device["hardware"],
                    "serial": device["serial"],
                    "site": device["location"],
                    "device_type": (
                        "router" if device["sysName"].startswith("cr") else "switch"
                    ),
        }
    return result

def get_normalized_netbox() -> dict:
    result = {}
    for device in nb.dcim.devices.all():
        name = str(device.name).split(".")[0]
        name = name.casefold()
        mgmt_ip = ""
        result[name] = {
            "full_name": device.name,
            #"netbox_id": device.id,
            "mgmt_ip": (str(device.primary_ip).split("/")[0] if device.primary_ip is not None else None),
            "platform_type": device.device_type.model if device.device_type is not None else None,
            "serial": device.serial,
            "site": device.site.name if device.site is not None else None,
            "device_type": device.device_role.name.casefold() if device.device_role is not None else None,
        }
    return result

# Body
ldevices = get_normalized_librenms()
ndevices = get_normalized_netbox()

print(ldevices)

# missing_info_in_netbox = list(diff(first=ndevices, second=ldevices))

# missing_info_in_librenms = list(diff(first=ldevices, second=ndevices))



# def get_value_mismatch(_source, _value):
#     wrong_names = [change for change in _source if _value in change[1]]
#     for i in wrong_names:
#        print (i)

#     template = "{0:25} {1:25} {2:25}"
#     output_lines = []
#     output_lines.append(template.format("Device", "Netbox", "LibreNMS"))
#     output_lines.append(template.format("-------------", "-------------", "-------------"))
#     for name in wrong_names:
#         output_lines.append(template.format(str(name[1].split('.')[0]), str(name[2][0]), str(name[2][1])))

#     return "\n".join(output_lines)


# formatted_output = get_value_mismatch(missing_info_in_librenms, ".serial")
# print(formatted_output)

