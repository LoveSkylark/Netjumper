#!/usr/bin/env python3

#  LibreNMS CLI
#
#  Usage:
#    lnms.py billing [customer]
#    lnms.py inventory
#    lnms.py neighbors [hostname]
#    lnms.py download
#    lnms.py firmware [hardware] [min-version]
#    lnms.py host update
#
#  @author Skylark (github.com/LoveSkylark)
#  @license GPL

import os
import re
import sys
import logging
import logging.handlers
import argparse

from python_hosts import Hosts, HostsEntry

from config import load_settings
from client import Client, APIError
from parsers import (
    format_mbps,
    format_bill_date,
    find_unknown_neighbors,
    get_sorted_port_list,
    group_by_hardware_version,
    save_firmware_files,
    print_firmware_list,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

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


def _ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _api_fetch(*fns):
    """Call each zero-arg API function, exit on error. Returns list of results."""
    try:
        return [fn() for fn in fns]
    except APIError as e:
        logging.error(f"API error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error calling API: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# billing
# ---------------------------------------------------------------------------

def cmd_billing(args, api: Client):
    if args.customer:
        bills, = _api_fetch(api.list_bills)
        bill = next((b for b in bills if b['bill_name'] == args.customer), None)
        if not bill:
            print("Customer not found!")
            sys.exit(1)
        print(f"Customer: {args.customer}\n")
        if args.ports:
            devices, = _api_fetch(api.list_devices)
            _print_bill_ports(bill['bill_id'], api, devices)
        else:
            _print_bill_history(bill['bill_id'], api)
    else:
        _print_bills(api, show_ports=args.ports)


def _print_bills(api: Client, show_ports: bool = False) -> None:
    template = "{0:20} {1:0} {2:20} {3:0} {4:0}"
    bills, = _api_fetch(api.list_bills)
    devices = None
    if show_ports:
        devices, = _api_fetch(api.list_devices)
    for bill in bills:
        if 'ISP:' in bill['bill_name']:
            continue
        formatted_95th = format_mbps(bill['rate_95th'])
        if bill['overuse'] != '-':
            print(template.format(bill['bill_name'], "95th:", formatted_95th, "over:", bill['overuse']))
        else:
            print(template.format(bill['bill_name'], "95th:", formatted_95th, "", ""))
        if show_ports:
            _print_bill_ports(bill['bill_id'], api, devices)


def _print_bill_ports(bill_id: int, api: Client, devices: list) -> None:
    device_names = {d['device_id']: d['sysName'].split('.')[0] for d in devices}
    try:
        ports = api.get_bill_ports(bill_id)
    except Exception as e:
        print(f"  (could not fetch ports: {e})")
        return
    if not ports:
        print("  (no ports assigned)")
        return
    for port in ports:
        device_name = device_names.get(port.get('device_id'), str(port.get('device_id', '?')))
        ifname      = port.get('ifName', 'unknown')
        try:
            detail   = api.get_port(port['port_id'])
            import json; print(json.dumps(detail, indent=2))
            rate_in  = format_mbps(detail.get('ifInOctets_rate', 0) * 8)
            rate_out = format_mbps(detail.get('ifOutOctets_rate', 0) * 8)
        except Exception:
            rate_in = rate_out = 'n/a'
        print(f"  {device_name:25} {ifname:20} in: {rate_in:15} out: {rate_out}")


def _print_bill_history(bill_id: int, api: Client) -> None:
    template = "{0:20} {1:0} {2:20} {3:0} {4:20}"
    history, = _api_fetch(lambda: api.get_bill_history(bill_id))
    for bill in history:
        formatted_95th = format_mbps(bill['rate_95th'])
        formatted_date = format_bill_date(bill['bill_datefrom'])
        if bill['bill_overuse'] > 0:
            print(template.format(formatted_date, "95th:", formatted_95th, "over:", format_mbps(bill['bill_overuse'])))
        else:
            print(template.format(formatted_date, "95th:", formatted_95th, "", ""))


# ---------------------------------------------------------------------------
# inventory
# ---------------------------------------------------------------------------

def cmd_inventory(args, api: Client):
    output_dir = _ensure_dir(args.settings.info_dir)
    devices, = _api_fetch(api.list_devices)

    csv_path = os.path.join(output_dir, "device-list.csv")
    print("\nDevices with a serial number:")
    with open(csv_path, "w") as f:
        f.write("NAME, IP, HARDWARE, VERSION, SERIAL\n")
        for device in devices:
            short_name = device['sysName'].split('.')[0]
            if device['serial']:
                print(f"  {short_name}  S:{device['serial']}")
            else:
                logging.warning(f"Unable to get serial number from {short_name}")
            logging.info(f"device added to list: {short_name}")
            f.write(f"{short_name}, {device['hostname']}, {device['hardware'] or ''}, {device['version'] or ''}, {device['serial'] or ''}\n")

    print(f"\nDone, detailed list saved to: {csv_path}\n")


# ---------------------------------------------------------------------------
# neighbors
# ---------------------------------------------------------------------------

def cmd_neighbors(args, api: Client):
    devices, links, ports = _api_fetch(api.list_devices, api.list_links, api.get_all_ports)

    neighbours = find_unknown_neighbors(devices, links)
    matched = [n for n in neighbours if not args.hostname or re.search(args.hostname, n, re.IGNORECASE)]

    for neighbour in matched:
        logging.info(f"Neighbour {neighbour} discovered")
        print(neighbour)
        if args.ports:
            for device_name, port_name in get_sorted_port_list(neighbour, devices, links, ports):
                print(f"  -> {device_name} ({port_name})")

    if not args.hostname:
        print()
        print("Add hostname to narrow list")
        print("Examples:")
        print("     lnms.py neighbors 'partial-or-full-hostname'")
    elif matched and not args.ports:
        print("(add -p to see port details)")


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------

def cmd_download(args, api: Client):
    output_dir = _ensure_dir(args.settings.config_dir)
    devices, oxidized = _api_fetch(api.list_devices, api.list_oxidized)

    hostname_to_sysname = {d['hostname']: d['sysName'] for d in devices}
    total = len(oxidized)
    saved = 0

    print(f"Downloading {total} configs...")
    for device in oxidized:
        hostname = device['hostname']
        short_name = hostname_to_sysname.get(hostname, hostname).split('.')[0]
        config = api.get_oxidized_config(hostname)
        if config and config != "node not found":
            with open(os.path.join(output_dir, short_name + ".txt"), "w") as f:
                f.write(config)
            logging.info(f"Saved config from {short_name} ({hostname})")
            saved += 1
        else:
            print(f"  Config missing for: {short_name}")
            logging.warning(f"Unable to get config from {short_name} ({hostname})")

    print(f"\nDone, saved {saved}/{total} configs to: {output_dir}\n")


# ---------------------------------------------------------------------------
# firmware
# ---------------------------------------------------------------------------

def cmd_firmware(args, api: Client):
    firmware_dir = _ensure_dir(os.path.join(args.settings.info_dir, 'list_firmware'))

    devices, = _api_fetch(api.list_devices)
    grouped = group_by_hardware_version(devices)
    save_firmware_files(grouped, firmware_dir)
    print_firmware_list(grouped, args.hardware, args.version)

    if not args.version:
        print()
        print("Add model name and version to narrow list")
        print("Examples:")
        if not args.hardware:
            print("     lnms.py firmware WS-C4500X-32")
        print("     lnms.py firmware WS-C4500X-32 03.11")


# ---------------------------------------------------------------------------
# api
# ---------------------------------------------------------------------------

def cmd_api(_args, api: Client):
    try:
        data = api.ping()
        info = data.get('system', {}) if isinstance(data, dict) else {}
        version = info.get('local_ver', 'unknown')
        print(f"OK  API is reachable and token is valid (LibreNMS {version})")
    except APIError as e:
        print(f"FAIL  {e}")
        sys.exit(1)
    except Exception as e:
        if "timed out" in str(e).lower() or "timeout" in type(e).__name__.lower():
            print(f"FAIL  Connection timed out: {api._url}")
        else:
            print(f"FAIL  Could not reach API: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# host
# ---------------------------------------------------------------------------

def cmd_host(args, api: Client):
    if args.host_action == "update":
        _host_update(args, api)
    elif args.host_action == "compare":
        _host_compare(args, api)


def _host_update(args, api: Client) -> None:
    devices, = _api_fetch(api.list_devices)
    entries = [(d['sysName'].lower().split('.', 1)[0], d['hostname']) for d in devices]

    _write_hosts_file(entries, args.settings.hosts_dir)
    logging.info(f"Written {len(entries)} entries to {args.settings.hosts_dir}")

    hosts_list = os.path.join(_ensure_dir(args.settings.info_dir), "hosts.list")
    _write_hosts_file(entries, hosts_list)
    logging.info(f"Written {len(entries)} entries to {hosts_list}")

    print(f"Done, {len(entries)} hosts written.")


def _host_compare(args, api: Client) -> None:
    devices, = _api_fetch(api.list_devices)
    nms = {d['sysName'].lower().split('.', 1)[0]: d['hostname'] for d in devices}

    hosts = Hosts(path=args.settings.hosts_dir)
    current = {}
    for entry in hosts.entries:
        if entry.entry_type == 'ipv4' and hasattr(entry, 'names'):
            for name in entry.names:
                current[name] = entry.address

    to_add    = [(n, ip) for n, ip in sorted(nms.items()) if n not in current]
    to_update = [(n, current[n], ip) for n, ip in sorted(nms.items()) if n in current and current[n] != ip]

    if to_add:
        print("To be added:")
        for name, ip in to_add:
            print(f"  + {ip:<20} {name}")
    if to_update:
        print("To be updated:")
        for name, old_ip, new_ip in to_update:
            print(f"  ~ {old_ip:<20} -> {new_ip:<20} {name}")
    if not to_add and not to_update:
        print("Hosts file is already up to date.")


def _write_hosts_file(entries: list[tuple[str, str]], path: str) -> None:
    hosts = Hosts(path=path)
    for name, ip in entries:
        hosts.add([HostsEntry(entry_type='ipv4', address=ip, names=[name])])
    hosts.write()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMANDS = {
    "billing":   cmd_billing,
    "inventory": cmd_inventory,
    "neighbors": cmd_neighbors,
    "download":  cmd_download,
    "firmware":  cmd_firmware,
    "host":      cmd_host,
    "api":       cmd_api,
}


def build_parser():
    parser = argparse.ArgumentParser(prog="lnms.py", description="LibreNMS CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_billing = sub.add_parser("billing",   help="Show 95th-percentile billing data")
    p_billing.add_argument("customer", nargs="?", help="Customer name (shows history when provided)")
    p_billing.add_argument("-p", dest="ports", action="store_true", help="Show ports and current rates")

    sub.add_parser("inventory", help="List devices and write device-list.csv")

    p_neighbors = sub.add_parser("neighbors", help="Discover unknown LLDP/CDP neighbors")
    p_neighbors.add_argument("hostname", nargs="?", help="Regex filter on neighbor name")
    p_neighbors.add_argument("-p", dest="ports", action="store_true", help="Show connected ports")

    sub.add_parser("download", help="Download device configs from Oxidized")

    p_firmware = sub.add_parser("firmware", help="List devices grouped by hardware/firmware version")
    p_firmware.add_argument("hardware", nargs="?", help="Hardware model to filter on")
    p_firmware.add_argument("version",  nargs="?", help="Minimum version to filter on")

    p_host = sub.add_parser("host", help="Manage /etc/hosts entries")
    host_sub = p_host.add_subparsers(dest="host_action", required=True)
    host_sub.add_parser("update",  help="Sync LibreNMS devices to hosts file")
    host_sub.add_parser("compare", help="Preview changes before running host update")

    sub.add_parser("api", help=argparse.SUPPRESS)

    return parser


def main():
    args = build_parser().parse_args()
    settings = load_settings()
    args.settings = settings
    setup_logging(f"lnms_{args.command}.log", settings.log_dir)
    api = Client(settings.url, settings.token)
    COMMANDS[args.command](args, api)


if __name__ == "__main__":
    main()
