from flask import Flask, render_template, send_file, Response
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.storage import StorageManagementClient
import csv
import io

app = Flask(__name__)

# Azure Credentials
TENANT_ID = "aefa267e-2783-4254-8760-523bc200d286"
CLIENT_ID = "0ae8647e-1988-4b1b-bd4e-494f4d2f2f8c"
CLIENT_SECRET = "PlH8Q~6I5gJylvUe8pP5Xj96gM8BrUABILx_Ua.9"
SUBSCRIPTION_ID = "a6cbacda-278f-4a18-bf27-b46cd749d2ac"

credential = ClientSecretCredential(
    tenant_id=TENANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET
)

resource_client = ResourceManagementClient(credential, SUBSCRIPTION_ID)
compute_client = ComputeManagementClient(credential, SUBSCRIPTION_ID)
network_client = NetworkManagementClient(credential, SUBSCRIPTION_ID)
storage_client = StorageManagementClient(credential, SUBSCRIPTION_ID)


# -------------------- DASHBOARD HOME PAGE --------------------
@app.route("/")
def index():

    total_vms = len(list(compute_client.virtual_machines.list_all()))
    total_vnets = len(list(network_client.virtual_networks.list_all()))
    total_subnets = sum([len(list(network_client.subnets.list(v.id.split("/")[4], v.name)))
                         for v in network_client.virtual_networks.list_all()])
    total_storage = len(list(storage_client.storage_accounts.list()))

    return render_template(
        "index.html",
        total_vms=total_vms,
        total_vnets=total_vnets,
        total_subnets=total_subnets,
        total_storage=total_storage
    )


# -------------------- VIRTUAL MACHINES PAGE --------------------
@app.route("/vms")
def virtual_machines():
    vms = []

    all_nics = list(network_client.network_interfaces.list_all())

    for vm in compute_client.virtual_machines.list_all():

        # OS Type
        os_type = None
        if vm.storage_profile and vm.storage_profile.os_disk:
            raw_os = vm.storage_profile.os_disk.os_type
            os_type = getattr(raw_os, "value", raw_os)

        plan_name = vm.plan.name if vm.plan else None
        vm_size = vm.hardware_profile.vm_size if vm.hardware_profile else "N/A"

        # Network Mapping
        vnet_name = "N/A"
        subnet_name = "N/A"
        ip_address = "N/A"

        for nic in all_nics:
            if nic.virtual_machine and nic.virtual_machine.id == vm.id:
                if nic.ip_configurations:
                    ip_config = nic.ip_configurations[0]
                    ip_address = ip_config.private_ip_address or "N/A"

                    if ip_config.subnet:
                        subnet_id = ip_config.subnet.id
                        subnet_name = subnet_id.split("/")[-1]
                        vnet_name = subnet_id.split("/")[8]

        vms.append({
            "name": vm.name,
            "location": vm.location,
            "os_type": os_type,
            "plan": plan_name,
            "size": vm_size,
            "vnet": vnet_name,
            "subnet": subnet_name,
            "ip_address": ip_address,
            "resource_group": vm.id.split("/")[4]
        })

    return render_template("vms.html", vms=vms)


# VM CSV Download
@app.route("/vms/download")
def download_vms():
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Name", "Location", "Size", "OS", "Plan", "VNET", "Subnet", "IP", "Resource Group"])

    all_nics = list(network_client.network_interfaces.list_all())

    for vm in compute_client.virtual_machines.list_all():

        os_type = None
        if vm.storage_profile and vm.storage_profile.os_disk:
            raw_os = vm.storage_profile.os_disk.os_type
            os_type = getattr(raw_os, "value", raw_os)

        plan_name = vm.plan.name if vm.plan else None
        vm_size = vm.hardware_profile.vm_size if vm.hardware_profile else "N/A"

        vnet = subnet = ip = "N/A"

        for nic in all_nics:
            if nic.virtual_machine and nic.virtual_machine.id == vm.id:
                if nic.ip_configurations:
                    ip = nic.ip_configurations[0].private_ip_address or "N/A"
                    if nic.ip_configurations[0].subnet:
                        sid = nic.ip_configurations[0].subnet.id
                        subnet = sid.split("/")[-1]
                        vnet = sid.split("/")[8]

        writer.writerow([vm.name, vm.location, vm_size, os_type, plan_name, vnet, subnet, ip, vm.id.split("/")[4]])

    return Response(output.getvalue(),
                    mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=virtual_machines.csv"})


# -------------------- VIRTUAL NETWORKS PAGE --------------------
@app.route("/vnets")
def virtual_networks():
    vnets = []
    for vnet in network_client.virtual_networks.list_all():
        vnets.append({
            "name": vnet.name,
            "location": vnet.location,
            "address_space": ", ".join(vnet.address_space.address_prefixes),
            "resource_group": vnet.id.split("/")[4]
        })
    return render_template("vnets.html", vnets=vnets)


@app.route("/vnets/download")
def download_vnets():
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Name", "Location", "Address Space", "Resource Group"])

    for vnet in network_client.virtual_networks.list_all():
        writer.writerow([
            vnet.name,
            vnet.location,
            ", ".join(vnet.address_space.address_prefixes),
            vnet.id.split("/")[4]
        ])

    return Response(output.getvalue(),
                    mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=virtual_networks.csv"})


# -------------------- SUBNETS PAGE --------------------
@app.route("/subnets")
def subnets():
    all_subnets = []
    for vnet in network_client.virtual_networks.list_all():
        for subnet in network_client.subnets.list(vnet.id.split("/")[4], vnet.name):
            all_subnets.append({
                "vnet": vnet.name,
                "subnet": subnet.name,
                "address_prefix": ", ".join(subnet.address_prefixes or []),
                "resource_group": vnet.id.split("/")[4]
            })
    return render_template("subnets.html", subnets=all_subnets)


@app.route("/subnets/download")
def download_subnets():
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Virtual Network", "Subnet", "Address Prefix", "Resource Group"])

    for vnet in network_client.virtual_networks.list_all():
        for subnet in network_client.subnets.list(vnet.id.split("/")[4], vnet.name):
            writer.writerow([
                vnet.name,
                subnet.name,
                ", ".join(subnet.address_prefixes or []),
                vnet.id.split("/")[4]
            ])

    return Response(output.getvalue(),
                    mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=subnets.csv"})


# -------------------- STORAGE ACCOUNTS PAGE --------------------
@app.route("/storage")
def storage_accounts():
    accounts = []
    for acc in storage_client.storage_accounts.list():

        access_tier = "N/A"
        try:
            props = storage_client.storage_accounts.get_properties(acc.id.split("/")[4], acc.name)
            access_tier = getattr(props, "access_tier", "N/A")
        except:
            pass

        accounts.append({
            "name": acc.name,
            "location": acc.location,
            "sku": acc.sku.name,
            "kind": acc.kind,
            "access_tier": access_tier,
            "resource_group": acc.id.split("/")[4]
        })

    return render_template("storage.html", accounts=accounts)


@app.route("/storage/download")
def download_storage():
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Name", "Location", "SKU", "Kind", "Access Tier", "Resource Group"])

    for acc in storage_client.storage_accounts.list():

        access_tier = "N/A"
        try:
            props = storage_client.storage_accounts.get_properties(acc.id.split("/")[4], acc.name)
            access_tier = getattr(props, "access_tier", "N/A")
        except:
            pass

        writer.writerow([
            acc.name,
            acc.location,
            acc.sku.name,
            acc.kind,
            access_tier,
            acc.id.split("/")[4]
        ])

    return Response(output.getvalue(),
                    mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=storage_accounts.csv"})


# --------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
