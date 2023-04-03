#!/usr/bin/python3
#This Script downloads all of your device configs from Oxidized.
import os
import logging
from logging.handlers import RotatingFileHandler
from  Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient


lnms = LibreNMSAPIClient()

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
output_dir = os.environ['config_dir']
if not os.path.exists(output_dir): 
    os.makedirs(output_dir)


device_hostname_sysname={}
device_config_fail={}

for device in lnms.list_devices():
    device_hostname_sysname[device['hostname']] = device['sysName']

for device in lnms.list_oxidized(): 
    dev_config=lnms.i_get_oxidized_config(device['hostname']) #Get Config from Oxidized
    output_device = device_hostname_sysname[device['hostname']].split(".")[0]
    if(len(dev_config) != 0 and dev_config != "node not found"): #Verify Valid Config
        f=open(output_dir + output_device + ".txt","w")
        f.write(dev_config)
        f.close()
        logging.info(f"Saving config from {output_device} ({device['hostname']})")
    else:
        print(f"Config missing for: {output_device}")
        logging.warning(f"Unable to get config from {output_device} ({device['hostname']})")
    
print("\n"+f"Done, configs files can be found under: ./{output_dir}"+"\n")
