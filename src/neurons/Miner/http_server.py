import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ComputeRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request = json.loads(post_data.decode())
            
            # Process request based on path
            if self.path == '/allocate':
                response = self.server.allocator.allocate_resources(request)
            else:
                response = {"status": "error", "message": "Invalid endpoint"}

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            logger.error(f"HTTP request handling failed: {str(e)}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_response = {"status": "error", "message": str(e)}
            self.wfile.write(json.dumps(error_response).encode())

    def do_GET(self):
        try:
            if self.path == '/containers':
                # Get list of active containers
                containers = self.server.allocator.get_active_containers()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(containers).encode())
            else:
                self.send_error(404, "Endpoint not found")
        except Exception as e:
            logger.error(f"GET request handling failed: {str(e)}")
            self.send_error(500, str(e))

    def do_PUT(self):
        try:
            if self.path.startswith('/challenge/'):
                container_id = self.path.split('/')[-1]
                content_length = int(self.headers['Content-Length'])
                challenge_data = self.rfile.read(content_length)
                challenge = json.loads(challenge_data.decode())
                
                # Process challenge
                result = self.server.allocator.process_challenge(container_id, challenge)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            else:
                self.send_error(404, "Endpoint not found")
        except Exception as e:
            logger.error(f"PUT request handling failed: {str(e)}")
            self.send_error(500, str(e))


class ComputeServer:
    def __init__(self, port: int = 8080, allocator=None):
        self.port = port
        self.server = None
        self.allocator = allocator
        
    def start(self):
        try:
            self.server = HTTPServer(('', self.port), ComputeRequestHandler)
            # Add allocator to server instance
            self.server.allocator = self.allocator
            server_thread = threading.Thread(target=self.server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            logger.info(f"Server started on port {self.port}")
        except Exception as e:
            logger.error(f"Server start failed: {str(e)}")
            raise

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()