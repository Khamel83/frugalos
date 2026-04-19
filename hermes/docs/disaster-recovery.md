# Disaster Recovery Guide for Hermes AI Assistant

## Overview

This document provides comprehensive disaster recovery procedures for the Hermes AI Assistant system. It covers backup strategies, recovery procedures, and contingency plans to ensure business continuity during various failure scenarios.

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Backup Strategy](#backup-strategy)
3. [Recovery Procedures](#recovery-procedures)
4. [Contingency Plans](#contingency-plans)
5. [Testing and Validation](#testing-and-validation)
6. [Contact Information](#contact-information)

## System Architecture Overview

### Components

- **Application Layer**: Hermes AI Assistant (Kubernetes Deployment)
- **Database Layer**: PostgreSQL (Primary + Replica)
- **Cache Layer**: Redis Cluster
- **Load Balancer**: Nginx Ingress Controller
- **Monitoring**: Prometheus + Grafana
- **Logging**: ELK Stack (Elasticsearch, Logstash, Kibana)

### Data Classification

| Data Type | Criticality | Backup Frequency | Retention | Location |
|-----------|------------|------------------|-----------|----------|
| Application Data | Critical | Hourly | 30 days | Primary + DR |
| Configuration | Critical | On change | 90 days | Git + DR |
| Database | Critical | Every 15 min | 90 days | Primary + DR |
| Logs | Important | Real-time | 7 days | Local + DR |
| Metrics | Important | Real-time | 30 days | Local + DR |

## Backup Strategy

### Automated Backups

#### Database Backups

```bash
#!/bin/bash
# scripts/backup-postgresql.sh

set -e

BACKUP_DIR="/opt/hermes/backups/database"
DATE=$(date +%Y%m%d_%H%M%S)
NAMESPACE="hermes"
POD_NAME="postgres-0"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create database backup
kubectl exec -n $NAMESPACE $POD_NAME -- pg_dump -U hermes hermes | gzip > $BACKUP_DIR/hermes_backup_$DATE.sql.gz

# Verify backup
if [ -f "$BACKUP_DIR/hermes_backup_$DATE.sql.gz" ]; then
    echo "Backup successful: hermes_backup_$DATE.sql.gz"

    # Upload to cloud storage
    aws s3 cp $BACKUP_DIR/hermes_backup_$DATE.sql.gz s3://hermes-backups/database/

    # Clean local backups older than 7 days
    find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

    # Create backup metadata
    echo "{\"date\":\"$DATE\",\"type\":\"database\",\"size\":\"$(stat -c%s $BACKUP_DIR/hermes_backup_$DATE.sql.gz)\",\"checksum\":\"$(sha256sum $BACKUP_DIR/hermes_backup_$DATE.sql.gz | cut -d' ' -f1)\"}" > $BACKUP_DIR/hermes_backup_$DATE.json
    aws s3 cp $BACKUP_DIR/hermes_backup_$DATE.json s3://hermes-backups/metadata/
else
    echo "Backup failed!"
    exit 1
fi
```

#### Configuration Backups

```bash
#!/bin/bash
# scripts/backup-config.sh

set -e

BACKUP_DIR="/opt/hermes/backups/config"
DATE=$(date +%Y%m%d_%H%M%S)
NAMESPACE="hermes"

mkdir -p $BACKUP_DIR

# Backup Kubernetes configurations
kubectl get configmaps,secrets,deployments,services,ingress -n $NAMESPACE -o yaml > $BACKUP_DIR/k8s_config_$DATE.yaml

# Backup application configuration
kubectl get configmap hermes-config -n $NAMESPACE -o yaml > $BACKUP_DIR/app_config_$DATE.yaml

# Backup Helm values (if using Helm)
helm get values hermes -n $NAMESPACE > $BACKUP_DIR/helm_values_$DATE.yaml

# Upload to cloud storage
aws s3 cp $BACKUP_DIR/k8s_config_$DATE.yaml s3://hermes-backups/config/
aws s3 cp $BACKUP_DIR/app_config_$DATE.yaml s3://hermes-backups/config/
aws s3 cp $BACKUP_DIR/helm_values_$DATE.yaml s3://hermes-backups/config/

# Create backup metadata
echo "{\"date\":\"$DATE\",\"type\":\"config\",\"components\":[\"k8s\",\"app\",\"helm\"]}" > $BACKUP_DIR/config_backup_$DATE.json
aws s3 cp $BACKUP_DIR/config_backup_$DATE.json s3://hermes-backups/metadata/
```

#### Redis Backup

```bash
#!/bin/bash
# scripts/backup-redis.sh

set -e

BACKUP_DIR="/opt/hermes/backups/redis"
DATE=$(date +%Y%m%d_%H%M%S)
NAMESPACE="hermes"
REDIS_POD="redis-0"

mkdir -p $BACKUP_DIR

# Create Redis backup
kubectl exec -n $NAMESPACE $REDIS_POD -- redis-cli BGSAVE
kubectl exec -n $NAMESPACE $REDIS_POD -- redis-cli LASTSAVE

# Wait for backup to complete
sleep 10

# Copy dump file
kubectl cp $NAMESPACE/$REDIS_POD:/data/dump.rdb $BACKUP_DIR/redis_dump_$DATE.rdb

# Compress backup
gzip $BACKUP_DIR/redis_dump_$DATE.rdb

# Upload to cloud storage
aws s3 cp $BACKUP_DIR/redis_dump_$DATE.rdb.gz s3://hermes-backups/redis/

# Create backup metadata
echo "{\"date\":\"$DATE\",\"type\":\"redis\",\"size\":\"$(stat -c%s $BACKUP_DIR/redis_dump_$DATE.rdb.gz)\"}" > $BACKUP_DIR/redis_backup_$DATE.json
aws s3 cp $BACKUP_DIR/redis_backup_$DATE.json s3://hermes-backups/metadata/
```

### Backup Scheduling

#### Kubernetes CronJob for Database Backups

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: hermes-database-backup
  namespace: hermes
spec:
  schedule: "*/15 * * * *"  # Every 15 minutes
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: backup-service-account
          restartPolicy: OnFailure
          containers:
          - name: postgres-backup
            image: postgres:15-alpine
            command:
            - /bin/bash
            - -c
            - |
              pg_dump -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB | gzip > /backup/hermes_backup_$(date +%Y%m%d_%H%M%S).sql.gz
              aws s3 cp /backup/ s3://hermes-backups/database/ --recursive
            env:
            - name: POSTGRES_HOST
              value: "postgres-service"
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: username
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgres-secret
                  key: password
            - name: POSTGRES_DB
              value: "hermes"
            - name: AWS_DEFAULT_REGION
              value: "us-west-2"
            - name: AWS_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: aws-credentials
                  key: access-key-id
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: aws-credentials
                  key: secret-access-key
            volumeMounts:
            - name: backup-storage
              mountPath: /backup
          volumes:
          - name: backup-storage
            emptyDir: {}
```

## Recovery Procedures

### Database Recovery

#### Scenario 1: Database Corruption

1. **Stop Application**
   ```bash
   kubectl scale deployment hermes --replicas=0 -n hermes
   ```

2. **Restore Database**
   ```bash
   # Download latest backup
   aws s3 cp s3://hermes-backups/database/hermes_backup_latest.sql.gz ./

   # Decompress
   gunzip hermes_backup_latest.sql.gz

   # Restore to temporary database
   kubectl exec -i -n hermes postgres-0 -- psql -U hermes -d hermes_restore < hermes_backup_latest.sql

   # Verify restore
   kubectl exec -n hermes postgres-0 -- psql -U hermes -d hermes_restore -c "SELECT COUNT(*) FROM conversations;"
   ```

3. **Switch to Restored Database**
   ```bash
   # Update connection to point to restored database
   kubectl patch secret hermes-secrets -n hermes -p '{"data":{"DATABASE_URL":"'$(echo -n 'postgresql://hermes:password@postgres-service:5432/hermes_restore' | base64)'"}}'

   # Restart application
   kubectl scale deployment hermes --replicas=3 -n hermes
   ```

4. **Verify Recovery**
   ```bash
   # Test API endpoint
   curl -X POST http://hermes.example.com/api/orchestrator/conversation \
     -H "Content-Type: application/json" \
     -d '{"context":{"user_id":"test"}}'

   # Check logs
   kubectl logs -l app=hermes-ai-assistant -n hermes --tail=50
   ```

#### Scenario 2: Complete Database Loss

1. **Create New Database**
   ```bash
   # Create new database
   kubectl exec -n hermes postgres-0 -- createdb -U hermes hermes_recovery

   # Restore schema
   aws s3 cp s3://hermes-backups/schema/hermes_schema_latest.sql ./
   kubectl exec -i -n hermes postgres-0 -- psql -U hermes -d hermes_recovery < hermes_schema_latest.sql
   ```

2. **Restore Data**
   ```bash
   # Find latest backup
   LATEST_BACKUP=$(aws s3 ls s3://hermes-backups/database/ --recursive | sort | tail -n 1 | awk '{print $4}')

   # Download and restore
   aws s3 cp s3://$LATEST_BACKUP ./
   gunzip $(basename $LATEST_BACKUP)
   kubectl exec -i -n hermes postgres-0 -- psql -U hermes -d hermes_recovery < $(basename $LATEST_BACKUP .gz)
   ```

3. **Update Configuration**
   ```bash
   # Update secrets
   kubectl patch secret hermes-secrets -n hermes -p '{"data":{"DATABASE_URL":"'$(echo -n 'postgresql://hermes:password@postgres-service:5432/hermes_recovery' | base64)'"}}'

   # Restart application
   kubectl rollout restart deployment hermes -n hermes
   ```

### Application Recovery

#### Scenario 1: Application Crash

1. **Check Pod Status**
   ```bash
   kubectl get pods -n hermes -l app=hermes-ai-assistant
   kubectl describe pod -n hermes -l app=hermes-ai-assistant
   ```

2. **Check Logs**
   ```bash
   kubectl logs -n hermes -l app=hermes-ai-assistant --tail=100
   ```

3. **Restart Application**
   ```bash
   kubectl rollout restart deployment hermes -n hermes
   kubectl rollout status deployment hermes -n hermes
   ```

4. **Scale Up if Needed**
   ```bash
   kubectl scale deployment hermes --replicas=5 -n hermes
   ```

#### Scenario 2: Complete Application Loss

1. **Restore from Git Repository**
   ```bash
   git clone https://github.com/hermes-ai/hermes.git /tmp/hermes-recovery
   cd /tmp/hermes-recovery
   git checkout v1.0.0
   ```

2. **Restore Configuration**
   ```bash
   # Download latest config backup
   aws s3 cp s3://hermes-backups/config/k8s_config_latest.yaml ./
   aws s3 cp s3://hermes-backups/config/helm_values_latest.yaml ./

   # Apply configurations
   kubectl apply -f k8s_config_latest.yaml
   helm upgrade hermes ./deployments/helm -f helm_values_latest.yaml --install
   ```

3. **Verify Deployment**
   ```bash
   kubectl get all -n hermes
   kubectl get pods -n hermes -l app=hermes-ai-assistant
   ```

### Infrastructure Recovery

#### Scenario 1: Kubernetes Cluster Failure

1. **Recreate Cluster**
   ```bash
   # Using AWS EKS
   aws eks create-cluster \
     --name hermes-recovery \
     --role-arn arn:aws:iam::ACCOUNT:role/eks-service-role \
     --resources-vpc-config subnetIds=subnet-abc123,subnet-def456,subnet-ghi789 \
     --nodegroup-name hermes-nodes \
     --node-type m5.large \
     --nodes 3
   ```

2. **Install Required Components**
   ```bash
   # Install Ingress Controller
   helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
   helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx

   # Install Prometheus
   helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
   helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring
   ```

3. **Deploy Hermes**
   ```bash
   # Clone repository
   git clone https://github.com/hermes-ai/hermes.git
   cd hermes/deployments/helm

   # Deploy
   helm install hermes . -f values-prod.yaml
   ```

#### Scenario 2: Region Failure

1. **Deploy to DR Region**
   ```bash
   # Set up DR region context
   kubectl config use-context hermes-dr-region

   # Deploy to DR region
   helm install hermes ./deployments/helm -f values-dr.yaml
   ```

2. **Update DNS**
   ```bash
   # Update Route53 to point to DR region
   aws route53 change-resource-record-sets \
     --hosted-zone-id ZONE_ID \
     --change-batch file://route53-dr-failover.json
   ```

## Contingency Plans

### Manual Recovery Procedures

#### Emergency Contact List

| Role | Contact | Phone | Email |
|------|---------|-------|-------|
| DevOps Lead | John Doe | +1-555-0101 | john.doe@hermes-ai.com |
| Backend Lead | Jane Smith | +1-555-0102 | jane.smith@hermes-ai.com |
| Infrastructure Lead | Mike Johnson | +1-555-0103 | mike.johnson@hermes-ai.com |
| On-call Engineer | Sarah Wilson | +1-555-0104 | sarah.wilson@hermes-ai.com |

#### Emergency Response Checklist

1. **Initial Assessment (0-15 minutes)**
   - [ ] Identify affected systems
   - [ ] Assess impact severity
   - [ ] Notify stakeholders
   - [ ] Initialize incident response

2. **Immediate Response (15-60 minutes)**
   - [ ] Implement temporary fixes
   - [ ] Scale unaffected services
   - [ ] Activate backup systems
   - [ ] Monitor system health

3. **Recovery (1-4 hours)**
   - [ ] Restore from backups
   - [ ] Validate system integrity
   - [ ] Restore normal operations
   - [ ] Update monitoring alerts

4. **Post-Recovery (4-24 hours)**
   - [ ] Conduct root cause analysis
   - [ ] Update documentation
   - [ ] Review and improve procedures
   - [ ] Communicate resolution

### Communication Plan

#### Stakeholder Notifications

**Critical Outage (> 1 hour)**
- Email all stakeholders
- Post status page update
- Send Slack notifications
- Activate phone tree for critical stakeholders

**Degraded Service (30 minutes - 1 hour)**
- Update status page
- Send email notifications
- Post Slack updates

**Minor Issue (< 30 minutes)**
- Update status page
- Post Slack notification

#### Status Page Updates

| Status | Description | Color |
|--------|-------------|-------|
| Operational | All systems normal | Green |
| Degraded Performance | Some features slow | Yellow |
| Partial Outage | Some features unavailable | Orange |
| Major Outage | Significant service disruption | Red |

## Testing and Validation

### Backup Testing

#### Monthly Backup Validation

```bash
#!/bin/bash
# scripts/test-backups.sh

set -e

echo "Starting backup validation..."

# Test database backup
echo "Testing database backup..."
LATEST_DB_BACKUP=$(aws s3 ls s3://hermes-backups/database/ --recursive | sort | tail -n 1 | awk '{print $4}')
aws s3 cp s3://$LATEST_DB_BACKUP ./test_backup.sql.gz
gunzip test_backup.sql

# Verify backup integrity
kubectl run test-backup --image=postgres:15-alpine --rm -i --restart=Never \
  --env="PGPASSWORD=testpassword" \
  -- psql -h postgres-service -U hermes -d hermes_test -c "\dt"

echo "Database backup validation: PASSED"

# Test configuration backup
echo "Testing configuration backup..."
LATEST_CONFIG_BACKUP=$(aws s3 ls s3://hermes-backups/config/ --recursive | sort | tail -n 1 | awk '{print $4}')
aws s3 cp s3://$LATEST_CONFIG_BACKUP ./test_config.yaml

# Validate YAML syntax
kubectl apply --dry-run=client -f test_config.yaml

echo "Configuration backup validation: PASSED"

# Test Redis backup
echo "Testing Redis backup..."
LATEST_REDIS_BACKUP=$(aws s3 ls s3://hermes-backups/redis/ --recursive | sort | tail -n 1 | awk '{print $4}')
aws s3 cp s3://$LATEST_REDIS_BACKUP ./test_redis.rdb.gz
gunzip test_redis.rdb.gz

# Validate Redis dump file
file test_redis.rdb | grep -q "Redis RDB"

echo "Redis backup validation: PASSED"

echo "All backup validations completed successfully!"

# Cleanup
rm -f test_backup.sql test_config.yaml test_redis.rdb
```

### Disaster Recovery Drills

#### Annual Full DR Drill

1. **Planning Phase (2 weeks before)**
   - Define drill objectives
   - Prepare test scenarios
   - Schedule resources
   - Notify stakeholders

2. **Execution Phase (Drill day)**
   - Simulate primary region failure
   - Activate DR environment
   - Validate all systems
   - Document issues

3. **Debrief Phase (1 week after)**
   - Analyze drill results
   - Identify improvement areas
   - Update procedures
   - Share findings

#### Quarterly Tabletop Exercises

- Review disaster recovery procedures
- Test communication plans
- Validate contact information
- Practice decision-making scenarios

## Monitoring and Alerting

### Backup Monitoring

```yaml
# Prometheus backup monitoring rules
groups:
  - name: backup.rules
    rules:
      - alert: BackupFailed
        expr: backup_success == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Backup failed for {{ $labels.backup_type }}"
          description: "Backup failed for {{ $labels.backup_type }} at {{ $labels.timestamp }}"

      - alert: BackupAgeTooHigh
        expr: time() - backup_last_success_timestamp > 86400
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Backup too old for {{ $labels.backup_type }}"
          description: "Last successful backup for {{ $labels.backup_type }} was more than 24 hours ago"

      - alert: BackupSizeAnomaly
        expr: abs(backup_size - backup_size_avg) / backup_size_avg > 0.5
        for: 2h
        labels:
          severity: warning
        annotations:
          summary: "Backup size anomaly for {{ $labels.backup_type }}"
          description: "Backup size for {{ $labels.backup_type }} is significantly different from average"
```

### Recovery Time Objectives (RTO)

| System | RTO Target | RPO Target | Current RTO | Current RPO |
|--------|-------------|-------------|-------------|-------------|
| Application | 15 minutes | 5 minutes | 10 minutes | 5 minutes |
| Database | 1 hour | 15 minutes | 45 minutes | 15 minutes |
| Cache | 15 minutes | 5 minutes | 10 minutes | 5 minutes |
| Configuration | 30 minutes | 1 hour | 20 minutes | 1 hour |

## Contact Information

### Emergency Contacts

**Primary Contacts**
- DevOps Team: devops@hermes-ai.com
- Engineering Team: engineering@hermes-ai.com
- Support Team: support@hermes-ai.com

**Critical Incident Response**
- PagerDuty: https://hermes-ai.pagerduty.com
- Slack Channel: #incidents
- Phone: +1-555-9999 (24/7)

**Cloud Provider Support**
- AWS: 1-855-284-2315
- Google Cloud: 1-855-814-2128
- Microsoft Azure: 1-800-425-4696

### Documentation Access

- Disaster Recovery Plan: https://docs.hermes-ai.com/dr
- Runbooks: https://docs.hermes-ai.com/runbooks
- Architecture Diagrams: https://docs.hermes-ai.com/architecture
- Configuration Management: https://github.com/hermes-ai/hermes

## Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2024-01-01 | Initial document creation | DevOps Team |
| 1.1 | 2024-01-15 | Added Redis backup procedures | Backend Team |
| 1.2 | 2024-02-01 | Updated RTO/RPO targets | Infrastructure Team |
| 1.3 | 2024-02-15 | Added multi-region recovery | DevOps Team |

---

**This document is confidential and proprietary to Hermes AI. Unauthorized distribution is prohibited.**