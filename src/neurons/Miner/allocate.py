import logging
from typing import Any, Dict, List

from .container import ContainerManager

logger = logging.getLogger(__name__)

class ResourceAllocator:
    def __init__(self):
        self.container_manager = ContainerManager()
        self.allocations = {}

    def allocate_resources(self, request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Validate resource request
            if not self._validate_request(request):
                return {"status": "error", "message": "Invalid resource request"}

            # Create container with requested resources
            container_result = self.container_manager.run_container({
                "memory": request.get('memory', '1g'),
                "cpu_count": request.get('cpu_count', 1),
                "devices": request.get('devices', [])
            })

            if container_result["status"] == "success":
                allocation_id = container_result["container_id"]
                self.allocations[allocation_id] = request
                
            return container_result

        except Exception as e:
            logger.error(f"Resource allocation failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _validate_request(self, request: Dict[str, Any]) -> bool:
        required_fields = ['memory', 'cpu_count']
        return all(field in request for field in required_fields)

    def get_active_containers(self) -> List[Dict[str, Any]]:
        try:
            return [{
                'container_id': container_id,
                'allocation': allocation
            } for container_id, allocation in self.allocations.items()]
        except Exception as e:
            logger.error(f"Error getting active containers: {str(e)}")
            return []

    def process_challenge(self, container_id: str, challenge: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Get container metrics
            metrics = self.container_manager.get_container_stats(container_id)
            
            # Process challenge based on type
            if challenge['type'] == 'compute':
                return self._process_compute_challenge(container_id, challenge, metrics)
            elif challenge['type'] == 'memory':
                return self._process_memory_challenge(container_id, challenge, metrics)
            else:
                return {"status": "error", "message": "Unknown challenge type"}
                
        except Exception as e:
            logger.error(f"Error processing challenge: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _process_compute_challenge(self, container_id: str, challenge: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Execute the stress command
            command_result = self.container_manager.execute_command(
                container_id, 
                challenge['data']['command']
            )

            # Get updated metrics after stress test
            metrics = self.container_manager.get_container_stats(container_id)
            if metrics["status"] == "success":
                return {
                    "status": "success",
                    "type": "compute",
                    "command_result": command_result,
                    "metrics": metrics["metrics"]
                }
            return metrics

        except Exception as e:
            logger.error(f"Error processing compute challenge: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _process_memory_challenge(self, container_id: str, challenge: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Execute the stress command
            command_result = self.container_manager.execute_command(
                container_id, 
                challenge['data']['command']
            )

            # Get updated metrics after stress test
            metrics = self.container_manager.get_container_stats(container_id)
            if metrics["status"] == "success":
                return {
                    "status": "success",
                    "type": "memory",
                    "command_result": command_result,
                    "metrics": metrics["metrics"]
                }
            return metrics

        except Exception as e:
            logger.error(f"Error processing memory challenge: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _convert_memory_to_bytes(self, memory_str: str) -> int:
        """Convert memory string (e.g., '1g', '512m') to bytes"""
        try:
            value = int(memory_str[:-1])
            unit = memory_str[-1].lower()
            
            if unit == 'g':
                return value * 1024 * 1024 * 1024
            elif unit == 'm':
                return value * 1024 * 1024
            elif unit == 'k':
                return value * 1024
            else:
                return int(memory_str)
        except (ValueError, IndexError):
            return 0