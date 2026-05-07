import asyncio
from pyzeebe import ZeebeClient, create_camunda_cloud_channel
import os
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("ZEEBE_CLIENT_ID")
client_secret = os.getenv("ZEEBE_CLIENT_SECRET")
cluster_id = os.getenv("ZEEBE_CLUSTER_ID")
region = os.getenv("ZEEBE_REGION", "lhr-1")

async def complete_job():
    channel = create_camunda_cloud_channel(
        client_id=client_id,
        client_secret=client_secret,
        cluster_id=cluster_id,
        region=region,
    )
    client = ZeebeClient(channel)
    # Replace with your actual job key from the JSON
    job_key = 2251799862101551
    variables = {"isValid": True}
    await client.complete_job(job_key, variables)
    print("Job completed manually")

asyncio.run(complete_job())
