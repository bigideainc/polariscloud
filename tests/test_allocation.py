# tests/test_allocation.py
import json
import time

import requests


def test_allocation():
    # Test data with 2-minute duration
    data = {
        "memory": "0.5g",
        "cpu_count": 2,
        "duration": 60  # 2 minutes in seconds
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
            print("\nContainer Details:")
            print(f"Container ID: {result.get('container_id', 'Unknown')}")
            print(f"Duration: 2 minutes")
            print(f"Scheduled Termination: {result.get('scheduled_termination')} seconds")
            
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
                
                # Monitor container status until termination
                print("\nMonitoring container status...")
                container_id = result.get('container_id')
                monitor_start = time.time()
                
                while time.time() - monitor_start < 130:  # Monitor for slightly longer than duration
                    try:
                        status_response = requests.get(f'http://localhost:8080/containers')
                        containers = status_response.json().get("containers", [])
                        
                        # Find our container
                        container = next(
                            (c for c in containers if c['container_id'] == container_id),
                            None
                        )
                        
                        if container:
                            runtime_status = container.get('runtime_status', {})
                            elapsed = runtime_status.get('elapsed_time', 0)
                            remaining = runtime_status.get('remaining_time', 0)
                            
                            print(f"\rRuntime: {elapsed:.1f}s | Remaining: {remaining:.1f}s", end='')
                        else:
                            print("\nContainer has been terminated")
                            break
                            
                    except Exception as e:
                        print(f"\nError monitoring container: {e}")
                        break
                        
                    time.sleep(5)  # Check every 5 seconds
                
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