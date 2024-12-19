# http_server.py
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict

logger = logging.getLogger(__name__)

class RequestLogger:
    """Utility class to log request details with timing"""
    @staticmethod
    def log_request(handler, request_data=None):
        client_address = handler.client_address[0]
        request_line = f"{handler.command} {handler.path}"
        logger.info(f"[←] Received request from {client_address}: {request_line}")
        if request_data:
            logger.info(f"[←] Request data: {json.dumps(request_data, indent=2)}")

    @staticmethod
    def log_response(handler, response_data, status_code, duration):
        client_address = handler.client_address[0]
        logger.info(f"[→] Sending response to {client_address} (Status: {status_code}, Duration: {duration:.3f}s)")
        logger.info(f"[→] Response data: {json.dumps(response_data, indent=2)}")

class ComputeRequestHandler(BaseHTTPRequestHandler):
    def _send_json_response(self, response_data: Dict[str, Any], status_code: int = 200):
        response_time = time.time() - self.request_start_time
        RequestLogger.log_response(self, response_data, status_code, response_time)
        
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode())

    def do_POST(self):
        self.request_start_time = time.time()
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request = json.loads(post_data.decode())
            
            RequestLogger.log_request(self, request)
            
            if self.path == '/allocate':
                logger.info(f"[↓] Processing allocation request...")
                response = self.server.allocator.allocate_resources(request)
                self._send_json_response(response)
            else:
                logger.warning(f"[!] Invalid endpoint requested: {self.path}")
                self._send_json_response(
                    {"status": "error", "message": "Invalid endpoint"},
                    status_code=404
                )
                
        except json.JSONDecodeError as e:
            logger.error(f"[!] Invalid JSON in request: {str(e)}")
            self._send_json_response(
                {"status": "error", "message": "Invalid JSON format"},
                status_code=400
            )
        except Exception as e:
            logger.error(f"[!] Request handling failed: {str(e)}", exc_info=True)
            self._send_json_response(
                {"status": "error", "message": str(e)},
                status_code=500
            )

    def do_GET(self):
        self.request_start_time = time.time()
        try:
            RequestLogger.log_request(self)
            
            if self.path == '/containers':
                logger.info(f"[↓] Fetching active containers...")
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
                logger.warning(f"[!] Invalid endpoint requested: {self.path}")
                self._send_json_response(
                    {"status": "error", "message": "Endpoint not found"},
                    status_code=404
                )
        except Exception as e:
            logger.error(f"[!] GET request handling failed: {str(e)}", exc_info=True)
            self._send_json_response(
                {"status": "error", "message": str(e)},
                status_code=500
            )

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
            
            logger.info(f"[+] Compute server starting on port {self.port}")
            
            # Start server in a daemon thread
            server_thread = threading.Thread(target=self._run_server)
            server_thread.daemon = True
            server_thread.start()
            
            logger.info(f"[+] Server successfully started and ready to accept connections")
            return True
            
        except Exception as e:
            logger.error(f"[-] Failed to start server: {str(e)}", exc_info=True)
            self.is_running = False
            return False
            
    def _run_server(self):
        try:
            while self.is_running:
                self.server.handle_request()
        except Exception as e:
            logger.error(f"[-] Server loop error: {str(e)}", exc_info=True)
            self.is_running = False
            
    def stop(self):
        logger.info("[-] Initiating server shutdown...")
        self.is_running = False
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        logger.info("[-] Server shutdown complete")