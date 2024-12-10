# src/neurons/Miner/container.py

import logging
import os
import random
import socket
import string
import time
from io import BytesIO
from typing import Any, Dict

import docker
from docker.types import DeviceRequest

logger = logging.getLogger(__name__)

class ContainerManager:
   def __init__(self):
       self.client = docker.from_env()
       self.image_name = "polarise-compute-image"
       self.container_name = "polarise-compute-container"
       self.host_ip = self._get_host_ip()
       logger.info(f"Initialized ContainerManager with host IP: {self.host_ip}")

   def _get_host_ip(self) -> str:
       """Get the host machine's IP address"""
       try:
           # Create a socket to determine the host's IP
           s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
           # Doesn't actually connect but helps get local IP
           s.connect(('8.8.8.8', 80))
           ip = s.getsockname()[0]
           s.close()
           return ip
       except Exception as e:
           logger.error(f"Failed to get host IP: {e}")
           return "0.0.0.0"  # Fallback

   def generate_password(self, length: int = 5) -> str:
       # Generate a simple password
       return ''.join(str(random.randint(0, 9)) for _ in range(length))

   def run_container(self, resources: Dict[str, Any]) -> Dict[str, Any]:
       try:
           password = self.generate_password()
           
           # Get port from resources if specified
           ports = resources.get('ports', {})
           
           dockerfile_content = f"""
               FROM ubuntu:latest
               RUN apt-get update && apt-get install -y openssh-server stress-ng
               RUN mkdir /run/sshd
               RUN echo 'root:{password}' | chpasswd
               RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
               RUN sed -i 's/#ListenAddress 0.0.0.0/ListenAddress 0.0.0.0/' /etc/ssh/sshd_config
               
               EXPOSE 22
               CMD ["/usr/sbin/sshd", "-D", "-e"]
           """
           
           dockerfile = BytesIO(dockerfile_content.encode('utf-8'))
           
           # Build the image
           self.client.images.build(
               fileobj=dockerfile,
               tag=self.image_name,
               rm=True
           )
           
           # Run the container
           container = self.client.containers.run(
               image=self.image_name,
               name=f"{self.container_name}-{self.generate_password(8)}",
               detach=True,
               mem_limit=resources.get('memory', '1g'),
               cpu_count=resources.get('cpu_count', 1),
               ports=ports,
               publish_all_ports=True  # This will publish all exposed ports
           )
           
           # Get container info
           container_info = self.client.api.inspect_container(container.id)
           
           # Get SSH port from container info
           ssh_ports = {}
           for container_port, host_binding in container_info['NetworkSettings']['Ports'].items():
               if host_binding:
                   ssh_ports[container_port] = host_binding[0]['HostPort']
           
           # Prepare response
           response = {
               "status": "success",
               "container_id": container.id,
               "container_name": container.name,
               "password": password,
               "host": self.host_ip,
               "username": "root",
               "ports": ssh_ports,
           }

           # Add SSH command for convenience
           if '22/tcp' in ssh_ports:
               response["ssh_command"] = f"ssh root@{self.host_ip} -p {ssh_ports['22/tcp']}"
           
           return response
           
       except Exception as e:
           logger.error(f"Container creation failed: {str(e)}")
           return {"status": "error", "message": str(e)}

   def get_container_stats(self, container_id: str) -> Dict[str, Any]:
       try:
           container = self.client.containers.get(container_id)
           
           # Get initial stats
           stats_start = container.stats(stream=False)
           # Wait for metrics to stabilize
           time.sleep(1)
           # Get end stats
           stats_end = container.stats(stream=False)

           # Calculate CPU percentage with core count consideration
           cpu_percent = self._calculate_cpu_percentage(stats_start, stats_end)
           
           # Calculate memory usage
           memory_stats = stats_end['memory_stats']
           memory_usage = memory_stats.get('usage', 0)
           memory_limit = memory_stats.get('limit', 0)
           memory_percent = (memory_usage / memory_limit) * 100.0 if memory_limit > 0 else 0.0

           return {
               "status": "success",
               "metrics": {
                   "cpu_usage": round(cpu_percent, 2),
                   "memory_usage": memory_usage,
                   "memory_limit": memory_limit,
                   "memory_percent": round(memory_percent, 2)
               }
           }

       except Exception as e:
           logger.error(f"Failed to get container stats: {str(e)}")
           return {"status": "error", "message": str(e)}

   def _calculate_cpu_percentage(self, stats_start: Dict, stats_end: Dict) -> float:
       try:
           # Get number of CPU cores
           cpu_count = len(stats_end['cpu_stats']['cpu_usage'].get('percpu_usage', [1]))
           
           # Calculate CPU deltas
           cpu_delta = stats_end['cpu_stats']['cpu_usage']['total_usage'] - \
                      stats_start['cpu_stats']['cpu_usage']['total_usage']
           
           system_delta = stats_end['cpu_stats']['system_cpu_usage'] - \
                         stats_start['cpu_stats']['system_cpu_usage']

           if system_delta > 0 and cpu_delta > 0:
               return (cpu_delta / system_delta) * 100.0 * cpu_count
           return 0.0
       except Exception as e:
           logger.error(f"CPU percentage calculation failed: {str(e)}")
           return 0.0

   def execute_command(self, container_id: str, command: str) -> Dict[str, Any]:
       try:
           container = self.client.containers.get(container_id)
           
           # Execute command
           result = container.exec_run(command)
           
           # Wait for metrics to stabilize after command execution
           time.sleep(2)
           
           return {
               "status": "success",
               "exit_code": result.exit_code,
               "output": result.output.decode('utf-8')
           }
       except Exception as e:
           logger.error(f"Failed to execute command: {str(e)}")
           return {
               "status": "error", 
               "message": str(e)
           }