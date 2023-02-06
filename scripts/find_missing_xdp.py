#!/usr/bin/python

"""
This code will return a pdf file that represents the data of our network,
automatically generated from cdp & lldp data.
"""

import requests
import configparser
import graphviz
import csv

config = configparser.ConfigParser()
config.read('config.ini')

lnms_api      = config['librenms']['api_host']
lnms_token    = config['librenms']['api_token']

request_headers = {
    "X-Auth-Token": lnms_token,
}

def get_list_from_API(api_path, api_id, api_data):
    """ retrive a flaten list from an API call """
    get_api_list = requests.get(url=lnms_api+'/api/v0/'+api_path, headers=request_headers).json()
    # flatten response
    reply = {subdict[api_id] : subdict for subdict in get_api_list[api_data]}
    return(reply)

def search_device_id(_id):
    """ return the actual sysname from a given device id """
    sysname = devices[_id]['sysName']
    return(sysname)

def make_a_list_of_values(_source, _value):
    reply = []
    for key, value in _source.items():
        if isinstance(value, dict):
            reply.append(value[_value])
    return(reply)

def clean_host_list(_list):
    reply = []
    for value in _list:
        if value not in reply:
            reply.append(value.split(".", 1)[0])
    return(reply)

def draw_a_list_of_unknow_neighbours(_devices, _links):
    local_list = make_a_list_of_values(_devices, 'sysName')

    for key, value in _links.items():
        if isinstance(value, dict):
            remote_list = value['remote_hostname']
            try:
                start_index = remote_list.index("(")
                end_index = remote_list.rindex(")")
            except:
                pass
            else:
                remote_list = remote_list[:start_index] + remote_list[end_index + 1:]
            
            remote_list = remote_list.lower()
                    
            if remote_list not in local_list:
                draw.edge(devices[value['local_device_id']]['sysName'], remote_list[:16])

def write_a_list_of_unknow_neighbours(_devices, _links):
    reply = []
    local_list = make_a_list_of_values(_devices, 'sysName')

    local_match = clean_host_list(local_list)
    local_match.append("not advertised")

    for key, value in _links.items():
        if isinstance(value, dict):
            remote_list = value['remote_hostname']
            try:
                start_index = remote_list.index("(")
                end_index = remote_list.rindex(")")
            except:
                pass
            else:
                remote_list = remote_list[:start_index] + remote_list[end_index + 1:]
            
            remote_list = remote_list.lower()

            try:
                remote_match = remote_list.split(".", 1)[0]
            except:
                remote_match = remote_list

            if remote_match not in local_match:
                reply.append([
                    devices[value['local_device_id']]['sysName'], 
                    ports[value['local_port_id']]['ifName'], 
                    remote_list
                    ])
    return(reply)


# get all devices
devices = get_list_from_API('devices','device_id','devices')
# get all ports
ports = get_list_from_API('ports','port_id','ports')
# get all links (xdp)
links = get_list_from_API('resources/links','id','links')


draw = graphviz.Digraph('G', filename='xdp', format='svg')
draw.attr(rankdir='LR')
draw.attr('node', shape='box')
draw.attr(ranksep='20')

draw_a_list_of_unknow_neighbours(devices, links)

draw.render()

# opening the csv file in 'w+' mode
file = open('xdp.csv', 'w+', newline ='')

# writing the data into the file
with file:   
    write = csv.writer(file)
    write.writerows(write_a_list_of_unknow_neighbours(devices, links))


# print(write_a_list_of_unknow_neighbours(devices, links))
