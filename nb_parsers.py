"""Data normalization and matching helpers for NetBox sync."""

import re
from ipaddress import ip_network, ip_address, IPv4Network

from fuzzysearch import find_near_matches


# ---------------------------------------------------------------------------
# Priming data  (edit to match your environment)
# ---------------------------------------------------------------------------

DEVICE_ROLES = [
    'Appliance',
    'Collaboration',
    'Environment',
    'Firewalls',
    'Load Balancers',
    'Network',
    'Power',
    'Printers',
    'Servers',
    'Storage',
    'Wireless',
    'Workstation',
]


# ---------------------------------------------------------------------------
# Site mapping
# ---------------------------------------------------------------------------

def sites_from_mapping(mapping: dict) -> list:
    """Return the list of site names from a site_mapping dict."""
    return list(mapping.keys())


def compile_mapping(mapping: dict) -> list:
    """Pre-compile regex patterns in a site mapping dict for reuse across device loop.

    Input format: {site_name: {field: pattern, ...}, ...}
    where field is one of 'name', 'location', 'ip'.
    Returns a flat list of compiled entries used by match_site().
    """
    compiled = []
    for site, rules in mapping.items():
        for field, pattern in rules.items():
            e = {'site': site, 'field': field, 'pattern': pattern}
            if field != 'ip':
                pat = re.escape(str(pattern)).replace(r'\*', '.*')
                try:
                    e['_regex'] = re.compile(pat, re.IGNORECASE)
                except re.error:
                    e['_regex'] = None
            compiled.append(e)
    return compiled


def match_site(name: str, ip: str = None, location: str = None,
               mapping: list = None) -> str | None:
    """Return site name by matching device name, IP, or location against mapping rules.

    Pass a pre-compiled mapping from compile_mapping() for best performance.
    Each entry is a dict with keys: site, field, pattern (and _regex if pre-compiled).
    """
    if not mapping:
        return None

    for entry in mapping:
        site, field, pattern = entry['site'], entry['field'], entry['pattern']

        if field == 'ip' and ip:
            try:
                network = ip_network(pattern, strict=False)
                if isinstance(network, IPv4Network) and ip_address(ip) in network:
                    return site
            except ValueError:
                continue

        else:
            regex = entry.get('_regex')
            if regex is None:
                try:
                    regex = re.compile(re.escape(pattern).replace(r'\*', '.*'), re.IGNORECASE)
                except re.error:
                    continue

            if field == 'location' and location:
                if regex.search(location.replace('|', ' ')):
                    return site
            if field == 'name' and regex.search(name):
                return site

    return None


# ---------------------------------------------------------------------------
# Device normalization
# ---------------------------------------------------------------------------

def normalize_nb_devices(nb_devices) -> dict:
    """Convert NetBox device list to a normalized dict keyed by short lowercase name."""
    result = {}
    for device in nb_devices:
        name = str(device.name).split('.')[0].casefold()
        if not name:
            continue
        result[name] = {
            'full_name':   device.name,
            'mgmt_ip':     str(device.primary_ip4).split('/')[0] if device.primary_ip4 else '',
            'device_type': device.device_type.model if device.device_type else '',
            'serial':      device.serial or '',
            'location':    device.site.name if device.site else '',
            'device_role': device.role.name if device.role else '',
        }
    return result


def normalize_devices(lnms_devices: list[dict]) -> dict:
    """Convert LibreNMS device list to a normalized dict keyed by short lowercase name."""
    result = {}
    for device in lnms_devices:
        name = str(device.get('sysName', '')).split('.')[0].casefold()
        if not name:
            continue
        result[name] = {
            'full_name':   device.get('sysName', name),
            'mgmt_ip':     device.get('ip') or device.get('hostname', ''),
            'device_type': device.get('hardware', ''),
            'serial':      device.get('serial', ''),
            'location':    device.get('location', ''),
            'device_role': device.get('type', ''),
        }
    return result


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------

def clean_string(s: str) -> str:
    """Strip noise words and normalise separators for fuzzy matching."""
    noise = ['Chassis', 'Nexus']
    s = re.sub('|'.join(noise), '', s, flags=re.IGNORECASE)
    return s.replace('_', ' ').replace('-', ' ').replace(',', ' ').strip()


def build_clean_lookup(lookup_dict: dict) -> dict:
    """Return {clean_string(key): value} — pre-clean keys so find_closest_id
    doesn't repeat clean_string() on every key for every device."""
    return {clean_string(k): v for k, v in lookup_dict.items()}


def find_closest_id(search: str, lookup_dict: dict, threshold: int = 5) -> int | None:
    """Fuzzy-match search against lookup_dict keys; return the matching id or None.

    Pass a pre-cleaned dict from build_clean_lookup() for best performance.
    """
    if not search:
        return None
    cleaned = clean_string(search)
    matches = []
    for name in lookup_dict:
        match = find_near_matches(cleaned, name, max_l_dist=1)
        if match:
            matches.append((name, match[0].dist))
    matches.sort(key=lambda x: x[1])
    if matches and (matches[0][1] == 0 or 0 < len(matches) < threshold):
        return lookup_dict[matches[0][0]]
    return None
