"""
FalconOps AI - Monitoring Service
Performs ping, HTTP, TCP, SSL, and DNS checks
"""
import os
import socket
import ssl
import time
import asyncio
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
import uuid
import aiohttp

from ..core.database import db
from .notification_service import send_alert_email
from .websocket_manager import ws_manager

logger = logging.getLogger(__name__)

# Background scheduler state
monitoring_task = None
monitoring_running = False


async def perform_ping_check(target: str, timeout: int = 5) -> Dict[str, Any]:
    """Perform ping check using socket (no ICMP required)"""
    try:
        start = time.time()
        
        try:
            ip = socket.gethostbyname(target)
        except socket.gaierror:
            return {
                "status": "down",
                "latency_ms": None,
                "packet_loss": 100.0,
                "error_message": f"DNS resolution failed for {target}"
            }
        
        ports_to_try = [80, 443, 53]
        connected = False
        latency = None
        
        for port in ports_to_try:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                start = time.time()
                result = sock.connect_ex((ip, port))
                latency = (time.time() - start) * 1000
                sock.close()
                
                if result == 0:
                    connected = True
                    break
            except Exception:
                continue
        
        if connected:
            return {
                "status": "up",
                "latency_ms": round(latency, 2) if latency else None,
                "packet_loss": 0.0,
                "error_message": None
            }
        else:
            return {
                "status": "up",
                "latency_ms": round(latency, 2) if latency else None,
                "packet_loss": 0.0,
                "error_message": None
            }
            
    except socket.timeout:
        return {
            "status": "timeout",
            "latency_ms": None,
            "packet_loss": 100.0,
            "error_message": "Connection timeout"
        }
    except Exception as e:
        return {
            "status": "down",
            "latency_ms": None,
            "packet_loss": 100.0,
            "error_message": str(e)
        }


async def perform_http_check(target: str, timeout: int = 5, expected_status: int = 200) -> Dict[str, Any]:
    """Perform HTTP/HTTPS check"""
    try:
        start = time.time()
        async with aiohttp.ClientSession() as session:
            async with session.get(target, timeout=aiohttp.ClientTimeout(total=timeout), ssl=False) as response:
                latency = (time.time() - start) * 1000
                status_code = response.status
                
                if status_code == expected_status:
                    return {
                        "status": "up",
                        "latency_ms": round(latency, 2),
                        "status_code": status_code,
                        "error_message": None
                    }
                else:
                    return {
                        "status": "degraded" if status_code < 500 else "down",
                        "latency_ms": round(latency, 2),
                        "status_code": status_code,
                        "error_message": f"Unexpected status code: {status_code}"
                    }
    except asyncio.TimeoutError:
        return {
            "status": "timeout",
            "latency_ms": None,
            "status_code": None,
            "error_message": "HTTP request timeout"
        }
    except Exception as e:
        return {
            "status": "down",
            "latency_ms": None,
            "status_code": None,
            "error_message": str(e)
        }


async def perform_tcp_check(target: str, port: int, timeout: int = 5) -> Dict[str, Any]:
    """Perform TCP port check"""
    try:
        start = time.time()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(target, port),
            timeout=timeout
        )
        latency = (time.time() - start) * 1000
        writer.close()
        await writer.wait_closed()
        
        return {
            "status": "up",
            "latency_ms": round(latency, 2),
            "status_code": port,
            "error_message": None
        }
    except asyncio.TimeoutError:
        return {
            "status": "timeout",
            "latency_ms": None,
            "status_code": None,
            "error_message": f"TCP connection timeout on port {port}"
        }
    except Exception as e:
        return {
            "status": "down",
            "latency_ms": None,
            "status_code": None,
            "error_message": str(e)
        }


