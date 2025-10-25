"""
Hermes Notification System
Handles notifications via Telegram and other channels
"""

import logging
import requests
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from .config import Config
from .database import Database

logger = logging.getLogger(__name__)

class NotificationType(Enum):
    """Types of notifications"""
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_STARTED = "job_started"
    SYSTEM_ERROR = "system_error"
    SYSTEM_STATUS = "system_status"
    BACKEND_DOWN = "backend_down"
    BACKEND_RECOVERED = "backend_recovered"
    HIGH_ERROR_RATE = "high_error_rate"
    RESOURCE_WARNING = "resource_warning"

class NotificationPriority(Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class Notification:
    """Notification data structure"""
    notification_type: NotificationType
    title: str
    message: str
    priority: NotificationPriority
    timestamp: datetime
    context: Dict[str, Any]
    job_id: Optional[int] = None
    user_id: Optional[str] = None

class TelegramNotifier:
    """Telegram notification handler"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.enabled = self.config.get('notifications.telegram.enabled', False)
        self.bot_token = self.config.get('notifications.telegram.bot_token')
        self.chat_id = self.config.get('notifications.telegram.chat_id')
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured"""
        return (
            self.enabled and
            self.bot_token and
            self.chat_id and
            self.bot_token != "YOUR_BOT_TOKEN"
        )

    def send_notification(self, notification: Notification) -> bool:
        """Send notification via Telegram"""
        if not self.is_configured():
            logger.warning("Telegram not configured, skipping notification")
            return False

        try:
            # Format message based on type and priority
            message = self._format_message(notification)

            # Send to Telegram
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': True
                },
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"Telegram notification sent: {notification.title}")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    def _format_message(self, notification: Notification) -> str:
        """Format notification message for Telegram"""
        # Priority emojis
        priority_emojis = {
            NotificationPriority.LOW: "🔵",
            NotificationPriority.MEDIUM: "🟡",
            NotificationPriority.HIGH: "🟠",
            NotificationPriority.CRITICAL: "🔴"
        }

        # Type emojis
        type_emojis = {
            NotificationType.JOB_COMPLETED: "✅",
            NotificationType.JOB_FAILED: "❌",
            NotificationType.JOB_STARTED: "🚀",
            NotificationType.SYSTEM_ERROR: "🚨",
            NotificationType.SYSTEM_STATUS: "📊",
            NotificationType.BACKEND_DOWN: "⬇️",
            NotificationType.BACKEND_RECOVERED: "⬆️",
            NotificationType.HIGH_ERROR_RATE: "📈",
            NotificationType.RESOURCE_WARNING: "⚠️"
        }

        priority_emoji = priority_emojis.get(notification.priority, "ℹ️")
        type_emoji = type_emojis.get(notification.notification_type, "ℹ️")

        # Build message
        message = f"{priority_emoji} {type_emoji} <b>{notification.title}</b>\n\n"
        message += f"{notification.message}\n\n"

        # Add context information
        if notification.job_id:
            message += f"📋 Job ID: <code>{notification.job_id}</code>\n"

        if notification.context:
            context_items = []
            for key, value in notification.context.items():
                if key not in ['internal_details', 'traceback']:
                    context_items.append(f"{key}: {value}")
            if context_items:
                message += f"📝 Details: {', '.join(context_items)}\n"

        message += f"🕐 {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

        return message

    def test_connection(self) -> bool:
        """Test Telegram bot connection"""
        if not self.is_configured():
            return False

        try:
            response = requests.get(f"{self.api_url}/getMe", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False

class NotificationManager:
    """Centralized notification management"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.telegram = TelegramNotifier(self.config)
        self.notification_rules = self._load_notification_rules()

    def _load_notification_rules(self) -> Dict[str, Dict[str, Any]]:
        """Load notification rules from configuration"""
        return {
            'job_completed': {
                'enabled': self.config.get('notifications.job_completed.enabled', True),
                'priority': 'medium',
                'telegram': self.config.get('notifications.job_completed.telegram', True)
            },
            'job_failed': {
                'enabled': self.config.get('notifications.job_failed.enabled', True),
                'priority': 'high',
                'telegram': self.config.get('notifications.job_failed.telegram', True)
            },
            'system_error': {
                'enabled': self.config.get('notifications.system_error.enabled', True),
                'priority': 'critical',
                'telegram': self.config.get('notifications.system_error.telegram', True)
            },
            'backend_down': {
                'enabled': self.config.get('notifications.backend_down.enabled', True),
                'priority': 'high',
                'telegram': self.config.get('notifications.backend_down.telegram', True)
            },
            'high_error_rate': {
                'enabled': self.config.get('notifications.high_error_rate.enabled', True),
                'priority': 'high',
                'telegram': self.config.get('notifications.high_error_rate.telegram', True)
            }
        }

    def send_notification(self, notification: Notification) -> bool:
        """Send notification through configured channels"""
        try:
            # Check if this notification type is enabled
            type_key = notification.notification_type.value
            rule = self.notification_rules.get(type_key, {})

            if not rule.get('enabled', True):
                logger.debug(f"Notification type {type_key} disabled, skipping")
                return False

            # Send via Telegram if enabled
            telegram_success = True
            if rule.get('telegram', True) and self.telegram.is_configured():
                telegram_success = self.telegram.send_notification(notification)

            # Store notification in database
            self._store_notification(notification, telegram_success)

            return telegram_success

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    def _store_notification(self, notification: Notification, telegram_sent: bool):
        """Store notification in database"""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO notifications (
                        type, title, message, priority, timestamp,
                        job_id, user_id, context, telegram_sent
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    notification.notification_type.value,
                    notification.title,
                    notification.message,
                    notification.priority.value,
                    notification.timestamp,
                    notification.job_id,
                    notification.user_id,
                    json.dumps(notification.context),
                    telegram_sent
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to store notification: {e}")

    # Convenience methods for common notifications
    def notify_job_completed(self, job_id: int, result: Dict[str, Any], execution_time: float):
        """Send job completion notification"""
        notification = Notification(
            notification_type=NotificationType.JOB_COMPLETED,
            title="Job Completed Successfully",
            message=f"Job completed in {execution_time:.1f}s",
            priority=NotificationPriority.MEDIUM,
            timestamp=datetime.now(),
            context={
                'execution_time': execution_time,
                'backend': result.get('backend_used', 'unknown'),
                'model': result.get('model_used', 'unknown')
            },
            job_id=job_id
        )
        return self.send_notification(notification)

    def notify_job_failed(self, job_id: int, error_message: str, context: Dict[str, Any] = None):
        """Send job failure notification"""
        notification = Notification(
            notification_type=NotificationType.JOB_FAILED,
            title="Job Failed",
            message=f"Job failed: {error_message[:200]}...",
            priority=NotificationPriority.HIGH,
            timestamp=datetime.now(),
            context=context or {},
            job_id=job_id
        )
        return self.send_notification(notification)

    def notify_system_error(self, error_message: str, context: Dict[str, Any] = None):
        """Send system error notification"""
        notification = Notification(
            notification_type=NotificationType.SYSTEM_ERROR,
            title="System Error",
            message=error_message,
            priority=NotificationPriority.CRITICAL,
            timestamp=datetime.now(),
            context=context or {}
        )
        return self.send_notification(notification)

    def notify_backend_down(self, backend_name: str, error: str):
        """Send backend down notification"""
        notification = Notification(
            notification_type=NotificationType.BACKEND_DOWN,
            title=f"Backend Down: {backend_name}",
            message=f"Backend {backend_name} is unavailable: {error}",
            priority=NotificationPriority.HIGH,
            timestamp=datetime.now(),
            context={'backend_name': backend_name, 'error': error}
        )
        return self.send_notification(notification)

    def notify_backend_recovered(self, backend_name: str):
        """Send backend recovered notification"""
        notification = Notification(
            notification_type=NotificationType.BACKEND_RECOVERED,
            title=f"Backend Recovered: {backend_name}",
            message=f"Backend {backend_name} is now available",
            priority=NotificationPriority.MEDIUM,
            timestamp=datetime.now(),
            context={'backend_name': backend_name}
        )
        return self.send_notification(notification)

    def notify_high_error_rate(self, error_rate: float, recent_errors: List[str]):
        """Send high error rate notification"""
        notification = Notification(
            notification_type=NotificationType.HIGH_ERROR_RATE,
            title="High Error Rate Detected",
            message=f"Error rate is {error_rate:.1%} in the last hour",
            priority=NotificationPriority.HIGH,
            timestamp=datetime.now(),
            context={
                'error_rate': error_rate,
                'recent_errors': recent_errors[:5]  # Limit to 5 most recent
            }
        )
        return self.send_notification(notification)

    def get_notification_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent notification history"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM notifications
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get notification history: {e}")
            return []

    def get_notification_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get notification statistics"""
        try:
            with self.db.get_connection() as conn:
                cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)

                cursor = conn.execute("""
                    SELECT type, priority, COUNT(*) as count
                    FROM notifications
                    WHERE timestamp > ?
                    GROUP BY type, priority
                    ORDER BY count DESC
                """, (cutoff_date,))

                stats = {
                    'total_notifications': 0,
                    'by_type': {},
                    'by_priority': {},
                    'telegram_success_rate': 0
                }

                total_sent = 0
                total_telegram = 0

                for row in cursor.fetchall():
                    type_name = row['type']
                    priority = row['priority']
                    count = row['count']

                    stats['total_notifications'] += count

                    if type_name not in stats['by_type']:
                        stats['by_type'][type_name] = 0
                    stats['by_type'][type_name] += count

                    if priority not in stats['by_priority']:
                        stats['by_priority'][priority] = 0
                    stats['by_priority'][priority] += count

                # Get Telegram success rate
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN telegram_sent = 1 THEN 1 ELSE 0 END) as telegram_success
                    FROM notifications
                    WHERE timestamp > ?
                """, (cutoff_date,))

                row = cursor.fetchone()
                if row and row['total'] > 0:
                    stats['telegram_success_rate'] = row['telegram_success'] / row['total']

                return stats

        except Exception as e:
            logger.error(f"Failed to get notification stats: {e}")
            return {}

# Global notification manager
_notification_manager = None

def get_notification_manager(config: Optional[Config] = None) -> NotificationManager:
    """Get global notification manager instance"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager(config)
    return _notification_manager