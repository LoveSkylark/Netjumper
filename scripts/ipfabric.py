#!/usr/bin/env python3
"""
Basic IPFabric API Script
Structured to match the architecture of your ACI script.
"""

import os
import re
import argparse
import requests
from ipaddress import ip_address, ip_network

# Disable warnings for demo environments
requests.packages.urllib3.disable_warnings()

# -------------------------------
# Argument Parsing
# -------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="IPFabric API Utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Search by IP address
    ip_parser = subparsers.add_parser("ip", help="Search by IP address")
    ip_parser.add_argument("ip", help="IP to search for")

    # Device lookup
    dev_parser = subparsers.add_parser("device", help="Search for device by hostname")
    dev_parser.add_argument("name", help="Hostname")

    # Inventory dump
    subparsers.add_parser("inventory", help="List all discovered devices")

    return parser.parse_args()

# -------------------------------------------------------
#  REGEX DEFINITIONS (empty for now but structured)
# -------------------------------------------------------
RE_DEVICE_DN = re.compile(r"^/inventory/devices/(?P<id>[^/]+)$")

def parse_regex(regex, text):
    m = regex.search(text)
    return m.groupdict() if m else None


# -------------------------------
# IPFabric Client Class
# -------------------------------

class IPFClient:
    def __init__(self, base_url, token=None):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers["Content-Type"] = "application/json"

        # Token management
        self.token = token or os.getenv("IPF_TOKEN")
        if not self.token:
            raise ValueError("IPFabric token not provided (use env var IPF_TOKEN or --token).")

        self.session.headers["X-API-Token"] = self.token

    # -------------------------
    # Basic API wrapper
    # -------------------------
    def api(self, method, path, **kwargs):
        url = f"{self.base_url}{path}"
        try:
            r = self.session.request(method, url, **kwargs)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"❌ IPFabric API Error: {e}")
            return None

    def post(self, path, data=None):
        return self.api("POST", path, json=data)

    # -------------------------
    # Utility: IP in Subnet
    # -------------------------
    def ip_in_cidr(self, ip, cidr):
        try:
            return ip_address(ip) in ip_network(cidr, strict=False)
        except ValueError:
            return False

    # -------------------------
    # Queries
    # -------------------------

    def query_table(self, endpoint, columns=None, filters=None, limit=1000):
        """
        Generic table query method for API v7.3

        Args:
            endpoint: Table endpoint (e.g., "inventory/devices", "addressing/ip")
            columns: List of column names or None for default columns
            filters: Dict of filters (e.g., {"hostname": ["eq", "router1"]})
            limit: Maximum number of results to return

        Returns:
            API response dict with "data" key containing results
        """
        payload = {
            "attributeFilters": {},
            "filters": filters or {},
            "snapshot": "$last",
            "columns": columns or [],
            "pagination": {
                "start": 0,
                "limit": limit
            },
            "reports": f"/{endpoint}"
        }

        return self.post(f"/api/v7.3/tables/{endpoint}", data=payload)

    def lookup_ip(self, ip):
        """
        Search IPFabric for IP owner by querying interfaces table
        """
        print(f"🔍 Looking up IP: {ip}")

        # Query the inventory/interfaces table which should have IP addressing info
        result = self.query_table(
            endpoint="inventory/interfaces",
            columns=["hostname", "intName", "primaryIp", "vrf"],
            filters={},
            limit=10000
        )

        if not result or "data" not in result:
            print("Could not query inventory/interfaces endpoint.")
            print("IP lookup may not be available in this IPFabric version.")
            return

        # Filter results in Python for the matching IP
        matching_entries = []
        for entry in result["data"]:
            # Check various possible IP field names
            entry_ip = (entry.get("primaryIp") or
                       entry.get("ip") or
                       entry.get("ipAddress") or "").split("/")[0]  # Remove CIDR notation if present

            if entry_ip == ip:
                matching_entries.append(entry)

        if not matching_entries:
            print(f"No results found for IP {ip}.")
            print("Note: Only checking primary interface IPs.")
            return

        tree = {}
        for entry in matching_entries:
            device = entry.get("hostname", "unknown")
            intf   = entry.get("intName", "unknown")
            vrf    = entry.get("vrf") or entry.get("vrfName") or "default"

            tree.setdefault(device, {}).setdefault(vrf, []).append(intf)

        if tree:
            self.print_tree(tree, label=f"IP Owner for {ip}:")
        else:
            print("No device owns this IP.")

    def lookup_device(self, name):
        """
        Search /inventory/devices for hostname using v7.3 API
        """
        print(f"🔍 Searching device: {name}")

        result = self.query_table(
            endpoint="inventory/devices",
            columns=["hostname", "vendor", "platform", "version"],
            filters={"hostname": ["eq", name]},
            limit=100
        )

        if not result or "data" not in result:
            print("No results.")
            return

        tree = {}
        for dev in result["data"]:
            hostname = dev.get("hostname", "unknown")
            vendor   = dev.get("vendor", "")
            model    = dev.get("platform", "")
            version  = dev.get("version", "")

            tree.setdefault(hostname, []).append(f"{vendor} {model} ({version})")

        self.print_tree(tree, label=f"Device Info: {name}")

    def list_inventory(self, columns="*"):
        """
        Dump all discovered devices using API v7.3 POST structure

        Args:
            columns: Either "*" for all columns, or a list of column names
                    e.g., ["hostname", "sn", "siteName", "rd", "secDiscoveryDuration"]
        """
        result = self.query_table(
            endpoint="inventory/devices",
            columns=columns if isinstance(columns, list) else ["hostname", "vendor"],
            filters={},
            limit=1000
        )

        if not result or "data" not in result:
            print("No inventory found.")
            return

        tree = {}
        for dev in result["data"]:
            vendor = dev.get("vendor", "unknown")
            hostname = dev.get("hostname", "unknown")
            tree.setdefault(vendor, []).append(hostname)

        self.print_tree(tree, label="IPFabric Inventory:")

    # -------------------------
    # Tree Printer (same style as ACI)
    # -------------------------

    @staticmethod
    def print_tree(tree, label=None):
        if label:
            print(label)

        def walk(node, depth):
            indent = "  " * depth

            if isinstance(node, dict):
                for k, v in node.items():
                    print(f"{indent}{k}")
                    walk(v, depth + 1)

            elif isinstance(node, list):
                for item in node:
                    print(f"{indent}- {item}")

            else:
                print(f"{indent}{node}")

        walk(tree, 0)

# -------------------------------
# Main Script
# -------------------------------

def main():
    args = parse_args()

    client = IPFClient(
        base_url="https://185.130.15.15/",
        token="8e5d9974546a74b1eb2807a1b866b5ea"
    )

    if args.command == "ip":
        client.lookup_ip(args.ip)

    elif args.command == "device":
        client.lookup_device(args.name)

    elif args.command == "inventory":
        client.list_inventory()

if __name__ == "__main__":
    main()
