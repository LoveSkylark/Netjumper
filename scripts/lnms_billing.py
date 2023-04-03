#!/usr/bin/python3

import os
import sys
from dotenv import load_dotenv
from datetime import datetime
from Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient

# API connect to LibreNMS
lnms = LibreNMSAPIClient()

def get_argument(index):
    if len(sys.argv) > index:
        return sys.argv[index]
    else:
        return None

def list_bills():
    bills = lnms.list_bills()
    template = "{0:20} {1:0} {2:20} {3:0} {4:0}"
    for bill in bills:
        if 'ISP:' not in bill['bill_name']:
            # formatted_95th = "{:.2f} Mbps".format(bill['rate_95th']/1000000)
            # print(template.format( bill['bill_name'] , formatted_95th))

            formatted_95th = "{:.2f} Mbps".format(bill['rate_95th']/1000000)
            if bill['overuse'] != '-':
                #formatted_over = "{:.2f} Mbps".format(bill['bill_overuse']/1000000)
                print(template.format(bill['bill_name'], "95th:", formatted_95th, "over:", bill['overuse']))
            else:
                print(template.format(bill['bill_name'], "95th:", formatted_95th, "",""))

def get_bill_id_from_name(_customer):
    for bill in lnms.list_bills():
        if bill['bill_name'] == _customer:
            return(bill['bill_id'])


def list_bill_history(_bill_id):
    bill_history = lnms.get_bill_history(_bill_id)
    template = "{0:20} {1:0} {2:20} {3:0} {4:20}"
    for bill in bill_history:
        formatted_95th = "{:.2f} Mbps".format(bill['rate_95th']/1000000)
        formatted_date = datetime.strptime(bill['bill_datefrom'][:10], "%Y-%m-%d").strftime("%B %Y")
        if bill['bill_overuse'] > 0:
            formatted_over = "{:.2f} Mbps".format(bill['bill_overuse']/1000000)
            print(template.format(formatted_date, "95th:", formatted_95th, "over:", formatted_over))
        else:
            print(template.format(formatted_date, "95th:", formatted_95th, "",""))

def librenms_info():
    if get_argument(1):
        bill_id = get_bill_id_from_name(get_argument(1))
        if bill_id:
            print(f"Customer: {get_argument(1)}\n")
            list_bill_history(bill_id)
        else:
            print("Customer not found!")
    else:
        list_bills()


librenms_info()
