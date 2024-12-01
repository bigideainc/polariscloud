# tests/test_allocation.py
import json
import time

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
            
        print("\nResponse Body:")
        result = response.json()
        print(json.dumps(result, indent=2))
        
        if result["status"] == "success":
            print("\nSSH Connection Details:")
            print(f"Host: {result['host']}")
            print(f"Port: {result['ssh_port']}")
            print(f"Username: root")
            print(f"Password: {result['password']}")
            print("\nTo connect:")
            print(f"ssh root@{result['host']} -p {result['ssh_port']}")
        
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print("Raw response:", response.text)

if __name__ == "__main__":
    test_allocation()