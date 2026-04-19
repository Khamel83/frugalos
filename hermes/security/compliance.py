"""
Compliance and Audit Framework for Hermes AI Assistant

This module provides comprehensive compliance capabilities including:
- GDPR compliance
- SOC 2 Type II compliance
- HIPAA compliance
- PCI DSS compliance
- Audit logging and reporting
- Data retention policies
- Privacy controls
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
import hashlib
import ipaddress
from pathlib import Path

logger = logging.getLogger(__name__)


class ComplianceFramework(Enum):
    """Compliance frameworks"""
    GDPR = "gdpr"
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    ISO_27001 = "iso_27001"
    CCPA = "ccpa"


class AuditEventType(Enum):
    """Audit event types"""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTRATION = "user_registration"
    PASSWORD_CHANGE = "password_change"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    DATA_EXPORT = "data_export"
    PERMISSION_CHANGE = "permission_change"
    ROLE_CHANGE = "role_change"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_EVENT = "security_event"
    SYSTEM_ERROR = "system_error"
    BACKUP_OPERATION = "backup_operation"
    RESTORE_OPERATION = "restore_operation"
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class DataClassification(Enum):
    """Data classification levels"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class RetentionPeriod(Enum):
    """Data retention periods"""
    DAYS_30 = timedelta(days=30)
    DAYS_90 = timedelta(days=90)
    DAYS_180 = timedelta(days=180)
    DAYS_365 = timedelta(days=365)
    YEARS_2 = timedelta(days=730)
    YEARS_5 = timedelta(days=1825)
    YEARS_7 = timedelta(days=2555)
    PERMANENT = None


@dataclass
class AuditEvent:
    """Audit event record"""
    event_id: str
    event_type: AuditEventType
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    compliance_frameworks: List[ComplianceFramework] = field(default_factory=list)
    data_classification: DataClassification = DataClassification.INTERNAL
    risk_score: int = 0  # 0-100


@dataclass
class ComplianceRule:
    """Compliance rule definition"""
    rule_id: str
    framework: ComplianceFramework
    name: str
    description: str
    enabled: bool = True
    data_types: List[str] = field(default_factory=list)
    retention_period: Optional[RetentionPeriod] = None
    encryption_required: bool = False
    audit_required: bool = True
    geo_restrictions: List[str] = field(default_factory=list)
    user_consent_required: bool = False
    anonymization_required: bool = False


