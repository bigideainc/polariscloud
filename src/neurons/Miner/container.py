import logging
import os
import random
import socket
import tarfile
import tempfile
import time
from io import BytesIO
from typing import Any, Dict

import docker
from docker.errors import DockerException, NotFound

logging.basicConfig(
   level=logging.INFO,
   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ContainerManager:
   def __init__(self):
       try:
           self.client = docker.from_env()
           self.image_name = "polarise-compute-image"
           self.container_name = "polarise-compute-container"
           self.host_ip = os.environ.get("SSH_HOST", self._get_host_ip())
           
           if "BASE_SSH_PORT" not in os.environ:
               raise ValueError("BASE_SSH_PORT environment variable must be set") 
           if "BASE_OPEN_PORT" not in os.environ:
               raise ValueError("BASE_OPEN_PORT environment variable must be set")
               
           self.base_ssh_port = int(os.environ["BASE_SSH_PORT"])
           self.base_open_port = int(os.environ["BASE_OPEN_PORT"])
           
           logger.info(f"Initialized ContainerManager with host IP: {self.host_ip}")
       except DockerException as e:
           logger.error(f"Failed to initialize Docker client: {e}")
           raise

   def _get_host_ip(self) -> str:
       try:
           with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
               s.connect(('8.8.8.8', 80))
               ip = s.getsockname()[0]
           return ip
       except Exception as e:
           logger.error(f"Failed to get host IP: {e}")
           return "0.0.0.0"

   def generate_password(self, length: int = 5) -> str:
       return ''.join(str(random.randint(0, 9)) for _ in range(length))

   def run_container(self, resources: Dict[str, Any]) -> Dict[str, Any]:
       try:
           password = self.generate_password()
           
           server_num = resources.get('server_number', 1)
           user_num = resources.get('user_number', 1)
           ssh_port = self.base_ssh_port + ((server_num - 1) * 7) + user_num
           
           ports_per_user = resources.get('ports_per_user', 10)
           open_port_start = self.base_open_port + ((user_num - 1) * ports_per_user)
           
           ports = {
               "22/tcp": ssh_port
           }
           
           for i in range(ports_per_user):
               port_num = open_port_start + i
               ports[f"{port_num}/tcp"] = port_num

           dockerfile_content = f'''
               FROM ubuntu:latest
               RUN apt-get update && apt-get install -y openssh-server stress-ng
               RUN mkdir /run/sshd

               RUN useradd -m -s /bin/bash polaris
               RUN echo "polaris:{password}" | chpasswd

               RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config
               RUN sed -i 's/#ListenAddress 0.0.0.0/ListenAddress 0.0.0.0/' /etc/ssh/sshd_config

               EXPOSE 22
               {" ".join(f"EXPOSE {port}" for port in range(open_port_start, open_port_start + ports_per_user))}
               
               CMD ["/usr/sbin/sshd", "-D", "-e"]
           '''

           with tempfile.TemporaryDirectory() as tmpdir:
               dockerfile_path = os.path.join(tmpdir, 'Dockerfile')
               with open(dockerfile_path, 'w', encoding='utf-8') as f:
                   f.write(dockerfile_content)
               
               image, _ = self.client.images.build(
                   path=tmpdir,
                   tag=f"{self.image_name}-{server_num}-{user_num}",
                   rm=True
               )

           container_name = f"{self.container_name}-{server_num}-{user_num}"
           
           container = self.client.containers.run(
               image=image.id,
               name=container_name,
               detach=True,
               mem_limit=resources.get('memory', '1g'),
               nano_cpus=int(resources.get('cpu_count', 1) * 1e9),
               ports=ports,
               publish_all_ports=False
           )

           welcome_message = f"""Welcome to Polarise Compute Container!

Your Container Details:
-----------------------
User: polaris
Password: {password}
Host IP: {self.host_ip}
SSH Port: {ssh_port}
Open Ports: {open_port_start}-{open_port_start + ports_per_user - 1}

CPU Cores: {resources.get('cpu_count', 1)}
Memory: {resources.get('memory', '1g')}

Access Info:
ssh polaris@{self.host_ip} -p {ssh_port}
""".encode('utf-8')

           with tempfile.NamedTemporaryFile(delete=False) as temp_file:
               temp_file.write(welcome_message)
               temp_file.flush()
               tar_data = self._create_tar_archive(temp_file.name, '/etc/motd')
               container.put_archive('/', tar_data)
               os.unlink(temp_file.name)

           return {
               "status": "success",
               "container_id": container.id,
               "container_name": container.name,
               "password": password,
               "host": self.host_ip,
               "username": "polaris",
               "ssh_port": ssh_port,
               "open_ports": list(range(open_port_start, open_port_start + ports_per_user)),
               "ssh_command": f"ssh polaris@{self.host_ip} -p {ssh_port}"
           }

       except Exception as e:
           logger.error(f"Container creation failed: {str(e)}")
           return {"status": "error", "message": str(e)}

   def _create_tar_archive(self, file_path: str, arcname: str) -> bytes:
       tar_stream = BytesIO()
       with tarfile.open(fileobj=tar_stream, mode='w') as tar:
           tar.add(file_path, arcname=arcname)
       tar_stream.seek(0)
       return tar_stream.read()

   def get_container_stats(self, container_id: str) -> Dict[str, Any]:
       try:
           container = self.client.containers.get(container_id)
           stats_start = container.stats(stream=False)
           time.sleep(1)
           stats_end = container.stats(stream=False)

           cpu_percent = self._calculate_cpu_percentage(stats_start, stats_end)

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

       except NotFound:
           return {"status": "error", "message": "Container not found."}
       except Exception as e:
           return {"status": "error", "message": str(e)}

   def _calculate_cpu_percentage(self, stats_start: Dict, stats_end: Dict) -> float:
       try:
           cpu_count = len(stats_end['cpu_stats']['cpu_usage'].get('percpu_usage', [1]))
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
           result = container.exec_run(command)
           time.sleep(2)

           output = result.output.decode('utf-8') if result.output else ""
           return {
               "status": "success",
               "exit_code": result.exit_code,
               "output": output
           }
       except NotFound:
           return {"status": "error", "message": "Container not found."}
       except Exception as e:
           return {"status": "error", "message": str(e)}
