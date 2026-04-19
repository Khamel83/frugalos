#!/bin/bash

# Comprehensive Backup Script for Hermes AI Assistant
# This script creates automated backups of all system components

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_ROOT="/opt/hermes/backups"
LOG_FILE="/var/log/hermes/backup.log"
DATE=$(date +%Y%m%d_%H%M%S)
NAMESPACE="hermes"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Create backup directory structure
create_backup_dirs() {
    log "Creating backup directory structure"
    mkdir -p "$BACKUP_ROOT"/{database,redis,config,logs,metadata,full}
    mkdir -p "$BACKUP_ROOT/database"/{daily,weekly,monthly}
    mkdir -p "$BACKUP_ROOT/config"/{k8s,helm,app}
}

# Backup PostgreSQL Database
backup_postgresql() {
    log "Starting PostgreSQL database backup"

    local BACKUP_FILE="$BACKUP_ROOT/database/hermes_postgres_$DATE.sql.gz"
    local POD_NAME="postgres-0"

    # Check if PostgreSQL pod is running
    if ! kubectl get pod "$POD_NAME" -n "$NAMESPACE" &>/dev/null; then
        error_exit "PostgreSQL pod $POD_NAME not found"
    fi

    # Create backup
    if kubectl exec -n "$NAMESPACE" "$POD_NAME" -- pg_dump -U hermes hermes | gzip > "$BACKUP_FILE"; then
        local BACKUP_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE")
        log "PostgreSQL backup completed successfully. Size: $BACKUP_SIZE bytes"

        # Upload to cloud storage
        if command -v aws &>/dev/null; then
            aws s3 cp "$BACKUP_FILE" "s3://hermes-backups/database/" --storage-class STANDARD_IA
            log "PostgreSQL backup uploaded to S3"
        fi

        # Create metadata
        local METADATA_FILE="$BACKUP_ROOT/metadata/postgres_backup_$DATE.json"
        cat > "$METADATA_FILE" << EOF
{
    "date": "$DATE",
    "type": "postgresql",
    "component": "database",
    "size_bytes": $BACKUP_SIZE,
    "file_path": "$(basename "$BACKUP_FILE")",
    "pod_name": "$POD_NAME",
    "namespace": "$NAMESPACE",
    "checksum": "$(sha256sum "$BACKUP_FILE" | cut -d' ' -f1)",
    "created_at": "$(date -Iseconds)"
}
EOF

        # Upload metadata
        if command -v aws &>/dev/null; then
            aws s3 cp "$METADATA_FILE" "s3://hermes-backups/metadata/"
        fi

        # Clean old local backups (keep last 7 days)
        find "$BACKUP_ROOT/database" -name "*.sql.gz" -mtime +7 -delete
        find "$BACKUP_ROOT/metadata" -name "postgres_backup_*.json" -mtime +7 -delete

        log "PostgreSQL backup cleanup completed"
    else
        error_exit "PostgreSQL backup failed"
    fi
}

# Backup Redis
backup_redis() {
    log "Starting Redis backup"

    local BACKUP_FILE="$BACKUP_ROOT/redis/hermes_redis_$DATE.rdb.gz"
    local POD_NAME="redis-master"

    # Check if Redis pod is running
    if ! kubectl get pod "$POD_NAME" -n "$NAMESPACE" &>/dev/null; then
        log "WARNING: Redis pod $POD_NAME not found, skipping Redis backup"
        return
    fi

    # Create background save
    kubectl exec -n "$NAMESPACE" "$POD_NAME" -- redis-cli BGSAVE

    # Wait for save to complete
    sleep 10

    # Copy dump file
    if kubectl cp "$NAMESPACE/$POD_NAME:/data/dump.rdb" "$BACKUP_ROOT/redis/hermes_redis_$DATE.rdb" 2>/dev/null; then
        # Compress backup
        gzip "$BACKUP_ROOT/redis/hermes_redis_$DATE.rdb"

        local BACKUP_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE")
        log "Redis backup completed successfully. Size: $BACKUP_SIZE bytes"

        # Upload to cloud storage
        if command -v aws &>/dev/null; then
            aws s3 cp "$BACKUP_FILE" "s3://hermes-backups/redis/" --storage-class STANDARD_IA
            log "Redis backup uploaded to S3"
        fi

        # Create metadata
        local METADATA_FILE="$BACKUP_ROOT/metadata/redis_backup_$DATE.json"
        cat > "$METADATA_FILE" << EOF
{
    "date": "$DATE",
    "type": "redis",
    "component": "cache",
    "size_bytes": $BACKUP_SIZE,
    "file_path": "$(basename "$BACKUP_FILE")",
    "pod_name": "$POD_NAME",
    "namespace": "$NAMESPACE",
    "checksum": "$(sha256sum "$BACKUP_FILE" | cut -d' ' -f1)",
    "created_at": "$(date -Iseconds)"
}
EOF

        # Upload metadata
        if command -v aws &>/dev/null; then
            aws s3 cp "$METADATA_FILE" "s3://hermes-backups/metadata/"
        fi

        # Clean old local backups (keep last 7 days)
        find "$BACKUP_ROOT/redis" -name "*.rdb.gz" -mtime +7 -delete
        find "$BACKUP_ROOT/metadata" -name "redis_backup_*.json" -mtime +7 -delete

        log "Redis backup cleanup completed"
    else
        log "WARNING: Redis backup failed"
    fi
}

