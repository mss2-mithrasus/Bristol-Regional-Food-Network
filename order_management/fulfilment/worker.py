import os
import asyncio
from dotenv import load_dotenv
from pyzeebe import ZeebeWorker, Job, create_camunda_cloud_channel

# Load env
load_dotenv()

CLIENT_ID = os.getenv("ZEEBE_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZEEBE_CLIENT_SECRET")
CLUSTER_ID = os.getenv("ZEEBE_CLUSTER_ID")
REGION = os.getenv("ZEEBE_REGION", "lhr-1")

if not CLIENT_ID or not CLIENT_SECRET or not CLUSTER_ID:
    raise RuntimeError("Missing Camunda credentials")

# --- Handlers ---

async def handle_validate_order(job: Job):
    print("🔥 JOB RECEIVED: validate-order")
    print(job.variables)
    return {"isValid": True}

async def handle_prepare_delivery(job: Job):
    print("🔥 JOB RECEIVED: prepare-delivery")
    return {"deliveryPrepared": True}

async def handle_deliver_order(job: Job):
    print("🔥 JOB RECEIVED: deliver-order")
    return {"delivered": True}

async def handle_prepare_collection(job: Job):
    print("🔥 JOB RECEIVED: prepare-collection")
    return {"collectionReady": True}

# --- Main ---

async def main():
    print("🔌 Creating channel...")

    channel = create_camunda_cloud_channel(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        cluster_id=CLUSTER_ID,
        region=REGION,
    )

    print("✅ Channel created")

    worker = ZeebeWorker(channel)

    worker.task("validate-order")(handle_validate_order)
    worker.task("prepare-delivery")(handle_prepare_delivery)
    worker.task("deliver-order")(handle_deliver_order)
    worker.task("prepare-collection")(handle_prepare_collection)

    print("🚀 Worker started...")
    await worker.work()

if __name__ == "__main__":
    asyncio.run(main())