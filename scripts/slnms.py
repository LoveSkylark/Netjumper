#!/usr/bin/env python3

#  LibreNMS CLI
#
#  Usage:
#    slnms.py billing [customer]
#    slnms.py inventory
#    slnms.py neighbors [hostname]
#    slnms.py download
#    slnms.py firmware [hardware] [min-version]
#    slnms.py host update
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

from scripts.config_service import load_settings
from scripts.slnms_client import Client, APIError
from scripts.nb_client import NetboxClient
from scripts.nb_parsers import normalize_devices, normalize_nb_devices, match_site, compile_mapping, sites_from_mapping, find_closest_id, build_clean_lookup, DEVICE_ROLES
from scripts.slnms_parsers import (
    format_mbps,
    format_bill_date,
    find_unknown_neighbors,
    get_sorted_port_list,
    group_by_hardware_version,
    save_firmware_files,
    print_firmware_list,
    get_vendor,
)
from scripts.tree_utils import CLITreeBuilder


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
        f.write("NAME, IP, VENDOR, HARDWARE, VERSION, SERIAL\n")
        for device in devices:
            short_name = device['sysName'].split('.')[0]
            vendor = get_vendor(device.get('icon', ''))
            if args.vendor and args.vendor.lower() != vendor.lower():
                continue
            if device['serial']:
                print(f"  {short_name}  S:{device['serial']}")
            else:
                logging.warning(f"Unable to get serial number from {short_name}")
            logging.info(f"device added to list: {short_name}")
            f.write(f"{short_name}, {device['hostname']}, {vendor}, {device['hardware'] or ''}, {device['version'] or ''}, {device['serial'] or ''}\n")

    print(f"\nDone, detailed list saved to: {csv_path}\n")


# ---------------------------------------------------------------------------
# neighbors
# ---------------------------------------------------------------------------

def cmd_neighbors(args, api: Client):
    devices, links, ports = _api_fetch(api.list_devices, api.list_links, api.get_all_ports)

    neighbours = find_unknown_neighbors(devices, links)
    matched = [n for n in neighbours if not args.hostname or re.search(args.hostname, n, re.IGNORECASE)]

    if args.tree:
        _print_neighbors_tree(matched, devices, links, ports, show_ports=args.ports)
        return

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


def _print_neighbors_tree(matched: list[str], devices: list[dict], links: list[dict], ports: list[dict], show_ports: bool) -> None:
    tree = CLITreeBuilder()

    for neighbour in matched:
        logging.info(f"Neighbour {neighbour} discovered")
        if show_ports:
            port_rows = get_sorted_port_list(neighbour, devices, links, ports)
            if not port_rows:
                tree.add(neighbour, label="(no local ports)")
                continue
            for device_name, port_name in port_rows:
                tree.add(neighbour, device_name or "unknown-device", label=port_name or "unknown-port")
        else:
            tree.add(neighbour, label="discovered")

    if matched:
        tree.print(label="Unknown neighbors")
    else:
        print("No unknown neighbors found.")


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
    if args.tree:
        _print_firmware_tree(grouped, args.hardware, args.version)
    else:
        print_firmware_list(grouped, args.hardware, args.version)

    if not args.version:
        print()
        print("Add model name and version to narrow list")
        print("Examples:")
        if not args.hardware:
            print("     lnms.py firmware WS-C4500X-32")
        print("     lnms.py firmware WS-C4500X-32 03.11")


def _print_firmware_tree(grouped: dict, hardware_filter: str | None, version_filter: str | None) -> None:
    tree = CLITreeBuilder()

    for hardware, version_dict in sorted(grouped.items()):
        if hardware_filter and hardware_filter != hardware:
            continue

        for version, ip_list in sorted(version_dict.items(), reverse=bool(hardware_filter)):
            if hardware_filter and version_filter and version < version_filter:
                continue
            for ip in sorted(ip_list):
                tree.add(hardware, version, label=ip)

    if tree.tree:
        tree.print(label="Firmware inventory")
    else:
        print("No firmware entries matched the provided filters.")


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
# nb
# ---------------------------------------------------------------------------

def _nb_connect(args) -> NetboxClient:
    if not args.settings.nb_url or not args.settings.nb_token:
        raise SystemExit("Missing required config value(s): netbox.url, netbox.token")
    return NetboxClient(args.settings.nb_url, args.settings.nb_token)


def cmd_nb(args, api: Client):
    if args.nb_action == "load":
        cmd_nb_load(args, api)
    elif args.nb_action == "prime":
        cmd_nb_prime(args)
    elif args.nb_action == "diff":
        cmd_nb_diff(args, api)