@dataclass
class DataSubjectRequest:
    """Data subject request (GDPR/CCPA)"""
    request_id: str
    subject_id: str
    request_type: str  # access, deletion, correction, portability
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    processed_by: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class ComplianceManager:
    """
    Comprehensive compliance management system
    """

    def __init__(self, storage_path: str = "/var/log/hermes/compliance"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.audit_events: List[AuditEvent] = []
        self.compliance_rules: Dict[str, ComplianceRule] = {}
        self.data_subject_requests: Dict[str, DataSubjectRequest] = {}

        # Initialize compliance rules
        self._initialize_compliance_rules()

    def _initialize_compliance_rules(self):
        """Initialize default compliance rules"""
        rules = [
            # GDPR Rules
            ComplianceRule(
                rule_id="gdpr_data_minimization",
                framework=ComplianceFramework.GDPR,
                name="Data Minimization",
                description="Collect only necessary data",
                retention_period=RetentionPeriod.DAYS_365,
                anonymization_required=True
            ),
            ComplianceRule(
                rule_id="gdpr_consent",
                framework=ComplianceFramework.GDPR,
                name="Explicit Consent",
                description="Require explicit consent for data processing",
                user_consent_required=True
            ),
            ComplianceRule(
                rule_id="gdpr_retention",
                framework=ComplianceFramework.GDPR,
                name="Data Retention",
                description="Limited data retention period",
                retention_period=RetentionPeriod.DAYS_365
            ),

            # HIPAA Rules
            ComplianceRule(
                rule_id="hipaa_encryption",
                framework=ComplianceFramework.HIPAA,
                name="Data Encryption",
                description="Encrypt all PHI data",
                data_types=["phi", "medical_record"],
                encryption_required=True
            ),
            ComplianceRule(
                rule_id="hipaa_audit",
                framework=ComplianceFramework.HIPAA,
                name="Audit Trail",
                description="Comprehensive audit logging",
                audit_required=True
            ),

            # PCI DSS Rules
            ComplianceRule(
                rule_id="pci_encryption",
                framework=ComplianceFramework.PCI_DSS,
                name="Card Data Encryption",
                description="Encrypt cardholder data",
                data_types=["credit_card", "payment_info"],
                encryption_required=True
            ),
            ComplianceRule(
                rule_id="pci_retention",
                framework=ComplianceFramework.PCI_DSS,
                name="Card Data Retention",
                description="Limited retention of card data",
                retention_period=RetentionPeriod.DAYS_90
            ),

            # SOC 2 Rules
            ComplianceRule(
                rule_id="soc2_access_control",
                framework=ComplianceFramework.SOC2,
                name="Access Control",
                description="Proper access controls",
                audit_required=True
            ),
            ComplianceRule(
                rule_id="soc2_availability",
                framework=ComplianceFramework.SOC2,
                name="Service Availability",
                description="Monitor service availability",
                audit_required=True
            )
        ]

        for rule in rules:
            self.compliance_rules[rule.rule_id] = rule

    async def log_audit_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        result: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        compliance_frameworks: Optional[List[ComplianceFramework]] = None,
        data_classification: DataClassification = DataClassification.INTERNAL
    ) -> AuditEvent:
        """Log an audit event"""
        event_id = hashlib.sha256(
            f"{event_type.value}{datetime.now().isoformat()}{user_id or ''}".encode()
        ).hexdigest()[:16]

        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_id=resource_id,
            resource_type=resource_type,
            action=action,
            result=result,
            details=details or {},
            compliance_frameworks=compliance_frameworks or [],
            data_classification=data_classification,
            risk_score=self._calculate_risk_score(event_type, data_classification, details or {})
        )

        self.audit_events.append(event)
        await self._store_audit_event(event)

        # Check for compliance violations
        await self._check_compliance_violations(event)

        logger.info(f"Logged audit event: {event_type.value} for user {user_id}")
        return event

    def _calculate_risk_score(
        self,
        event_type: AuditEventType,
        data_classification: DataClassification,
        details: Dict[str, Any]
    ) -> int:
        """Calculate risk score for audit event"""
        base_score = 0

        # Base scores by event type
        event_scores = {
            AuditEventType.SECURITY_EVENT: 80,
            AuditEventType.DATA_DELETION: 70,
            AuditEventType.DATA_EXPORT: 60,
            AuditEventType.PERMISSION_CHANGE: 50,
            AuditEventType.ROLE_CHANGE: 50,
            AuditEventType.PASSWORD_CHANGE: 30,
            AuditEventType.MFA_DISABLED: 40,
            AuditEventType.API_KEY_CREATED: 20,
            AuditEventType.API_KEY_REVOKED: 20,
        }
        base_score = event_scores.get(event_type, 10)

        # Adjust based on data classification
        classification_multipliers = {
            DataClassification.PUBLIC: 0.5,
            DataClassification.INTERNAL: 1.0,
            DataClassification.CONFIDENTIAL: 1.5,
            DataClassification.RESTRICTED: 2.0,
        }
        multiplier = classification_multipliers.get(data_classification, 1.0)

        # Adjust based on failure/error
        if details.get("success") is False:
            base_score += 20

        if details.get("error"):
            base_score += 15

        # Calculate final score
        final_score = int(base_score * multiplier)
        return min(100, final_score)

    async def _store_audit_event(self, event: AuditEvent):
        """Store audit event to file"""
        event_file = self.storage_path / "audit" / f"{event.timestamp.strftime('%Y%m')}.jsonl"
        event_file.parent.mkdir(exist_ok=True)

        event_data = asdict(event)
        event_data["timestamp"] = event.timestamp.isoformat()
        event_data["compliance_frameworks"] = [f.value for f in event.compliance_frameworks]
        event_data["event_type"] = event.event_type.value
        event_data["data_classification"] = event.data_classification.value

        with open(event_file, "a") as f:
            f.write(json.dumps(event_data) + "\n")

    async def _check_compliance_violations(self, event: AuditEvent):
        """Check for compliance violations"""
        for rule in self.compliance_rules.values():
            if not rule.enabled:
                continue

            violation = await self._check_rule_violation(rule, event)
            if violation:
                await self._handle_compliance_violation(rule, event, violation)

    async def _check_rule_violation(
        self,
        rule: ComplianceRule,
        event: AuditEvent
    ) -> Optional[Dict[str, Any]]:
        """Check if event violates a specific compliance rule"""
        violation = None

        # Check if rule applies to this event
        if rule.framework not in event.compliance_frameworks:
            return None

        # Check various violation conditions
        if rule.encryption_required and not event.details.get("encrypted"):
            violation = {"type": "encryption_required", "description": "Data should be encrypted"}

        if rule.audit_required and not event.details.get("audited"):
            violation = {"type": "audit_required", "description": "Operation should be audited"}

        if rule.user_consent_required and not event.details.get("consent_obtained"):
            violation = {"type": "consent_required", "description": "User consent required"}

        if rule.geo_restrictions and event.ip_address:
            ip = ipaddress.ip_address(event.ip_address)
            for restriction in rule.geo_restrictions:
                if not self._is_ip_allowed(ip, restriction):
                    violation = {"type": "geo_restriction", "description": f"Access from {restriction} not allowed"}
                    break

        return violation

    def _is_ip_allowed(self, ip: ipaddress.IPv4Address, restriction: str) -> bool:
        """Check if IP is allowed based on geo restriction"""
        # This is a simplified implementation
        # In production, use a proper IP geolocation service
        allowed_regions = {
            "US": ["192.168.0.0/16", "10.0.0.0/8"],  # Example private networks
            "EU": ["172.16.0.0/12"],
        }

        if restriction in allowed_regions:
            for network in allowed_regions[restriction]:
                if ip in ipaddress.ip_network(network):
                    return True

        return False

    async def _handle_compliance_violation(
        self,
        rule: ComplianceRule,
        event: AuditEvent,
        violation: Dict[str, Any]
    ):
        """Handle compliance violation"""
        violation_event = AuditEvent(
            event_id=hashlib.sha256(
                f"violation_{rule.rule_id}_{event.event_id}".encode()
            ).hexdigest()[:16],
            event_type=AuditEventType.SECURITY_EVENT,
            user_id=event.user_id,
            ip_address=event.ip_address,
            details={
                "violation_type": violation["type"],
                "violation_description": violation["description"],
                "rule_id": rule.rule_id,
                "framework": rule.framework.value,
                "original_event_id": event.event_id,
                "original_event_type": event.event_type.value
            },
            compliance_frameworks=[rule.framework],
            risk_score=90
        )

        self.audit_events.append(violation_event)
        await self._store_audit_event(violation_event)

        logger.warning(
            f"Compliance violation detected: {rule.framework.value} - {violation['description']}"
        )

    async def create_data_subject_request(
        self,
        subject_id: str,
        request_type: str,
        details: Optional[Dict[str, Any]] = None
    ) -> DataSubjectRequest:
        """Create a data subject request (GDPR/CCPA)"""
        request_id = hashlib.sha256(
            f"{subject_id}{request_type}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        request = DataSubjectRequest(
            request_id=request_id,
            subject_id=subject_id,
            request_type=request_type,
            details=details or {}
        )

        self.data_subject_requests[request_id] = request
        await self._store_data_subject_request(request)

        logger.info(f"Created data subject request {request_id} for subject {subject_id}")
        return request

    async def process_data_subject_request(
        self,
        request_id: str,
        processed_by: str,
        result: Dict[str, Any]
    ) -> bool:
        """Process a data subject request"""
        request = self.data_subject_requests.get(request_id)
        if not request:
            return False

        request.status = "completed"
        request.completed_at = datetime.now()
        request.processed_by = processed_by
        request.details.update(result)

        await self._store_data_subject_request(request)

        # Log the processing
        await self.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS if request.request_type == "access" else AuditEventType.DATA_DELETION,
            user_id=processed_by,
            resource_id=request.subject_id,
            resource_type="data_subject_request",
            action=f"process_{request.request_type}_request",
            result="success",
            details={
                "request_id": request_id,
                "request_type": request.request_type,
                "subject_id": request.subject_id
            },
            compliance_frameworks=[ComplianceFramework.GDPR, ComplianceFramework.CCPA]
        )

        logger.info(f"Processed data subject request {request_id}")
        return True

    async def _store_data_subject_request(self, request: DataSubjectRequest):
        """Store data subject request to file"""
        request_file = self.storage_path / "data_subject_requests.json"

        # Load existing requests
        requests = []
        if request_file.exists():
            with open(request_file, "r") as f:
                requests = json.load(f)

        # Update or add request
        request_data = asdict(request)
        request_data["created_at"] = request.created_at.isoformat()
        if request.completed_at:
            request_data["completed_at"] = request.completed_at.isoformat()

        # Find and update existing request or add new one
        for i, req in enumerate(requests):
            if req["request_id"] == request.request_id:
                requests[i] = request_data
                break
        else:
            requests.append(request_data)

        # Save back to file
        with open(request_file, "w") as f:
            json.dump(requests, f, indent=2)

    async def generate_compliance_report(
        self,
        framework: ComplianceFramework,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate compliance report for a framework"""
        start_date = start_date or datetime.now() - timedelta(days=30)
        end_date = end_date or datetime.now()

        # Filter events by framework and date range
        relevant_events = [
            event for event in self.audit_events
            if framework in event.compliance_frameworks
            and start_date <= event.timestamp <= end_date
        ]

        # Generate report
        report = {
            "framework": framework.value,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_events": len(relevant_events),
                "high_risk_events": len([e for e in relevant_events if e.risk_score >= 70]),
                "unique_users": len(set(e.user_id for e in relevant_events if e.user_id)),
                "unique_ips": len(set(e.ip_address for e in relevant_events if e.ip_address))
            },
            "event_types": {},
            "risk_distribution": {
                "low": 0,    # 0-30
                "medium": 0, # 31-70
                "high": 0,   # 71-90
                "critical": 0 # 91-100
            },
            "violations": [],
            "recommendations": []
        }

        # Categorize events
        for event in relevant_events:
            event_type = event.event_type.value
            report["event_types"][event_type] = report["event_types"].get(event_type, 0) + 1

            # Risk distribution
            if event.risk_score <= 30:
                report["risk_distribution"]["low"] += 1
            elif event.risk_score <= 70:
                report["risk_distribution"]["medium"] += 1
            elif event.risk_score <= 90:
                report["risk_distribution"]["high"] += 1
            else:
                report["risk_distribution"]["critical"] += 1

        # Find violations
        for event in relevant_events:
            if event.event_type == AuditEventType.SECURITY_EVENT:
                if "violation_type" in event.details:
                    report["violations"].append({
                        "timestamp": event.timestamp.isoformat(),
                        "type": event.details.get("violation_type"),
                        "description": event.details.get("violation_description"),
                        "rule_id": event.details.get("rule_id"),
                        "user_id": event.user_id,
                        "risk_score": event.risk_score
                    })

        # Generate recommendations
        report["recommendations"] = self._generate_recommendations(framework, report)

        return report

    def _generate_recommendations(
        self,
        framework: ComplianceFramework,
        report: Dict[str, Any]
    ) -> List[str]:
        """Generate compliance recommendations"""
        recommendations = []

        # General recommendations based on risk distribution
        high_risk_percentage = (
            report["risk_distribution"]["high"] + report["risk_distribution"]["critical"]
        ) / report["summary"]["total_events"] * 100

        if high_risk_percentage > 20:
            recommendations.append(
                "High percentage of high-risk events detected. Review security controls."
            )

        if report["risk_distribution"]["critical"] > 0:
            recommendations.append(
                "Critical risk events detected. Immediate investigation required."
            )

        # Framework-specific recommendations
        if framework == ComplianceFramework.GDPR:
            if any("consent" in v.get("type", "") for v in report["violations"]):
                recommendations.append(
                    "Consent-related violations detected. Review consent management process."
                )
        elif framework == ComplianceFramework.HIPAA:
            if any("encryption" in v.get("type", "") for v in report["violations"]):
                recommendations.append(
                    "Encryption violations detected. Review PHI encryption policies."
                )
        elif framework == ComplianceFramework.PCI_DSS:
            if any("encryption" in v.get("type", "") for v in report["violations"]):
                recommendations.append(
                    "Card data encryption violations detected. Review PCI compliance."
                )

        return recommendations

    async def cleanup_expired_data(self) -> Dict[str, int]:
        """Clean up expired data based on retention policies"""
        cleanup_stats = {
            "audit_events": 0,
            "data_subject_requests": 0
        }

        now = datetime.now()

        # Clean up audit events
        for rule in self.compliance_rules.values():
            if rule.retention_period:
                cutoff_date = now - rule.retention_period.value

                # Keep events that are still within retention period
                self.audit_events = [
                    event for event in self.audit_events
                    if event.timestamp > cutoff_date or rule.framework not in event.compliance_frameworks
                ]

                cleanup_stats["audit_events"] += 1

        # Clean up completed data subject requests older than 7 years
        cutoff_date = now - timedelta(days=7 * 365)
        completed_requests = [
            req for req in self.data_subject_requests.values()
            if req.status == "completed" and req.completed_at and req.completed_at < cutoff_date
        ]

        for request in completed_requests:
            del self.data_subject_requests[request.request_id]
            cleanup_stats["data_subject_requests"] += 1

        logger.info(f"Data cleanup completed: {cleanup_stats}")
        return cleanup_stats

    def get_compliance_status(self) -> Dict[str, Any]:
        """Get overall compliance status"""
        now = datetime.now()
        last_24_hours = now - timedelta(hours=24)
        last_7_days = now - timedelta(days=7)

        recent_events = [e for e in self.audit_events if e.timestamp > last_24_hours]
        weekly_events = [e for e in self.audit_events if e.timestamp > last_7_days]

        status = {
            "timestamp": now.isoformat(),
            "active_rules": len([r for r in self.compliance_rules.values() if r.enabled]),
            "total_audit_events": len(self.audit_events),
            "recent_activity": {
                "last_24_hours": len(recent_events),
                "last_7_days": len(weekly_events),
                "high_risk_last_24h": len([e for e in recent_events if e.risk_score >= 70]),
                "violations_last_24h": len([
                    e for e in recent_events
                    if e.event_type == AuditEventType.SECURITY_EVENT and "violation_type" in e.details
                ])
            },
            "data_subject_requests": {
                "pending": len([r for r in self.data_subject_requests.values() if r.status == "pending"]),
                "completed": len([r for r in self.data_subject_requests.values() if r.status == "completed"]),
                "total": len(self.data_subject_requests)
            },
            "frameworks": list(set(
                framework for event in self.audit_events
                for framework in event.compliance_frameworks
            ))
        }

        return status


# Global compliance manager instance
compliance_manager = ComplianceManager()


async def initialize_compliance_manager(storage_path: Optional[str] = None):
    """Initialize the global compliance manager"""
    global compliance_manager
    compliance_manager = ComplianceManager(storage_path or "/var/log/hermes/compliance")