# Backup Kubernetes Configurations
backup_k8s_config() {
    log "Starting Kubernetes configuration backup"

    local CONFIG_DIR="$BACKUP_ROOT/config/k8s"

    # Backup all resources
    kubectl get all,configmaps,secrets,ingress,pv,pvc,storageclass -n "$NAMESPACE" -o yaml > "$CONFIG_DIR/k8s_resources_$DATE.yaml"

    # Backup specific resources separately
    kubectl get deployment hermes -n "$NAMESPACE" -o yaml > "$CONFIG_DIR/hermes_deployment_$DATE.yaml"
    kubectl get service hermes-service -n "$NAMESPACE" -o yaml > "$CONFIG_DIR/hermes_service_$DATE.yaml"
    kubectl get ingress hermes-ingress -n "$NAMESPACE" -o yaml > "$CONFIG_DIR/hermes_ingress_$DATE.yaml"

    # Backup CRDs if any
    kubectl get crds -o yaml > "$CONFIG_DIR/crds_$DATE.yaml"

    log "Kubernetes configuration backup completed"

    # Upload to cloud storage
    if command -v aws &>/dev/null; then
        aws s3 cp "$CONFIG_DIR/" "s3://hermes-backups/config/k8s/" --recursive --exclude "*" --include "*_$DATE.yaml"
        log "Kubernetes configuration backup uploaded to S3"
    fi

    # Create metadata
    local METADATA_FILE="$BACKUP_ROOT/metadata/k8s_config_backup_$DATE.json"
    cat > "$METADATA_FILE" << EOF
{
    "date": "$DATE",
    "type": "kubernetes",
    "component": "config",
    "namespace": "$NAMESPACE",
    "resources": [
        "deployments",
        "services",
        "configmaps",
        "secrets",
        "ingress",
        "pv",
        "pvc"
    ],
    "created_at": "$(date -Iseconds)"
}
EOF

    # Upload metadata
    if command -v aws &>/dev/null; then
        aws s3 cp "$METADATA_FILE" "s3://hermes-backups/metadata/"
    fi

    # Clean old local backups (keep last 30 days)
    find "$CONFIG_DIR" -name "*_$DATE.yaml" -mtime +30 -delete
}

# Backup Helm Configuration
backup_helm_config() {
    log "Starting Helm configuration backup"

    local CONFIG_DIR="$BACKUP_ROOT/config/helm"

    # Check if Helm is available
    if ! command -v helm &>/dev/null; then
        log "WARNING: Helm not found, skipping Helm backup"
        return
    fi

    # Get Helm releases
    helm list -n "$NAMESPACE" -o yaml > "$CONFIG_DIR/helm_releases_$DATE.yaml"

    # Get values for Hermes deployment
    if helm get values hermes -n "$NAMESPACE" > "$CONFIG_DIR/hermes_values_$DATE.yaml" 2>/dev/null; then
        log "Helm values backup completed"
    else
        log "WARNING: Could not get Helm values for hermes"
    fi

    # Upload to cloud storage
    if command -v aws &>/dev/null; then
        aws s3 cp "$CONFIG_DIR/" "s3://hermes-backups/config/helm/" --recursive --exclude "*" --include "*_$DATE.yaml"
        log "Helm configuration backup uploaded to S3"
    fi

    # Create metadata
    local METADATA_FILE="$BACKUP_ROOT/metadata/helm_config_backup_$DATE.json"
    cat > "$METADATA_FILE" << EOF
{
    "date": "$DATE",
    "type": "helm",
    "component": "config",
    "namespace": "$NAMESPACE",
    "releases": ["hermes"],
    "created_at": "$(date -Iseconds)"
}
EOF

    # Upload metadata
    if command -v aws &>/dev/null; then
        aws s3 cp "$METADATA_FILE" "s3://hermes-backups/metadata/"
    fi

    # Clean old local backups (keep last 30 days)
    find "$CONFIG_DIR" -name "*_$DATE.yaml" -mtime +30 -delete
}

