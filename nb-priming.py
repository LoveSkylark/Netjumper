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

def create_object(nb_object, list):
    for i in list:
        slug = i.lower().replace(' ', '-')  
        if not nb_object.get(slug=slug):
            nb_object.create(
            name=i,
            slug=slug, 
            )
            print(f"{i} created")
        else:
            print(f"{i} already exists - skipping")

device_roles = [
    'Appliance',
    'Collaboration', 
    'Environment',
    'Firewalls',
    'Load Balancers',
    'Network',
    'Printers',
    'Power',
    'Servers',
    'Storage', 
    'Wireless',
    'Workstation'
]

sites = [
  ('Site A', 'formula1'),
  ('Site B', 'formula3'),
  ('Site C', 'formuul4'),
]
site_names = [name for name, regex in sites]

regions = [
    'Region 1',
    'Region 2',
    'Region 3'
]

create_object(nb.dcim.sites, site_names)
create_object(nb.dcim.regions, regions)
create_object(nb.dcim.device_roles , device_roles)
        
print("Script complete!")