def cmd_nb_diff(args, api: Client) -> None:
    nb = _nb_connect(args)

    print("Fetching devices...")
    lnms_devices, = _api_fetch(api.list_devices)
    ldevices  = normalize_devices(lnms_devices)
    nbdevices = normalize_nb_devices(nb.get_all_devices())

    only_lnms = sorted(set(ldevices) - set(nbdevices))
    only_nb   = sorted(set(nbdevices) - set(ldevices))

    COMPARE_FIELDS = ['mgmt_ip', 'serial']
    mismatches = {
        name: {
            f: (ldevices[name][f], nbdevices[name][f])
            for f in COMPARE_FIELDS
            if ldevices[name][f] and nbdevices[name][f]
            and ldevices[name][f] != nbdevices[name][f]
        }
        for name in sorted(set(ldevices) & set(nbdevices))
    }
    mismatches = {k: v for k, v in mismatches.items() if v}

    if only_lnms:
        print(f"\nMissing in NetBox ({len(only_lnms)}):")
        for name in only_lnms:
            print(f"  - {name:<30} {ldevices[name]['mgmt_ip']}")

    if only_nb:
        print(f"\nMissing in LibreNMS ({len(only_nb)}):")
        for name in only_nb:
            print(f"  - {name:<30} {nbdevices[name]['mgmt_ip']}")

    if mismatches:
        print(f"\nField mismatches ({len(mismatches)}):")
        for name, diffs in mismatches.items():
            print(f"  {name}:")
            for field, (lval, nbval) in diffs.items():
                print(f"    {field:<12} LibreNMS: {lval}  NetBox: {nbval}")

    if not only_lnms and not only_nb and not mismatches:
        print("\nLibreNMS and NetBox are in sync.")
    else:
        print(f"\nSummary: {len(only_lnms)} missing in NetBox, {len(only_nb)} missing in LibreNMS, {len(mismatches)} mismatches.")


def cmd_nb_prime(args) -> None:
    nb = _nb_connect(args)
    s  = args.settings

    print("Checking NetBox...\n")
    to_create = {
        'Regions':      (nb.regions,      s.nb_regions),
        'Sites':        (nb.sites,         sites_from_mapping(s.nb_site_mapping)),
        'Device roles': (nb.device_roles,  DEVICE_ROLES),
    }

    plan  = {label: nb.diff_objects(ep, names) for label, (ep, names) in to_create.items()}
    total = sum(len(v) for v in plan.values())

    if total == 0:
        print("Nothing to create — NetBox is already up to date.")
        return

    print("The following objects will be created:\n")
    for label, missing in plan.items():
        if missing:
            print(f"  {label}:")
            for name in missing:
                print(f"    + {name}")

    if input("\nProceed? [y/N] ").strip().lower() != 'y':
        print("Aborted.")
        return

    print()
    for label, (ep, _) in to_create.items():
        if plan[label]:
            print(f"{label}:")
            nb.create_objects(ep, plan[label])

    print("\nDone.")


