#!/usr/bin/python3

import os
import sys
import logging.handlers
import argparse
from dotenv import load_dotenv
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

def parse_args():
    parser = argparse.ArgumentParser(description="Script to download LibreNMS configuration")
    parser.add_argument("hardware_filter", nargs="?", help="Hardware model name to filter on")
    parser.add_argument("version_filter", nargs=argparse.REMAINDER, help="Version to filter on")
    return parser.parse_args()

def create_output_directory(output_dir):
    info_dir = os.environ['info_dir']
    firmware_dir = os.path.join(info_dir, output_dir)
    os.makedirs(firmware_dir, exist_ok=True)
    return (firmware_dir)

def print_help(args):
    if not args.hostname:
        print()
        print("Add hostname to narrow list")
        print("Examples:")
        print("     ./lnms_neighbors.py 'partial-or-full-hostname'")

# -------

def get_api_data(lnms):
    try:
        devices = lnms.list_devices()
    except Exception as e:
        logging.error(f"Error calling API: {e}")
        sys.exit(1)
    
    logging.info("API call succeeded")
    return devices


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

def save_devices_to_files(_list, firmware_dir):
    for hardware, version_dict in sorted(_list.items()):
        filename = hardware.replace(" ", "_").replace("/", "_")
        with open(firmware_dir + filename + ".txt", "w") as f:
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

    # Load environment variables
    load_dotenv()

    args = parse_args()

    # Setup logging
    log_file = "lnms_firmware.log"
    setup_logging(log_file)

    # Setup File location
    output_dir='list_firmware'
    firmware_dir = create_output_directory(output_dir)

    # API connect to LibreNMS & get device list
    lnms = LibreNMSAPIClient()
    lnms_devices = get_api_data(lnms)
    
    lnms_list = group_devices_by_hardware_version(lnms_devices)

    save_devices_to_files(lnms_list, firmware_dir)

    print_device_list(lnms_list, args.hardware_filter, args.version_filter)

    print_help(args.hardware_filter, args.version_filter)

if __name__ == "__main__":
    main()
