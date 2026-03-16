"""Pure data-processing helpers for lnms.py commands."""

import os
from datetime import datetime


def format_mbps(bps: float) -> str:
    return "{:.2f} Mbps".format(bps / 1_000_000)


def get_vendor(icon: str) -> str:
    if not icon:
        return ''
    return os.path.splitext(os.path.basename(icon))[0].capitalize()


# ------------------------------------------------------------------
# Neighbors
# ------------------------------------------------------------------

def find_unknown_neighbors(devices: list[dict], links: list[dict]) -> list[str]:
    """Return sorted list of remote hostnames not present in local device list."""
    local = {
        d['sysName'].lower().split('.', 1)[0]
        for d in devices if isinstance(d, dict)
    }
    remote = {
        lnk['remote_hostname'].lower().split('(', 1)[0].split('.', 1)[0]
        for lnk in links if isinstance(lnk, dict)
    }
    return sorted(remote - local)


def get_sorted_port_list(
    hostname: str,
    devices: list[dict],
    links: list[dict],
    ports: list[dict],
) -> list[tuple[str, str]]:
    """Return (device_name, port_name) pairs for links whose remote matches *hostname*."""
    device_by_id = {d['device_id']: d['sysName'] for d in devices}
    port_by_id   = {p['port_id']:   p['ifName']  for p in ports}
    result = [
        (device_by_id.get(lnk['local_device_id']), port_by_id.get(lnk['local_port_id']))
        for lnk in links
        if hostname in lnk['remote_hostname'].lower().split('.', 1)[0]
    ]
    result.sort(key=lambda x: x[0].lower() if x[0] else '')
    return result


# ------------------------------------------------------------------
# Firmware
# ------------------------------------------------------------------

def group_by_hardware_version(devices: list[dict]) -> dict[str, dict[str, list[str]]]:
    """Group devices as {hardware: {version: [ip, ...]}}."""
    result: dict = {}
    for device in devices:
        if not device.get('hardware'):
            continue
        hardware = device['hardware'].replace(' ', '_').replace('/', '_')
        ip = device['hostname'] if device['status'] else f"#{device['hostname']}"
        result.setdefault(hardware, {}).setdefault(device['version'], []).append(ip)
    return result


def save_firmware_files(grouped: dict, firmware_dir: str) -> None:
    for hardware, version_dict in sorted(grouped.items()):
        with open(os.path.join(firmware_dir, hardware + '.txt'), 'w') as f:
            for version, ip_list in sorted(version_dict.items()):
                f.write(f'> {version}\n')
                for ip in sorted(ip_list):
                    f.write(f'  {ip}\n')


def print_firmware_list(
    grouped: dict,
    hardware_filter: str | None,
    version_filter: str | None,
) -> None:
    for hardware, version_dict in sorted(grouped.items()):
        if hardware_filter and hardware_filter != hardware:
            continue
        print(hardware)
        if hardware_filter:
            for version, ip_list in sorted(version_dict.items(), reverse=True):
                if not version_filter:
                    print('  ', version)
                    for ip in sorted(ip_list):
                        print('    ', ip)
                else:
                    for ip in sorted(ip_list):
                        if version_filter <= version:
                            print(ip)


# ------------------------------------------------------------------
# Billing
# ------------------------------------------------------------------

def format_bill_date(date_str: str) -> str:
    return datetime.strptime(date_str[:10], '%Y-%m-%d').strftime('%B %Y')
