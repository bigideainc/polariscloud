import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.neurons.Miner.schedule import TaskScheduler

logger = logging.getLogger(__name__)

class ContainerMonitor:
    def __init__(self):
        self.containers: Dict[str, Dict[str, Any]] = {}
        self.task_scheduler = TaskScheduler()
        
    def add_container(self, container_id: str, container_info: Dict[str, Any], duration: Optional[int] = None):
        """Add a container to be monitored"""
        creation_time = time.time()
        self.containers[container_id] = {
            "container_info": container_info,
            "creation_time": creation_time,
            "duration": duration,
            "expiration_time": creation_time + duration if duration else None
        }
        
        logger.info(f"[+] Added container {container_id} to monitor. Duration: {duration}s")
        
    def remove_container(self, container_id: str):
        """Remove a container from monitoring"""
        if container_id in self.containers:
            del self.containers[container_id]
            logger.info(f"[-] Removed container {container_id} from monitor")
            
    def get_container_status(self, container_id: str) -> Dict[str, Any]:
        """Get current status of a monitored container"""
        if container_id not in self.containers:
            return {"status": "not_found"}
            
        container = self.containers[container_id]
        current_time = time.time()
        elapsed_time = current_time - container["creation_time"]
        
        status = {
            "container_id": container_id,
            "creation_time": datetime.fromtimestamp(container["creation_time"]).isoformat(),
            "elapsed_time": elapsed_time,
            "duration": container["duration"],
            "is_expired": False
        }
        
        if container["expiration_time"]:
            status["expiration_time"] = datetime.fromtimestamp(container["expiration_time"]).isoformat()
            status["remaining_time"] = max(0, container["expiration_time"] - current_time)
            status["is_expired"] = current_time >= container["expiration_time"]
            
        return status
        
    def get_expired_containers(self) -> List[str]:
        """Get list of expired container IDs"""
        current_time = time.time()
        expired = []
        
        for container_id, info in self.containers.items():
            if info["expiration_time"] and current_time >= info["expiration_time"]:
                expired.append(container_id)
                
        return expired