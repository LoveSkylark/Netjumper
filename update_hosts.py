#!/usr/bin/python3

##
# update_hosts.py
#
# Retrieves devices from LibreNMS and writes them to /etc/hosts (or a custom path).
##

import os
import sys
import logging
import logging.handlers

from python_hosts import Hosts, HostsEntry

from config import load_settings
from client import Client, APIError


def setup_logging(log_file: str, log_dir: str) -> None:
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s:%(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.handlers.RotatingFileHandler(
                os.path.join(log_dir, log_file),
                maxBytes=5 * 1024 * 1024,
                backupCount=10,
            )
        ],
    )


def get_devices(api: Client) -> list[tuple[str, str]]:
    """Return (short_name, ip) pairs for all devices."""
    try:
        devices = api.list_devices()
    except APIError as e:
        logging.error(f"API error: {e}")
        sys.exit(1)

    logging.info("API call succeeded")
    return [
        (d['sysName'].lower().split('.', 1)[0], d['hostname'])
        for d in devices
    ]


def write_hosts_file(entries: list[tuple[str, str]], path: str) -> None:
    try:
        hosts = Hosts(path=path)
        for name, ip in entries:
            hosts.add([HostsEntry(entry_type='ipv4', address=ip, names=[name])])
        hosts.write()
    except Exception:
        logging.exception("Failed to write hosts file")


def main():
    settings = load_settings()
    setup_logging("update_hosts.log", settings.log_dir)

    logging.info("Connecting to LibreNMS")
    api = Client(settings.url, settings.token)

    logging.info("Gathering device list")
    entries = get_devices(api)

    logging.info(f"Writing {len(entries)} entries to {settings.hosts_dir}")
    write_hosts_file(entries, settings.hosts_dir)

    info_hosts = os.path.join(settings.info_dir, "hosts.list")
    os.makedirs(settings.info_dir, exist_ok=True)
    logging.info(f"Writing device list to {info_hosts}")
    write_hosts_file(entries, info_hosts)

    print("Done!")


if __name__ == "__main__":
    main()
