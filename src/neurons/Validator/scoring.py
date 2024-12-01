# src/neurons/Validator/scoring.py
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ScoringSystem:
    def __init__(self):
        self.scores = {}
        self.weights = {
            'resource_compliance': 0.4,
            'availability': 0.3,
            'performance': 0.3
        }

    def calculate_score(self, container_id: str, result: Dict[str, Any]) -> float:
        try:
            metrics = result.get('metrics', {})
            challenge_type = result.get('type')
            
            if not self._validate_metrics(metrics):
                logger.warning(f"Invalid metrics for container {container_id}")
                return 0.0

            # Calculate individual scores
            resource_score = self._calculate_resource_score(metrics)
            availability_score = self._calculate_availability_score(metrics)
            performance_score = self._calculate_performance_score(metrics, challenge_type)

            # Calculate weighted score
            final_score = (
                resource_score * self.weights['resource_compliance'] +
                availability_score * self.weights['availability'] +
                performance_score * self.weights['performance']
            )

            # Store score history
            if container_id not in self.scores:
                self.scores[container_id] = []
            self.scores[container_id].append(final_score)

            return final_score

        except Exception as e:
            logger.error(f"Score calculation failed: {str(e)}")
            return 0.0

    def _validate_metrics(self, metrics: Dict[str, Any]) -> bool:
        """Validate that all required metrics are present"""
        required_fields = ['cpu_usage', 'memory_usage', 'memory_limit', 'memory_percent']
        return all(field in metrics for field in required_fields)

    def _calculate_resource_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate score based on resource utilization"""
        try:
            # Check memory utilization
            memory_score = min(metrics['memory_percent'] / 20.0, 1.0)
            
            # Check CPU utilization
            cpu_score = min(metrics['cpu_usage'] / 80.0, 1.0)
            
            # Combined resource score
            return (memory_score + cpu_score) / 2

        except Exception as e:
            logger.error(f"Resource score calculation failed: {str(e)}")
            return 0.0

    def _calculate_availability_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate score based on availability metrics"""
        try:
            # Check if resources are within limits
            memory_within_limits = metrics['memory_usage'] <= metrics['memory_limit']
            cpu_within_limits = metrics['cpu_usage'] <= 100.0

            # Basic availability score
            if memory_within_limits and cpu_within_limits:
                return 1.0
            elif memory_within_limits or cpu_within_limits:
                return 0.5
            return 0.0

        except Exception as e:
            logger.error(f"Availability score calculation failed: {str(e)}")
            return 0.0

    def _calculate_performance_score(self, metrics: Dict[str, Any], challenge_type: str) -> float:
        """Calculate score based on performance metrics and challenge type"""
        try:
            if challenge_type == 'memory':
                # For memory challenges
                memory_percent = metrics.get('memory_percent', 0)
                return min(memory_percent / 20.0, 1.0)  # 20% usage = full score
            
            elif challenge_type == 'compute':
                # For compute challenges
                cpu_usage = metrics.get('cpu_usage', 0)
                return min(cpu_usage / 80.0, 1.0)  # 80% usage = full score
            
            return 0.0

        except Exception as e:
            logger.error(f"Performance score calculation failed: {str(e)}")
            return 0.0

    def get_score_history(self, container_id: str) -> list:
        """Get the score history for a container"""
        return self.scores.get(container_id, [])

    def get_average_score(self, container_id: str) -> float:
        """Calculate the average score for a container"""
        scores = self.scores.get(container_id, [])
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def reset_scores(self, container_id: str = None):
        """Reset scores for a specific container or all containers"""
        if container_id:
            self.scores.pop(container_id, None)
        else:
            self.scores = {}