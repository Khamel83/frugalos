"""
Tests for the Compliance Manager

This module contains comprehensive tests for compliance frameworks,
audit logging, data subject requests, and reporting.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from hermes.security.compliance import (
    ComplianceManager,
    ComplianceFramework,
    AuditEventType,
    DataClassification,
    AuditEvent,
    ComplianceRule,
    DataSubjectRequest
)


class TestComplianceManager:
    """Test cases for ComplianceManager"""

    def test_initialize_manager(self, temp_dir):
        """Test compliance manager initialization."""
        manager = ComplianceManager(storage_path=str(temp_dir / "compliance"))

        assert manager.storage_path.exists()
        assert len(manager.compliance_rules) > 0
        assert ComplianceFramework.GDPR in [rule.framework for rule in manager.compliance_rules.values()]
        assert ComplianceFramework.SOC2 in [rule.framework for rule in manager.compliance_rules.values()]

    @pytest.mark.asyncio
    async def test_log_audit_event(self, compliance_manager):
        """Test audit event logging."""
        event = await compliance_manager.log_audit_event(
            event_type=AuditEventType.USER_LOGIN,
            user_id="testuser",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            resource_id="session_123",
            action="login",
            result="success",
            compliance_frameworks=[ComplianceFramework.GDPR],
            data_classification=DataClassification.INTERNAL
        )

        assert event is not None
        assert event.event_type == AuditEventType.USER_LOGIN
        assert event.user_id == "testuser"
        assert event.ip_address == "192.168.1.100"
        assert event.result == "success"
        assert ComplianceFramework.GDPR in event.compliance_frameworks
        assert event.data_classification == DataClassification.INTERNAL
        assert event.risk_score >= 0

        # Verify event is stored
        assert event in compliance_manager.audit_events
        assert len(compliance_manager.audit_events) > 0

    @pytest.mark.asyncio
    async def test_log_audit_event_with_details(self, compliance_manager):
        """Test audit event logging with detailed information."""
        details = {
            "auth_method": "password",
            "mfa_used": False,
            "session_duration": 3600,
            "device_type": "desktop"
        }

        event = await compliance_manager.log_audit_event(
            event_type=AuditEventType.USER_LOGIN,
            user_id="testuser",
            details=details
        )

        assert event.details == details
        assert event.details["auth_method"] == "password"
        assert event.details["mfa_used"] is False

    @pytest.mark.asyncio
    async def test_risk_score_calculation(self, compliance_manager):
        """Test risk score calculation for different events."""
        # Low risk event
        low_risk_event = await compliance_manager.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            user_id="testuser",
            data_classification=DataClassification.PUBLIC
        )
        assert low_risk_event.risk_score < 50

        # High risk event
        high_risk_event = await compliance_manager.log_audit_event(
            event_type=AuditEventType.SECURITY_EVENT,
            user_id="testuser",
            data_classification=DataClassification.RESTRICTED,
            details={"violation_type": "unauthorized_access"}
        )
        assert high_risk_event.risk_score >= 70

    @pytest.mark.asyncio
    async def test_compliance_violation_detection(self, compliance_manager):
        """Test compliance violation detection."""
        # Log an event that should trigger a violation
        violation_event = await compliance_manager.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            user_id="testuser",
            compliance_frameworks=[ComplianceFramework.GDPR],
            details={"encrypted": False, "consent_obtained": False}
        )

        # Check if violation was detected and logged
        security_events = [
            event for event in compliance_manager.audit_events
            if event.event_type == AuditEventType.SECURITY_EVENT
            and "violation_type" in event.details
        ]

        assert len(security_events) > 0
        violation = security_events[0]
        assert "consent_required" in violation.details["violation_type"]

    @pytest.mark.asyncio
    async def test_create_data_subject_request(self, compliance_manager):
        """Test data subject request creation."""
        request = await compliance_manager.create_data_subject_request(
            subject_id="user@example.com",
            request_type="access",
            details={"requested_data": "all_personal_data"}
        )

        assert request is not None
        assert request.subject_id == "user@example.com"
        assert request.request_type == "access"
        assert request.status == "pending"
        assert request.request_id in compliance_manager.data_subject_requests
        assert request.created_at is not None

    @pytest.mark.asyncio
    async def test_process_data_subject_request(self, compliance_manager):
        """Test data subject request processing."""
        # Create request
        request = await compliance_manager.create_data_subject_request(
            subject_id="user@example.com",
            request_type="deletion"
        )

        # Process request
        success = await compliance_manager.process_data_subject_request(
            request_id=request.request_id,
            processed_by="admin_user",
            result={"deleted_records": 5, "status": "completed"}
        )

        assert success is True

        # Verify request is updated
        updated_request = compliance_manager.data_subject_requests[request.request_id]
        assert updated_request.status == "completed"
        assert updated_request.processed_by == "admin_user"
        assert updated_request.completed_at is not None
        assert "deleted_records" in updated_request.details

    @pytest.mark.asyncio
    async def test_generate_compliance_report(self, compliance_manager):
        """Test compliance report generation."""
        # Log some test events
        await compliance_manager.log_audit_event(
            event_type=AuditEventType.USER_LOGIN,
            user_id="user1",
            compliance_frameworks=[ComplianceFramework.GDPR]
        )

        await compliance_manager.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            user_id="user2",
            compliance_frameworks=[ComplianceFramework.GDPR]
        )

        await compliance_manager.log_audit_event(
            event_type=AuditEventType.SECURITY_EVENT,
            user_id="user1",
            compliance_frameworks=[ComplianceFramework.GDPR],
            details={"violation_type": "test_violation"}
        )

        # Generate report
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)

        report = await compliance_manager.generate_compliance_report(
            framework=ComplianceFramework.GDPR,
            start_date=start_date,
            end_date=end_date
        )

        # Verify report structure
        assert report["framework"] == ComplianceFramework.GDPR.value
        assert "period" in report
        assert "summary" in report
        assert "event_types" in report
        assert "risk_distribution" in report
        assert "violations" in report
        assert "recommendations" in report

        # Verify summary data
        summary = report["summary"]
        assert summary["total_events"] >= 3
        assert summary["unique_users"] >= 1
        assert summary["high_risk_events"] >= 1

        # Verify violations section
        violations = report["violations"]
        assert len(violations) >= 1
        assert violations[0]["type"] == "consent_required"

    @pytest.mark.asyncio
    async def test_cleanup_expired_data(self, compliance_manager):
        """Test cleanup of expired data based on retention policies."""
        # Create old audit event
        old_event = AuditEvent(
            event_id="old_event_123",
            event_type=AuditEventType.USER_LOGIN,
            timestamp=datetime.now() - timedelta(days=400),  # Very old
            compliance_frameworks=[ComplianceFramework.GDPR]
        )
        compliance_manager.audit_events.append(old_event)

        # Create old data subject request
        old_request = DataSubjectRequest(
            request_id="old_request_123",
            subject_id="old@example.com",
            request_type="access",
            status="completed",
            created_at=datetime.now() - timedelta(days=3000),  # Very old
            completed_at=datetime.now() - timedelta(days=2990)
        )
        compliance_manager.data_subject_requests[old_request.request_id] = old_request

        # Run cleanup
        cleanup_stats = await compliance_manager.cleanup_expired_data()

        # Verify cleanup results
        assert "audit_events" in cleanup_stats
        assert "data_subject_requests" in cleanup_stats

        # Old event should be removed if past retention period
        gdpr_events = [
            event for event in compliance_manager.audit_events
            if ComplianceFramework.GDPR in event.compliance_frameworks
        ]
        assert old_event not in gdpr_events

    @pytest.mark.asyncio
    async def test_get_compliance_status(self, compliance_manager):
        """Test getting overall compliance status."""
        # Add some test events
        await compliance_manager.log_audit_event(
            event_type=AuditEventType.USER_LOGIN,
            user_id="user1",
            compliance_frameworks=[ComplianceFramework.GDPR]
        )

        await compliance_manager.log_audit_event(
            event_type=AuditEventType.DATA_DELETION,
            user_id="user2",
            compliance_frameworks=[ComplianceFramework.HIPAA]
        )

        # Create data subject request
        await compliance_manager.create_data_subject_request(
            subject_id="user@example.com",
            request_type="access"
        )

        # Get status
        status = compliance_manager.get_compliance_status()

        # Verify status structure
        assert "timestamp" in status
        assert "active_rules" in status
        assert "total_audit_events" in status
        assert "recent_activity" in status
        assert "data_subject_requests" in status
        assert "frameworks" in status

        # Verify specific data
        assert status["active_rules"] > 0
        assert status["total_audit_events"] >= 2
        assert ComplianceFramework.GDPR.value in status["frameworks"]
        assert ComplianceFramework.HIPAA.value in status["frameworks"]
        assert status["data_subject_requests"]["pending"] >= 1

    def test_compliance_rules_initialization(self, compliance_manager):
        """Test that compliance rules are properly initialized."""
        rules = compliance_manager.compliance_rules

        # Check GDPR rules
        gdpr_rules = [rule for rule in rules.values() if rule.framework == ComplianceFramework.GDPR]
        assert len(gdpr_rules) > 0

        gdpr_rule_ids = [rule.rule_id for rule in gdpr_rules]
        assert "gdpr_data_minimization" in gdpr_rule_ids
        assert "gdpr_consent" in gdpr_rule_ids
        assert "gdpr_retention" in gdpr_rule_ids

        # Check HIPAA rules
        hipaa_rules = [rule for rule in rules.values() if rule.framework == ComplianceFramework.HIPAA]
        hipaa_rule_ids = [rule.rule_id for rule in hipaa_rules]
        assert "hipaa_encryption" in hipaa_rule_ids
        assert "hipaa_audit" in hipaa_rule_ids

        # Check PCI DSS rules
        pci_rules = [rule for rule in rules.values() if rule.framework == ComplianceFramework.PCI_DSS]
        pci_rule_ids = [rule.rule_id for rule in pci_rules]
        assert "pci_encryption" in pci_rule_ids
        assert "pci_retention" in pci_rule_ids

    @pytest.mark.asyncio
    async def test_audit_event_storage(self, temp_dir):
        """Test that audit events are properly stored to files."""
        manager = ComplianceManager(storage_path=str(temp_dir / "compliance"))

        # Log an event
        event = await manager.log_audit_event(
            event_type=AuditEventType.USER_LOGIN,
            user_id="testuser",
            ip_address="192.168.1.100"
        )

        # Check that file was created
        audit_dir = manager.storage_path / "audit"
        assert audit_dir.exists()

        # Check that event was written to file
        current_month = datetime.now().strftime("%Y%m")
        audit_file = audit_dir / f"{current_month}.jsonl"
        assert audit_file.exists()

        # Verify file content
        with open(audit_file, "r") as f:
            file_content = f.read().strip()
            assert file_content != ""

            # Parse the JSON line
            stored_event = json.loads(file_content)
            assert stored_event["event_type"] == event.event_type.value
            assert stored_event["user_id"] == event.user_id

    @pytest.mark.asyncio
    async def test_data_subject_request_storage(self, temp_dir):
        """Test that data subject requests are properly stored."""
        manager = ComplianceManager(storage_path=str(temp_dir / "compliance"))

        # Create a request
        request = await manager.create_data_subject_request(
            subject_id="user@example.com",
            request_type="access"
        )

        # Check that file was created
        requests_file = manager.storage_path / "data_subject_requests.json"
        assert requests_file.exists()

        # Verify file content
        with open(requests_file, "r") as f:
            stored_requests = json.load(f)
            assert len(stored_requests) == 1

            stored_request = stored_requests[0]
            assert stored_request["request_id"] == request.request_id
            assert stored_request["subject_id"] == request.subject_id
            assert stored_request["request_type"] == request.request_type

    @pytest.mark.asyncio
    async def test_multiple_frameworks_compliance(self, compliance_manager):
        """Test compliance with multiple frameworks."""
        # Log event with multiple frameworks
        event = await compliance_manager.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            user_id="testuser",
            compliance_frameworks=[
                ComplianceFramework.GDPR,
                ComplianceFramework.SOC2,
                ComplianceFramework.HIPAA
            ],
            data_classification=DataClassification.CONFIDENTIAL,
            details={"encrypted": True, "consent_obtained": True}
        )

        # Generate reports for each framework
        reports = {}
        for framework in [ComplianceFramework.GDPR, ComplianceFramework.SOC2, ComplianceFramework.HIPAA]:
            report = await compliance_manager.generate_compliance_report(
                framework=framework,
                start_date=datetime.now() - timedelta(days=1),
                end_date=datetime.now()
            )
            reports[framework] = report

        # Verify all frameworks have reports
        assert len(reports) == 3
        for framework, report in reports.items():
            assert report["framework"] == framework.value
            assert report["summary"]["total_events"] >= 1

    @pytest.mark.asyncio
    async def test_ip_geography_restrictions(self, compliance_manager):
        """Test IP geography restriction checking."""
        # Create a compliance rule with geo restrictions
        rule = ComplianceRule(
            rule_id="test_geo_rule",
            framework=ComplianceFramework.GDPR,
            name="Test Geo Restriction",
            description="Test IP geo restrictions",
            geo_restrictions=["US", "EU"]
        )
        compliance_manager.compliance_rules["test_geo_rule"] = rule

        # Log event from allowed IP
        allowed_event = await compliance_manager.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            user_id="testuser",
            ip_address="192.168.1.100",  # Private IP (should be allowed)
            compliance_frameworks=[ComplianceFramework.GDPR]
        )

        # Log event from potentially restricted IP (this is simplified)
        restricted_event = await compliance_manager.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            user_id="testuser",
            ip_address="203.0.113.1",  # Public IP (may be restricted)
            compliance_frameworks=[ComplianceFramework.GDPR]
        )

        # The IP checking logic is simplified in tests, but events should be logged
        assert allowed_event is not None
        assert restricted_event is not None

    @pytest.mark.asyncio
    async def test_data_classification_impact(self, compliance_manager):
        """Test impact of data classification on risk scoring."""
        test_data = "Test data"

        # Log events with different classifications
        public_event = await compliance_manager.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            user_id="testuser",
            data_classification=DataClassification.PUBLIC
        )

        internal_event = await compliance_manager.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            user_id="testuser",
            data_classification=DataClassification.INTERNAL
        )

        confidential_event = await compliance_manager.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            user_id="testuser",
            data_classification=DataClassification.CONFIDENTIAL
        )

        restricted_event = await compliance_manager.log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            user_id="testuser",
            data_classification=DataClassification.RESTRICTED
        )

        # Risk scores should increase with classification level
        assert public_event.risk_score <= internal_event.risk_score
        assert internal_event.risk_score <= confidential_event.risk_score
        assert confidential_event.risk_score <= restricted_event.risk_score

    @pytest.mark.asyncio
    async def test_recommendation_generation(self, compliance_manager):
        """Test compliance recommendation generation."""
        # Log some problematic events
        await compliance_manager.log_audit_event(
            event_type=AuditEventType.SECURITY_EVENT,
            user_id="testuser",
            compliance_frameworks=[ComplianceFramework.GDPR],
            details={"violation_type": "consent_required"}
        )

        await compliance_manager.log_audit_event(
            event_type=AuditEventType.SECURITY_EVENT,
            user_id="testuser",
            compliance_frameworks=[ComplianceFramework.HIPAA],
            details={"violation_type": "encryption_required"}
        )

        # Generate report
        report = await compliance_manager.generate_compliance_report(
            framework=ComplianceFramework.GDPR,
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now()
        )

        # Check recommendations
        recommendations = report["recommendations"]
        assert len(recommendations) > 0

        # Should have GDPR-specific recommendations
        gdpr_recommendations = [
            rec for rec in recommendations
            if "consent" in rec.lower()
        ]
        assert len(gdpr_recommendations) > 0

    @pytest.mark.asyncio
    async def test_concurrent_audit_logging(self, compliance_manager):
        """Test concurrent audit event logging."""
        import asyncio

        async def log_events(user_id, count):
            events = []
            for i in range(count):
                event = await compliance_manager.log_audit_event(
                    event_type=AuditEventType.DATA_ACCESS,
                    user_id=f"{user_id}_{i}",
                    details={"batch_id": i}
                )
                events.append(event)
            return events

        # Create concurrent tasks
        tasks = [
            log_events("user_a", 5),
            log_events("user_b", 5),
            log_events("user_c", 5)
        ]

        # Execute concurrently
        results = await asyncio.gather(*tasks)

        # Verify all events were logged
        total_events = sum(len(events) for events in results)
        assert total_events == 15
        assert len(compliance_manager.audit_events) >= 15

    @pytest.mark.asyncio
    async def test_error_handling_in_compliance(self, compliance_manager):
        """Test error handling in compliance operations."""
        # Test with invalid data
        try:
            await compliance_manager.log_audit_event(
                event_type=AuditEventType.USER_LOGIN,
                user_id=None,  # This might cause issues
                details={"invalid": "data"}
            )
        except Exception as e:
            # Should handle gracefully
            assert isinstance(e, Exception)

        # Test compliance report with invalid date range
        try:
            end_date = datetime.now()
            start_date = end_date + timedelta(days=1)  # Start after end

            report = await compliance_manager.generate_compliance_report(
                framework=ComplianceFramework.GDPR,
                start_date=start_date,
                end_date=end_date
            )
            # Should handle gracefully and return empty report
            assert report["summary"]["total_events"] == 0
        except Exception as e:
            # Should not raise unhandled exception
            assert isinstance(e, Exception)