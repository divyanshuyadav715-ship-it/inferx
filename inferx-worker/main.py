import asyncio
import base64
import json
import time
import io
import uuid
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from PIL import Image
import torch
from torchvision import models, transforms
import redis.asyncio as redis
from redis.exceptions import ResponseError

import os

# --- Configuration ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_SSL = os.getenv("REDIS_SSL", "False").lower() in ("true", "1", "yes")
STREAM_NAME = "inferx_tasks"
GROUP_NAME = "inferx_group"
# Unique consumer name for this instance
CONSUMER_NAME = f"worker-{socket.gethostname()}-{uuid.uuid4().hex[:6]}"

MAX_BATCH_SIZE = 16
MAX_BATCH_TIME_MS = 50

# PyTorch setup
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = None
preprocess = None

async def setup_model():
    """Load the ML model (ResNet50) into memory/VRAM."""
    global model, preprocess
    print(f"Loading ResNet50 model onto {device}...")
    model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
    model.to(device)
    model.eval()
    
    preprocess = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    print("Model initialized and ready.")

async def process_batch(r, stream_entries):
    """Process a batch of messages pulled from the Redis stream."""
    if not stream_entries:
        return
        
    tensors = []
    message_ids = []
    req_ids = []
    
    # Extract messages from stream format: [(stream_name, [(msg_id, {field: value})])]
    messages = stream_entries[0][1]
    
    for i, (msg_id, msg_data) in enumerate(messages):
        try:
            # Parse JSON payload pushed by the Java Gateway
            payload = json.loads(msg_data[b'payload'].decode('utf-8'))
            req_id = payload['id']
            
            # Assume image_base64 is provided in the JSON
            image_data = base64.b64decode(payload['image_base64'])
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
            tensor = preprocess(image)
            
            tensors.append(tensor)
            message_ids.append(msg_id)
            req_ids.append(req_id)
        except Exception as e:
            print(f"Error parsing message {msg_id}: {e}")
            # Fault Tolerance: acknowledge invalid messages so they aren't stuck in pending state
            await r.xack(STREAM_NAME, GROUP_NAME, msg_id)
            
    if not tensors:
        return
        
    try:
        # 2. Dynamic batching logic applied to messages pulled from Redis
        batch_tensor = torch.stack(tensors).to(device)
        
        # Inference
        with torch.no_grad():
            outputs = model(batch_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            confidences, class_ids = torch.max(probabilities, 1)
            
        # 4. Result Handling: save results and trigger PUBLISH in an atomic pipeline
        pipeline = r.pipeline()
        for i in range(len(tensors)):
            req_id = req_ids[i]
            msg_id = message_ids[i]
            
            result_json = json.dumps({
                "class_id": class_ids[i].item(),
                "confidence": confidences[i].item()
            })
            
            # HSET: Save to Redis Hash keyed by Request ID
            pipeline.hset(f"result:{req_id}", mapping={"data": result_json})
            # PUBLISH: Notify the Java Gateway that this specific task is done
            pipeline.publish(f"channel:{req_id}", "done")
            # 3. Fault Tolerance: XACK only upon successful inference
            pipeline.xack(STREAM_NAME, GROUP_NAME, msg_id)
            
        await pipeline.execute()
        print(f"Successfully processed and XACKed batch of size {len(tensors)}")
        
    except Exception as e:
        print(f"Inference error during batch execution: {e}")
        # We do NOT XACK here. If the worker crashes, the janitor will reclaim these messages.

async def consumer_loop():
    """Background Redis Stream consumer using XREADGROUP."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, password=REDIS_PASSWORD, ssl=REDIS_SSL)
    
    # Initialize the consumer group if it doesn't exist
    try:
        await r.xgroup_create(STREAM_NAME, GROUP_NAME, id='0', mkstream=True)
        print(f"Created consumer group '{GROUP_NAME}' on stream '{STREAM_NAME}'")
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            print(f"Error creating group: {e}")
            
    print(f"Python Worker {CONSUMER_NAME} started listening to stream...")
    
    while True:
        try:
            # 2. Consumer Groups (XREADGROUP) allow parallel consumers.
            # We block up to MAX_BATCH_TIME_MS to dynamically batch requests.
            entries = await r.xreadgroup(
                groupname=GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams={STREAM_NAME: ">"},
                count=MAX_BATCH_SIZE,
                block=MAX_BATCH_TIME_MS
            )
            
            if entries:
                await process_batch(r, entries)
                
        except Exception as e:
            print(f"Error in consumer loop: {e}")
            await asyncio.sleep(1)

async def janitor_loop():
    """3. Fault Tolerance: Background loop to recover stalled messages."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, password=REDIS_PASSWORD, ssl=REDIS_SSL)
    print("Janitor loop started.")
    
    while True:
        try:
            # XAUTOCLAIM recovers messages stuck in pending state for > 60 seconds
            # Result contains: next_start_id, messages, deleted_message_ids
            result = await r.xautoclaim(
                name=STREAM_NAME,
                groupname=GROUP_NAME,
                consumername=CONSUMER_NAME,
                min_idle_time=60000,
                start_id='0',
                count=MAX_BATCH_SIZE
            )
            messages = result[1]
            if messages:
                print(f"Janitor reclaimed {len(messages)} stalled messages from dead workers!")
                await process_batch(r, [(STREAM_NAME, messages)])
        except Exception as e:
            print(f"Error in janitor loop: {e}")
        
        # Run the janitor process every 30 seconds
        await asyncio.sleep(30)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Started dummy health check server on port {port} for Render")
    server.serve_forever()

async def main():
    # Start the dummy HTTP server in a background thread for Render
    threading.Thread(target=start_health_server, daemon=True).start()
    
    await setup_model()
    
    # Run consumer and janitor loops concurrently
    consumer_task = asyncio.create_task(consumer_loop())
    janitor_task = asyncio.create_task(janitor_loop())
    
    await asyncio.gather(consumer_task, janitor_task)

if __name__ == "__main__":
    # Removed FastAPI/uvicorn. Worker now runs purely as an async daemon.
    asyncio.run(main())