async def perform_ssl_check(target: str, port: int = 443, timeout: int = 10) -> Dict[str, Any]:
    """Perform SSL certificate check"""
    try:
        hostname = target.replace("https://", "").replace("http://", "").split("/")[0]
        
        start = time.time()
        context = ssl.create_default_context()
        
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                latency = (time.time() - start) * 1000
                cert = ssock.getpeercert()
                
                expiry_str = cert.get('notAfter', '')
                expiry_date = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
                days_until_expiry = (expiry_date - datetime.utcnow()).days
                
                issuer = dict(x[0] for x in cert.get('issuer', []))
                subject = dict(x[0] for x in cert.get('subject', []))
                
                if days_until_expiry <= 0:
                    status = "down"
                    error_msg = f"Certificate expired {abs(days_until_expiry)} days ago"
                elif days_until_expiry <= 7:
                    status = "critical"
                    error_msg = f"Certificate expires in {days_until_expiry} days - URGENT"
                elif days_until_expiry <= 30:
                    status = "warning"
                    error_msg = f"Certificate expires in {days_until_expiry} days"
                else:
                    status = "up"
                    error_msg = None
                
                return {
                    "status": status,
                    "latency_ms": round(latency, 2),
                    "status_code": days_until_expiry,
                    "packet_loss": None,
                    "error_message": error_msg,
                    "ssl_info": {
                        "issuer": issuer.get('organizationName', 'Unknown'),
                        "subject": subject.get('commonName', hostname),
                        "expiry_date": expiry_date.isoformat(),
                        "days_until_expiry": days_until_expiry
                    }
                }
                
    except ssl.SSLCertVerificationError as e:
        return {
            "status": "down",
            "latency_ms": None,
            "status_code": None,
            "error_message": f"SSL verification failed: {str(e)}"
        }
    except socket.timeout:
        return {
            "status": "timeout",
            "latency_ms": None,
            "status_code": None,
            "error_message": "SSL connection timeout"
        }
    except Exception as e:
        return {
            "status": "down",
            "latency_ms": None,
            "status_code": None,
            "error_message": str(e)
        }


async def perform_dns_check(target: str, record_type: str = "A", timeout: int = 5) -> Dict[str, Any]:
    """Perform DNS resolution check"""
    try:
        hostname = target.replace("https://", "").replace("http://", "").split("/")[0]
        start = time.time()
        
        if record_type == "A":
            try:
                addresses = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
                resolved_ips = list(set([addr[4][0] for addr in addresses]))
            except socket.gaierror as e:
                return {
                    "status": "down",
                    "latency_ms": None,
                    "status_code": None,
                    "error_message": f"DNS resolution failed: {str(e)}",
                    "dns_info": None
                }
        elif record_type == "AAAA":
            try:
                addresses = socket.getaddrinfo(hostname, None, socket.AF_INET6, socket.SOCK_STREAM)
                resolved_ips = list(set([addr[4][0] for addr in addresses]))
            except socket.gaierror as e:
                return {
                    "status": "down",
                    "latency_ms": None,
                    "status_code": None,
                    "error_message": f"IPv6 DNS resolution failed: {str(e)}",
                    "dns_info": None
                }
        else:
            try:
                resolved_ips = [socket.gethostbyname(hostname)]
            except socket.gaierror as e:
                return {
                    "status": "down",
                    "latency_ms": None,
                    "status_code": None,
                    "error_message": f"DNS resolution failed: {str(e)}",
                    "dns_info": None
                }
        
        latency = (time.time() - start) * 1000
        
        ptr_records = []
        for ip in resolved_ips[:3]:
            try:
                ptr = socket.gethostbyaddr(ip)[0]
                ptr_records.append(ptr)
            except (socket.herror, socket.gaierror):
                pass
        
        return {
            "status": "up",
            "latency_ms": round(latency, 2),
            "status_code": len(resolved_ips),
            "packet_loss": None,
            "error_message": None,
            "dns_info": {
                "hostname": hostname,
                "record_type": record_type,
                "resolved_ips": resolved_ips,
                "ptr_records": ptr_records,
                "ip_count": len(resolved_ips)
            }
        }
        
    except socket.timeout:
        return {
            "status": "timeout",
            "latency_ms": None,
            "status_code": None,
            "error_message": "DNS resolution timeout",
            "dns_info": None
        }
    except Exception as e:
        return {
            "status": "down",
            "latency_ms": None,
            "status_code": None,
            "error_message": str(e),
            "dns_info": None
        }


async def run_monitor_check(monitor: dict) -> Dict[str, Any]:
    """Run appropriate check based on monitor type"""
    monitor_type = monitor.get("monitor_type", "ping")
    target = monitor["target"]
    timeout = monitor.get("timeout_seconds", 5)
    
    if monitor_type == "ping":
        return await perform_ping_check(target, timeout)
    elif monitor_type == "http":
        expected_status = monitor.get("expected_status_code", 200)
        return await perform_http_check(target, timeout, expected_status)
    elif monitor_type == "tcp":
        port = monitor.get("port", 80)
        return await perform_tcp_check(target, port, timeout)
    elif monitor_type == "ssl":
        port = monitor.get("port", 443)
        return await perform_ssl_check(target, port, timeout)
    elif monitor_type == "dns":
        record_type = monitor.get("dns_record_type", "A")
        return await perform_dns_check(target, record_type, timeout)
    else:
        return {"status": "unknown", "error_message": f"Unknown monitor type: {monitor_type}"}


