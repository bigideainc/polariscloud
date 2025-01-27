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

# Configure root logger if desired
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContainerManager:
    def __init__(self):
        """
        Initialize the Docker client and some defaults.
        We'll read the host IP from env var SSH_HOST, or fall back to local IP if not present.
        """
        try:
            self.client = docker.from_env()
            self.image_name = "polarise-compute-image"
            self.container_name = "polarise-compute-container"
            # Try to read the host IP from environment variable SSH_HOST
            self.host_ip = os.environ.get("SSH_HOST", self._get_host_ip())
            logger.info(f"Initialized ContainerManager with host IP: {self.host_ip}")
        except DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise

    def _get_host_ip(self) -> str:
        """
        Get the host machine's IP address for later SSH use.
        Only called if SSH_HOST isn't set in the environment.
        """
        try:
            # Create a socket to determine the host's IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # This doesn't actually connect but helps get local IP
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
            logger.debug(f"Determined host IP: {ip}")
            return ip
        except Exception as e:
            logger.error(f"Failed to get host IP: {e}")
            return "0.0.0.0"  # fallback

    def generate_password(self, length: int = 5) -> str:
        """Generate a simple numeric password."""
        return ''.join(str(random.randint(0, 9)) for _ in range(length))

    def run_container(self, resources: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a new Docker image, run a container with a 'polaris' user,
        and map container port 22 to a random port on the host.
        """
        try:
            # Generate a random password for the 'polaris' user
            password = self.generate_password()

            # Process any user-supplied ports (optional usage)
            ports = resources.get('ports', {})
            ports = self._process_ports(ports) if ports else {}

            # Dockerfile content: creates non-root user 'polaris'
            # and disables root login (PermitRootLogin no).
            dockerfile_content = f'''
                FROM ubuntu:latest
                RUN apt-get update && apt-get install -y openssh-server stress-ng
                RUN mkdir /run/sshd

                # Create "polaris" user with home directory and set password
                RUN useradd -m -s /bin/bash polaris
                RUN echo "polaris:{password}" | chpasswd

                # Disable root SSH (uncomment to allow root)
                RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config

                # Listen on 0.0.0.0 for SSH
                RUN sed -i 's/#ListenAddress 0.0.0.0/ListenAddress 0.0.0.0/' /etc/ssh/sshd_config

                EXPOSE 22
                CMD ["/usr/sbin/sshd", "-D", "-e"]
            '''

            # Build the Docker image in a temp directory
            with tempfile.TemporaryDirectory() as tmpdir:
                dockerfile_path = os.path.join(tmpdir, 'Dockerfile')
                with open(dockerfile_path, 'w', encoding='utf-8') as f:
                    f.write(dockerfile_content)
                logger.info(f"Building Docker image '{self.image_name}'...")
                image, build_logs = self.client.images.build(
                    path=tmpdir,
                    tag=self.image_name,
                    rm=True
                )
                logger.info(f"Docker image '{self.image_name}' built successfully.")

            # Give the container a unique name (with random suffix)
            container_full_name = f"{self.container_name}-{self.generate_password(8)}"
            logger.info(f"Running container '{container_full_name}'...")

            # If user did not specify a custom port, default to a random publish of 22/tcp
            # That is, ports={"22/tcp": None} means Docker picks a random free host port
            if not ports:
                ports = {"22/tcp": None}

            # Start the container
            container = self.client.containers.run(
                image=self.image_name,
                name=container_full_name,
                detach=True,
                mem_limit=resources.get('memory', '1g'),
                nano_cpus=int(resources.get('cpu_count', 1) * 1e9),
                ports=ports,  # e.g. {"22/tcp": None}
                publish_all_ports=True
            )
            logger.info(f"Container '{container.name}' started with ID: {container.id}")

            # Create a welcome message to appear at /etc/motd
            welcome_message = f"""Welcome to Polarise Compute Container!

Your Container Details:
-----------------------
User: polaris
Password: {password}
Host IP: {self.host_ip}

CPU Cores: {resources.get('cpu_count', 1)}
Memory: {resources.get('memory', '1g')}

Access Info:
ssh polaris@{self.host_ip} -p <port_from_below>
""".encode('utf-8')

            # Write the welcome message to a temp file, then tar it
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(welcome_message)
                temp_file.flush()
                temp_file_path = temp_file.name

            tar_data = self._create_tar_archive(temp_file_path, '/etc/motd')
            success = container.put_archive('/', tar_data)
            if not success:
                logger.error("Failed to copy welcome message to /etc/motd in container.")
                raise DockerException("Failed to copy /etc/motd message.")
            logger.info("Copied welcome message to container's /etc/motd.")

            # Remove local temp file
            os.unlink(temp_file_path)

            # Inspect container to find the mapped SSH port
            container_info = self.client.api.inspect_container(container.id)
            ssh_ports = {
                cport: host_bindings[0]['HostPort']
                for cport, host_bindings in container_info['NetworkSettings']['Ports'].items()
                if host_bindings
            }
            host_ssh_port = ssh_ports.get('22/tcp')

            # Prepare final response
            response = {
                "status": "success",
                "container_id": container.id,
                "container_name": container.name,
                "password": password,
                "host": self.host_ip,
                "username": "polaris",
                "ports": ssh_ports,
            }
            if host_ssh_port:
                response["ssh_command"] = f"ssh polaris@{self.host_ip} -p {host_ssh_port}"

            logger.info(f"Container '{container.name}' created successfully.")
            return response

        except Exception as e:
            logger.error(f"Container creation failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _process_ports(self, ports: Any) -> Dict[str, Any]:
        """
        Validates and processes the 'ports' parameter to ensure it is in the correct format.
        Possible formats:
            - Dict[str, int]: e.g., {"22/tcp": 2222}
            - String: e.g., "22" => {"22/tcp": 22}
            - List[str/int]: e.g. ["22", "80"] => {"22/tcp": 22, "80/tcp": 80}
        """
        if isinstance(ports, str):
            try:
                port_num = int(ports)
                return {f"{port_num}/tcp": port_num}
            except ValueError:
                raise ValueError(f"Invalid port string: '{ports}'. Must be numeric.")
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
            # Validate keys are strings like '22/tcp' and values are ints or None
            valid_ports = {}
            for key, value in ports.items():
                if not isinstance(key, str):
                    raise ValueError(f"Port key '{key}' must be a string like '22/tcp'.")
                if not isinstance(value, int) and value is not None:
                    raise ValueError(f"Port value '{value}' must be an integer or None.")
                valid_ports[key] = value
            return valid_ports
        else:
            raise ValueError("`ports` must be a dictionary, string, or list.")

    def _create_tar_archive(self, file_path: str, arcname: str) -> bytes:
        """
        Creates a tar archive containing the specified file so we can copy it into the container.
        """
        tar_stream = BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            tar.add(file_path, arcname=arcname)
        tar_stream.seek(0)
        return tar_stream.read()

    def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """
        Retrieve CPU/memory usage stats from a running container.
        """
        try:
            container = self.client.containers.get(container_id)

            # Get initial stats, wait, then get another sample
            stats_start = container.stats(stream=False)
            time.sleep(1)
            stats_end = container.stats(stream=False)

            # CPU usage calculation
            cpu_percent = self._calculate_cpu_percentage(stats_start, stats_end)

            # Memory usage calculation
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
        """
        Calculate CPU usage percentage between two Docker stats samples.
        """
        try:
            cpu_count = len(stats_end['cpu_stats']['cpu_usage'].get('percpu_usage', [1]))
            cpu_delta = stats_end['cpu_stats']['cpu_usage']['total_usage'] \
                        - stats_start['cpu_stats']['cpu_usage']['total_usage']
            system_delta = stats_end['cpu_stats']['system_cpu_usage'] \
                           - stats_start['cpu_stats']['system_cpu_usage']

            logger.debug(f"CPU delta: {cpu_delta}, System delta: {system_delta}")

            if system_delta > 0 and cpu_delta > 0:
                return (cpu_delta / system_delta) * 100.0 * cpu_count
            return 0.0
        except Exception as e:
            logger.error(f"CPU percentage calculation failed: {str(e)}")
            return 0.0

    def execute_command(self, container_id: str, command: str) -> Dict[str, Any]:
        """
        Execute an arbitrary shell command inside the container.
        """
        try:
            container = self.client.containers.get(container_id)

            logger.info(f"Executing command in container '{container_id}': {command}")
            result = container.exec_run(command)

            # Wait briefly to let usage/metrics settle after execution
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
