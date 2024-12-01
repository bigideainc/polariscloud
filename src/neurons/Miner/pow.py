import hashlib
import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ProofOfWork:
    def __init__(self, difficulty: int = 4):
        self.difficulty = difficulty
        self.target = "0" * difficulty

    def create_challenge(self) -> Dict[str, str]:
        timestamp = str(time.time())
        return {
            "timestamp": timestamp,
            "challenge": hashlib.sha256(timestamp.encode()).hexdigest()
        }

    def verify_solution(self, challenge: str, solution: str) -> bool:
        try:
            hash_result = hashlib.sha256(solution.encode()).hexdigest()
            return hash_result.startswith(self.target)
        except Exception as e:
            logger.error(f"Verification failed: {str(e)}")
            return False