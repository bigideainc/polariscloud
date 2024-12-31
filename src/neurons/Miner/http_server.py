import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
logger.propagate = False  # Prevent duplicate logs

class RequestLogger:
    """Utility class to log request details with timing"""
    @staticmethod
    def log_request(handler, request_data=None):
        client_address = handler.client_address[0]
        request_line = f"{handler.command} {handler.path}"
        logger.info(f"Request from {client_address}: {request_line}")
        if request_data:
            request_str = json.dumps(request_data, indent=2)
            logger.info(f"Request data: {request_str}")

    @staticmethod
    def log_response(handler, response_data, status_code, duration):
        client_address = handler.client_address[0]
        logger.info(f"Response to {client_address} | Status: {status_code} | Time: {duration:.3f}s")
        if response_data:
            response_str = json.dumps(response_data, indent=2)
            logger.info(f"Response data: {response_str}")

class ComputeRequestHandler(BaseHTTPRequestHandler):
    def _send_json_response(self, response_data: Dict[str, Any], status_code: int = 200, send_body: bool = True):
        response_time = time.time() - self.request_start_time
        RequestLogger.log_response(self, response_data, status_code, response_time)
        
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', len(json.dumps(response_data).encode()))
        self.end_headers()
        
        if send_body:
            self.wfile.write(json.dumps(response_data).encode())

    def do_HEAD(self):
        """Handle HEAD requests."""
        self.request_start_time = time.time()
        try:
            RequestLogger.log_request(self)
            
            if self.path == '/allocate':
                # Respond with headers only for allocation endpoint
                self._send_json_response(
                    {"status": "success", "message": "Allocation endpoint"},
                    send_body=False
                )
            elif self.path == '/containers':
                # Respond with headers only for containers endpoint
                self._send_json_response(
                    {"status": "success", "message": "Containers endpoint"},
                    send_body=False
                )
            elif self.path == '/health':
                # Respond with headers only for health endpoint
                self._send_json_response(
                    {"status": "success", "message": "Health endpoint"},
                    send_body=False
                )
            else:
                # Respond with headers for invalid endpoint
                self._send_json_response(
                    {"status": "error", "message": "Endpoint not found"},
                    status_code=404,
                    send_body=False
                )
        except Exception as e:
            logger.error(f"HEAD request failed: {str(e)}", exc_info=True)
            self._send_json_response(
                {"status": "error", "message": str(e)},
                status_code=500,
                send_body=False
            )

    def do_POST(self):
        self.request_start_time = time.time()
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request = json.loads(post_data.decode())
            
            RequestLogger.log_request(self, request)
            
            if self.path == '/allocate':
                logger.info("Processing allocation request")
                response = self.server.allocator.allocate_resources(request)
                self._send_json_response(response)
            else:
                logger.warning(f"Invalid endpoint: {self.path}")
                self._send_json_response(
                    {"status": "error", "message": "Invalid endpoint"},
                    status_code=404
                )
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request: {str(e)}")
            self._send_json_response(
                {"status": "error", "message": "Invalid JSON format"},
                status_code=400
            )
        except Exception as e:
            logger.error(f"Request failed: {str(e)}", exc_info=True)
            self._send_json_response(
                {"status": "error", "message": str(e)},
                status_code=500
            )

    def do_GET(self):
        self.request_start_time = time.time()
        try:
            RequestLogger.log_request(self)
            
            if self.path == '/containers':
                logger.info("Fetching active containers")
                containers = self.server.allocator.get_active_containers()
                self._send_json_response({
                    "status": "success",
                    "containers": containers
                })
            elif self.path == '/health':
                self._send_json_response({
                    "status": "success",
                    "message": "Server is healthy",
                    "timestamp": time.time()
                })
            else:
                logger.warning(f"Invalid endpoint: {self.path}")
                self._send_json_response(
                    {"status": "error", "message": "Endpoint not found"},
                    status_code=404
                )
        except Exception as e:
            logger.error(f"GET request failed: {str(e)}", exc_info=True)
            self._send_json_response(
                {"status": "error", "message": str(e)},
                status_code=500
            )

    def log_message(self, format, *args):
        """Override to prevent default access logging"""
        pass

class ComputeServer:
    def __init__(self, port: int = 8080, allocator=None):
        self.port = port
        self.server = None
        self.allocator = allocator
        self.is_running = False
        
    def start(self):
        try:
            self.server = HTTPServer(('', self.port), ComputeRequestHandler)
            self.server.allocator = self.allocator
            self.is_running = True
            
            logger.info(f"Starting compute server on port {self.port}")
            
            # Start server in a daemon thread
            server_thread = threading.Thread(target=self._run_server)
            server_thread.daemon = True
            server_thread.start()
            
            logger.info("Server started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start server: {str(e)}", exc_info=True)
            self.is_running = False
            return False
            
    def _run_server(self):
        try:
            while self.is_running:
                self.server.handle_request()
        except Exception as e:
            logger.error(f"Server error: {str(e)}", exc_info=True)
            self.is_running = False
            
    def stop(self):
        logger.info("Shutting down server")
        self.is_running = False
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        logger.info("Server shutdown complete")