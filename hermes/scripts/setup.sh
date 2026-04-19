#!/bin/bash

# Hermes Autonomous AI Assistant - Setup Script
# This script sets up the complete Hermes environment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# System requirements check
check_system_requirements() {
    log_info "Checking system requirements..."

    # Check Python version
    if command_exists python3; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if [[ $(echo "$PYTHON_VERSION >= 3.11" | bc -l) -eq 1 ]]; then
            log_success "Python $PYTHON_VERSION found"
        else
            log_error "Python 3.11+ required. Found: $PYTHON_VERSION"
            exit 1
        fi
    else
        log_error "Python 3 is not installed"
        exit 1
    fi

    # Check for pip
    if command_exists pip3; then
        log_success "pip3 found"
    else
        log_error "pip3 is not installed"
        exit 1
    fi

    # Check for Docker (optional)
    if command_exists docker; then
        log_success "Docker found"
        DOCKER_AVAILABLE=true
    else
        log_warning "Docker not found. Docker deployment will not be available"
        DOCKER_AVAILABLE=false
    fi

    # Check for Docker Compose (optional)
    if command_exists docker-compose; then
        log_success "Docker Compose found"
        COMPOSE_AVAILABLE=true
    else
        log_warning "Docker Compose not found. Docker deployment will not be available"
        COMPOSE_AVAILABLE=false
    fi
}

# Create virtual environment
create_virtual_environment() {
    log_info "Creating virtual environment..."

    if [ -d "venv" ]; then
        log_warning "Virtual environment already exists. Removing it..."
        rm -rf venv
    fi

    python3 -m venv venv
    source venv/bin/activate

    # Upgrade pip
    pip install --upgrade pip

    log_success "Virtual environment created and activated"
}

# Install dependencies
install_dependencies() {
    log_info "Installing Python dependencies..."

    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        log_success "Dependencies installed"
    else
        log_error "requirements.txt not found"
        exit 1
    fi
}

# Setup configuration files
setup_configuration() {
    log_info "Setting up configuration files..."

    # Create directories
    mkdir -p config data logs cache backups

    # Copy example configuration if it doesn't exist
    if [ ! -f "config/config.yaml" ]; then
        if [ -f "config/config.yaml.example" ]; then
            cp config/config.yaml.example config/config.yaml
            log_success "Default configuration created"
        else
            log_warning "No example configuration found"
        fi
    else
        log_warning "Configuration file already exists"
    fi

    # Create .env file if it doesn't exist
    if [ ! -f ".env" ]; then
        cat > .env << EOF
# Hermes Environment Configuration
HERMES_SECRET_KEY=$(openssl rand -hex 32)
HERMES_ENV=development

# Database Configuration
DATABASE_URL=sqlite:///data/hermes.db
REDIS_URL=redis://localhost:6379/0

# Backend API Keys (replace with your actual keys)
OPENAI_API_KEY=your-openai-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
GOOGLE_API_KEY=your-google-key-here

# Email Configuration (for alerts)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Monitoring Passwords
GRAFANA_PASSWORD=admin123
POSTGRES_PASSWORD=postgres123
EOF
        log_success "Environment file created"
    else
        log_warning ".env file already exists"
    fi
}

# Initialize database
initialize_database() {
    log_info "Initializing database..."

    # Create data directory if it doesn't exist
    mkdir -p data

    # Initialize using Python script
    python3 -c "
import sys
sys.path.insert(0, '.')
from hermes.database import init_database
try:
    init_database()
    print('Database initialized successfully')
except Exception as e:
    print(f'Database initialization warning: {e}')
"

    log_success "Database initialization completed"
}

# Run tests to verify installation
run_tests() {
    log_info "Running basic tests to verify installation..."

    # Test basic imports
    python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from hermes.orchestrator import UnifiedOrchestrator
    from hermes.metalearning.question_generator import QuestionGenerator
    from hermes.backend_management.health_monitor import HealthMonitor
    print('✓ Core modules imported successfully')
except ImportError as e:
    print(f'✗ Import error: {e}')
    sys.exit(1)
"

    # Test configuration loading
    python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from hermes.config import load_config
    config = load_config()
    print('✓ Configuration loaded successfully')
except Exception as e:
    print(f'✗ Configuration error: {e}')
    sys.exit(1)
"

    log_success "Basic tests passed"
}