# Backup Application Configuration
backup_app_config() {
    log "Starting application configuration backup"

    local CONFIG_DIR="$BACKUP_ROOT/config/app"

    # Get configmap
    if kubectl get configmap hermes-config -n "$NAMESPACE" -o yaml > "$CONFIG_DIR/app_configmap_$DATE.yaml"; then
        log "Application configmap backup completed"
    else
        log "WARNING: Could not get application configmap"
    fi

    # Get secrets (without sensitive data)
    if kubectl get secret hermes-secrets -n "$NAMESPACE" -o yaml > "$CONFIG_DIR/app_secrets_$DATE.yaml"; then
        # Remove sensitive data from backup for security
        sed -i.bak '/data:/,/^[[:space:]]*$/c\
  data: # SENSITIVE_DATA_REDACTED' "$CONFIG_DIR/app_secrets_$DATE.yaml"
        rm "$CONFIG_DIR/app_secrets_$DATE.yaml.bak"
        log "Application secrets backup completed (sensitive data redacted)"
    else
        log "WARNING: Could not get application secrets"
    fi

    # Upload to cloud storage
    if command -v aws &>/dev/null; then
        aws s3 cp "$CONFIG_DIR/" "s3://hermes-backups/config/app/" --recursive --exclude "*" --include "*_$DATE.yaml"
        log "Application configuration backup uploaded to S3"
    fi

    # Create metadata
    local METADATA_FILE="$BACKUP_ROOT/metadata/app_config_backup_$DATE.json"
    cat > "$METADATA_FILE" << EOF
{
    "date": "$DATE",
    "type": "application",
    "component": "config",
    "namespace": "$NAMESPACE",
    "resources": ["configmap", "secrets"],
    "created_at": "$(date -Iseconds)"
}
EOF

    # Upload metadata
    if command -v aws &>/dev/null; then
        aws s3 cp "$METADATA_FILE" "s3://hermes-backups/metadata/"
    fi

    # Clean old local backups (keep last 30 days)
    find "$CONFIG_DIR" -name "*_$DATE.yaml" -mtime +30 -delete
}

# Create full system backup
create_full_backup() {
    log "Starting full system backup"

    local FULL_BACKUP_DIR="$BACKUP_ROOT/full/full_backup_$DATE"
    mkdir -p "$FULL_BACKUP_DIR"

    # Archive all recent backups
    tar -czf "$FULL_BACKUP_DIR/full_backup_$DATE.tar.gz" \
        -C "$BACKUP_ROOT" \
        database/ redis/ config/ metadata/ \
        --exclude="full/*"

    local FULL_BACKUP_SIZE=$(stat -f%z "$FULL_BACKUP_DIR/full_backup_$DATE.tar.gz" 2>/dev/null || stat -c%s "$FULL_BACKUP_DIR/full_backup_$DATE.tar.gz")
    log "Full system backup completed. Size: $FULL_BACKUP_SIZE bytes"

    # Upload to cloud storage
    if command -v aws &>/dev/null; then
        aws s3 cp "$FULL_BACKUP_DIR/full_backup_$DATE.tar.gz" "s3://hermes-backups/full/" --storage-class DEEP_ARCHIVE
        log "Full system backup uploaded to S3 (Deep Archive)"
    fi

    # Create metadata
    local METADATA_FILE="$BACKUP_ROOT/metadata/full_backup_$DATE.json"
    cat > "$METADATA_FILE" << EOF
{
    "date": "$DATE",
    "type": "full_system",
    "component": "complete_backup",
    "size_bytes": $FULL_BACKUP_SIZE,
    "file_path": "full_backup_$DATE.tar.gz",
    "includes": ["database", "redis", "config", "metadata"],
    "created_at": "$(date -Iseconds)"
}
EOF

    # Upload metadata
    if command -v aws &>/dev/null; then
        aws s3 cp "$METADATA_FILE" "s3://hermes-backups/metadata/"
    fi

    # Clean old full backups (keep last 90 days)
    find "$BACKUP_ROOT/full" -name "*.tar.gz" -mtime +90 -delete
    find "$BACKUP_ROOT/metadata" -name "full_backup_*.json" -mtime +90 -delete

    log "Full system backup cleanup completed"
}

