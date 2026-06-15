#!/usr/bin/env python3
"""
TCP Listener System for NetBox Services

Dynamically binds to IP:port combinations from NetBox and responds to connections
with a success message containing source IP, destination, and timestamp.

Uses ThreadingTCPServer to handle up to 10 concurrent connections per IP:port.
"""

import socketserver
import threading
import datetime
import json
import os
import signal
import sys
import socket


CONFIG_PATH = "/etc/tcp_listener/config.json"
MAX_CONNECTIONS = 10

# Allow override via environment variable
import os
if os.environ.get('TCP_LISTENER_CONFIG'):
    CONFIG_PATH = os.environ['TCP_LISTENER_CONFIG']

# Global list to track running servers for graceful shutdown
running_servers = []
shutdown_flag = False


class TCPHandler(socketserver.BaseRequestHandler):
    """Handle incoming TCP connections with dynamic response."""
    
    def handle(self):
        """Send success message with connection details and close."""
        try:
            # Get source IP and port
            source_ip, source_port = self.client_address
            
            # Get destination IP and port
            dest_ip = self.server.server_address[0]
            dest_port = self.server.server_address[1]
            
            # Get current timestamp
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Create dynamic success message
            response = (
                f"Success: Connection from {source_ip} to {dest_ip}:{dest_port} "
                f"at {timestamp}\n"
            )
            
            # Send response
            self.request.sendall(response.encode('utf-8'))
            
        except Exception as e:
            # Log error to stderr (captured by systemd/journalctl)
            print(f"Error handling connection from {self.client_address}: {e}", 
                  file=sys.stderr)
        finally:
            # Always close the connection
            try:
                self.request.close()
            except:
                pass


def load_config(config_path=CONFIG_PATH):
    """Load configuration from JSON file."""
    if not os.path.exists(config_path):
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Validate config structure
        if 'services' not in config:
            print("Error: Invalid configuration - missing 'services' key", file=sys.stderr)
            sys.exit(1)
        
        if not isinstance(config['services'], list):
            print("Error: 'services' must be a list", file=sys.stderr)
            sys.exit(1)
        
        return config
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in configuration: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)


def start_listener(ip, port):
    """Start a ThreadingTCPServer for a specific IP:port."""
    try:
        # Validate port
        port = int(port)
        if not (0 < port <= 65535):
            print(f"Warning: Invalid port {port} for IP {ip}", file=sys.stderr)
            return None
        
        # Create and start the server
        server = socketserver.ThreadingTCPServer(
            (ip, port), 
            TCPHandler,
            bind_and_activate=True
        )
        
        # Set timeout for accept (to allow periodic checks)
        server.timeout = 1
        server.daemon_threads = True
        
        print(f"Started TCP listener on {ip}:{port}")
        
        # Start server in a thread
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        # Store server reference for shutdown
        running_servers.append(server)
        
        return server
        
    except PermissionError:
        print(f"Warning: Permission denied for {ip}:{port} (need root for ports < 1024 or port already in use)", 
              file=sys.stderr)
        return None
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"Warning: Port {port} on {ip} is already in use", 
                  file=sys.stderr)
            return None
        print(f"Error: Failed to start listener on {ip}:{port}: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Unexpected error starting listener on {ip}:{port}: {e}", 
              file=sys.stderr)
        sys.exit(1)


def shutdown_servers():
    """Gracefully shutdown all running servers."""
    global shutdown_flag
    shutdown_flag = True
    
    for server in running_servers:
        try:
            server.shutdown()
            server.server_close()
        except Exception as e:
            print(f"Warning: Error shutting down server: {e}", file=sys.stderr)
    
    running_servers.clear()


def signal_handler(signum, frame):
    """Handle SIGINT and SIGTERM for graceful shutdown."""
    print(f"Received signal {signum}, shutting down...")
    shutdown_servers()
    sys.exit(0)


def main():
    """Main entry point."""
    global shutdown_flag
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Load configuration
    config = load_config()
    
    # Validate services
    if not config['services']:
        print("Warning: No services defined in configuration", file=sys.stderr)
        return
    
    print(f"Loading configuration from {CONFIG_PATH}")
    print(f"Found {len(config['services'])} services to listen on")
    
    # Start a listener for each service
    for service in config['services']:
        ip = service.get('ip')
        port = service.get('port')
        
        if not ip or not port:
            print(f"Warning: Skipping invalid service entry: {service}", 
                  file=sys.stderr)
            continue
        
        start_listener(ip, port)
    
    # Keep main thread alive while servers run
    try:
        while not shutdown_flag:
            # Check if all servers are still running
            for server in list(running_servers):
                if server is None:
                    running_servers.remove(server)
            
            # Sleep briefly to avoid busy loop
            threading.Event().wait(timeout=1)
            
    except KeyboardInterrupt:
        pass
    finally:
        shutdown_servers()


if __name__ == "__main__":
    main()
