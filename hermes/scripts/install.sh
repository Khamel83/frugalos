#!/bin/bash

# Hermes Autonomous AI Assistant - Production Installation Script
# This script performs a complete production installation

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
BACKUP_DIR="/opt/hermes/backups"
LOG_DIR="/var/log/hermes"

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

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Check system requirements
check_system() {
    log_step "Checking system requirements..."

    # Check OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        log_success "Linux detected"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        log_success "macOS detected"
    else
        log_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi

    # Check Python 3.11+
    if command_exists python3.11; then
        PYTHON_CMD="python3.11"
    elif command_exists python3; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if [[ $(echo "$PYTHON_VERSION >= 3.11" | bc -l 2>/dev/null || echo "0") -eq 1 ]]; then
            PYTHON_CMD="python3"
        else
            log_error "Python 3.11+ required. Found: $PYTHON_VERSION"
            exit 1
        fi
    else
        log_error "Python 3.11+ not found"
        exit 1
    fi

    log_success "Using $PYTHON_CMD"

    # Check available disk space (need at least 2GB)
    AVAILABLE_SPACE=$(df / | awk 'NR==2 {print $4}')
    if [[ $AVAILABLE_SPACE -lt 2097152 ]]; then  # 2GB in KB
        log_error "Insufficient disk space. At least 2GB required"
        exit 1
    fi

    log_success "System requirements check passed"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install system dependencies
install_system_deps() {
    log_step "Installing system dependencies..."

    if [[ "$OS" == "linux" ]]; then
        if command_exists apt-get; then
            # Ubuntu/Debian
            apt-get update
            apt-get install -y \
                python3.11 \
                python3.11-venv \
                python3.11-dev \
                python3-pip \
                build-essential \
                curl \
                wget \
                git \
                sqlite3 \
                nginx \
                redis-server \
                postgresql \
                postgresql-contrib \
                supervisor
        elif command_exists yum; then
            # CentOS/RHEL/Fedora
            yum update -y
            yum install -y \
                python3.11 \
                python3.11-devel \
                python3-pip \
                gcc \
                gcc-c++ \
                make \
                curl \
                wget \
                git \
                sqlite \
                nginx \
                redis \
                postgresql-server \
                postgresql-contrib \
                supervisor
        else
            log_error "Unsupported package manager. Please install dependencies manually"
            exit 1
        fi
    elif [[ "$OS" == "macos" ]]; then
        if command_exists brew; then
            brew install python@3.11 sqlite redis nginx postgresql supervisor
        else
            log_error "Homebrew not found. Please install Homebrew first"
            exit 1
        fi
    fi

    log_success "System dependencies installed"
}

# Create service user
create_service_user() {
    log_step "Creating service user..."

    if ! id "$SERVICE_USER" &>/dev/null; then
        useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
        log_success "Service user '$SERVICE_USER' created"
    else
        log_warning "Service user '$SERVICE_USER' already exists"
    fi
}

# Create directories
create_directories() {
    log_step "Creating directory structure..."

    # Main installation directory
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/config"
    mkdir -p "$INSTALL_DIR/data"
    mkdir -p "$INSTALL_DIR/cache"
    mkdir -p "$INSTALL_DIR/logs"
    mkdir -p "$INSTALL_DIR/backups"
    mkdir -p "$INSTALL_DIR/scripts"
    mkdir -p "$INSTALL_DIR/deployments"

    # System directories
    mkdir -p "$LOG_DIR"
    mkdir -p "$BACKUP_DIR"
    mkdir -p "/etc/hermes"

    # Set permissions
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$LOG_DIR"
    chown -R "$SERVICE_USER:$SERVICE_USER" "$BACKUP_DIR"
    chmod 755 "$INSTALL_DIR"
    chmod 755 "$LOG_DIR"
    chmod 755 "$BACKUP_DIR"

    log_success "Directory structure created"
}

# Copy application files
copy_application() {
    log_step "Installing application files..."

    # Get current directory (where the script is located)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

    # Copy application files
    cp -r "$SCRIPT_DIR/hermes" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/config" "$INSTALL_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/deployments" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/scripts" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/README.md" "$INSTALL_DIR/" 2>/dev/null || true

    # Copy configuration templates
    if [ -f "$SCRIPT_DIR/config/config.yaml.example" ]; then
        cp "$SCRIPT_DIR/config/config.yaml.example" "$INSTALL_DIR/config/config.yaml"
    fi

    # Set permissions
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    find "$INSTALL_DIR" -name "*.py" -exec chmod 644 {} \;
    find "$INSTALL_DIR" -name "*.sh" -exec chmod 755 {} \;

    log_success "Application files copied"
}

# Setup Python environment
setup_python_env() {
    log_step "Setting up Python environment..."

    cd "$INSTALL_DIR"

    # Create virtual environment
    sudo -u "$SERVICE_USER" "$PYTHON_CMD" -m venv venv

    # Activate virtual environment and install dependencies
    sudo -u "$SERVICE_USER" bash -c "
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
    "

    log_success "Python environment setup completed"
}

# Setup database
setup_database() {
    log_step "Setting up database..."

    # Initialize PostgreSQL if needed
    if [[ "$OS" == "linux" ]]; then
        if command_exists postgresql-setup; then
            postgresql-setup initdb
        fi
        systemctl enable postgresql
        systemctl start postgresql
    elif [[ "$OS" == "macos" ]]; then
        brew services start postgresql
    fi

    # Create database and user
    sudo -u postgres psql -c "CREATE USER hermes WITH PASSWORD 'hermes_db_password';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE hermes OWNER hermes;" 2>/dev/null || true
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE hermes TO hermes;" 2>/dev/null || true

    # Initialize application database
    sudo -u "$SERVICE_USER" bash -c "
        cd '$INSTALL_DIR'
        source venv/bin/activate
        python3 -c \"
import sys
sys.path.insert(0, '.')
from hermes.database import init_database
try:
    init_database()
    print('Database initialized successfully')
except Exception as e:
    print(f'Database initialization warning: {e}')
\"
    "

    log_success "Database setup completed"
}

# Setup Redis
setup_redis() {
    log_step "Setting up Redis..."

    if [[ "$OS" == "linux" ]]; then
        systemctl enable redis
        systemctl start redis
    elif [[ "$OS" == "macos" ]]; then
        brew services start redis
    fi

    # Test Redis connection
    if redis-cli ping >/dev/null 2>&1; then
        log_success "Redis is running"
    else
        log_warning "Redis may not be running properly"
    fi
}

# Setup configuration
setup_configuration() {
    log_step "Setting up production configuration..."

    # Create production environment file
    cat > "$INSTALL_DIR/.env" << EOF
# Hermes Production Environment
HERMES_SECRET_KEY=$(openssl rand -hex 32)
HERMES_ENV=production

# Database Configuration
DATABASE_URL=postgresql://hermes:hermes_db_password@localhost:5432/hermes
REDIS_URL=redis://localhost:6379/0

# Backend API Keys (REPLACE WITH ACTUAL KEYS)
OPENAI_API_KEY=your-openai-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
GOOGLE_API_KEY=your-google-key-here

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=hermes@$(hostname -f)

# Monitoring Configuration
GRAFANA_PASSWORD=$(openssl rand -base64 12)
POSTGRES_PASSWORD=hermes_db_password

# Paths
DATA_DIR=$INSTALL_DIR/data
CACHE_DIR=$INSTALL_DIR/cache
LOG_DIR=$LOG_DIR
BACKUP_DIR=$BACKUP_DIR
EOF

    # Copy production configuration
    if [ -f "$INSTALL_DIR/deployments/production.yaml" ]; then
        cp "$INSTALL_DIR/deployments/production.yaml" "$INSTALL_DIR/config/production.yaml"
    fi

    # Set permissions
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"

    log_success "Production configuration setup completed"
}

# Setup systemd service
setup_systemd_service() {
    log_step "Setting up systemd service..."

    cat > "/etc/systemd/system/hermes.service" << EOF
[Unit]
Description=Hermes Autonomous AI Assistant
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin
Environment=HERMES_ENV=production
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/gunicorn --bind 127.0.0.1:8080 --workers 4 --timeout 120 --keepalive 30 --max-requests 1000 --max-requests-jitter 50 --preload hermes.app:app
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hermes

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$INSTALL_DIR $LOG_DIR $BACKUP_DIR

[Install]
WantedBy=multi-user.target
EOF

    # Setup log rotation
    cat > "/etc/logrotate.d/hermes" << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 90
    compress
    delaycompress
    notifempty
    create 0644 $SERVICE_USER $SERVICE_USER
    postrotate
        systemctl reload hermes || true
    endscript
}
EOF

    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable hermes

    log_success "Systemd service setup completed"
}

