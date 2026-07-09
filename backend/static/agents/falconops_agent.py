#!/usr/bin/env python3
"""
FalconOps AI - Server Monitoring Agent
Lightweight Python agent for collecting and reporting server metrics

Usage:
    python falconops_agent.py --api-url https://your-falconops.com/api
    
Features:
    - CPU, Memory, Disk, Network metrics collection
    - Automatic server registration with secure token
    - Offline buffering with retry logic
    - Low resource footprint (<1% CPU, <50MB RAM)
    - Works on Linux and Windows
"""

import os
import sys
import time
import json
import socket
import platform
import argparse
import logging
import threading
from datetime import datetime
from pathlib import Path
from collections import deque

try:
    import psutil
except ImportError:
    print("Error: psutil is required. Install with: pip install psutil")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Error: requests is required. Install with: pip install requests")
    sys.exit(1)

# Configuration
DEFAULT_INTERVAL = 30  # seconds
DEFAULT_TIMEOUT = 10   # seconds
MAX_BUFFER_SIZE = 1000  # max offline metrics to buffer
CONFIG_DIR = Path.home() / ".falconops"
CONFIG_FILE = CONFIG_DIR / "agent.json"
LOG_FILE = CONFIG_DIR / "agent.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE) if CONFIG_DIR.exists() else logging.StreamHandler()
    ]
)
logger = logging.getLogger("FalconOpsAgent")


