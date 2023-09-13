#!/usr/bin/python3

import os
import pynetbox
from dotenv import load_dotenv


def connect_to_netbox(netbox_url=None, api_token=None):
    if api_token is None and netbox_url is None:
            load_dotenv()
            netbox_url = os.environ['Netbox_URL']
            api_token = os.environ['Netbox__APIToken']
    return(pynetbox.api(url=netbox_url, token=api_token))


nb = connect_to_netbox()
#nb.http_session.verify = False


devices = {
    'dc2-mgmt01': {'full_name': 'dc2-mgmt01.man.basis', 'mgmt_ip': '172.21.142.11', 'platform_type': 'WS-C2960X-48FPD-L', 'serial': 'FOC2145T4LE', 'site': 'Verne, Reykjanesbaer', 'device_type': 'switch'}, 
    'dc2-mgmt02': {'full_name': 'dc2-mgmt02.man.basis', 'mgmt_ip': '172.21.142.12', 'platform_type': 'WS-C2960X-48FPD-L', 'serial': 'FCW2145B70H', 'site': 'Reykjanesbaer | Flugbraut 262 | Verne', 'device_type': 'switch'}, 
    'dc2-ytri-access-01': {'full_name': 'dc2-ytri-access-01.man.basis', 'mgmt_ip': '172.21.142.14', 'platform_type': 'WS-C2960X-48TD-L', 'serial': 'FCW2232B5W2', 'site': 'Verne', 'device_type': 'switch'}, 
    'dc2-ytri-access-02': {'full_name': 'dc2-ytri-access-02.man.basis', 'mgmt_ip': '172.21.142.15', 'platform_type': 'WS-C2960X-48TD-L', 'serial': 'FCW2232A56K', 'site': 'Verne', 'device_type': 'switch'}, 
}


for name, device in devices.items():
    existing = nb.dcim.devices.get(name=name)

    device_type=nb.dcim.device_types.get(part_number=device['platform_type'])
    device_role=nb.dcim.device_roles.get(slug=device['device_type'])
    #site=nb.dcim.sites.get(name=device['site'])
    site=nb.dcim.sites.get(name='Datacenter 1')

    # Device created with requiree values

    changed = False
    if not existing:
        nb.dcim.devices.create(
            name=name, 
            device_type=device_type.id,
            device_role=device_role.id,
            site=site.id,
        )
        print(f"Creating new device {name}")
    
    # Device require values modified
    else:
        if existing.device_type.id != device_type.id:
            existing.device_type.id = device_type.id
            changed = True
            print(f"{name}: {existing.device_type} -> {device_type}")

        if existing.device_role.id != device_role.id:
            existing.device_role.id = device_role.id
            changed = True
            print(f"{name}: {existing.device_role} -> {device_role}")

        if existing.site.id != site.id:
            existing.site.id = site.id
            changed = True
            print(f"{name}: {existing.site} -> {site}")

    # Other Device values modified

    # ## Check if primary IP is correct
    try:
        primary_ip4 = existing.primary_ip4.address
    except AttributeError:
        primary_ip4 = False
    device_ip = device['mgmt_ip'] + "/32"

    if primary_ip4 != device_ip:
        #print(existing.id)

        ### Create Interface if it is missing
        try:
            mgmt_iface = nb.dcim.interfaces.filter(device=existing.id, name='Management')

        except AttributeError:
            print("Creating managment interface for:", name)

            mgmt_iface = nb.dcim.interfaces.create(
                device=existing.id,
                name='Management',
                type='virtual'
            )

        ### Create IP if it is missing
        try:
            mgmt_ip = nb.ipam.ip_addresses.filter(address=device_ip)
            print('x')
        except AttributeError:

            print("Creating managment IP for:", name)

            nb.ipam.ip_addresses.create(
                address=device_ip,
                assigned_object=mgmt_iface.id 
            )




            
    #     ### change  IP if it is different
    #     elif mgmt_ip[0].address  != device['mgmt_ip']:
    #             nb.ipam.ip_addresses.update(
    #                 mgmt_ip[0].id,
    #                 address=device['mgmt_ip']  
    #             )
    #     else:
    #         # Primary IP already set correctly
    #         print(f"{existing.name} mgmt IP unchanged ({device['mgmt_ip']})")

    if existing.serial != device['serial']:
        existing.serial = device['serial']
        changed = True

    if changed:
        existing.save()
print("Devices created!")