# Validate backups
validate_backups() {
    log "Starting backup validation"

    local VALIDATION_ERRORS=0

    # Validate PostgreSQL backup
    local LATEST_PG_BACKUP=$(find "$BACKUP_ROOT/database" -name "*.sql.gz" -type f -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)
    if [ -n "$LATEST_PG_BACKUP" ] && [ -f "$LATEST_PG_BACKUP" ]; then
        # Test if backup file is not empty and is a valid gzip file
        if gzip -t "$LATEST_PG_BACKUP" 2>/dev/null && [ -s "$LATEST_PG_BACKUP" ]; then
            log "PostgreSQL backup validation: PASSED"
        else
            log "PostgreSQL backup validation: FAILED"
            ((VALIDATION_ERRORS++))
        fi
    else
        log "PostgreSQL backup validation: FAILED - No backup file found"
        ((VALIDATION_ERRORS++))
    fi

    # Validate Redis backup
    local LATEST_REDIS_BACKUP=$(find "$BACKUP_ROOT/redis" -name "*.rdb.gz" -type f -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)
    if [ -n "$LATEST_REDIS_BACKUP" ] && [ -f "$LATEST_REDIS_BACKUP" ]; then
        if gzip -t "$LATEST_REDIS_BACKUP" 2>/dev/null && [ -s "$LATEST_REDIS_BACKUP" ]; then
            log "Redis backup validation: PASSED"
        else
            log "Redis backup validation: FAILED"
            ((VALIDATION_ERRORS++))
        fi
    else
        log "Redis backup validation: FAILED - No backup file found"
        ((VALIDATION_ERRORS++))
    fi

    # Validate configuration backup
    local LATEST_CONFIG_BACKUP=$(find "$BACKUP_ROOT/config" -name "*_$DATE.yaml" -type f -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)
    if [ -n "$LATEST_CONFIG_BACKUP" ] && [ -f "$LATEST_CONFIG_BACKUP" ]; then
        # Test YAML syntax
        if python3 -c "import yaml; yaml.safe_load(open('$LATEST_CONFIG_BACKUP'))" 2>/dev/null; then
            log "Configuration backup validation: PASSED"
        else
            log "Configuration backup validation: FAILED - Invalid YAML"
            ((VALIDATION_ERRORS++))
        fi
    else
        log "Configuration backup validation: FAILED - No backup file found"
        ((VALIDATION_ERRORS++))
    fi

    if [ $VALIDATION_ERRORS -eq 0 ]; then
        log "All backup validations: PASSED"
        return 0
    else
        log "Backup validations: FAILED - $VALIDATION_ERRORS errors"
        return 1
    fi
}

# Send backup notification
send_notification() {
    local STATUS="$1"
    local MESSAGE="$2"

    if command -v curl &>/dev/null; then
        # Send to Slack webhook (if configured)
        if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
            curl -X POST "$SLACK_WEBHOOK_URL" \
                -H 'Content-type: application/json' \
                --data "{\"text\":\"Hermes Backup $STATUS: $MESSAGE\"}" \
                2>/dev/null || log "Failed to send Slack notification"
        fi

        # Send to email (if configured)
        if command -v mail &>/dev/null && [ -n "${BACKUP_EMAIL:-}" ]; then
            echo "$MESSAGE" | mail -s "Hermes Backup $STATUS" "$BACKUP_EMAIL" 2>/dev/null || log "Failed to send email notification"
        fi
    fi
}

# Main backup function
main() {
    local START_TIME=$(date +%s)

    log "Starting Hermes AI Assistant backup process"

    # Create backup directories
    create_backup_dirs

    # Run backup procedures
    backup_postgresql
    backup_redis
    backup_k8s_config
    backup_helm_config
    backup_app_config

    # Validate backups
    if validate_backups; then
        # Create full backup (weekly)
        if [ "$(date +%u)" -eq 1 ]; then  # Monday
            create_full_backup
        fi

        local END_TIME=$(date +%s)
        local DURATION=$((END_TIME - START_TIME))

        log "Backup process completed successfully in ${DURATION} seconds"
        send_notification "SUCCESS" "All backups completed successfully in ${DURATION} seconds"
    else
        log "Backup process completed with validation errors"
        send_notification "FAILED" "Backup process completed with validation errors"
        exit 1
    fi
}

# Cleanup function
cleanup() {
    log "Backup process interrupted"
    send_notification "INTERRUPTED" "Backup process was interrupted"
    exit 1
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM

# Parse command line arguments
case "${1:-}" in
    "database")
        backup_postgresql
        ;;
    "redis")
        backup_redis
        ;;
    "config")
        backup_k8s_config
        backup_helm_config
        backup_app_config
        ;;
    "full")
        create_full_backup
        ;;
    "validate")
        validate_backups
        ;;
    *)
        main
        ;;
esac