"""
FalconOps AI - Notification Service
Email (SendGrid) and Teams webhook notifications
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


async def send_alert_email(recipient: str, subject: str, alert_data: dict) -> bool:
    """Send alert notification email via SendGrid"""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        sendgrid_key = os.environ.get('SENDGRID_API_KEY')
        sender_email = os.environ.get('SENDER_EMAIL', 'alerts@falconapps.com')
        
        if not sendgrid_key:
            logger.warning("SendGrid API key not configured - skipping email notification")
            return False
        
        severity_colors = {
            "critical": "#EF4444",
            "warning": "#F59E0B",
            "info": "#00F0FF"
        }
        severity = alert_data.get("severity", "warning")
        color = severity_colors.get(severity, "#F59E0B")
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #050505; color: #fff; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #0a0a0a; border: 1px solid #1a1a1a; border-radius: 4px; }}
                .header {{ background: {color}; color: #000; padding: 20px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 18px; text-transform: uppercase; letter-spacing: 2px; }}
                .content {{ padding: 20px; }}
                .alert-box {{ background: rgba(255,255,255,0.05); border-left: 3px solid {color}; padding: 15px; margin: 15px 0; }}
                .label {{ color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }}
                .value {{ color: #fff; font-size: 16px; margin-top: 5px; }}
                .footer {{ padding: 15px 20px; border-top: 1px solid #1a1a1a; text-align: center; color: #666; font-size: 12px; }}
                .logo {{ color: #D4AF37; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚨 {severity.upper()} ALERT</h1>
                </div>
                <div class="content">
                    <div class="alert-box">
                        <div class="label">Alert Title</div>
                        <div class="value">{alert_data.get('title', 'Unknown Alert')}</div>
                    </div>
                    <div class="alert-box">
                        <div class="label">Monitor</div>
                        <div class="value">{alert_data.get('monitor_name', 'N/A')}</div>
                    </div>
                    <div class="alert-box">
                        <div class="label">Target</div>
                        <div class="value">{alert_data.get('target', 'N/A')}</div>
                    </div>
                    <div class="alert-box">
                        <div class="label">Status</div>
                        <div class="value" style="color: {color};">{alert_data.get('status', 'Unknown').upper()}</div>
                    </div>
                    <div class="alert-box">
                        <div class="label">Details</div>
                        <div class="value">{alert_data.get('description', 'No additional details')}</div>
                    </div>
                    <div class="alert-box">
                        <div class="label">Timestamp</div>
                        <div class="value">{alert_data.get('timestamp', datetime.now(timezone.utc).isoformat())}</div>
                    </div>
                </div>
                <div class="footer">
                    <span class="logo">FALCON</span>APPS | AI-Powered NOC Intelligence
                </div>
            </div>
        </body>
        </html>
        """
        
        message = Mail(
            from_email=sender_email,
            to_emails=recipient,
            subject=subject,
            html_content=html_content
        )
        
        sg = SendGridAPIClient(sendgrid_key)
        response = sg.send(message)
        
        if response.status_code == 202:
            logger.info(f"Alert email sent successfully to {recipient}")
            return True
        else:
            logger.error(f"Failed to send email: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        return False


async def send_teams_notification(webhook_url: str, alert_data: dict) -> bool:
    """Send alert notification to Microsoft Teams via webhook"""
    import aiohttp
    
    try:
        if not webhook_url:
            logger.warning("Teams webhook URL not configured - skipping notification")
            return False
        
        severity = alert_data.get("severity", "warning")
        severity_colors = {
            "critical": "FF0000",
            "warning": "FFA500",
            "info": "00F0FF"
        }
        theme_color = severity_colors.get(severity, "FFA500")
        
        card_payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": theme_color,
            "summary": alert_data.get("title", "FalconApps Alert"),
            "sections": [{
                "activityTitle": f"🚨 {severity.upper()} ALERT",
                "activitySubtitle": alert_data.get("title", "Unknown Alert"),
                "activityImage": "https://img.icons8.com/fluency/48/000000/alarm.png",
                "facts": [
                    {"name": "Monitor", "value": alert_data.get("monitor_name", "N/A")},
                    {"name": "Target", "value": alert_data.get("target", "N/A")},
                    {"name": "Status", "value": alert_data.get("status", "Unknown").upper()},
                    {"name": "Severity", "value": severity.upper()},
                    {"name": "Details", "value": alert_data.get("description", "No details")},
                    {"name": "Timestamp", "value": alert_data.get("timestamp", datetime.now(timezone.utc).isoformat())}
                ],
                "markdown": True
            }],
            "potentialAction": [
                {
                    "@type": "OpenUri",
                    "name": "View in FalconApps",
                    "targets": [{"os": "default", "uri": os.environ.get("APP_URL", "https://falconapps.com") + "/alerts"}]
                }
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=card_payload, timeout=10) as response:
                if response.status == 200:
                    logger.info("Teams notification sent successfully")
                    return True
                else:
                    text = await response.text()
                    logger.error(f"Teams webhook failed: {response.status} - {text}")
                    return False
                    
    except Exception as e:
        logger.error(f"Teams notification failed: {str(e)}")
        return False


async def send_report_email_with_attachment(
    recipients: List[str],
    subject: str,
    html_content: str,
    pdf_data: Optional[bytes] = None,
    filename: str = "report.pdf"
) -> bool:
    """Send email with optional PDF attachment using SendGrid"""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
        import base64
        
        sendgrid_key = os.environ.get('SENDGRID_API_KEY')
        sender_email = os.environ.get('SENDGRID_FROM_EMAIL', 'noreply@falconops.ai')
        
        if not sendgrid_key:
            logger.warning("SendGrid API key not configured")
            return False
        
        for recipient in recipients:
            message = Mail(
                from_email=sender_email,
                to_emails=recipient,
                subject=subject,
                html_content=html_content
            )
            
            if pdf_data:
                encoded_pdf = base64.b64encode(pdf_data).decode()
                attachment = Attachment(
                    FileContent(encoded_pdf),
                    FileName(filename),
                    FileType('application/pdf'),
                    Disposition('attachment')
                )
                message.attachment = attachment
            
            sg = SendGridAPIClient(sendgrid_key)
            response = sg.send(message)
            
            if response.status_code not in [200, 202]:
                logger.error(f"SendGrid error: {response.status_code}")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Email send error: {e}")
        return False
