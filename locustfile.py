from locust import HttpUser, task, between


class MCPUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def get_estimated_fare(self):
        payload = {
            "tool": "get_estimated_fare",
            "start_loc": "Chennai",
            "destination_loc": "Bangalore"
        }

        self.client.post(
            "/api/tool-call",
            json=payload
        )

    @task(2)
    def get_cab_availability(self):
        payload = {
            "tool": "get_cab_availability",
            "operator_mobile": "9876543210"
        }

        self.client.post(
            "/api/tool-call",
            json=payload
        )