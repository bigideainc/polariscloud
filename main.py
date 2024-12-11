import os
import sys

from src.neurons.Miner.allocate import ResourceAllocator
from src.neurons.Miner.container import ContainerManager
from src.neurons.Miner.http_server import ComputeServer
from src.utils.logging import setup_logging


def main():
    # Setup logging
    logger = setup_logging()
    logger.info("Starting Polarise Compute Subnet...")

    try:
        # Initialize core components
        container_manager = ContainerManager()
        allocator = ResourceAllocator()
        
        # Start HTTP server with allocator
        server = ComputeServer(port=8080, allocator=allocator)
        server.start()
        
        logger.info("Polarise Compute Subnet is running")
        
        # Keep the main thread running
        try:
            while True:
                pass
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            server.stop()

    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
