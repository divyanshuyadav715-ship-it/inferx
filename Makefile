.PHONY: build up down logs load-test

# Builds the multi-stage Docker images for the Gateway and Workers
build:
	docker-compose build

# Spins up the Redis broker, Gateway, and scales Python workers horizontally
up:
	docker-compose up -d --scale worker=3

# Tears down the system and removes persistent volumes
down:
	docker-compose down -v

# Tails the logs of the entire stack
logs:
	docker-compose logs -f

# Runs the Locust load-testing script headlessly
load-test:
	locust -f locustfile.py --headless -u 1000 -r 50 --run-time 1m --host http://localhost:8080
