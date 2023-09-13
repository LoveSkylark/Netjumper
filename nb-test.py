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

device_name = 'dc2-mgmt02'
interface_name = 'Managment'
device_ip = "9.9.9.9/32"


ip = nb.ipam.ip_addresses.create(
    address='192.0.2.1/32',
    status='active',
    description='Example IP',
    assigned_object_type='dcim.interface',
    assigned_object_id=123,
    tags=['foo', 'bar']
)