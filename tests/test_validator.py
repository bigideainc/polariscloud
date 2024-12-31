import json
import logging
import os
import sys
import time
from typing import Dict, Optional

import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.neurons.Validator.challenges import ChallengeGenerator
from src.neurons.Validator.scoring import ScoringSystem
from src.neurons.Validator.verification import Verifier


class ValidatorTester:
    def __init__(self):
        self.base_url = 'http://localhost:8080'
        self.verifier = Verifier()
        self.scoring = ScoringSystem()
        self.challenge_gen = ChallengeGenerator()

    def allocate_container(self) -> Optional[str]:
        """Allocate a new container for testing"""
        test_data = {
            "memory": "2g",
            "cpu_count": 2
        }

        try:
            response = requests.post(
                f'{self.base_url}/allocate',
                json=test_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get("status") == "success":
                logger.info(f"Container allocated: {result['container_id']}")
                return result["container_id"]
            
            logger.error(f"Container allocation failed: {result.get('message', 'Unknown error')}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to allocate container: {str(e)}")
            return None

    def send_challenge(self, container_id: str, challenge: Dict) -> Optional[Dict]:
        """Send a challenge to a container"""
        try:
            response = requests.put(
                f'{self.base_url}/challenge/{container_id}',
                json=challenge,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send challenge: {str(e)}")
            return None

    def run_validation_test(self) -> bool:
        """Run a complete validation test cycle"""
        logger.info("Starting validation test cycle...")

        # Step 1: Allocate container
        container_id = self.allocate_container()
        if not container_id:
            logger.error("Container allocation failed")
            return False

        # Wait for container to initialize
        logger.info("Waiting for container initialization...")
        time.sleep(5)

        try:
            # Step 2: Generate and send challenge
            logger.info("Generating challenge...")
            challenge = self.challenge_gen.generate_challenge(container_id)
            logger.info(f"Challenge generated: {json.dumps(challenge, indent=2)}")

            logger.info("Sending challenge to container...")
            result = self.send_challenge(container_id, challenge)
            if not result:
                logger.error("Failed to get challenge response")
                return False

            if result.get("status") == "error":
                logger.error(f"Error from container: {result.get('message')}")
                return False

            # Step 3: Verify response
            logger.info("Verifying challenge response...")
            verification_result = self.verifier.verify_resource_usage(container_id, result)
            logger.info(f"Verification result: {verification_result}")

            # Step 4: Calculate score
            logger.info("Calculating performance score...")
            score = self.scoring.calculate_score(container_id, result)
            logger.info(f"Final score: {score}")

            return verification_result.success and score > 0

        except Exception as e:
            logger.error(f"Validation test failed: {str(e)}")
            return False

def main():
    """Main test execution function"""
    logger.info("Starting validator component tests...")
    
    tester = ValidatorTester()
    success = tester.run_validation_test()
    
    if success:
        logger.info("Validator test completed successfully")
        sys.exit(0)
    else:
        logger.error("Validator test failed")
        sys.exit(1)

if __name__ == "__main__":
    main()