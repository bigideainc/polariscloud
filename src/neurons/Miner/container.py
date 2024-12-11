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
from docker.utils.build import tar as docker_tar

# Configure logging
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
            self.host_ip = self._get_host_ip()
            logger.info(f"Initialized ContainerManager with host IP: {self.host_ip}")
        except DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise

    def _get_host_ip(self) -> str:
        """Get the host machine's IP address."""
        try:
            # Create a socket to determine the host's IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Doesn't actually connect but helps get local IP
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
            logger.debug(f"Determined host IP: {ip}")
            return ip
        except Exception as e:
            logger.error(f"Failed to get host IP: {e}")
            return "0.0.0.0"  # Fallback

    def generate_password(self, length: int = 5) -> str:
        """Generate a simple numeric password."""
        password = ''.join(str(random.randint(0, 9)) for _ in range(length))
        logger.debug(f"Generated password: {password}")
        return password

    def run_container(self, resources: Dict[str, Any]) -> Dict[str, Any]:
        try:
            password = self.generate_password()

            # Validate and process ports
            ports = resources.get('ports', {})
            ports = self._process_ports(ports)

            logger.debug(f"Processed ports: {ports}")

            # Create Dockerfile content
            dockerfile_content = f'''
                FROM ubuntu:latest
                RUN apt-get update && apt-get install -y openssh-server stress-ng
                RUN mkdir /run/sshd
                RUN echo 'root:{password}' | chpasswd
                RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
                RUN sed -i 's/#ListenAddress 0.0.0.0/ListenAddress 0.0.0.0/' /etc/ssh/sshd_config
                
                # Create empty motd file
                RUN touch /etc/motd
                
                EXPOSE 22
                CMD ["/usr/sbin/sshd", "-D", "-e"]
            '''

            # Create temporary directory for build context
            with tempfile.TemporaryDirectory() as tmpdir:
                dockerfile_path = os.path.join(tmpdir, 'Dockerfile')
                with open(dockerfile_path, 'w', encoding='utf-8') as f:
                    f.write(dockerfile_content)
                logger.debug(f"Dockerfile written to {dockerfile_path}")

                # Build the Docker image
                logger.info(f"Building Docker image '{self.image_name}'...")
                image, build_logs = self.client.images.build(
                    path=tmpdir,
                    tag=self.image_name,
                    rm=True
                )
                logger.info(f"Docker image '{self.image_name}' built successfully.")

            # Run the container
            container_full_name = f"{self.container_name}-{self.generate_password(8)}"
            logger.info(f"Running container '{container_full_name}'...")
            container = self.client.containers.run(
                image=self.image_name,
                name=container_full_name,
                detach=True,
                mem_limit=resources.get('memory', '1g'),
                nano_cpus=int(resources.get('cpu_count', 1) * 1e9),  # Ensure nano_cpus is an integer
                ports=ports,
                publish_all_ports=True
            )
            logger.info(f"Container '{container.name}' started with ID: {container.id}")

            # Prepare welcome message
            welcome_message = f"""⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⡖⠁⠀⠀⠀⠀⠀⠀⠈⢲⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⣼⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢹⣧⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣸⣿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⣿⣇⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣿⣿⡇⠀⢀⣀⣤⣤⣤⣤⣀⡀⠀⢸⣿⣿⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿⣔⢿⡿⠟⠛⠛⠛⠿⢿⣄⣿⣿⡟⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⣀⣤⣶⣾⣿⣿⣿⣷⣤⣀⡀⢀⣀⣤⣾⣿⣿⣿⣷⣶⣤⡀⠀⠀⠀⠀
⠀⠀⢠⣾⣿⡿⠿⠿⠿⣿⣿⣿⣿⡿⠏⠻⢿⣿⣿⣿⣿⠿⠿⠿⢿⣿⣷⡀⠀⠀
⠀⢠⡿⠋⠁⠀⠀⢸⣿⡇⠉⠻⣿⠇⠀⠀⠸⣿⡿⠋⢰⣿⡇⠀⠀⠈⠙⢿⡄⠀
⠀⡿⠁⠀⠀⠀⠀⠘⣿⣷⡀⠀⠰⣿⣶⣶⣿⡎⠀⢀⣾⣿⠇⠀⠀⠀⠀⠈⢿⠀
⠀⡇⠀⠀⠀⠀⠀⠀⠹⣿⣷⣄⠀⣿⣿⣿⣿⠀⣠⣾⣿⠏⠀⠀⠀⠀⠀⠀⢸⠀
⠀⠁⠀⠀⠀⠀⠀⠀⠀⠈⠻⢿⢇⣿⣿⣿⣿⡸⣿⠟⠁⠀⠀⠀⠀⠀⠀⠀⠈⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣼⣿⣿⣿⣿⣧⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠐⢤⣀⣀⢀⣀⣠⣴⣿⣿⠿⠋⠙⠿⣿⣿⣦⣄⣀⠀⣀⣀⡠⠂⠀⠀⠀
⠀⠀⠀⠀⠀⠈⠉⠛⠛⠛⠛⠉⠀⠀⠀⠀⠀⠈⠉⠛⠛⠛⠛⠋⠁⠀⠀⠀⠀⠀

Welcome to Polarise Compute Container!
===========================================
Your Container Details:
----------------------
Resources Allocated:
CPU Cores: {resources.get('cpu_count', 1)}
Memory: {resources.get('memory', '1g')}

Access Information:
------------------
Host: {self.host_ip}
Username: root
Password: {password}

Available Tools:
---------------
- stress-ng: CPU/Memory stress testing
- Basic system utilities

Need Help?
----------
- Use 'stress-ng --help' for stress testing options
- Contact support for assistance

Happy Computing!
===========================================""".encode('utf-8')

            # Create a temporary file with the welcome message
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(welcome_message)
                temp_file.flush()
                temp_file_path = temp_file.name
            logger.debug(f"Welcome message written to temporary file {temp_file_path}")

            # Create a tar archive containing the welcome message file
            tar_data = self._create_tar_archive(temp_file_path, '/etc/motd')
            logger.debug("Created tar archive for welcome message.")

            # Copy the tar archive to the container
            success = container.put_archive('/', tar_data)
            if not success:
                logger.error("Failed to copy welcome message to container's /etc/motd.")
                raise DockerException("Failed to copy welcome message to container.")

            logger.info("Copied welcome message to container's /etc/motd.")

            # Remove the temporary file
            os.unlink(temp_file_path)
            logger.debug(f"Deleted temporary file {temp_file_path}.")

            # Get container info
            container_info = self.client.api.inspect_container(container.id)

            # Get SSH port from container info
            ssh_ports = {
                container_port: host_binding[0]['HostPort']
                for container_port, host_binding in container_info['NetworkSettings']['Ports'].items()
                if host_binding
            }

            logger.debug(f"SSH Ports: {ssh_ports}")

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

            logger.info(f"Container '{container.name}' created successfully.")
            return response

        except Exception as e:
            logger.error(f"Container creation failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _process_ports(self, ports: Any) -> Dict[str, Any]:
        """
        Validates and processes the ports parameter to ensure it is in the correct format.
        Expected formats:
        - Dict[str, int]: e.g., {"22/tcp": 2222}
        - String: e.g., "22" which will be converted to {"22/tcp": 22}
        - List[str/int]: e.g., ["22", "80"] which will be converted to {"22/tcp": 22, "80/tcp": 80}
        """
        if isinstance(ports, str):
            try:
                port_num = int(ports)
                return {f"{port_num}/tcp": port_num}
            except ValueError:
                raise ValueError(f"Invalid port string: '{ports}'. Must be a numeric string.")
        elif isinstance(ports, list):
            port_dict = {}
            for port in ports:
                try:
                    port_num = int(port)
                    port_dict[f"{port_num}/tcp"] = port_num
                except ValueError:
                    raise ValueError(f"Invalid port in list: '{port}'. Must be numeric.")
            return port_dict
        elif isinstance(ports, dict):
            # Validate that keys and values are correct
            valid_ports = {}
            for key, value in ports.items():
                if not isinstance(key, str):
                    raise ValueError(f"Port key '{key}' must be a string like '22/tcp'.")
                if not isinstance(value, int):
                    raise ValueError(f"Port value '{value}' must be an integer.")
                valid_ports[key] = value
            return valid_ports
        else:
            raise ValueError("`ports` must be a dictionary, string, or list.")

    def _create_tar_archive(self, file_path: str, arcname: str) -> bytes:
        """
        Creates a tar archive containing the specified file.

        :param file_path: Path to the file to be archived.
        :param arcname: Archive name inside the tar.
        :return: Bytes of the tar archive.
        """
        tar_stream = BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            tar.add(file_path, arcname=arcname)
        tar_stream.seek(0)
        return tar_stream.read()

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

            logger.debug(f"Container '{container_id}' stats: CPU {cpu_percent}%, Memory {memory_percent}%")

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
            logger.error(f"Container with ID '{container_id}' not found.")
            return {"status": "error", "message": "Container not found."}
        except Exception as e:
            logger.error(f"Failed to get container stats: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _calculate_cpu_percentage(self, stats_start: Dict, stats_end: Dict) -> float:
        try:
            # Get number of CPU cores
            cpu_count = len(stats_end['cpu_stats']['cpu_usage'].get('percpu_usage', [1]))
            logger.debug(f"CPU count: {cpu_count}")

            # Calculate CPU deltas
            cpu_delta = stats_end['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats_start['cpu_stats']['cpu_usage']['total_usage']
            system_delta = stats_end['cpu_stats']['system_cpu_usage'] - \
                          stats_start['cpu_stats']['system_cpu_usage']

            logger.debug(f"CPU delta: {cpu_delta}, System delta: {system_delta}")

            if system_delta > 0 and cpu_delta > 0:
                cpu_percentage = (cpu_delta / system_delta) * 100.0 * cpu_count
                logger.debug(f"Calculated CPU percentage: {cpu_percentage}%")
                return cpu_percentage
            return 0.0
        except Exception as e:
            logger.error(f"CPU percentage calculation failed: {str(e)}")
            return 0.0

    def execute_command(self, container_id: str, command: str) -> Dict[str, Any]:
        try:
            container = self.client.containers.get(container_id)

            # Execute command
            logger.info(f"Executing command in container '{container_id}': {command}")
            result = container.exec_run(command)

            # Wait for metrics to stabilize after command execution
            time.sleep(2)

            output = result.output.decode('utf-8') if result.output else ""
            logger.debug(f"Command execution output: {output}")

            return {
                "status": "success",
                "exit_code": result.exit_code,
                "output": output
            }
        except NotFound:
            logger.error(f"Container with ID '{container_id}' not found.")
            return {
                "status": "error",
                "message": "Container not found."
            }
        except Exception as e:
            logger.error(f"Failed to execute command: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }