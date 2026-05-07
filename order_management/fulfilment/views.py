import requests
from django.shortcuts import redirect
from django.conf import settings

def submit_order(request):
    if request.method == "POST":
        # Extract form data
        delivery_date = request.POST.get("delivery_date")
        collection_date = request.POST.get("collection_date")
        method = request.POST.get("method")
        producer_id = request.POST.get("producer_id")

        # Convert to ISO 8601 for Camunda 8
        delivery_iso = f"{delivery_date}T00:00:00Z"
        collection_iso = f"{collection_date}T00:00:00Z"

        # Start Camunda 8 process
        url = f"https://api.camunda.io/{settings.CAMUNDA_CLUSTER_ID}/workflow/v1/process-instances"

        payload = {
            "bpmnProcessId": "order_process",
            "variables": {
                "delivery_date": delivery_iso,
                "collection_date": collection_iso,
                "method": method,
                "producer_id": int(producer_id)
            }
        }

        headers = {
            "Authorization": f"Bearer {settings.CAMUNDA_OAUTH_TOKEN}",
            "Content-Type": "application/json"
        }

        requests.post(url, json=payload, headers=headers)

        return redirect("order_success")
