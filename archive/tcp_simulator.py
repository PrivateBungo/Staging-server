#!/usr/bin/env python3
"""
TCP Service Simulator for NetBox

This service listens on configured IP addresses and ports, returning
configured banners to connecting clients. It logs all connection attempts
for operational visibility.

Configuration is read from a JSON file (default: /etc/netbox_reconcile/tcp_services.json)

The service supports:
- Multiple TCP listeners on different IP:port combinations
- Custom banner responses per service
- Connection logging with timestamps, source/dest IP, and port
- Graceful shutdown on SIGTERM/SIGINT
- Automatic configuration reload on SIGHUP
"""

import socket
import json
import logging
import signal
import sys
import os
import threading
import time
from datetime import datetime
from pathlib import Path

# Configuration
DEFAULT_CONFIG_PATH = "/etc/netbox_reconcile/tcp_services.json"
DEFAULT_LOG_PATH = "/etc/netbox_reconcile/tcp_connections.log"
DEFAULT_PID_FILE = "/etc/netbox_reconcile/tcp_simulator.pid"

# Global state
running = True
listener_threads = []
config = {"services": []}
logger = None


def setup_logging(log_path: str = DEFAULT_LOG_PATH):
    """Set up logging for connection tracking."""
    global logger
    
    # Ensure log directory exists
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Create a dedicated logger for connection events
    logger = logging.getLogger('tcp_simulator')
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers = []
    
    # File handler for persistent logs
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Also log to stdout for container visibility
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    
    return logger


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"services": []}
    except json.JSONDecodeError as e:
        print(f"Error parsing config file: {e}", file=sys.stderr)
        return {"services": []}
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return {"services": []}


def log_connection(src_ip: str, src_port: int, dest_ip: str, dest_port: int, banner: str, success: bool = True):
    """Log a TCP connection attempt."""
    if logger:
        status = "ACCEPTED" if success else "REJECTED"
        logger.info(f"{status} | src={src_ip}:{src_port} | dst={dest_ip}:{dest_port} | banner={banner}")


def handle_client(conn: socket.socket, addr: tuple, banner: str):
    """Handle a single TCP client connection."""
    src_ip, src_port = addr
    try:
        # Send the banner
        conn.sendall(banner.encode('utf-8', errors='replace') + b'\n')
        log_connection(src_ip, src_port, conn.getpeername()[0] if hasattr(conn, 'getpeername') else 'unknown', 
                      conn.getsockname()[1] if hasattr(conn, 'getsockname') else 'unknown', banner, True)
    except (ConnectionResetError, BrokenPipeError):
        # Client disconnected before we could respond
        log_connection(src_ip, src_port, 'unknown', 0, banner, False)
    except Exception as e:
        log_connection(src_ip, src_port, 'unknown', 0, banner, False)
        print(f"Error handling client {addr}: {e}", file=sys.stderr)
    finally:
        try:
            conn.close()
        except:
            pass


def create_listener(ip: str, port: int, banner: str, protocol: str = "tcp"):
    """Create a TCP listener for a specific IP:port with a banner."""
    addr = (ip, port)
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # For specific IP binding
        if ip != '0.0.0.0':
            sock.bind(addr)
        else:
            # Bind to all interfaces on the port
            sock.bind(('', port))
        
        sock.listen(128)
        print(f"Listening on {ip}:{port} with banner: {banner}")
        
        def listener_loop():
            while running:
                try:
                    conn, addr = sock.accept()
                    # Handle client in a new thread
                    client_thread = threading.Thread(
                        target=handle_client,
                        args=(conn, addr, banner),
                        daemon=True
                    )
                    client_thread.start()
                except OSError:
                    # Socket closed
                    break
                except Exception as e:
                    print(f"Error in listener for {ip}:{port}: {e}", file=sys.stderr)
        
        thread = threading.Thread(target=listener_loop, daemon=True)
        thread.start()
        listener_threads.append((sock, thread))
        
        return sock, thread
        
    except Exception as e:
        print(f"Failed to create listener for {ip}:{port}: {e}", file=sys.stderr)
        return None, None


def start_listeners(config_data: dict):
    """Start TCP listeners based on configuration."""
    global listener_threads
    
    # Clear existing listeners
    stop_all_listeners()
    
    services = config_data.get("services", [])
    
    for service in services:
        ip = service.get("ip", "0.0.0.0")
        port = service.get("port", 0)
        banner = service.get("banner", "")
        protocol = service.get("protocol", "tcp")
        
        if port > 0 and ip:
            create_listener(ip, port, banner, protocol)
        else:
            print(f"Skipping invalid service: {service}", file=sys.stderr)


def stop_all_listeners():
    """Stop all active TCP listeners."""
    global listener_threads
    
    for sock, thread in listener_threads:
        try:
            sock.close()
        except:
            pass
    
    listener_threads = []


def write_pid_file(pid_file: str = DEFAULT_PID_FILE):
    """Write PID file for the running service."""
    try:
        pid_dir = os.path.dirname(pid_file)
        if pid_dir:
            os.makedirs(pid_dir, exist_ok=True)
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        print(f"Warning: Could not write PID file: {e}", file=sys.stderr)


def remove_pid_file(pid_file: str = DEFAULT_PID_FILE):
    """Remove PID file."""
    try:
        if os.path.exists(pid_file):
            os.remove(pid_file)
    except:
        pass


def signal_handler(sig, frame):
    """Handle signals for graceful shutdown."""
    global running
    
    if sig in (signal.SIGTERM, signal.SIGINT):
        print("Shutting down gracefully...")
        running = False
        stop_all_listeners()
        remove_pid_file()
        sys.exit(0)
    elif sig == signal.SIGHUP:
        print("Reloading configuration...")
        global config
        config = load_config()
        start_listeners(config)


def main():
    """Main entry point for the TCP simulator service."""
    global config, running
    
    # Parse command line arguments
    config_path = DEFAULT_CONFIG_PATH
    log_path = DEFAULT_LOG_PATH
    
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    if len(sys.argv) > 2:
        log_path = sys.argv[2]
    
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGHUP, signal_handler)
    
    # Set up logging
    setup_logging(log_path)
    
    # Write PID file
    write_pid_file()
    
    print(f"Starting TCP Simulator Service")
    print(f"  Config: {config_path}")
    print(f"  Log: {log_path}")
    
    # Load initial configuration
    config = load_config(config_path)
    
    # Start listeners
    start_listeners(config)
    
    # Keep main thread alive
    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    # Cleanup
    stop_all_listeners()
    remove_pid_file()


if __name__ == "__main__":
    main()