# Setup Docker deployment (if available)
setup_docker() {
    if [ "$DOCKER_AVAILABLE" = true ] && [ "$COMPOSE_AVAILABLE" = true ]; then
        log_info "Setting up Docker deployment..."

        # Create Docker volumes directory
        mkdir -p docker-data/{redis,postgres,elasticsearch,grafana,prometheus}

        # Set permissions for Docker volumes
        chmod 755 docker-data

        log_success "Docker setup completed"
        log_info "To deploy with Docker, run: docker-compose -f deployments/docker-compose.prod.yaml up -d"
    else
        log_info "Skipping Docker setup (Docker/Docker Compose not available)"
    fi
}

# Create startup scripts
create_startup_scripts() {
    log_info "Creating startup scripts..."

    # Development startup script
    cat > start_dev.sh << 'EOF'
#!/bin/bash
# Development startup script

# Activate virtual environment
source venv/bin/activate

# Set environment
export HERMES_ENV=development

# Start the application
python3 -m hermes.app
EOF
    chmod +x start_dev.sh

    # Production startup script
    cat > start_prod.sh << 'EOF'
#!/bin/bash
# Production startup script

# Activate virtual environment
source venv/bin/activate

# Set environment
export HERMES_ENV=production

# Start with Gunicorn
gunicorn --bind 0.0.0.0:8080 --workers 4 --timeout 120 hermes.app:app
EOF
    chmod +x start_prod.sh

    log_success "Startup scripts created"
}

# Create service files (systemd)
create_service_files() {
    log_info "Creating systemd service file..."

    cat > hermes.service << EOF
[Unit]
Description=Hermes Autonomous AI Assistant
After=network.target

[Service]
Type=simple
User=hermes
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
Environment=HERMES_ENV=production
ExecStart=$(pwd)/venv/bin/gunicorn --bind 0.0.0.0:8080 --workers 4 --timeout 120 hermes.app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    log_success "Systemd service file created"
    log_info "To install as system service:"
    log_info "  sudo cp hermes.service /etc/systemd/system/"
    log_info "  sudo systemctl daemon-reload"
    log_info "  sudo systemctl enable hermes"
    log_info "  sudo systemctl start hermes"
}

# Final verification
final_verification() {
    log_info "Performing final verification..."

    # Check if main application can start
    python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from hermes.app import app
    print('✓ Application can be imported')
except Exception as e:
    print(f'✗ Application error: {e}')
    sys.exit(1)
"

    # Check configuration
    if [ -f "config/config.yaml" ]; then
        log_success "✓ Configuration file exists"
    else
        log_warning "Configuration file missing"
    fi

    # Check data directory
    if [ -d "data" ]; then
        log_success "✓ Data directory exists"
    else
        log_warning "Data directory missing"
    fi

    log_success "Final verification completed"
}

# Print next steps
print_next_steps() {
    log_success "Hermes setup completed successfully!"
    echo
    echo "🚀 Next Steps:"
    echo
    echo "1. Configure your environment:"
    echo "   - Edit .env file with your API keys"
    echo "   - Update config/config.yaml as needed"
    echo
    echo "2. Start the application:"
    echo "   Development: ./start_dev.sh"
    echo "   Production:  ./start_prod.sh"
    echo "   Docker:      docker-compose -f deployments/docker-compose.prod.yaml up -d"
    echo
    echo "3. Access the application:"
    echo "   - Web Interface: http://localhost:8080"
    echo "   - Dashboard: http://localhost:8080/dashboard"
    echo "   - API Status: http://localhost:8080/api/orchestrator/status"
    echo
    echo "4. Monitor the system:"
    echo "   - Grafana: http://localhost:3000 (admin/admin123)"
    echo "   - Prometheus: http://localhost:9090"
    echo
    echo "5. For more information, see README.md"
    echo
    log_info "Thank you for installing Hermes Autonomous AI Assistant!"
}

# Main execution
main() {
    echo "🤖 Hermes Autonomous AI Assistant - Setup Script"
    echo "=================================================="
    echo

    # Check if we're in the right directory
    if [ ! -f "hermes/app.py" ]; then
        log_error "Please run this script from the Hermes root directory"
        exit 1
    fi

    # Execute setup steps
    check_system_requirements
    create_virtual_environment
    install_dependencies
    setup_configuration
    initialize_database
    run_tests
    setup_docker
    create_startup_scripts
    create_service_files
    final_verification
    print_next_steps
}

# Handle script interruption
trap 'log_error "Setup interrupted"; exit 1' INT

# Run main function
main "$@"