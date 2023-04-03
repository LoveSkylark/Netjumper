#!/usr/bin/python

"""
This code will return a pdf file that represents the data of our network,
automatically generated from cdp & lldp data.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from  Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient

import graphviz
import csv

lnms = LibreNMSAPIClient()

# making log file
log_dir = os.environ['log_dir']
if not os.path.exists(log_dir): 
    os.makedirs(log_dir)

log_file = log_dir + "librenms_config_downloader.log"

logging.basicConfig (
    level = logging.INFO,
    format = "%(asctime)s:%(levelname)s - %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
    handlers = [
        RotatingFileHandler(
        log_file,
        maxBytes = 5*1024*1024,
        backupCount = 10
        )
    ]
)

devices = lnms.list_devices()
ports = lnms.get_all_ports()
links = lnms.list_links()

def write_a_list_of_unknow_neighbours(_devices, _links, _ports):
    reply = []
    remote_match =[]
    local_match = [i['sysName'].lower().split('.', 1)[0] for i in _devices if isinstance(i, dict)]
    
    for value in _links:
        if isinstance(value, dict):
            remote_list = value['remote_hostname']
            try:
                start_index = remote_list.index("(")
                end_index = remote_list.rindex(")")
                remote_list = remote_list[:start_index] + remote_list[end_index + 1:]
            except:
                pass
            remote_match.append(remote_list.lower().split('.', 1)[0])

    print (local_match)
    print("-----")
    print (remote_match)

    # for value in remote_match:
    #     if value in local_match:
   
            
    #     id = value['local_device_id']
    #     # print(id)
    #     # print (value['sysName'])
    #     # print(devices[value[id]]['sysName'])

            # reply.append([
            #     # devices[value['local_device_id']]['sysName'] if value['local_device_id'] in devices else "", 
            #     # ports[value['local_port_id']]['ifName'] if value['local_port_id'] in ports else "", 
            #     remote_list
            # ])
    # print(reply)
    return(reply)


print (write_a_list_of_unknow_neighbours(devices, links , ports))


# print (devices[15]['sysName'])

                # print(remote_match, " NOT IN ", local_match)
    #                     # print (_devices[43]['sysName'])
    #                     #print(_devices[value['local_device_id']])
                
    #                     # reply.append([
    #                     #     devices[value['local_device_id']]['sysName'], 
    #                     #     #_ports[value['local_port_id']]['ifName'], 
    #                     #     remote_list
    #                     #     ])
#     return(reply)


# # devices = get_list_from_API('devices','device_id','devices')
# devices = lnms.list_devices()
# # print (devices.43)

# ports = lnms.get_all_ports()
# # links = get_list_from_API('resources/links','id','links')
# links = lnms.list_links()

# # # TEST
# # for i in devices:
# #     print(i)





# draw = graphviz.Digraph('G', filename='xdp', format='svg')sss
# draw.attr(rankdir='LR')
# draw.attr('node', shape='box')
# draw.attr(ranksep='20')

# draw_a_list_of_unknow_neighbours(devices, links)

# draw.render()

# # opening the csv file in 'w+' mode
# file = open('xdp.csv', 'w+', newline ='')

# # writing the data into the file
# with file:   
#     write = csv.writer(file)
#     write.writerows(write_a_list_of_unknow_neighbours(devices, links))




# print(write_a_list_of_unknow_neighbours(devices, links, ports))