def cmd_nb_load(args, api: Client) -> None:
    nb = _nb_connect(args)

    print("Fetching devices from LibreNMS...")
    devices, = _api_fetch(api.list_devices)
    ldevices = normalize_devices(devices)

    print("Caching NetBox lookups...")
    device_types = build_clean_lookup(nb.get_device_types())
    roles        = build_clean_lookup(nb.get_roles())
    sites        = nb.get_sites()
    nb_all       = {str(d.name).split('.')[0].casefold(): d for d in nb.get_all_devices()}
    mapping      = compile_mapping(args.settings.nb_site_mapping)

    # --- Plan phase ---
    to_create = []
    to_update = []
    to_skip   = []

    for name, info in sorted(ldevices.items()):
        device_type_id = find_closest_id(info['device_type'], device_types)
        role_id        = find_closest_id(info['device_role'], roles)
        site_name      = match_site(name, info['mgmt_ip'], info['location'], mapping)
        site_id        = sites.get(site_name) if site_name else None

        if not device_type_id:
            to_skip.append((name, f"no device type match: {info['device_type']}"))
            continue
        if not role_id:
            to_skip.append((name, f"no role match: {info['device_role']}"))
            continue
        if not site_id:
            to_skip.append((name, "no site match"))
            continue

        existing = nb_all.get(name)
        if not existing:
            to_create.append((name, info, device_type_id, role_id, site_id))
        else:
            changes = {}
            if existing.device_type.id != device_type_id:
                changes['device_type'] = (existing.device_type, device_type_id)
            if existing.role.id != role_id:
                changes['role'] = (existing.role, role_id)
            if existing.site.id != site_id:
                changes['site'] = (existing.site, site_id)
            if info['serial'] and existing.serial != info['serial']:
                changes['serial'] = (existing.serial, info['serial'])
            if info['mgmt_ip']:
                try:
                    current_ip = existing.primary_ip4.address if existing.primary_ip4 else None
                except AttributeError:
                    current_ip = None
                if current_ip != info['mgmt_ip'] + '/32':
                    changes['mgmt_ip'] = (current_ip or 'none', info['mgmt_ip'])
            if changes:
                to_update.append((name, existing, info, device_type_id, role_id, site_id, changes))

    # --- Display plan ---
    if to_create:
        print(f"\nTo be created ({len(to_create)}):")
        for name, info, *_ in to_create:
            print(f"  + {name:<30} {info['mgmt_ip']:<18} {info['device_type']}")

    if to_update:
        print(f"\nTo be updated ({len(to_update)}):")
        for name, _, __, *rest in to_update:
            changes = rest[-1]
            print(f"  ~ {name}")
            for field, (old, new) in changes.items():
                print(f"      {field:<14} {str(old):<25} -> {new}")

    if to_skip:
        print(f"\nSkipped ({len(to_skip)}):")
        for name, reason in to_skip:
            print(f"  - {name:<30} ({reason})")

    if not to_create and not to_update:
        print("\nNetBox is already up to date.")
        return

    print()
    if input("Proceed? [y/N] ").strip().lower() != 'y':
        print("Aborted.")
        return

    # --- Apply phase ---
    print()
    for name, info, device_type_id, role_id, site_id in to_create:
        existing = nb.create_device(name, device_type_id, role_id, site_id)
        print(f"  CREATE {name}")
        if existing and info['mgmt_ip']:
            nb.ensure_mgmt_ip(existing, info['mgmt_ip'] + '/32')

    for name, existing, info, device_type_id, role_id, site_id, changes in to_update:
        if 'device_type' in changes:
            existing.device_type = device_type_id
        if 'role' in changes:
            existing.role = role_id
        if 'site' in changes:
            existing.site = site_id
        if 'serial' in changes:
            existing.serial = info['serial']
        existing.save()
        print(f"  UPDATE {name}")
        if info['mgmt_ip']:
            nb.ensure_mgmt_ip(existing, info['mgmt_ip'] + '/32')

    print(f"\nDone: {len(to_create)} created, {len(to_update)} updated, {len(to_skip)} skipped.")


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
    "nb":        cmd_nb,
    "api":       cmd_api,
}


def build_parser():
    parser = argparse.ArgumentParser(prog="slnms", description="LibreNMS CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_billing = sub.add_parser("billing",   help="Show 95th-percentile billing data")
    p_billing.add_argument("customer", nargs="?", help="Customer name (shows history when provided)")
    p_billing.add_argument("-p", dest="ports", action="store_true", help="Show ports and current rates")

    p_inventory = sub.add_parser("inventory", help="List devices and write device-list.csv")
    p_inventory.add_argument("-v", dest="vendor", metavar="VENDOR", help="Filter by vendor name")

    p_neighbors = sub.add_parser("neighbors", help="Discover unknown LLDP/CDP neighbors")
    p_neighbors.add_argument("hostname", nargs="?", help="Regex filter on neighbor name")
    p_neighbors.add_argument("-p", dest="ports", action="store_true", help="Show connected ports")
    p_neighbors.add_argument("-t", "--tree", action="store_true", help="Print output as a tree")

    sub.add_parser("download", help="Download device configs from Oxidized")

    p_firmware = sub.add_parser("firmware", help="List devices grouped by hardware/firmware version")
    p_firmware.add_argument("hardware", nargs="?", help="Hardware model to filter on")
    p_firmware.add_argument("version",  nargs="?", help="Minimum version to filter on")
    p_firmware.add_argument("-t", "--tree", action="store_true", help="Print output as a tree")

    p_host = sub.add_parser("host", help="Manage /etc/hosts entries")
    host_sub = p_host.add_subparsers(dest="host_action", required=True)
    host_sub.add_parser("update",  help="Sync LibreNMS devices to hosts file")
    host_sub.add_parser("compare", help="Preview changes before running host update")

    p_nb = sub.add_parser("nb", help="NetBox operations")
    nb_sub = p_nb.add_subparsers(dest="nb_action", required=True)
    nb_sub.add_parser("load",    help="Sync LibreNMS devices into NetBox")
    nb_sub.add_parser("prime",   help="Create base objects (regions, sites, roles) in NetBox")
    nb_sub.add_parser("diff",    help="Compare devices between LibreNMS and NetBox")

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
