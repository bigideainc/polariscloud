# tests/test_validator.py
import json
import os
import sys
import time

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.neurons.Validator.challenges import ChallengeGenerator
from src.neurons.Validator.scoring import ScoringSystem
from src.neurons.Validator.verification import Verifier


def get_latest_container():
    """First create a container if none exists"""
    test_data = {
        "memory": "2g",
        "cpu_count": 2
    }
    
    # Create a new container
    response = requests.post(
        'http://localhost:8080/allocate',
        json=test_data,
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 200:
        result = response.json()
        if result["status"] == "success":
            return result["container_id"]
    return None

def test_validator_flow():
    print("\nTesting Validator Components...")
    
    # Initialize components
    verifier = Verifier()
    scoring = ScoringSystem()
    challenge_gen = ChallengeGenerator()

    # 1. Get active container details
    print("\n1. Getting container details...")
    container_id = get_latest_container()
    if container_id:
        print(f"Found container: {container_id}")
    else:
        print("No container found. Creating new one...")
        container_id = get_latest_container()
        if not container_id:
            print("Failed to create container")
            return

    # Wait for container to fully start
    time.sleep(5)

    # 2. Generate challenge
    print("\n2. Generating challenge...")
    challenge = challenge_gen.generate_challenge(container_id)
    print(f"Challenge generated: {json.dumps(challenge, indent=2)}")

    # 3. Send challenge to container
    print("\n3. Sending challenge to container...")
    try:
        response = requests.put(
            f'http://localhost:8080/challenge/{container_id}',
            json=challenge,
            headers={'Content-Type': 'application/json'}
        )
        result = response.json()
        print(f"Challenge response: {json.dumps(result, indent=2)}")

        if result["status"] == "error":
            print(f"Error from server: {result['message']}")
            return

    except Exception as e:
        print(f"Error sending challenge: {e}")
        return

    # 4. Verify response
    print("\n4. Verifying response...")
    verification_result = verifier.verify_resource_usage(container_id, result)
    print(f"Verification result: {verification_result}")

    # 5. Calculate score
    print("\n5. Calculating score...")
    score = scoring.calculate_score(container_id, result)
    print(f"Final score: {score}")

if __name__ == "__main__":
    test_validator_flow()