class FalconOpsAgent:
    """FalconOps Server Monitoring Agent"""
    
    def __init__(self, api_url: str, interval: int = DEFAULT_INTERVAL):
        self.api_url = api_url.rstrip('/')
        self.interval = interval
        self.agent_token = None
        self.server_id = None
        self.running = False
        self.offline_buffer = deque(maxlen=MAX_BUFFER_SIZE)
        
        # Ensure config directory exists
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load existing config
        self.load_config()
    
    def load_config(self):
        """Load agent configuration from file"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.agent_token = config.get('agent_token')
                    self.server_id = config.get('server_id')
                    self.api_url = config.get('api_url', self.api_url)
                    logger.info(f"Loaded config: server_id={self.server_id}")
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
    
    def save_config(self):
        """Save agent configuration to file"""
        try:
            config = {
                'agent_token': self.agent_token,
                'server_id': self.server_id,
                'api_url': self.api_url,
                'registered_at': datetime.utcnow().isoformat()
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved config to {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def get_hostname(self) -> str:
        """Get server hostname"""
        return socket.gethostname()
    
    def get_ip_address(self) -> str:
        """Get primary IP address"""
        try:
            # Create a socket to determine the primary IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def get_os_info(self) -> tuple:
        """Get OS type and version"""
        os_type = platform.system().lower()
        if os_type == "linux":
            try:
                import distro
                os_version = f"{distro.name()} {distro.version()}"
            except ImportError:
                os_version = platform.release()
        elif os_type == "windows":
            os_version = platform.version()
        elif os_type == "darwin":
            os_type = "macos"
            os_version = platform.mac_ver()[0]
        else:
            os_version = platform.release()
        
        return os_type, os_version
    
    def register(self) -> bool:
        """Register server with FalconOps API"""
        if self.agent_token:
            logger.info("Already registered, using existing token")
            return True
        
        os_type, os_version = self.get_os_info()
        
        payload = {
            "hostname": self.get_hostname(),
            "ip_address": self.get_ip_address(),
            "os_type": os_type,
            "os_version": os_version,
            "agent_version": "1.0.0"
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/servers/register",
                json=payload,
                timeout=DEFAULT_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                self.agent_token = data.get('agent_token')
                self.server_id = data.get('server_id')
                self.save_config()
                logger.info(f"Registered successfully: server_id={self.server_id}")
                return True
            else:
                logger.error(f"Registration failed: {response.status_code} - {response.text}")
                return False
        except requests.RequestException as e:
            logger.error(f"Registration failed: {e}")
            return False
    
    def collect_metrics(self) -> dict:
        """Collect server metrics"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_gb = memory.used / (1024 ** 3)
            memory_total_gb = memory.total / (1024 ** 3)
            
            # Disk
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_used_gb = disk.used / (1024 ** 3)
            disk_total_gb = disk.total / (1024 ** 3)
            
            # Network
            net_io = psutil.net_io_counters()
            # Convert to Mbps (rough estimate over interval)
            network_in_mbps = (net_io.bytes_recv / 1024 / 1024) / self.interval if hasattr(self, '_last_net_recv') else 0
            network_out_mbps = (net_io.bytes_sent / 1024 / 1024) / self.interval if hasattr(self, '_last_net_sent') else 0
            self._last_net_recv = net_io.bytes_recv
            self._last_net_sent = net_io.bytes_sent
            
            # Load average (Linux/Mac only)
            load_average_1m = None
            load_average_5m = None
            load_average_15m = None
            if hasattr(os, 'getloadavg'):
                load = os.getloadavg()
                load_average_1m = load[0]
                load_average_5m = load[1]
                load_average_15m = load[2]
            
            # Process count
            process_count = len(psutil.pids())
            
            # Uptime
            boot_time = psutil.boot_time()
            uptime_seconds = int(time.time() - boot_time)
            
            return {
                "agent_token": self.agent_token,
                "cpu_percent": round(cpu_percent, 1),
                "memory_percent": round(memory_percent, 1),
                "memory_used_gb": round(memory_used_gb, 2),
                "memory_total_gb": round(memory_total_gb, 2),
                "disk_percent": round(disk_percent, 1),
                "disk_used_gb": round(disk_used_gb, 2),
                "disk_total_gb": round(disk_total_gb, 2),
                "network_in_mbps": round(network_in_mbps, 2),
                "network_out_mbps": round(network_out_mbps, 2),
                "load_average_1m": round(load_average_1m, 2) if load_average_1m else None,
                "load_average_5m": round(load_average_5m, 2) if load_average_5m else None,
                "load_average_15m": round(load_average_15m, 2) if load_average_15m else None,
                "process_count": process_count,
                "uptime_seconds": uptime_seconds,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to collect metrics: {e}")
            return None
    
    def send_metrics(self, metrics: dict) -> bool:
        """Send metrics to FalconOps API"""
        try:
            response = requests.post(
                f"{self.api_url}/servers/metrics/ingest",
                json=metrics,
                timeout=DEFAULT_TIMEOUT
            )
            
            if response.status_code == 200:
                logger.debug(f"Metrics sent successfully")
                return True
            elif response.status_code == 401:
                logger.error("Invalid agent token - re-registering")
                self.agent_token = None
                self.register()
                return False
            else:
                logger.error(f"Failed to send metrics: {response.status_code}")
                return False
        except requests.RequestException as e:
            logger.error(f"Failed to send metrics: {e}")
            return False
    
    def flush_buffer(self):
        """Attempt to send buffered metrics"""
        while self.offline_buffer:
            metrics = self.offline_buffer[0]
            if self.send_metrics(metrics):
                self.offline_buffer.popleft()
            else:
                break
    
    def run(self):
        """Main agent loop"""
        logger.info(f"Starting FalconOps Agent v1.0.0")
        logger.info(f"API URL: {self.api_url}")
        logger.info(f"Interval: {self.interval}s")
        
        # Register if needed
        if not self.register():
            logger.error("Failed to register, retrying in 60 seconds...")
            time.sleep(60)
            if not self.register():
                logger.error("Registration failed, exiting")
                return
        
        self.running = True
        logger.info("Agent started, collecting metrics...")
        
        while self.running:
            try:
                # Collect metrics
                metrics = self.collect_metrics()
                if not metrics:
                    continue
                
                # Try to flush any buffered metrics first
                if self.offline_buffer:
                    self.flush_buffer()
                
                # Send current metrics
                if not self.send_metrics(metrics):
                    # Buffer for later
                    self.offline_buffer.append(metrics)
                    logger.warning(f"Metrics buffered ({len(self.offline_buffer)} in queue)")
                
                # Wait for next interval
                time.sleep(self.interval)
                
            except KeyboardInterrupt:
                logger.info("Shutting down agent...")
                self.running = False
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(self.interval)
        
        logger.info("Agent stopped")
    
    def stop(self):
        """Stop the agent"""
        self.running = False


def main():
    parser = argparse.ArgumentParser(
        description="FalconOps AI Server Monitoring Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start agent with default settings
  python falconops_agent.py --api-url https://your-falconops.com/api
  
  # Custom interval
  python falconops_agent.py --api-url https://your-falconops.com/api --interval 60
  
  # View current config
  python falconops_agent.py --show-config
        """
    )
    
    parser.add_argument(
        '--api-url',
        help='FalconOps API URL (e.g., https://your-falconops.com/api)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=DEFAULT_INTERVAL,
        help=f'Metrics collection interval in seconds (default: {DEFAULT_INTERVAL})'
    )
    parser.add_argument(
        '--show-config',
        action='store_true',
        help='Show current agent configuration'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset agent configuration and re-register'
    )
    
    args = parser.parse_args()
    
    # Show config
    if args.show_config:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                print(json.dumps(config, indent=2))
        else:
            print("No configuration found. Run with --api-url to register.")
        return
    
    # Reset config
    if args.reset:
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
            print("Configuration reset. Run again with --api-url to re-register.")
        else:
            print("No configuration to reset.")
        return
    
    # Load API URL from config if not provided
    api_url = args.api_url
    if not api_url and CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                api_url = config.get('api_url')
        except Exception:
            pass
    
    if not api_url:
        print("Error: --api-url is required for first run")
        print("Usage: python falconops_agent.py --api-url https://your-falconops.com/api")
        sys.exit(1)
    
    # Create and run agent
    agent = FalconOpsAgent(api_url, args.interval)
    
    try:
        agent.run()
    except KeyboardInterrupt:
        agent.stop()


if __name__ == "__main__":
    main()
