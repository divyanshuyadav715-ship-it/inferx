import json
from locust import HttpUser, task, between

# A minimal 1x1 pixel base64 encoded PNG image
# This simulates a realistic request payload size structure while minimizing memory overhead in Locust
DUMMY_IMAGE_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

class InferenceUser(HttpUser):
    # Wait time between requests for each user is dynamically randomized
    wait_time = between(0.1, 0.5)

    @task
    def predict(self):
        payload = {
            "image_base64": DUMMY_IMAGE_BASE64
        }
        headers = {'Content-Type': 'application/json'}
        
        # Post the request to the Spring Boot Gateway
        with self.client.post("/api/predict", data=json.dumps(payload), headers=headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}: {response.text}")
