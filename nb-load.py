#!/usr/bin/python3

import os
import re
import pynetbox
from ipaddress import ip_network, ip_address, IPv4Network
from dotenv import load_dotenv
from fuzzysearch import find_near_matches
from  Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient

def connect_to_netbox(netbox_url=None, api_token=None):
    if api_token is None and netbox_url is None:
            load_dotenv()
            netbox_url = os.environ['Netbox_URL']
            api_token = os.environ['Netbox__APIToken']
    return(pynetbox.api(url=netbox_url, token=api_token))

def cache_dicts(nb):

    # Cache device types by Part Number
    device_types = {}
    all_types = nb.dcim.device_types.all()
    for dt in all_types:
        device_types[dt.part_number] = dt.id
    
    # Cache roles
    roles = {} 
    all_roles = nb.dcim.device_roles.all()
    for role in all_roles:
        roles[role.display] = role.id  

    # Cache sites 
    sites = {}
    all_sites = nb.dcim.sites.all() 
    for site in all_sites:
        sites[site.display] = site.id

    return device_types, roles, sites


mapping = [
    ["Datacenter 1", "name", "dc1-*"],
    ["Datacenter 2", "name", "c2-*"], 
    ["Datacenter 1", "location", "Verne"], 
    ["Datacenter 2", "location", "Fortress*"],
    ["XXX", "ip", "172.21.42.0/24"]
]
def match_site(name, ip=None, location=None):

    for site, field, pattern in mapping:
        
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            print(f"Invalid pattern {pattern}") 
            continue
                
        # print(type(location), location)


        if field == "ip":
            try:
                network = ip_network(pattern)
                if isinstance(network, IPv4Network):
                    ip_addr = ip_address(ip)
                if ip_addr in network:
                    return site
            except ValueError:
                print(f"Invalid network: {pattern}")
                continue

        if field == "location": 
            if location:
                location = location.replace("|", " ")
                if regex.search(location):
                    print(site, location)
                    return site


        if field == "name" and regex.search(name):
            print(site, name)  
            return site

    return None

    # return None
            # if field == "location" and re.search(".*verne.*", "Verne", re.IGNORECASE):
            #     print("GAY!!")
        # if field == "location" and re.search(pattern, location, re.IGNORECASE):
        #     return site
        
        # if field == "name" and re.search(pattern, name):  
        #     return site
        
        # if field == "ip" and re.search(pattern, ip):  
        #     return site
        
    return None

def create_devices(nb, ldevices, device_types, roles, sites):

    # print(find_closest_id('FGT_1800F', device_types))
    # print(roles)
    # print(sites)

    for name, value in ldevices.items():
        device_type_id = find_closest_id(value['device_type'], device_types, 4)
        role_id = find_closest_id(value['device_role'], roles, 2)
        
        # print(name, value["mgmt_ip"], value["location"])
        site_id = match_site(name, value["mgmt_ip"], value["location"])

        # print(f" {value['device_type']} -- {device_type_id}")
        # print(f" {name} : {value['device_role']} -- {role_id}")
        # print(f" {name} : {value['site']} -- {site_id}")

    
        # print(f"type: {device_type_id}  role: {role_id},  site: {site_id}")

        # nb.dcim.devices.create(
        #     name=name,
        #     device_type=device_type_id,
        #     device_role=role_id,  
        #     site=site_id,
        #     # other attrs
        # )

# def find_closest_value(search_string, variable_names, threshold=5):
#     matches = []
#     for name in variable_names:
#         match = find_near_matches(search_string, name, max_l_dist=1)
#         if match:
#             matches.append((name, match[0].dist))

#     matches.sort(key=lambda x: x[1]) # Sort matches by distance

#     if 0 < len(matches) < threshold:
#         return matches[0][0]
    
#     return None

def find_closest_id(search_string, lookup_dict, threshold=5):
    if not search_string:
        return None
    
    search = clean_string(search_string)

    matches = []
    for name in lookup_dict:
        lookup = clean_string(name)
        match = find_near_matches(search, lookup, max_l_dist=1)
        if match:
            matches.append((name, match[0].dist))

    matches.sort(key=lambda x: x[1]) # Sort matches by distance

    if matches and (matches[0][1] == 0 or (0 < len(matches) < threshold)):
        return lookup_dict[matches[0][0]]
    
    return None

def clean_string(string):
    ignore_words = ["Chassis", "Nexus"]
    string = re.sub("|".join(ignore_words) , "", string, flags=re.I)
    return string.replace("_", " ").replace("-", " ").replace(",", " ")


def get_normalized_librenms(lnms) -> dict:
    result = {}
    for device in lnms.list_devices():
        name = str(device["sysName"]).split(".")[0]
        name = name.casefold()
        result[name] = {
                    "full_name": device["sysName"],
                    #"libre_id": device["device_id"],
                    "mgmt_ip": device["ip"],
                    "device_type": device["hardware"],
                    "serial": device["serial"],
                    "location": device["location"],
                    "device_role": device["type"],
        }
    return result

def main():
    lnms = LibreNMSAPIClient()
    nb = connect_to_netbox()
    #nb.http_session.verify = False #if netbox has no cert



    # Cache lookups  
    device_types, roles, sites = cache_dicts(nb)
    ldevices = get_normalized_librenms(lnms)

    ### WORKS:
    # search_term = 'S-C290X-48FPD-L'
    # closest_matches = find_closest_id(search_term, device_types)
    # print(closest_matches)

    #TEST PRINTS
    # print(ldevices)
    # print(device_types)
    # print(roles)
    # print(sites)

    # Create devices
    create_devices(nb, ldevices, device_types, roles, sites)

    

if __name__ == "__main__":
    main()