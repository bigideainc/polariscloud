# tests/test_allocation.py
import json

import requests


def test_allocation():
    # Test data
    data = {
        "memory": "0.5g",
        "cpu_count": 2
    }

    try:
        print("Sending allocation request...")
        response = requests.post(
            'http://localhost:8080/allocate', 
            json=data,
            headers={'Content-Type': 'application/json'}
        )

        print("\nResponse Status Code:", response.status_code)
        print("\nResponse Headers:")
        for header, value in response.headers.items():
            print(f"{header}: {value}")

        # Attempt to parse JSON response
        result = response.json()
        print("\nResponse Body:")
        print(json.dumps(result, indent=2))

        # Check if the request was successful
        if result.get("status") == "success":
            print("\nSSH Connection Details:")
            host = result.get("host", "Unknown")
            username = result.get("username", "root")
            password = result.get("password", "Unknown")
            ports = result.get("ports", {})

            # Attempt to extract the SSH port (commonly bound to "22/tcp")
            ssh_port = ports.get("22/tcp")
            if ssh_port:
                print(f"Host: {host}")
                print(f"Port: {ssh_port}")
                print(f"Username: {username}")
                print(f"Password: {password}")
                print("\nTo connect:")
                print(f"ssh {username}@{host} -p {ssh_port}")
            else:
                print("No SSH port found in the ports dictionary.")
        else:
            print("Allocation failed or returned an unexpected status.")

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print("Raw response:", response.text)

if __name__ == "__main__":
    test_allocation()
