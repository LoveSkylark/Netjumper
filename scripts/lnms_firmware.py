#!/usr/bin/python3

import os
import sys
from Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient

def get_argument(index):
    if len(sys.argv) > index:
        return sys.argv[index]
    else:
        return None

def group_devices_by_hardware_version(_device):
    # Group devices by hardware type, then by version, 
    # and sort IP addresses within each group
    result = {}
    for device in _device:
        if device['hardware'] != None:
            hardware = device['hardware'].replace(" ", "_").replace("/", "_")
            version = device['version']
            ip = device['hostname']
            status = device['status']
            if hardware not in result:
                result[hardware] = {}
            if version not in result[hardware]:
                result[hardware][version] = []
            if not device['status']:
                ip = f"#{ip}"
            result[hardware][version].append(ip)
    return result

def save_devices_to_files(_list):
    for hardware, version_dict in sorted(_list.items()):
        filename = hardware.replace(" ", "_").replace("/", "_")
        f=open(output_dir + "list_firmware/" + filename + ".txt","w")
        for version, ip_list in sorted(version_dict.items()):
            f.write(f"> {version}\n")
            for ip in sorted(ip_list):
                f.write(f"  {ip}\n")
        f.close()

def print_device_list(_list):
    for hardware, version_dict in sorted(_list.items()):
        if not get_argument(1) or get_argument(1) == hardware:
            print(hardware)
            if get_argument(1):
                for version, ip_list in sorted(version_dict.items(), reverse=True):
                    if not get_argument(2):
                        print("  ", version)
                        for ip in sorted(ip_list):
                            print("    ",ip)
                    else:
                        for ip in sorted(ip_list):
                            if version <= get_argument(2):
                                print(ip)

def print_help():
    if not get_argument(2):
        print()
        print("Add model name and serial number to narrow list")
        print("Examples:")
        [print("     ./lnms_firmware WS-C4500X-32") if not get_argument(1) else None]
        print("     ./lnms_firmware WS-C4500X-32 03.11")

# API connect to LibreNMS & get device list
lnms = LibreNMSAPIClient()
lnms_devices = lnms.list_devices()

# File location
output_dir = os.environ['info_dir']
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
if not os.path.exists(f"{output_dir}/list_firmware"):
    os.makedirs(f"{output_dir}/list_firmware")

lnms_list = group_devices_by_hardware_version(lnms_devices)

save_devices_to_files(lnms_list)

print_device_list(lnms_list)

print_help()
