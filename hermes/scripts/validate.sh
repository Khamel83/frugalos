#!/bin/bash

# Hermes Autonomous AI Assistant - System Validation Script
# This script performs comprehensive validation of the Hermes installation

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/hermes"
SERVICE_USER="hermes"
VALIDATION_LOG="/tmp/hermes_validation.log"

# Validation results
VALIDATION_PASSED=0
VALIDATION_FAILED=0
VALIDATION_WARNINGS=0

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$VALIDATION_LOG"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1" | tee -a "$VALIDATION_LOG"
    ((VALIDATION_PASSED++))
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$VALIDATION_LOG"
    ((VALIDATION_WARNINGS++))
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1" | tee -a "$VALIDATION_LOG"
    ((VALIDATION_FAILED++))
}

log_test() {
    echo -e "${CYAN}[TEST]${NC} $1" | tee -a "$VALIDATION_LOG"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"
    local should_succeed="${3:-true}"

    log_test "$test_name"

    if eval "$test_command" >/dev/null 2>&1; then
        if [ "$should_succeed" = "true" ]; then
            log_success "$test_name"
            return 0
        else
            log_error "$test_name (should have failed)"
            return 1
        fi
    else
        if [ "$should_succeed" = "true" ]; then
            log_error "$test_name"
            return 1
        else
            log_success "$test_name (correctly failed)"
            return 0
        fi
    fi
}

# Validate system requirements
validate_system() {
    log_info "Validating system requirements..."

    # Check OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        run_test "Linux OS" "test '$OSTYPE' = 'linux-gnu'"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        run_test "macOS OS" "test '$OSTYPE' = 'darwin'*"
    else
        log_warning "Unsupported OS: $OSTYPE"
    fi

    # Check Python
    if command_exists python3.11; then
        run_test "Python 3.11 available" "command_exists python3.11"
    elif command_exists python3; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        run_test "Python 3.11+ available" "python3 -c 'import sys; exit(0 if sys.version_info >= (3, 11) else 1)'"
    else
        log_error "Python 3.11+ not found"
    fi

    # Check system resources
    TOTAL_MEM=$(free -m 2>/dev/null | awk 'NR==2{print $2}' || echo "0")
    if [ "$TOTAL_MEM" -gt 4096 ]; then
        run_test "Adequate memory (>4GB)" "test $TOTAL_MEM -gt 4096"
    else
        log_warning "Low memory: ${TOTAL_MEM}MB (recommended: 8GB+)"
    fi

    # Check disk space
    AVAILABLE_SPACE=$(df "$INSTALL_DIR" 2>/dev/null | awk 'NR==2 {print $4}' || echo "0")
    if [ "$AVAILABLE_SPACE" -gt 1048576 ]; then  # 1GB in KB
        run_test "Adequate disk space (>1GB)" "test $AVAILABLE_SPACE -gt 1048576"
    else
        log_error "Insufficient disk space: ${AVAILABLE_SPACE}KB"
    fi
}

# Validate installation directories
validate_directories() {
    log_info "Validating installation directories..."

    local dirs=(
        "$INSTALL_DIR"
        "$INSTALL_DIR/hermes"
        "$INSTALL_DIR/config"
        "$INSTALL_DIR/data"
        "$INSTALL_DIR/cache"
        "$INSTALL_DIR/logs"
        "$INSTALL_DIR/backups"
        "$INSTALL_DIR/scripts"
        "$INSTALL_DIR/deployments"
        "/var/log/hermes"
        "/opt/hermes/backups"
    )

    for dir in "${dirs[@]}"; do
        run_test "Directory exists: $dir" "test -d '$dir'"
        run_test "Directory readable: $dir" "test -r '$dir'"
    done

    # Check ownership
    run_test "Installation directory ownership" "test \"\$(stat -c '%U' '$INSTALL_DIR')\" = '$SERVICE_USER'"
}

# Validate files
validate_files() {
    log_info "Validating installation files..."

    # Core application files
    local files=(
        "$INSTALL_DIR/hermes/app.py"
        "$INSTALL_DIR/hermes/orchestrator.py"
        "$INSTALL_DIR/requirements.txt"
        "$INSTALL_DIR/config/config.yaml"
        "$INSTALL_DIR/.env"
        "$INSTALL_DIR/deployments/production.yaml"
        "$INSTALL_DIR/deployments/Dockerfile.prod"
        "$INSTALL_DIR/deployments/docker-compose.prod.yaml"
        "$INSTALL_DIR/scripts/monitor.sh"
        "/etc/systemd/system/hermes.service"
        "/etc/nginx/sites-available/hermes"
    )

    for file in "${files[@]}"; do
        run_test "File exists: $file" "test -f '$file'"
    done

    # Check file permissions
    run_test "Environment file permissions" "test \"\$(stat -c '%a' '$INSTALL_DIR/.env')\" = '600'"
    run_test "Scripts executable" "test -x '$INSTALL_DIR/scripts/monitor.sh'"
}

