#!/usr/bin/python3

import os
import sys
import argparse
from Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient

def group_devices_by_hardware_version(_device):
    # Group devices by hardware type, then by version, 
    # and sort IP addresses within each group
    result = {}
    for device in _device:
        if device['hardware'] is not None:
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

def save_devices_to_files(_list, output_dir):
    for hardware, version_dict in sorted(_list.items()):
        filename = hardware.replace(" ", "_").replace("/", "_")
        with open(output_dir + "list_firmware/" + filename + ".txt", "w") as f:
            for version, ip_list in sorted(version_dict.items()):
                f.write(f"> {version}\n")
                for ip in sorted(ip_list):
                    f.write(f"  {ip}\n")

def print_device_list(_list, hardware_filter, version_filter):
    for hardware, version_dict in sorted(_list.items()):
        if not hardware_filter or hardware_filter == hardware:
            print(hardware)
            if hardware_filter:
                for version, ip_list in sorted(version_dict.items(), reverse=True):
                    if not version_filter:
                        print("  ", version)
                        for ip in sorted(ip_list):
                            print("    ", ip)
                    else:
                        for ip in sorted(ip_list):
                            version_str = " ".join(version_filter)
                            if str(version_str) <= str(version):
                                print(ip)


def print_help(hardware_filter, version_filter):
    if not version_filter:
        print()
        print("Add model name and serial number to narrow list")
        print("Examples:")
        [print("     ./lnms_firmware WS-C4500X-32") if not hardware_filter else None]
        print("     ./lnms_firmware WS-C4500X-32 03.11")

def main():
    parser = argparse.ArgumentParser(description="Script to download LibreNMS configuration")
    parser.add_argument("hardware_filter", nargs="?", help="Hardware model name to filter on")
    parser.add_argument("version_filter", nargs=argparse.REMAINDER, help="Version to filter on")
    args = parser.parse_args()

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

    save_devices_to_files(lnms_list, output_dir)

    print_device_list(lnms_list, args.hardware_filter, args.version_filter)

    print_help(args.hardware_filter, args.version_filter)

if __name__ == "__main__":
    main()
