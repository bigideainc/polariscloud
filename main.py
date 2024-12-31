# main.py

import os
import signal
import sys
import time
from contextlib import contextmanager

from src.neurons.Miner.allocate import ResourceAllocator
from src.neurons.Miner.container import ContainerManager
from src.neurons.Miner.http_server import ComputeServer
from src.utils.logging import setup_logging


@contextmanager
def graceful_shutdown(server, logger):
    """Context manager for graceful shutdown handling."""
    def handle_shutdown(signum, frame):
        logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
        server.stop()
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        yield
    finally:
        logger.info("Cleanup complete")

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
        
        with graceful_shutdown(server, logger):
            if not server.start():
                logger.error("Failed to start server. Exiting...")
                sys.exit(1)
                
            logger.info("Polarise Compute Subnet is running")
            
            # Keep main thread alive - cross-platform solution
            try:
                while server.is_running:
                    time.sleep(1)  # Sleep for 1 second intervals
                    if not server.is_running:
                        logger.error("Server stopped unexpectedly")
                        break
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                server.stop()
                
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()