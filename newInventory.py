from flask import Flask, render_template
import os
from collections import defaultdict

# Azure SDK imports
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient

app = Flask(__name__)
app.secret_key = "change-me"

# 🔹 Azure Credentials (replace these with your actual values)
TENANT_ID = "aefa267e-2783-4254-8760-523bc200d286"
CLIENT_ID = "0ae8647e-1988-4b1b-bd4e-494f4d2f2f8c"
CLIENT_SECRET = "PlH8Q~6I5gJylvUe8pP5Xj96gM8BrUABILx_Ua.9"
SUBSCRIPTION_ID = "a6cbacda-278f-4a18-bf27-b46cd749d2ac"

# 🔹 Create the credential object
credential = ClientSecretCredential(
    tenant_id=TENANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET
)

# 🔹 Function to fetch all resources for the given subscription
def get_azure_inventory():
    resource_client = ResourceManagementClient(credential, SUBSCRIPTION_ID)
    resources = []
    for res in resource_client.resources.list():
        resources.append({
            "subscription_id": SUBSCRIPTION_ID,
            "resource_name": res.name,
            "resource_type": res.type,
            "location": getattr(res, "location", "N/A"),
            "id": res.id,
            "tags": dict(res.tags or {})
        })
    return resources

@app.route("/")
def index():
    try:
        resources = get_azure_inventory()
        counts = defaultdict(int)
        for r in resources:
            counts[(r["subscription_id"])] += 1
        return render_template("index.html", resources=resources, counts=counts, errors=None)
    except Exception as e:
        return render_template("index.html", resources=None, counts=None, errors=[str(e)])

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