# Validate Python environment
validate_python_env() {
    log_info "Validating Python environment..."

    # Check virtual environment
    run_test "Virtual environment exists" "test -d '$INSTALL_DIR/venv'"
    run_test "Python executable in venv" "test -x '$INSTALL_DIR/venv/bin/python'"

    # Test Python imports
    local modules=(
        "hermes.app"
        "hermes.orchestrator"
        "hermes.metalearning.question_generator"
        "hermes.backend_management.health_monitor"
        "hermes.autonomous.scheduler"
    )

    for module in "${modules[@]}"; do
        run_test "Module import: $module" "cd '$INSTALL_DIR' && source venv/bin/activate && python -c 'import $module'"
    done
}

# Validate services
validate_services() {
    log_info "Validating system services..."

    local services=(
        "hermes"
        "redis"
        "postgresql"
        "nginx"
    )

    for service in "${services[@]}"; do
        run_test "Service enabled: $service" "systemctl is-enabled '$service'"
        run_test "Service active: $service" "systemctl is-active '$service'"
    done

    # Check service configuration
    run_test "Hermes service configuration" "grep -q 'WorkingDirectory=$INSTALL_DIR' /etc/systemd/system/hermes.service"
    run_test "Nginx configuration valid" "nginx -t"
}

# Validate database
validate_database() {
    log_info "Validating database connectivity..."

    # Test PostgreSQL
    run_test "PostgreSQL running" "pg_isready -h localhost -p 5432"

    # Test database exists
    run_test "Hermes database exists" "sudo -u postgres psql -lqt | cut -d \\| -f 1 | grep -qw hermes"

    # Test database connection from application
    run_test "Database connection from app" "cd '$INSTALL_DIR' && sudo -u '$SERVICE_USER' bash -c 'source venv/bin/activate && python3 -c \"from hermes.database import get_db_connection; conn = get_db_connection(); conn.close()\"'"

    # Test Redis
    run_test "Redis running" "redis-cli ping"
}

# Validate API endpoints
validate_api() {
    log_info "Validating API endpoints..."

    # Wait a moment for services to be fully ready
    sleep 2

    # Test basic endpoints
    local endpoints=(
        "http://localhost/api/orchestrator/status"
        "http://localhost/health"
    )

    for endpoint in "${endpoints[@]}"; do
        run_test "API endpoint: $endpoint" "curl -s -f '$endpoint'"
    done

    # Test API response format
    run_test "API returns JSON" "curl -s http://localhost/api/orchestrator/status | python -m json.tool >/dev/null"
}

# Validate configuration
validate_configuration() {
    log_info "Validating configuration files..."

    # Test YAML syntax
    run_test "Main config YAML syntax" "python3 -c \"import yaml; yaml.safe_load(open('$INSTALL_DIR/config/config.yaml'))\""

    # Test environment file
    run_test "Environment file has required variables" "grep -q 'HERMES_SECRET_KEY=' '$INSTALL_DIR/.env'"

    # Test configuration loading
    run_test "Configuration loads successfully" "cd '$INSTALL_DIR' && source venv/bin/activate && python3 -c \"from hermes.config import load_config; config = load_config()\""
}

# Validate security
validate_security() {
    log_info "Validating security settings..."

    # Check file permissions
    run_test "Config directory permissions" "test \"\$(stat -c '%a' '$INSTALL_DIR/config')\" = '755'"
    run_test "Logs directory permissions" "test \"\$(stat -c '%a' '/var/log/hermes')\" = '755'"

    # Check for secrets in code (basic check)
    run_test "No hardcoded secrets in config" "! grep -r 'sk-' '$INSTALL_DIR/config/' 2>/dev/null"
    run_test "No API keys in code" "! grep -r 'AIza' '$INSTALL_DIR/hermes/' 2>/dev/null"

    # Check service user restrictions
    run_test "Service user has no shell" "test \"\$(getent passwd '$SERVICE_USER' | cut -d: -f7)\" = '/bin/false'"
}