# Setup Nginx reverse proxy
setup_nginx() {
    log_step "Setting up Nginx reverse proxy..."

    cat > "/etc/nginx/sites-available/hermes" << EOF
# Hermes AI Assistant Nginx Configuration
server {
    listen 80;
    server_name _;  # Replace with your domain

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy strict-origin-when-cross-origin;

    # Rate limiting
    limit_req_zone \$binary_remote_addr zone=hermes_limit:10m rate=10r/s;
    limit_req zone=hermes_limit burst=20 nodelay;

    # Main application
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # WebSocket support (if needed)
    location /ws {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Static files (if any)
    location /static/ {
        alias $INSTALL_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint
    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:8080/api/orchestrator/status;
    }
}
EOF

    # Enable site
    if [ -d "/etc/nginx/sites-enabled" ]; then
        ln -sf "/etc/nginx/sites-available/hermes" "/etc/nginx/sites-enabled/"
        rm -f "/etc/nginx/sites-enabled/default" 2>/dev/null || true
    fi

    # Test Nginx configuration
    nginx -t

    log_success "Nginx configuration setup completed"
}

# Setup monitoring
setup_monitoring() {
    log_step "Setting up basic monitoring..."

    # Create monitoring script
    cat > "$INSTALL_DIR/scripts/monitor.sh" << 'EOF'
#!/bin/bash

# Basic monitoring script for Hermes
INSTALL_DIR="/opt/hermes"
LOG_FILE="/var/log/hermes/monitoring.log"

# Check if Hermes service is running
if ! systemctl is-active --quiet hermes; then
    echo "$(date): Hermes service is not running" >> $LOG_FILE
    systemctl restart hermes
fi

# Check disk space
DISK_USAGE=$(df $INSTALL_DIR | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "$(date): Disk usage is ${DISK_USAGE}%" >> $LOG_FILE
fi

# Check memory usage
MEM_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ $MEM_USAGE -gt 90 ]; then
    echo "$(date): Memory usage is ${MEM_USAGE}%" >> $LOG_FILE
fi

# Check Redis
if ! redis-cli ping >/dev/null 2>&1; then
    echo "$(date): Redis is not responding" >> $LOG_FILE
    systemctl restart redis
fi
EOF

    chmod +x "$INSTALL_DIR/scripts/monitor.sh"
    chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/scripts/monitor.sh"

    # Add to crontab
    (crontab -l 2>/dev/null; echo "*/5 * * * * $INSTALL_DIR/scripts/monitor.sh") | crontab -

    log_success "Basic monitoring setup completed"
}

# Start services
start_services() {
    log_step "Starting services..."

    # Start Redis
    systemctl restart redis

    # Start PostgreSQL
    systemctl restart postgresql

    # Start Nginx
    systemctl restart nginx

    # Start Hermes
    systemctl restart hermes

    # Wait a moment for services to start
    sleep 5

    # Check if services are running
    if systemctl is-active --quiet hermes; then
        log_success "Hermes service is running"
    else
        log_error "Hermes service failed to start"
        systemctl status hermes
        exit 1
    fi

    if systemctl is-active --quiet nginx; then
        log_success "Nginx is running"
    else
        log_warning "Nginx is not running"
    fi

    log_success "All services started"
}

# Final verification
verify_installation() {
    log_step "Verifying installation..."

    # Check service status
    if systemctl is-active --quiet hermes; then
        log_success "✓ Hermes service is running"
    else
        log_error "✗ Hermes service is not running"
        return 1
    fi

    # Test API endpoint
    if curl -s http://localhost/api/orchestrator/status >/dev/null 2>&1; then
        log_success "✓ API is responding"
    else
        log_warning "✗ API is not responding (may need configuration)"
    fi

    # Check database connection
    if sudo -u "$SERVICE_USER" bash -c "cd '$INSTALL_DIR' && source venv/bin/activate && python3 -c 'import sqlite3; sqlite3.connect(\"data/hermes.db\")'" 2>/dev/null; then
        log_success "✓ Database is accessible"
    else
        log_warning "✗ Database connection issue"
    fi

    log_success "Installation verification completed"
}

# Print completion message
print_completion() {
    log_success "Hermes installation completed successfully!"
    echo
    echo "🎉 Installation Summary:"
    echo
    echo "Installation Directory: $INSTALL_DIR"
    echo "Service User: $SERVICE_USER"
    echo "Log Directory: $LOG_DIR"
    echo "Backup Directory: $BACKUP_DIR"
    echo
    echo "🚀 Next Steps:"
    echo
    echo "1. Configure API Keys:"
    echo "   Edit $INSTALL_DIR/.env"
    echo "   Add your OpenAI, Anthropic, and Google API keys"
    echo
    echo "2. Configure Domain (optional):"
    echo "   Edit /etc/nginx/sites-available/hermes"
    echo "   Replace 'server_name _;' with your domain"
    echo
    echo "3. Access the Application:"
    echo "   http://$(hostname -I | awk '{print $1}')"
    echo "   http://localhost"
    echo
    echo "4. Service Management:"
    echo "   Status: systemctl status hermes"
    echo "   Start:  systemctl start hermes"
    echo "   Stop:   systemctl stop hermes"
    echo "   Restart: systemctl restart hermes"
    echo "   Logs:   journalctl -u hermes -f"
    echo
    echo "5. Configuration:"
    echo "   Main Config: $INSTALL_DIR/config/config.yaml"
    echo "   Production Config: $INSTALL_DIR/config/production.yaml"
    echo "   Environment: $INSTALL_DIR/.env"
    echo
    echo "📊 Monitoring:"
    echo "   System Logs: $LOG_DIR/"
    echo "   Service Logs: journalctl -u hermes"
    echo "   Monitoring Script: $INSTALL_DIR/scripts/monitor.sh"
    echo
    log_info "Thank you for installing Hermes Autonomous AI Assistant!"
    echo
    echo "⚠️  Important:"
    echo "- Remember to configure your API keys in .env"
    echo "- Set up proper SSL certificates for production use"
    echo "- Configure firewall rules as needed"
    echo "- Set up regular backups"
}

# Main execution
main() {
    echo "🤖 Hermes Autonomous AI Assistant - Production Installation"
    echo "=========================================================="
    echo

    # Check root privileges
    check_root

    # Check system
    check_system

    # Installation steps
    install_system_deps
    create_service_user
    create_directories
    copy_application
    setup_python_env
    setup_database
    setup_redis
    setup_configuration
    setup_systemd_service
    setup_nginx
    setup_monitoring
    start_services
    verify_installation
    print_completion
}

# Handle script interruption
trap 'log_error "Installation interrupted"; exit 1' INT

# Run main function
main "$@"