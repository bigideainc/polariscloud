# resource_allocator.py

import asyncio
import logging
import time
from datetime import datetime
from functools import partial
from threading import Lock
from typing import Any, Dict, List

import httpx
from docker.errors import NotFound

from src.neurons.Miner.container import ContainerManager
from src.neurons.Miner.schedule import TaskScheduler

logger = logging.getLogger(__name__)

# Configuration
ALLOCATION_SERVICE_URL = "http://localhost:8000/api/v1"

class ResourceAllocator:
    def __init__(self):
        logger.info("Initializing resource allocator service")
        self.container_manager = ContainerManager()
        self.allocations = {}
        self.task_scheduler = TaskScheduler()
        self.termination_lock = Lock()

    async def notify_allocation_service(self, container_id: str, final_metrics: Dict[str, Any], termination_result: Dict[str, Any]):
        """Notify allocation service about container termination"""
        try:
            async with httpx.AsyncClient() as client:
                notification_data = {
                    "reason": termination_result.get("reason", "normal"),
                    "metrics": final_metrics.get("metrics", {}),
                    "termination_time": datetime.utcnow().isoformat(),
                    "runtime_info": termination_result.get("runtime_info", {}),
                }

                response = await client.post(
                    f"{ALLOCATION_SERVICE_URL}/containers/{container_id}/terminated",
                    json=notification_data,
                    timeout=30.0
                )
                response.raise_for_status()
                logger.info(f"Successfully notified allocation service for container {container_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to notify allocation service: {str(e)}")
            return False

    def allocate_resources(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resource allocation request"""
        try:
            # Validate request
            if not self._validate_request(request):
                logger.error("Resource request missing required fields or invalid duration")
                return {"status": "error", "message": "Invalid resource request"}

            # Create container
            container_result = self.container_manager.run_container({
                "memory": request.get('memory', '1g'),
                "cpu_count": request.get('cpu_count', 1),
                "devices": request.get('devices', [])
            })

            if container_result["status"] == "success":
                allocation_id = container_result["container_id"]
                creation_time = time.time()

                logger.info(
                    f"Container created - ID: {allocation_id[:12]} | "
                    f"Memory: {request.get('memory', '1g')} | "
                    f"CPUs: {request.get('cpu_count', 1)}"
                )

                # Store container info
                self.allocations[allocation_id] = {
                    "request": request,
                    "container_info": container_result,
                    "creation_time": creation_time,
                    "status": {
                        "started_at": datetime.fromtimestamp(creation_time).isoformat(),
                        "duration": request.get('duration'),
                        "is_terminated": False
                    }
                }

                # Schedule termination if duration specified
                duration = request.get('duration')
                if duration and isinstance(duration, (int, float)) and duration > 0:
                    logger.info(f"Container {allocation_id[:12]} scheduled for termination in {duration}s")
                    self.task_scheduler.schedule_task(
                        task_id=f"terminate_{allocation_id}",
                        callback=partial(self._terminate_container, allocation_id),
                        delay=duration
                    )
                    container_result["scheduled_termination"] = duration
            else:
                logger.error(f"Container creation failed: {container_result.get('message', 'Unknown error')}")

            return container_result

        except Exception as e:
            logger.error(f"Resource allocation failed: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def _terminate_container(self, container_id: str, reason: str = "normal") -> Dict[str, Any]:
        """Terminate container and collect final metrics"""
        with self.termination_lock:
            try:
                # Check if already terminated
                container_info = self.allocations.get(container_id, {})
                if container_info.get("status", {}).get("is_terminated", False):
                    logger.warning(f"Attempted to terminate already terminated container {container_id[:12]}")
                    return {
                        "status": "success",
                        "message": "Container already terminated",
                        "container_id": container_id
                    }

                # Get final metrics before termination
                final_metrics = self.container_manager.get_container_stats(container_id)

                try:
                    # Stop and remove container
                    container = self.container_manager.client.containers.get(container_id)
                    container.stop()
                    container.remove()
                except NotFound:
                    logger.warning(f"Container {container_id} already removed")
                except Exception as e:
                    logger.error(f"Error stopping container {container_id}: {str(e)}")
                    return {
                        "status": "error",
                        "message": f"Error stopping container: {str(e)}",
                        "container_id": container_id
                    }

                # Calculate runtime stats
                started_at = datetime.fromisoformat(container_info["status"]["started_at"])
                ended_at = datetime.utcnow()
                runtime = (ended_at - started_at).total_seconds()

                # Log termination with key metrics
                logger.info(
                    f"Container terminated - ID: {container_id[:12]} | "
                    f"Runtime: {runtime:.1f}s | "
                    f"CPU: {final_metrics.get('metrics', {}).get('cpu_usage', 0):.1f}% | "
                    f"Memory: {final_metrics.get('metrics', {}).get('memory_percent', 0):.1f}%"
                )

                termination_result = {
                    "status": "success",
                    "message": "Container terminated successfully",
                    "reason": reason,
                    "container_id": container_id,
                    "final_metrics": final_metrics.get("metrics", {}),
                    "runtime_info": {
                        "started_at": container_info["status"]["started_at"],
                        "ended_at": ended_at.isoformat(),
                        "runtime_seconds": runtime,
                        "scheduled_duration": container_info["status"].get("duration")
                    },
                    "original_request": container_info.get("request", {}),
                    "container_info": container_info.get("container_info", {})
                }

                # Notify allocation service
                try:
                    asyncio.run(
                        self.notify_allocation_service(
                            container_id=container_id,
                            final_metrics=final_metrics,
                            termination_result=termination_result
                        )
                    )
                except RuntimeError as e:
                    logger.error(f"Failed to run async notify_allocation_service: {str(e)}")
                except Exception as e:
                    logger.error(f"Unexpected error during notify_allocation_service: {str(e)}")

                # Mark as terminated and cleanup
                if container_id in self.allocations:
                    self.allocations[container_id]["status"]["is_terminated"] = True
                    self.allocations[container_id]["status"]["end_time"] = ended_at.isoformat()
                    self.allocations[container_id]["final_metrics"] = final_metrics
                    del self.allocations[container_id]

                return termination_result

            except Exception as e:
                logger.error(f"Failed to terminate container {container_id[:12]}: {str(e)}", exc_info=True)
                return {
                    "status": "error",
                    "message": f"Container termination failed: {str(e)}",
                    "container_id": container_id
                }

    def _validate_request(self, request: Dict[str, Any]) -> bool:
        """Validate resource request"""
        required_fields = ['memory', 'cpu_count']
        is_valid = all(field in request for field in required_fields)

        if 'duration' in request:
            duration = request['duration']
            if not isinstance(duration, (int, float)) or duration <= 0:
                logger.warning(f"Invalid duration value: {duration} (must be positive number)")
                return False

        return is_valid

    def get_active_containers(self) -> List[Dict[str, Any]]:
        """Get all active containers"""
        try:
            active_containers = []

            for container_id, allocation in self.allocations.items():
                if not allocation["status"].get("is_terminated", False):
                    # Calculate runtime info
                    started_at = datetime.fromisoformat(allocation["status"]["started_at"])
                    elapsed_time = (datetime.utcnow() - started_at).total_seconds()
                    duration = allocation["status"].get("duration")

                    status = {
                        "started_at": allocation["status"]["started_at"],
                        "elapsed_time": elapsed_time
                    }

                    if duration:
                        status["duration"] = duration
                        status["remaining_time"] = max(0, duration - elapsed_time)
                        status["is_expired"] = elapsed_time >= duration

                    active_containers.append({
                        'container_id': container_id,
                        'allocation': allocation,
                        'runtime_status': status
                    })

            if active_containers:
                logger.info(f"Active containers: {len(active_containers)}")
                for container in active_containers:
                    status = container['runtime_status']
                    remaining = status.get('remaining_time', 'unlimited')
                    if isinstance(remaining, float):
                        remaining = f"{remaining:.1f}s"
                    logger.info(
                        f"Container {container['container_id'][:12]} | "
                        f"Runtime: {status['elapsed_time']:.1f}s | "
                        f"Remaining: {remaining}"
                    )

            return active_containers

        except Exception as e:
            logger.error(f"Error getting active containers: {str(e)}", exc_info=True)
            return []

    def shutdown(self):
        """Cleanup method to stop task scheduler and terminate containers"""
        logger.info("Shutting down resource allocator")
        try:
            self.task_scheduler.stop()
            active_count = len(self.allocations)

            if active_count > 0:
                logger.info(f"Terminating {active_count} active container(s)")
                for container_id in list(self.allocations.keys()):
                    self._terminate_container(container_id, reason="shutdown")

            logger.info("Shutdown complete")

        except Exception as e:
            logger.error(f"Shutdown failed: {str(e)}", exc_info=True)
