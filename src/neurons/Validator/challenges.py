# src/neurons/Validator/challenges.py
import logging
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class ChallengeType(Enum):
    COMPUTE = "compute"
    MEMORY = "memory"

@dataclass
class Challenge:
    type: ChallengeType
    command: str
    duration: int
    expected_values: Dict[str, float]

class ChallengeGenerator:
    def __init__(self):
        self.active_challenges: Dict[str, Challenge] = {}
        
    def generate_challenge(self, container_id: str) -> Dict[str, Any]:
        """Generate a new challenge for a container."""
        try:
            challenge_type = random.choice([ChallengeType.COMPUTE, ChallengeType.MEMORY])
            challenge = self._create_challenge(challenge_type)
            self.active_challenges[container_id] = challenge
            
            return {
                "type": challenge.type.value,
                "data": {
                    "command": challenge.command,
                    "duration": challenge.duration,
                    **challenge.expected_values
                }
            }
        except Exception as e:
            logger.error(f"Challenge generation failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _create_challenge(self, challenge_type: ChallengeType) -> Challenge:
        if challenge_type == ChallengeType.COMPUTE:
            return Challenge(
                type=ChallengeType.COMPUTE,
                command="stress-ng --cpu 2 --cpu-method all --timeout 15s",
                duration=15,
                expected_values={"expected_cpu": 80.0}
            )
        else:
            memory_mb = 256
            return Challenge(
                type=ChallengeType.MEMORY,
                command=f"stress-ng --vm 2 --vm-bytes {memory_mb}M --vm-method all --timeout 15s",
                duration=15,
                expected_values={"expected_memory": memory_mb * 1024 * 1024}
            )

    def get_active_challenge(self, container_id: str) -> Optional[Challenge]:
        """Retrieve the active challenge for a container."""
        return self.active_challenges.get(container_id)

# src/neurons/Validator/verification.py
import logging
from dataclasses import dataclass
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

@dataclass
class VerificationResult:
    success: bool
    details: Dict[str, Any]
    message: str

class Verifier:
    def __init__(self):
        self.verifications: Dict[str, List[VerificationResult]] = {}
        
    def verify_resource_usage(self, container_id: str, result: Dict[str, Any]) -> VerificationResult:
        try:
            if result["status"] != "success":
                return VerificationResult(
                    success=False,
                    details={},
                    message=f"Challenge failed: {result.get('message', 'Unknown error')}"
                )

            metrics = result.get("metrics", {})
            challenge_type = result.get("type")

            if not self._validate_metrics(metrics):
                return VerificationResult(
                    success=False,
                    details={},
                    message="Invalid or missing metrics"
                )

            if challenge_type == "compute":
                success, details = self._verify_compute_usage(metrics)
            elif challenge_type == "memory":
                success, details = self._verify_memory_usage(metrics)
            else:
                return VerificationResult(
                    success=False,
                    details={},
                    message=f"Unknown challenge type: {challenge_type}"
                )

            result = VerificationResult(
                success=success,
                details=details,
                message="Verification successful" if success else "Resource usage below threshold"
            )
            
            self._store_verification(container_id, result)
            return result

        except Exception as e:
            logger.error(f"Resource verification failed: {str(e)}")
            return VerificationResult(
                success=False,
                details={},
                message=f"Verification error: {str(e)}"
            )

    def _validate_metrics(self, metrics: Dict[str, Any]) -> bool:
        required_fields = ['cpu_usage', 'memory_usage', 'memory_limit', 'memory_percent']
        return all(field in metrics for field in required_fields)

    def _verify_compute_usage(self, metrics: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        cpu_usage = metrics.get("cpu_usage", 0)
        success = cpu_usage > 50.0
        return success, {
            "cpu_usage": cpu_usage,
            "threshold": 50.0
        }

    def _verify_memory_usage(self, metrics: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        try:
            memory_percent = metrics.get("memory_percent", 0)
            success = memory_percent >= 15.0
            return success, {
                "memory_percent": memory_percent,
                "threshold": 15.0,
                "memory_usage": metrics.get("memory_usage", 0),
                "memory_limit": metrics.get("memory_limit", 0)
            }
        except Exception as e:
            logger.error(f"Memory verification failed: {str(e)}")
            return False, {}

    def _store_verification(self, container_id: str, result: VerificationResult):
        if container_id not in self.verifications:
            self.verifications[container_id] = []
        self.verifications[container_id].append(result)

    def get_verification_history(self, container_id: str) -> List[VerificationResult]:
        """Retrieve verification history for a container."""
        return self.verifications.get(container_id, [])