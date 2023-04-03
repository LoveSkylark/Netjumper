# #!/usr/bin/python3

# import os
# import sys
# from dotenv import load_dotenv
# from datetime import datetime
# from Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient
# from arya.session import Session

# # API connect to LibreNMS
# lnms = LibreNMSAPIClient()

# def connect_to_apic():
#     apic_url = "https://10.227.0.13/"
#     apic_user = "stefan.sigurdsson"
#     apic_password = ""

#     if None in [apic_url, apic_user, apic_password]:
#         load_dotenv()
#         apic_url = os.environ.get('APIC_URL')
#         apic_user = os.environ.get('APIC_user')
#         apic_password = os.environ.get('APIC_password')

#     try:
#         session = Session(apic_url, apic_user, apic_password)
#         apic = session.login()
#         return apic
#     except Exception as e:
#         print(f"Error: {e}")
#         sys.exit(1)

# apic = connect_to_apic()
# tenants = apic.get("tagInst")

# for tenant in tenants:
#     print(tenant)

##### COBRA 

#!/usr/bin/python3

import os
import sys
from dotenv import load_dotenv
from Libs.LibreNMSAPIClient.LibreNMSAPIClient import LibreNMSAPIClient
from cobra.mit.access import MoDirectory
from cobra.mit.session import LoginSession
from cobra.model.fv import Tenant

# API connect to LibreNMS
lnms = LibreNMSAPIClient()

def connect_to_apic():
    apic_url = "https://10.227.0.13/"
    apic_user = "stefan.sigurdsson"
    apic_password = ""

    if None in [apic_url, apic_user, apic_password]:
        load_dotenv()
        apic_url = os.environ.get('APIC_URL')
        apic_user = os.environ.get('APIC_user')
        apic_password = os.environ.get('APIC_password')

    login_session = LoginSession(apic_url, apic_user, apic_password)
    mo_dir = MoDirectory(login_session)
    mo_dir.login()

    return mo_dir

mo_dir = connect_to_apic()
tenants = mo_dir.lookupByClass(Tenant)

for tenant in tenants:
    print(tenant.name)