# Validate performance
validate_performance() {
    log_info "Validating performance metrics..."

    # Test API response time
    local response_time=$(curl -o /dev/null -s -w '%{time_total}' http://localhost/api/orchestrator/status 2>/dev/null || echo "10")
    if (( $(echo "$response_time < 2.0" | bc -l) )); then
        run_test "API response time < 2s" "true"
    else
        log_warning "Slow API response time: ${response_time}s"
    fi

    # Test memory usage
    local memory_usage=$(ps -o pid,ppid,cmd,%mem,%cpu -C python --no-headers | awk '{sum+=$4} END {print sum+0}')
    if (( $(echo "$memory_usage < 50" | bc -l) )); then
        run_test "Memory usage < 50%" "true"
    else
        log_warning "High memory usage: ${memory_usage}%"
    fi

    # Test concurrent requests
    run_test "Concurrent request handling" "for i in {1..5}; do curl -s http://localhost/api/orchestrator/status >/dev/null & done; wait"
}

# Validate monitoring
validate_monitoring() {
    log_info "Validating monitoring setup..."

    # Check log files
    run_test "Application logs accessible" "test -r '/var/log/hermes/'"
    run_test "Systemd logs accessible" "journalctl -u hermes --lines=1 >/dev/null"

    # Check monitoring script
    run_test "Monitoring script executable" "test -x '$INSTALL_DIR/scripts/monitor.sh'"
    run_test "Monitoring cron job exists" "crontab -l 2>/dev/null | grep -q 'monitor.sh'"

    # Check log rotation
    run_test "Log rotation configured" "test -f '/etc/logrotate.d/hermes'"
}

# Run integration tests
run_integration_tests() {
    log_info "Running integration tests..."

    cd "$INSTALL_DIR"

    # Test conversation creation
    run_test "Conversation creation" "source venv/bin/activate && python3 -c \"
import sys
sys.path.insert(0, '.')
from hermes.orchestrator import UnifiedOrchestrator
orchestrator = UnifiedOrchestrator()
conversation_id = orchestrator.start_conversation()
print(f'Conversation created: {conversation_id}')
\""

    # Test meta-learning functionality
    run_test "Meta-learning question generation" "source venv/bin/activate && python3 -c \"
import sys
sys.path.insert(0, '.')
from hermes.metalearning.question_generator import QuestionGenerator
qg = QuestionGenerator()
questions = qg.generate_questions('improve customer service', 1)
print(f'Generated {len(questions)} questions')
\""

    # Test backend management
    run_test "Backend health check" "source venv/bin/activate && python3 -c \"
import sys
sys.path.insert(0, '.')
from hermes.backend_management.health_monitor import HealthMonitor
hm = HealthMonitor()
health = hm.check_all_backends()
print(f'Health check completed')
\""
}

# Generate validation report
generate_report() {
    echo
    echo "🔍 Validation Report"
    echo "===================="
    echo
    echo "Tests Passed: $VALIDATION_PASSED"
    echo "Tests Failed: $VALIDATION_FAILED"
    echo "Warnings: $VALIDATION_WARNINGS"
    echo

    local total_tests=$((VALIDATION_PASSED + VALIDATION_FAILED))
    local success_rate=0
    if [ $total_tests -gt 0 ]; then
        success_rate=$((VALIDATION_PASSED * 100 / total_tests))
    fi

    echo "Success Rate: ${success_rate}%"
    echo

    if [ $VALIDATION_FAILED -eq 0 ]; then
        echo "🎉 All critical tests passed!"
        if [ $VALIDATION_WARNINGS -eq 0 ]; then
            echo "✨ Perfect installation with no warnings!"
        else
            echo "⚠️  Some warnings detected. Review the log above."
        fi
    else
        echo "❌ Some tests failed. Please address the issues above."
        echo
        echo "Common fixes:"
        echo "- Start failed services: sudo systemctl start <service-name>"
        echo "- Check configuration files"
        echo "- Verify API keys in .env file"
        echo "- Review logs: journalctl -u hermes -f"
    fi

    echo
    echo "Full validation log saved to: $VALIDATION_LOG"
}

# Main validation function
main() {
    echo "🔍 Hermes Autonomous AI Assistant - System Validation"
    echo "===================================================="
    echo

    # Initialize log
    echo "Hermes Validation - $(date)" > "$VALIDATION_LOG"
    echo "======================================" >> "$VALIDATION_LOG"

    # Check if running with appropriate privileges
    if [[ $EUID -ne 0 ]]; then
        log_warning "Not running as root. Some tests may fail."
    fi

    # Run validation tests
    validate_system
    validate_directories
    validate_files
    validate_python_env
    validate_services
    validate_database
    validate_api
    validate_configuration
    validate_security
    validate_performance
    validate_monitoring

    # Run integration tests (if application is running)
    if systemctl is-active --quiet hermes 2>/dev/null; then
        run_integration_tests
    else
        log_warning "Skipping integration tests (Hermes service not running)"
    fi

    # Generate report
    generate_report

    # Exit with appropriate code
    if [ $VALIDATION_FAILED -eq 0 ]; then
        exit 0
    else
        exit 1
    fi
}

# Handle script interruption
trap 'log_error "Validation interrupted"; exit 1' INT

# Run main function
main "$@"