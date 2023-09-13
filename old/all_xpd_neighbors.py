#!/usr/bin/python

"""
This code will return a pdf file that represents the data of our network,
automatically generated from cdp & lldp data.
"""

import requests
import configparser
import graphviz


config = configparser.ConfigParser()
config.read('config.ini')

lnms_api      = config['librenms']['api_host']
lnms_token    = config['librenms']['api_token']
log_file      = config['other']['log_file']
file_path     = config['other']['file_path']
hosts_dir     = config['other']['hosts_dir']


AUTH_TOKEN = config['librenms']['api_token']
DEVICES_API_URL = lnms_api+'/api/v0/devices'
PORTS_API_URL = lnms_api+'/api/v0/ports'
LINKS_API_URL = lnms_api+'/api/v0/resources/links'

request_headers = {
    "X-Auth-Token": AUTH_TOKEN,
}
# get all devices
resp_devices = requests.get(url=lnms_api+'/api/v0/devices', headers=request_headers)
data_devices = resp_devices.json()
# flatten response
devices = {subdict['device_id']
    : subdict for subdict in data_devices['devices']}


# print (devices)


# get all links (xdp)
resp_links = requests.get(url=LINKS_API_URL, headers=request_headers)
data_links = resp_links.json()
# flatten response
links = {subdict['id']: subdict for subdict in data_links['links']}

print (links)


# def search_device_id(_id):
#     """ return the actual hostname from a given device id """
#     hostname = devices[_id]['sysName']
#     return hostname

# f = graphviz.Digraph('G', filename='lldp', format='svg')
# f.attr(rankdir='LR')
# f.attr('node', shape='box')
# f.attr(ranksep='30', dpi='72', size='3000,30000')

# for key, value in links.items():
#     if isinstance(value, dict):
#         f.edge(search_device_id(
#             value['local_device_id']), value['remote_hostname'][:16])
# f.view()