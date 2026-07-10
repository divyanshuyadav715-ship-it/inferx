# InferX - Scalable AI Serving Engine

![Java](https://img.shields.io/badge/Java-ED8B00?style=for-the-badge&logo=openjdk&logoColor=white)
![Spring Boot](https://img.shields.io/badge/Spring_Boot-F2F4F9?style=for-the-badge&logo=spring-boot)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)

**A high-performance, distributed deep learning inference gateway bridging Systems Engineering and Machine Learning.**

---

## 🎯 The "Why"
**The Problem:** Companies build incredible AI models, but serving them concurrently to thousands of users is a massive bottleneck. GPU memory is expensive, and routing high-volume HTTP traffic directly to Python inference scripts typically results in cascading timeouts and dropped connections.

**The Solution:** InferX decouples the client-facing API from the heavy GPU workers using an **event-driven Redis architecture**. It introduces **Dynamic Batching** at the worker level, seamlessly grouping individual incoming requests into a single tensor block for highly efficient parallel GPU execution, preventing timeouts and skyrocketing throughput.

---

## 🏗️ Architecture Flow

```mermaid
graph TD
    Client((Client)) -->|POST JSON| Gateway[Spring Boot Gateway Layer 7]
    Gateway -->|XADD Push| RedisStream[(Redis Stream: inferx_tasks)]
    
    subgraph PyTorch ML Workers
        Worker1[Worker 1]
        Worker2[Worker 2]
        Worker3[Worker 3]
    end
    
    RedisStream -->|XREADGROUP Pull| Worker1
    RedisStream -->|XREADGROUP Pull| Worker2
    RedisStream -->|XREADGROUP Pull| Worker3
    
    Worker1 -.->|HSET Result & PUBLISH| RedisPubSub((Redis Pub/Sub))
    Worker2 -.->|HSET Result & PUBLISH| RedisPubSub
    Worker3 -.->|HSET Result & PUBLISH| RedisPubSub
    
    RedisPubSub -.->|Wake up Gateway| Gateway
    Gateway -->|HTTP 200 OK| Client
```

---

## 🚀 Quickstart Guide

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/inferx.git
   cd inferx
   ```

2. **Start the distributed system via Docker Compose:**
   The `Makefile` makes this effortless. This will compile the Java Gateway, build the Python images, and spin up Redis and 3 scalable ML workers.
   ```bash
   make build
   make up
   ```

3. **Monitor the logs:**
   ```bash
   make logs
   ```

4. **Send a test inference request:**
   ```bash
   curl -X POST http://localhost:8080/api/predict \
        -H "Content-Type: application/json" \
        -d '{"image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="}'
   ```

5. **Tear down the system:**
   ```bash
   make down
   ```

---

## 📊 Benchmarking & Performance

We rigorously load-test the Gateway and Dynamic Batching logic using `locust` to prove the architecture scales under pressure.

### Running the Load Test
Ensure the stack is running (`make up`), install Locust locally (`pip install locust`), and run:
```bash
make load-test
```

### Metrics (1,000 Concurrent Users)
*Run the test locally and record your metrics here for your portfolio!*

| Metric | Result | Description |
|--------|--------|-------------|
| **Total Requests** | *TBD* | Total POST requests successfully served. |
| **Requests Per Second (RPS)** | *TBD* | The max throughput of the entire pipeline. |
| **p95 Latency** | *TBD ms* | Maximum latency for 95% of users. |
| **Failure Rate** | *0.00%* | Percentage of dropped/timed-out connections. |
