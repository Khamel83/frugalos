"""
Advanced Threat Detection System
Real-time threat detection and prevention with machine learning
"""

import logging
import time
import hashlib
import ipaddress
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('security.threat_detector')

class ThreatType(Enum):
    """Types of security threats"""
    BRUTE_FORCE = "brute_force"
    RATE_LIMITING = "rate_limiting"
    SUSPICIOUS_REQUEST = "suspicious_request"
    ABNORMAL_BEHAVIOR = "abnormal_behavior"
    DATA_EXFILTRATION = "data_exfiltration"
    INJECTION_ATTACK = "injection_attack"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    UNAUTHORIZED_ACCESS = "unauthorized_access"

class ThreatLevel(Enum):
    """Threat severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ThreatEvent:
    """Security threat event"""
    event_id: str
    threat_type: ThreatType
    threat_level: ThreatLevel
    source_ip: str
    user_id: Optional[str]
    timestamp: datetime
    description: str
    evidence: Dict[str, Any]
    blocked: bool
    mitigated: bool
    confidence: float

class ThreatDetector:
    """Advanced threat detection system"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = get_logger('threat_detector')

        # Configuration
        self.enabled = self.config.get('security.threat_detection.enabled', True)
        self.learning_enabled = self.config.get('security.threat_detection.ml_enabled', True)
        self.block_threshold = self.config.get('security.threat_detection.block_threshold', 0.8)

        # Threat tracking
        self._threat_events = deque(maxlen=10000)
        self._blocked_ips = defaultdict(lambda: datetime.min)
        self._suspicious_users = defaultdict(lambda: datetime.min)
        self._rate_limits = defaultdict(list)  # IP -> [timestamp1, timestamp2, ...]

        # Pattern learning
        self._baseline_patterns = {}
        self._anomaly_threshold = self.config.get('security.threat_detection.anomaly_threshold', 2.0)

        # Threat rules
        self._threat_rules = self._initialize_threat_rules()

    def _initialize_threat_rules(self) -> Dict[ThreatType, List[Dict[str, Any]]]:
        """Initialize threat detection rules"""
        return {
            ThreatType.BRUTE_FORCE: [
                {
                    'condition': 'failed_login_attempts',
                    'threshold': 5,
                    'time_window_minutes': 5,
                    'severity': ThreatLevel.HIGH
                },
                {
                    'condition': 'failed_login_attempts',
                    'threshold': 10,
                    'time_window_minutes': 15,
                    'severity': ThreatLevel.CRITICAL
                }
            ],
            ThreatType.RATE_LIMITING: [
                {
                    'condition': 'requests_per_minute',
                    'threshold': 100,
                    'severity': ThreatLevel.MEDIUM
                },
                {
                    'condition': 'requests_per_minute',
                    'threshold': 500,
                    'severity': ThreatLevel.HIGH
                }
            ],
            ThreatType.SUSPICIOUS_REQUEST: [
                {
                    'condition': 'abnormal_payload_size',
                    'threshold': 10485760,  # 10MB
                    'severity': ThreatLevel.MEDIUM
                },
                {
                    'condition': 'abnormal_headers',
                    'pattern': r'(?i)(union|select|insert|update|delete|drop)',
                    'severity': ThreatLevel.HIGH
                }
            ],
            ThreatType.DATA_EXFILTRATION: [
                {
                    'condition': 'large_data_transfer',
                    'threshold': 104857600,  # 100MB
                    'time_window_minutes': 10,
                    'severity': ThreatLevel.HIGH
                }
            ],
            ThreatType.INJECTION_ATTACK: [
                {
                    'condition': 'sql_injection_pattern',
                    'patterns': [
                        r'(?i)(union\s+select|or\s+1\s*=\s*1|drop\s+table|exec\s*\()',
                        r'(?i)(<script|javascript:|onload\s*=)',
                        r'(?i)(cat\s+/etc/passwd|\.\./\.\./)'
                    ],
                    'severity': ThreatLevel.CRITICAL
                }
            ]
        }

    def analyze_request(
        self,
        source_ip: str,
        user_id: Optional[str],
        endpoint: str,
        method: str,
        headers: Dict[str, str],
        payload: Any,
        response_status: int
    ) -> List[ThreatEvent]:
        """
        Analyze a request for security threats

        Args:
            source_ip: Client IP address
            user_id: User ID if authenticated
            endpoint: API endpoint
            method: HTTP method
            headers: Request headers
            payload: Request payload
            response_status: HTTP response status

        Returns:
            List of detected threats
        """
        if not self.enabled:
            return []

        threats = []

        # Track rate limiting
        self._track_rate_limiting(source_ip)

        # Check each threat type
        threats.extend(self._check_brute_force(source_ip, user_id, response_status))
        threats.extend(self._check_rate_limiting(source_ip))
        threats.extend(self._check_suspicious_request(headers, payload))
        threats.extend(self._check_injection_attack(headers, payload))
        threats.extend(self._check_abnormal_behavior(source_ip, user_id, endpoint, method))

        # Process detected threats
        for threat in threats:
            self._process_threat(threat)

        return threats

    def _track_rate_limiting(self, source_ip: str):
        """Track request rate for IP"""
        now = datetime.now()
        rate_list = self._rate_limits[source_ip]

        # Add current request
        rate_list.append(now)

        # Clean old requests (older than 1 hour)
        cutoff = now - timedelta(hours=1)
        self._rate_limits[source_ip] = [
            timestamp for timestamp in rate_list
            if timestamp > cutoff
        ]

    def _check_brute_force(self, source_ip: str, user_id: Optional[str], response_status: int) -> List[ThreatEvent]:
        """Check for brute force attacks"""
        threats = []

        if response_status == 401:  # Unauthorized
            # Count recent failed attempts
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM security_events
                    WHERE source_ip = ? AND response_status = 401
                    AND created_at >= datetime('now', '-15 minutes')
                """, (source_ip,))
                row = cursor.fetchone()
                failed_attempts = row['count'] if row else 0

            # Check against rules
            for rule in self._threat_rules[ThreatType.BRUTE_FORCE]:
                if failed_attempts >= rule['threshold']:
                    threat = ThreatEvent(
                        event_id=self._generate_event_id(),
                        threat_type=ThreatType.BRUTE_FORCE,
                        threat_level=rule['severity'],
                        source_ip=source_ip,
                        user_id=user_id,
                        timestamp=datetime.now(),
                        description=f"Brute force attack detected: {failed_attempts} failed attempts",
                        evidence={
                            'failed_attempts': failed_attempts,
                            'rule_threshold': rule['threshold'],
                            'time_window_minutes': rule['time_window_minutes']
                        },
                        blocked=False,
                        mitigated=False,
                        confidence=0.9
                    )
                    threats.append(threat)

        return threats

    def _check_rate_limiting(self, source_ip: str) -> List[ThreatEvent]:
        """Check for rate limiting violations"""
        threats = []

        # Count requests in last minute
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)

        recent_requests = [
            timestamp for timestamp in self._rate_limits[source_ip]
            if timestamp > minute_ago
        ]

        # Check against rules
        for rule in self._threat_rules[ThreatType.RATE_LIMITING]:
            if len(recent_requests) >= rule['threshold']:
                threat = ThreatEvent(
                    event_id=self._generate_event_id(),
                    threat_type=ThreatType.RATE_LIMITING,
                    threat_level=rule['severity'],
                    source_ip=source_ip,
                    user_id=None,
                    timestamp=now,
                    description=f"Rate limit exceeded: {len(recent_requests)} requests in 1 minute",
                    evidence={
                        'requests_per_minute': len(recent_requests),
                        'rule_threshold': rule['threshold']
                    },
                    blocked=False,
                    mitigated=False,
                    confidence=0.8
                )
                threats.append(threat)

        return threats

    def _check_suspicious_request(self, headers: Dict[str, str], payload: Any) -> List[ThreatEvent]:
        """Check for suspicious request patterns"""
        threats = []

        # Check payload size
        payload_size = len(str(payload)) if payload else 0

        for rule in self._threat_rules[ThreatType.SUSPICIOUS_REQUEST]:
            if rule['condition'] == 'abnormal_payload_size':
                if payload_size > rule['threshold']:
                    threat = ThreatEvent(
                        event_id=self._generate_event_id(),
                        threat_type=ThreatType.SUSPICIOUS_REQUEST,
                        threat_level=rule['severity'],
                        source_ip=headers.get('X-Forwarded-For', 'unknown'),
                        user_id=None,
                        timestamp=datetime.now(),
                        description=f"Abnormally large payload: {payload_size} bytes",
                        evidence={
                            'payload_size': payload_size,
                            'threshold': rule['threshold']
                        },
                        blocked=False,
                        mitigated=False,
                        confidence=0.7
                    )
                    threats.append(threat)

            elif rule['condition'] == 'abnormal_headers':
                headers_text = ' '.join(f"{k}: {v}" for k, v in headers.items())
                import re
                if re.search(rule['pattern'], headers_text):
                    threat = ThreatEvent(
                        event_id=self._generate_event_id(),
                        threat_type=ThreatType.SUSPICIOUS_REQUEST,
                        threat_level=rule['severity'],
                        source_ip=headers.get('X-Forwarded-For', 'unknown'),
                        user_id=None,
                        timestamp=datetime.now(),
                        description=f"Suspicious headers detected",
                        evidence={
                            'matched_pattern': rule['pattern'],
                            'headers_sample': str(headers)[:200]
                        },
                        blocked=False,
                        mitigated=False,
                        confidence=0.8
                    )
                    threats.append(threat)

        return threats

    def _check_injection_attack(self, headers: Dict[str, str], payload: Any) -> List[ThreatEvent]:
        """Check for injection attacks"""
        threats = []

        for rule in self._threat_rules[ThreatType.INJECTION_ATTACK]:
            if rule['condition'] == 'sql_injection_pattern':
                # Combine headers and payload for analysis
                content = ' '.join(headers.values())
                if payload:
                    content += ' ' + str(payload)

                import re
                for pattern in rule['patterns']:
                    if re.search(pattern, content):
                        threat = ThreatEvent(
                            event_id=self._generate_event_id(),
                            threat_type=ThreatType.INJECTION_ATTACK,
                            threat_level=rule['severity'],
                            source_ip=headers.get('X-Forwarded-For', 'unknown'),
                            user_id=None,
                            timestamp=datetime.now(),
                            description=f"Injection attack pattern detected: {pattern}",
                            evidence={
                                'matched_pattern': pattern,
                                'content_sample': content[:200]
                            },
                            blocked=True,
                            mitigated=False,
                            confidence=0.95
                        )
                        threats.append(threat)

        return threats

    def _check_abnormal_behavior(
        self,
        source_ip: str,
        user_id: Optional[str],
        endpoint: str,
        method: str
    ) -> List[ThreatEvent]:
        """Check for abnormal behavioral patterns"""
        threats = []

        if not self.learning_enabled:
            return threats

        # Analyze user behavior patterns
        if user_id:
            normal_patterns = self._baseline_patterns.get(user_id, {})
            current_pattern = self._analyze_user_pattern(user_id, source_ip, endpoint, method)

            if normal_patterns:
                # Check for anomalies
                if self._is_pattern_anomalous(normal_patterns, current_pattern):
                    threat = ThreatEvent(
                        event_id=self._generate_event_id(),
                        threat_type=ThreatType.ABNORMAL_BEHAVIOR,
                        threat_level=ThreatLevel.MEDIUM,
                        source_ip=source_ip,
                        user_id=user_id,
                        timestamp=datetime.now(),
                        description="Abnormal user behavior detected",
                        evidence={
                            'normal_pattern': normal_patterns,
                            'current_pattern': current_pattern
                        },
                        blocked=False,
                        mitigated=False,
                        confidence=0.6
                    )
                    threats.append(threat)

            # Update baseline
            self._update_baseline_pattern(user_id, current_pattern)

        return threats

    def _analyze_user_pattern(
        self,
        user_id: str,
        source_ip: str,
        endpoint: str,
        method: str
    ) -> Dict[str, Any]:
        """Analyze current user behavior pattern"""
        with self.db.get_connection() as conn:
            # Get recent user activity
            cursor = conn.execute("""
                SELECT endpoint, method, source_ip, COUNT(*) as count
                FROM security_events
                WHERE user_id = ? AND created_at >= datetime('now', '-1 hour')
                GROUP BY endpoint, method, source_ip
            """, (user_id,))

            pattern = {
                'unique_ips': set(),
                'unique_endpoints': set(),
                'request_frequency': 0,
                'time_distribution': defaultdict(int)
            }

            total_requests = 0
            for row in cursor.fetchall():
                pattern['unique_ips'].add(row['source_ip'])
                pattern['unique_endpoints'].add(row['endpoint'])
                total_requests += row['count']

            pattern['unique_ips'] = len(pattern['unique_ips'])
            pattern['unique_endpoints'] = len(pattern['unique_endpoints'])
            pattern['request_frequency'] = total_requests

            return pattern

    def _is_pattern_anomalous(self, normal: Dict[str, Any], current: Dict[str, Any]) -> bool:
        """Check if current pattern is anomalous compared to baseline"""
        # Simple anomaly detection based on statistical deviations
        checks = [
            ('unique_ips', 2.0),
            ('unique_endpoints', 3.0),
            ('request_frequency', 2.0)
        ]

        for metric, threshold in checks:
            normal_value = normal.get(metric, 0)
            current_value = current.get(metric, 0)

            if normal_value > 0:
                deviation = abs(current_value - normal_value) / normal_value
                if deviation > threshold:
                    return True

        return False

    def _update_baseline_pattern(self, user_id: str, pattern: Dict[str, Any]):
        """Update baseline pattern for user"""
        if user_id not in self._baseline_patterns:
            self._baseline_patterns[user_id] = pattern
        else:
            # Exponential moving average update
            alpha = 0.1
            baseline = self._baseline_patterns[user_id]

            for key in ['unique_ips', 'unique_endpoints', 'request_frequency']:
                if key in pattern and key in baseline:
                    baseline[key] = (
                        (1 - alpha) * baseline[key] +
                        alpha * pattern[key]
                    )

    def _process_threat(self, threat: ThreatEvent):
        """Process detected threat"""
        # Add to threat events
        self._threat_events.append(threat)

        # Log threat
        log_level = {
            ThreatLevel.LOW: 'warning',
            ThreatLevel.MEDIUM: 'warning',
            ThreatLevel.HIGH: 'error',
            ThreatLevel.CRITICAL: 'critical'
        }.get(threat.threat_level, 'warning')

        self.logger.log(
            getattr(logging, log_level),
            f"Security threat detected: {threat.description} "
            f"[{threat.threat_type.value}] {threat.threat_level.value} "
            f"from {threat.source_ip}"
        )

        # Apply mitigation based on threat level
        if threat.confidence >= self.block_threshold:
            self._apply_mitigation(threat)

        # Store in database
        self._store_threat_event(threat)

    def _apply_mitigation(self, threat: ThreatEvent):
        """Apply threat mitigation"""
        if threat.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            # Block IP temporarily
            block_duration = {
                ThreatLevel.HIGH: timedelta(hours=1),
                ThreatLevel.CRITICAL: timedelta(hours=24)
            }.get(threat.threat_level, timedelta(hours=1))

            self._blocked_ips[threat.source_ip] = datetime.now() + block_duration
            threat.blocked = True

        # Mark as mitigated
        threat.mitigated = True

        self.logger.warning(
            f"Threat mitigation applied: {threat.source_ip} blocked "
            f"due to {threat.threat_type.value}"
        )

    def _store_threat_event(self, threat: ThreatEvent):
        """Store threat event in database"""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO security_events (
                        event_id, threat_type, threat_level, source_ip, user_id,
                        created_at, description, evidence, blocked, mitigated, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    threat.event_id,
                    threat.threat_type.value,
                    threat.threat_level.value,
                    threat.source_ip,
                    threat.user_id,
                    threat.timestamp.isoformat(),
                    threat.description,
                    str(threat.evidence),
                    int(threat.blocked),
                    int(threat.mitigated),
                    threat.confidence
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Error storing threat event: {e}")

    def is_ip_blocked(self, source_ip: str) -> bool:
        """Check if IP is currently blocked"""
        block_time = self._blocked_ips.get(source_ip, datetime.min)
        return block_time > datetime.now()

    def is_user_suspicious(self, user_id: str) -> bool:
        """Check if user has suspicious activity"""
        suspicious_time = self._suspicious_users.get(user_id, datetime.min)
        return suspicious_time > datetime.now()

    def get_threat_summary(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get threat summary for time window"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        recent_threats = [
            threat for threat in self._threat_events
            if threat.timestamp >= cutoff_time
        ]

        # Count by type and level
        threats_by_type = defaultdict(int)
        threats_by_level = defaultdict(int)

        for threat in recent_threats:
            threats_by_type[threat.threat_type.value] += 1
            threats_by_level[threat.threat_level.value] += 1

        return {
            'total_threats': len(recent_threats),
            'threats_by_type': dict(threats_by_type),
            'threats_by_level': dict(threats_by_level),
            'blocked_ips': len(self._blocked_ips),
            'suspicious_users': len(self._suspicious_users),
            'top_source_ips': self._get_top_threat_sources(recent_threats)
        }

    def _get_top_threat_sources(self, threats: List[ThreatEvent]) -> List[Dict[str, Any]]:
        """Get top threat source IPs"""
        ip_counts = defaultdict(int)
        ip_levels = defaultdict(list)

        for threat in threats:
            ip_counts[threat.source_ip] += 1
            ip_levels[threat.source_ip].append(threat.threat_level.value)

        # Sort by threat count
        top_ips = sorted(
            ip_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return [
            {
                'ip': ip,
                'threat_count': count,
                'max_level': max(ip_levels[ip]) if ip_levels[ip] else 'low'
            }
            for ip, count in top_ips
        ]

    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        return f"threat_{int(time.time() * 1000)}_{hash(threading.get_ident()) % 10000}"