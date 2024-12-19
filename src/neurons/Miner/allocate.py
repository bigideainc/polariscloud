import logging
from typing import Any, Dict, List

from .container import ContainerManager

logger = logging.getLogger(__name__)

class ResourceAllocator:
    def __init__(self):
        logger.info("[+] Initializing ResourceAllocator")
        self.container_manager = ContainerManager()
        self.allocations = {}
        logger.info("[+] ResourceAllocator initialized successfully")

    def allocate_resources(self, request: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("[←] Received resource allocation request")
        logger.debug(f"[←] Request details: {request}")

        try:
            # Validate resource request
            logger.info("[↓] Validating resource request")
            if not self._validate_request(request):
                logger.warning("[!] Invalid resource request - missing required fields")
                return {"status": "error", "message": "Invalid resource request"}

            # Log requested resources
            logger.info("[↓] Requested resources:")
            logger.info(f"    Memory: {request.get('memory', '1g')}")
            logger.info(f"    CPU Count: {request.get('cpu_count', 1)}")
            logger.info(f"    Devices: {request.get('devices', [])}")

            # Create container with requested resources
            logger.info("[↓] Creating container with requested resources")
            container_result = self.container_manager.run_container({
                "memory": request.get('memory', '1g'),
                "cpu_count": request.get('cpu_count', 1),
                "devices": request.get('devices', [])
            })

            if container_result["status"] == "success":
                allocation_id = container_result["container_id"]
                self.allocations[allocation_id] = request
                logger.info(f"[→] Resource allocation successful - Container ID: {allocation_id}")
                logger.debug(f"[→] Container result: {container_result}")
            else:
                logger.error(f"[!] Container creation failed: {container_result}")

            return container_result

        except Exception as e:
            logger.error(f"[!] Resource allocation failed: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def _validate_request(self, request: Dict[str, Any]) -> bool:
        required_fields = ['memory', 'cpu_count']
        is_valid = all(field in request for field in required_fields)
        if not is_valid:
            logger.warning(f"[!] Missing required fields. Required: {required_fields}, Got: {list(request.keys())}")
        return is_valid

    def get_active_containers(self) -> List[Dict[str, Any]]:
        logger.info("[←] Received request for active containers")
        try:
            active_containers = [{
                'container_id': container_id,
                'allocation': allocation
            } for container_id, allocation in self.allocations.items()]
            
            logger.info(f"[→] Found {len(active_containers)} active containers")
            logger.debug(f"[→] Active containers: {active_containers}")
            return active_containers
            
        except Exception as e:
            logger.error(f"[!] Error getting active containers: {str(e)}", exc_info=True)
            return []

    def process_challenge(self, container_id: str, challenge: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[←] Received challenge for container {container_id}")
        logger.debug(f"[←] Challenge details: {challenge}")

        try:
            # Get container metrics
            logger.info(f"[↓] Getting container metrics for {container_id}")
            metrics = self.container_manager.get_container_stats(container_id)
            
            # Process challenge based on type
            challenge_type = challenge.get('type', 'unknown')
            logger.info(f"[↓] Processing {challenge_type} challenge")

            if challenge_type == 'compute':
                result = self._process_compute_challenge(container_id, challenge, metrics)
            elif challenge_type == 'memory':
                result = self._process_memory_challenge(container_id, challenge, metrics)
            else:
                logger.warning(f"[!] Unknown challenge type: {challenge_type}")
                return {"status": "error", "message": "Unknown challenge type"}

            logger.info(f"[→] Challenge processing complete")
            logger.debug(f"[→] Challenge result: {result}")
            return result
                
        except Exception as e:
            logger.error(f"[!] Error processing challenge: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def _process_compute_challenge(self, container_id: str, challenge: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[↓] Processing compute challenge for container {container_id}")
        try:
            # Execute the stress command
            command = challenge['data']['command']
            logger.info(f"[↓] Executing command: {command}")
            command_result = self.container_manager.execute_command(container_id, command)

            # Get updated metrics after stress test
            logger.info("[↓] Getting updated container metrics")
            metrics = self.container_manager.get_container_stats(container_id)
            
            if metrics["status"] == "success":
                logger.info("[→] Compute challenge completed successfully")
                return {
                    "status": "success",
                    "type": "compute",
                    "command_result": command_result,
                    "metrics": metrics["metrics"]
                }
            
            logger.warning(f"[!] Failed to get metrics: {metrics}")
            return metrics

        except Exception as e:
            logger.error(f"[!] Error processing compute challenge: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def _process_memory_challenge(self, container_id: str, challenge: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[↓] Processing memory challenge for container {container_id}")
        try:
            # Execute the stress command
            command = challenge['data']['command']
            logger.info(f"[↓] Executing command: {command}")
            command_result = self.container_manager.execute_command(container_id, command)

            # Get updated metrics after stress test
            logger.info("[↓] Getting updated container metrics")
            metrics = self.container_manager.get_container_stats(container_id)
            
            if metrics["status"] == "success":
                logger.info("[→] Memory challenge completed successfully")
                return {
                    "status": "success",
                    "type": "memory",
                    "command_result": command_result,
                    "metrics": metrics["metrics"]
                }
            
            logger.warning(f"[!] Failed to get metrics: {metrics}")
            return metrics

        except Exception as e:
            logger.error(f"[!] Error processing memory challenge: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def _convert_memory_to_bytes(self, memory_str: str) -> int:
        """Convert memory string (e.g., '1g', '512m') to bytes"""
        logger.debug(f"[↓] Converting memory string: {memory_str}")
        try:
            value = int(memory_str[:-1])
            unit = memory_str[-1].lower()
            
            if unit == 'g':
                bytes_value = value * 1024 * 1024 * 1024
            elif unit == 'm':
                bytes_value = value * 1024 * 1024
            elif unit == 'k':
                bytes_value = value * 1024
            else:
                bytes_value = int(memory_str)
                
            logger.debug(f"[↓] Converted {memory_str} to {bytes_value} bytes")
            return bytes_value
            
        except (ValueError, IndexError) as e:
            logger.error(f"[!] Error converting memory string: {str(e)}")
            return 0