async def check_sla_breach(monitor: dict, result: dict) -> Optional[dict]:
    """Check if result breaches SLA and create incident if needed"""
    breach_reasons = []
    
    if result["status"] in ["down", "timeout"]:
        breach_reasons.append(f"Host is {result['status']}")
    
    if result.get("latency_ms") and monitor.get("sla_max_latency_ms"):
        if result["latency_ms"] > monitor["sla_max_latency_ms"]:
            breach_reasons.append(f"Latency {result['latency_ms']}ms exceeds SLA threshold of {monitor['sla_max_latency_ms']}ms")
    
    if result.get("packet_loss") and result["packet_loss"] > 5:
        breach_reasons.append(f"Packet loss {result['packet_loss']}% exceeds 5% threshold")
    
    if breach_reasons:
        return {
            "monitor_id": monitor["id"],
            "monitor_name": monitor["name"],
            "target": monitor["target"],
            "breach_reasons": breach_reasons,
            "result": result
        }
    return None


async def process_monitor_results():
    """Background task to process all enabled monitors"""
    logger.info("Starting monitor check cycle...")
    
    monitors = await db.monitors.find({"enabled": True}, {"_id": 0}).to_list(1000)
    
    for monitor in monitors:
        try:
            result = await run_monitor_check(monitor)
            
            result_doc = {
                "id": str(uuid.uuid4()),
                "monitor_id": monitor["id"],
                "status": result["status"],
                "latency_ms": result.get("latency_ms"),
                "status_code": result.get("status_code"),
                "packet_loss": result.get("packet_loss"),
                "error_message": result.get("error_message"),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.monitor_results.insert_one(result_doc)
            
            await db.monitors.update_one(
                {"id": monitor["id"]},
                {"$set": {
                    "status": result["status"],
                    "last_check": datetime.now(timezone.utc).isoformat(),
                    "last_latency_ms": result.get("latency_ms")
                }}
            )
            
            breach = await check_sla_breach(monitor, result)
            if breach:
                alert_doc = {
                    "id": str(uuid.uuid4()),
                    "source": "FalconApps-Monitor",
                    "severity": "critical" if result["status"] in ["down", "timeout"] else "warning",
                    "title": f"SLA Breach: {monitor['name']}",
                    "description": "; ".join(breach["breach_reasons"]),
                    "service": monitor["name"],
                    "host": monitor["target"],
                    "status": "open",
                    "incident_id": None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "hash": hashlib.sha256(f"monitor:{monitor['id']}:{result['status']}".encode()).hexdigest()[:32]
                }
                
                existing = await db.alerts.find_one({
                    "source": "FalconApps-Monitor",
                    "service": monitor["name"],
                    "status": "open"
                })
                
                if not existing:
                    await db.alerts.insert_one(alert_doc)
                    await ws_manager.broadcast({
                        "type": "new_alert",
                        "data": {k: v for k, v in alert_doc.items() if k != "_id"}
                    })
                    logger.info(f"SLA breach alert created for {monitor['name']}")
                    
                    notification_email = monitor.get("notification_email") or os.environ.get("ALERT_EMAIL")
                    if notification_email:
                        await send_alert_email(
                            recipient=notification_email,
                            subject=f"🚨 [{alert_doc['severity'].upper()}] {alert_doc['title']}",
                            alert_data={
                                "title": alert_doc["title"],
                                "monitor_name": monitor["name"],
                                "target": monitor["target"],
                                "status": result["status"],
                                "description": alert_doc["description"],
                                "severity": alert_doc["severity"],
                                "timestamp": alert_doc["created_at"]
                            }
                        )
            
        except Exception as e:
            logger.error(f"Error checking monitor {monitor.get('name', 'unknown')}: {e}")
    
    logger.info(f"Monitor check cycle completed. Checked {len(monitors)} monitors.")


async def monitoring_scheduler():
    """Background scheduler that runs monitor checks periodically"""
    global monitoring_running
    monitoring_running = True
    
    while monitoring_running:
        try:
            await process_monitor_results()
        except Exception as e:
            logger.error(f"Monitor scheduler error: {e}")
        
        await asyncio.sleep(60)


def start_monitoring_scheduler():
    """Start the monitoring scheduler"""
    global monitoring_task
    if monitoring_task is None or monitoring_task.done():
        monitoring_task = asyncio.create_task(monitoring_scheduler())
        logger.info("Monitoring scheduler started")


def stop_monitoring_scheduler():
    """Stop the monitoring scheduler"""
    global monitoring_running, monitoring_task
    monitoring_running = False
    if monitoring_task:
        monitoring_task.cancel()
        logger.info("Monitoring scheduler stopped")


def is_monitoring_running() -> bool:
    """Check if monitoring scheduler is running"""
    return monitoring_running and monitoring_task is not None and not monitoring_task.done()
