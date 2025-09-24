#!/bin/bash

#═══════════════════════════════════════════════
#   SharewareZ Linux Auto-Installer v1.0
#   Automated installation script for Linux systems
#   Compatible with bash, zsh, and other POSIX shells
#═══════════════════════════════════════════════

# Use bash for advanced features but detect shell for compatibility
if [ -n "${ZSH_VERSION:-}" ]; then
    # Running in zsh
    setopt SH_WORD_SPLIT  # Make zsh behave more like bash for word splitting
    setopt BASH_REMATCH   # Enable bash-style regex matching
elif [ -n "${BASH_VERSION:-}" ]; then
    # Running in bash
    set -euo pipefail  # Exit on error, undefined vars, pipe failures
else
    # Fallback for other POSIX shells
    set -eu
fi

# Colors and formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Global variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/install.log"
DISTRO=""
PACKAGE_MANAGER=""
DB_PASSWORD=""
SECRET_KEY=""
GAMES_DIR=""
FORCE_INSTALL=false
DEV_MODE=false
SKIP_DB=false
CUSTOM_PORT="5006"

# Cleanup function
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo -e "\n${RED}✗ Installation failed!${NC}"
        echo -e "${YELLOW}Check the log file: $LOG_FILE${NC}"
    fi
}
trap cleanup EXIT

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1" >> "$LOG_FILE"
}

# Print functions
print_header() {
    clear
    echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
    echo -e "${WHITE}    SharewareZ Linux Auto-Installer v1.0${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
    echo
}

print_step() {
    echo -e "${BLUE}[→]${NC} $1"
    log "STEP: $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    log "SUCCESS: $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
    log "ERROR: $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
    log "WARNING: $1"
}

print_info() {
    echo -e "${CYAN}[ℹ]${NC} $1"
    log "INFO: $1"
}

# Check if running as root (bad) or with sudo access (good)
check_permissions() {
    # Check if running as root - use $USER and id as EUID may not be available in all shells
    if [ "$(id -u)" -eq 0 ]; then
        print_error "This script should not be run as root!"
        print_info "Please run as a regular user with sudo access:"
        print_info "  ./install-linux.sh"
        exit 1
    fi

    if ! sudo -n true 2>/dev/null; then
        print_error "This script requires sudo access"
        print_info "Please ensure your user can run sudo commands"
        exit 1
    fi

    print_success "Running with appropriate permissions"
}

# Generate secure random password
generate_secure_password() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c "import secrets; print(secrets.token_urlsafe(25))"
    else
        # Fallback to /dev/urandom
        cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 25 | head -n 1
    fi
}

# Generate secure secret key
generate_secret_key() {
    if command -v python3 >/dev/null 2>&1; then
        python3 -c "import secrets; print(secrets.token_urlsafe(32))"
    else
        # Fallback method
        openssl rand -base64 32 | tr -d "=+/"
    fi
}

# Parse command line arguments (POSIX compatible)
parse_arguments() {
    while [ $# -gt 0 ]; do
        case $1 in
            --force)
                FORCE_INSTALL=true
                shift
                ;;
            --dev)
                DEV_MODE=true
                shift
                ;;
            --no-db)
                SKIP_DB=true
                shift
                ;;
            --games-dir)
                if [ $# -lt 2 ]; then
                    print_error "--games-dir requires an argument"
                    exit 1
                fi
                GAMES_DIR="$2"
                shift 2
                ;;
            --port)
                if [ $# -lt 2 ]; then
                    print_error "--port requires an argument"
                    exit 1
                fi
                CUSTOM_PORT="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Show help information
show_help() {
    echo "SharewareZ Linux Auto-Installer"
    echo
    echo "USAGE:"
    echo "  ./install-linux.sh [OPTIONS]"
    echo
    echo "OPTIONS:"
    echo "  --force           Override existing installation"
    echo "  --dev            Install development dependencies"
    echo "  --no-db          Skip database setup (use existing)"
    echo "  --games-dir PATH Specify games directory"
    echo "  --port PORT      Custom port (default: 5006)"
    echo "  --help, -h       Show this help message"
    echo
    echo "EXAMPLES:"
    echo "  ./install-linux.sh"
    echo "  ./install-linux.sh --games-dir /home/user/games"
    echo "  ./install-linux.sh --force --dev"
}

# Backup existing configuration files
backup_existing_config() {
    if [ -f "$SCRIPT_DIR/.env" ] && [ "$FORCE_INSTALL" != true ]; then
        print_step "Backing up existing configuration..."
        cp "$SCRIPT_DIR/.env" "$SCRIPT_DIR/.env.backup.$(date +%Y%m%d-%H%M%S)"
        print_success "Configuration backed up"
    fi
}

# Detect Linux distribution
detect_distribution() {
    print_step "Detecting Linux distribution..."

    if [ -f /etc/os-release ]; then
        source /etc/os-release
        DISTRO="$ID"

        case "$DISTRO" in
            ubuntu|debian)
                PACKAGE_MANAGER="apt"
                print_success "Detected: $PRETTY_NAME (using apt)"
                ;;
            fedora|rhel|centos|rocky|almalinux)
                if command -v dnf >/dev/null 2>&1; then
                    PACKAGE_MANAGER="dnf"
                else
                    PACKAGE_MANAGER="yum"
                fi
                print_success "Detected: $PRETTY_NAME (using $PACKAGE_MANAGER)"
                ;;
            arch|manjaro)
                PACKAGE_MANAGER="pacman"
                print_success "Detected: $PRETTY_NAME (using pacman)"
                ;;
            opensuse*|sles)
                PACKAGE_MANAGER="zypper"
                print_success "Detected: $PRETTY_NAME (using zypper)"
                ;;
            *)
                print_warning "Unsupported distribution: $PRETTY_NAME"
                print_info "This script supports Ubuntu, Debian, Fedora, RHEL, CentOS, Arch, and openSUSE"
                print_info "You may need to install prerequisites manually"
                return 1
                ;;
        esac
    else
        print_error "Cannot detect Linux distribution"
        print_info "Please install prerequisites manually and run the application setup"
        return 1
    fi
}

# Install packages based on distribution
install_package() {
    local packages="$1"

    case "$PACKAGE_MANAGER" in
        apt)
            sudo apt update -qq
            sudo apt install -y $packages
            ;;
        dnf)
            sudo dnf install -y $packages
            ;;
        yum)
            sudo yum install -y $packages
            ;;
        pacman)
            sudo pacman -Sy --noconfirm $packages
            ;;
        zypper)
            sudo zypper install -y $packages
            ;;
        *)
            print_error "Unsupported package manager: $PACKAGE_MANAGER"
            return 1
            ;;
    esac
}

# Check and install prerequisites
install_prerequisites() {
    print_step "Installing prerequisites..."

    # Update package lists
    case "$PACKAGE_MANAGER" in
        apt)
            print_info "Updating package lists..."
            sudo apt update -qq
            ;;
    esac

    # Define packages per distribution
    local python_packages=""
    local git_package="git"
    local postgresql_packages=""
    local build_packages=""

    case "$PACKAGE_MANAGER" in
        apt)
            python_packages="python3 python3-pip python3-venv python3-dev"
            postgresql_packages="postgresql postgresql-contrib"
            build_packages="build-essential libpq-dev"
            ;;
        dnf|yum)
            python_packages="python3 python3-pip python3-devel"
            postgresql_packages="postgresql postgresql-server postgresql-contrib"
            build_packages="gcc gcc-c++ make postgresql-devel"
            ;;
        pacman)
            python_packages="python python-pip python-virtualenv"
            postgresql_packages="postgresql"
            build_packages="base-devel postgresql-libs"
            ;;
        zypper)
            python_packages="python3 python3-pip python3-devel"
            postgresql_packages="postgresql postgresql-server postgresql-contrib"
            build_packages="gcc gcc-c++ make postgresql-devel"
            ;;
    esac

    # Install Python and pip
    print_info "Installing Python and pip..."
    install_package "$python_packages"

    # Install git
    print_info "Installing Git..."
    install_package "$git_package"

    # Install build dependencies
    print_info "Installing build dependencies..."
    install_package "$build_packages"

    # Install PostgreSQL
    if [ "$SKIP_DB" != true ]; then
        print_info "Installing PostgreSQL..."
        install_package "$postgresql_packages"
    fi

    # Verify installations
    print_step "Verifying installations..."

    if ! command -v python3 >/dev/null 2>&1; then
        print_error "Python3 installation failed"
        return 1
    fi
    print_success "Python3 installed: $(python3 --version)"

    if ! python3 -m pip --version >/dev/null 2>&1; then
        print_error "pip installation failed"
        return 1
    fi
    print_success "pip installed: $(python3 -m pip --version | cut -d' ' -f2)"

    if ! command -v git >/dev/null 2>&1; then
        print_error "Git installation failed"
        return 1
    fi
    print_success "Git installed: $(git --version | cut -d' ' -f3)"

    if [ "$SKIP_DB" != true ]; then
        if ! command -v psql >/dev/null 2>&1; then
            print_error "PostgreSQL installation failed"
            return 1
        fi
        print_success "PostgreSQL installed"
    fi
}

# Get PostgreSQL configuration path based on distribution
get_pg_config_path() {
    case "$PACKAGE_MANAGER" in
        apt)
            # Find the PostgreSQL version directory
            if [ -d "/etc/postgresql" ]; then
                PG_VERSION=$(ls /etc/postgresql/ 2>/dev/null | head -1)
                if [ -n "$PG_VERSION" ]; then
                    echo "/etc/postgresql/$PG_VERSION/main"
                    return 0
                fi
            fi
            echo "/etc/postgresql"
            ;;
        dnf|yum)
            echo "/var/lib/pgsql/data"
            ;;
        pacman)
            echo "/var/lib/postgres/data"
            ;;
        zypper)
            echo "/var/lib/pgsql/data"
            ;;
        *)
            # Try common locations
            for path in "/etc/postgresql" "/var/lib/pgsql/data" "/var/lib/postgres/data"; do
                if [ -d "$path" ]; then
                    echo "$path"
                    return 0
                fi
            done
            echo "/etc/postgresql"
            ;;
    esac
}

# Configure PostgreSQL authentication for password-based access
configure_postgresql_auth() {
    print_step "Configuring PostgreSQL authentication..."

    # Get PostgreSQL config path
    PG_CONFIG_PATH=$(get_pg_config_path)
    PG_HBA_CONF="$PG_CONFIG_PATH/pg_hba.conf"

    # Check if pg_hba.conf exists
    if [ ! -f "$PG_HBA_CONF" ]; then
        print_warning "PostgreSQL pg_hba.conf not found at $PG_HBA_CONF"
        print_info "Skipping authentication configuration"
        return 0
    fi

    # Backup original configuration
    sudo cp "$PG_HBA_CONF" "$PG_HBA_CONF.backup.$(date +%Y%m%d-%H%M%S)" 2>/dev/null || {
        print_warning "Could not backup pg_hba.conf (permissions issue)"
        print_info "Continuing without modifying authentication..."
        return 0
    }

    # Add password authentication for sharewarez database
    print_info "Adding password authentication for sharewarez database..."

    # Add our rules at the top (before default rules)
    {
        echo "# Added by SharewareZ installer - $(date)"
        echo "local   sharewarez   sharewarezuser   md5"
        echo "host    sharewarez   sharewarezuser   127.0.0.1/32   md5"
        echo "host    sharewarez   sharewarezuser   ::1/128        md5"
        echo ""
    } | sudo tee "$PG_HBA_CONF.new" >/dev/null

    # Append original content
    sudo cat "$PG_HBA_CONF" | sudo tee -a "$PG_HBA_CONF.new" >/dev/null

    # Replace original with new configuration
    sudo mv "$PG_HBA_CONF.new" "$PG_HBA_CONF"

    # Reload PostgreSQL configuration
    if sudo systemctl reload postgresql 2>/dev/null; then
        print_success "PostgreSQL authentication configured and reloaded"
    elif sudo service postgresql reload 2>/dev/null; then
        print_success "PostgreSQL authentication configured and reloaded"
    else
        print_warning "Could not reload PostgreSQL - changes will take effect on next restart"
    fi
}

# Test database connection with multiple methods
test_database_connection() {
    local max_attempts=3
    local attempt=1

    print_info "Testing database connection..."

    while [ $attempt -le $max_attempts ]; do
        print_info "Connection attempt $attempt/$max_attempts"

        # Method 1: TCP/IP with localhost
        if PGPASSWORD="$DB_PASSWORD" psql -h localhost -U sharewarezuser -d sharewarez -c "SELECT 1;" >/dev/null 2>&1; then
            print_success "Database connection test successful (localhost TCP/IP)"
            return 0
        fi

        # Method 2: TCP/IP with 127.0.0.1
        if PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U sharewarezuser -d sharewarez -c "SELECT 1;" >/dev/null 2>&1; then
            print_success "Database connection test successful (127.0.0.1 TCP/IP)"
            return 0
        fi

        # Method 3: Create .pgpass file for authentication
        if [ "$attempt" -eq $max_attempts ]; then
            print_info "Trying .pgpass authentication method..."
            echo "localhost:5432:sharewarez:sharewarezuser:$DB_PASSWORD" > ~/.pgpass
            chmod 600 ~/.pgpass

            if psql -h localhost -U sharewarezuser -d sharewarez -c "SELECT 1;" >/dev/null 2>&1; then
                rm ~/.pgpass 2>/dev/null
                print_success "Database connection test successful (.pgpass method)"
                return 0
            fi
            rm ~/.pgpass 2>/dev/null
        fi

        attempt=$((attempt + 1))
        if [ $attempt -le $max_attempts ]; then
            print_info "Waiting 2 seconds before retry..."
            sleep 2
        fi
    done

    # If all methods failed, provide detailed error information
    print_error "All database connection methods failed"
    print_info "This may be due to PostgreSQL authentication configuration"
    print_info "The database and user were created successfully, but connection testing failed"
    print_info "You may need to manually configure PostgreSQL authentication"

    return 1
}

# Start and configure PostgreSQL
setup_postgresql() {
    if [ "$SKIP_DB" = true ]; then
        print_info "Skipping PostgreSQL setup (--no-db flag)"
        return 0
    fi

    print_step "Setting up PostgreSQL database..."

    # Start PostgreSQL service
    case "$PACKAGE_MANAGER" in
        apt)
            sudo systemctl start postgresql
            sudo systemctl enable postgresql
            ;;
        dnf|yum)
            # Initialize database if needed
            if [ ! -d "/var/lib/pgsql/data/base" ]; then
                print_info "Initializing PostgreSQL database..."
                sudo postgresql-setup --initdb >/dev/null 2>&1 || true
            fi
            sudo systemctl start postgresql
            sudo systemctl enable postgresql
            ;;
        pacman)
            # Initialize database if needed
            if [ ! -d "/var/lib/postgres/data/base" ]; then
                print_info "Initializing PostgreSQL database..."
                sudo -u postgres initdb -D /var/lib/postgres/data
            fi
            sudo systemctl start postgresql
            sudo systemctl enable postgresql
            ;;
        zypper)
            sudo systemctl start postgresql
            sudo systemctl enable postgresql
            ;;
    esac

    # Wait for PostgreSQL to start
    print_info "Waiting for PostgreSQL to start..."
    for i in {1..30}; do
        if sudo -u postgres psql -c "SELECT 1;" >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    if ! sudo -u postgres psql -c "SELECT 1;" >/dev/null 2>&1; then
        print_error "PostgreSQL failed to start properly"
        return 1
    fi

    print_success "PostgreSQL is running"

    # Generate secure password for database user
    DB_PASSWORD=$(generate_secure_password)

    print_info "Creating database and user..."

    # Create database user and database
    sudo -u postgres psql << EOF
-- Create user
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sharewarezuser') THEN
        CREATE USER sharewarezuser WITH ENCRYPTED PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;

-- Create database
SELECT 'CREATE DATABASE sharewarez OWNER sharewarezuser'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sharewarez')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE sharewarez TO sharewarezuser;
GRANT CREATE ON SCHEMA public TO sharewarezuser;

-- Exit without testing connection here (avoids peer auth issues)
\q
EOF

    if [ $? -eq 0 ]; then
        print_success "Database 'sharewarez' created with user 'sharewarezuser'"
    else
        print_error "Failed to create database or user"
        return 1
    fi

    # Configure PostgreSQL authentication for password access
    configure_postgresql_auth

    # Test the database connection with multiple methods
    if ! test_database_connection; then
        print_warning "Database connection test failed"
        print_info "The database and user were created, but connection testing failed"
        print_info "This may not prevent SharewareZ from working if the application can connect"
        print_info "You can continue with the installation"

        # Ask user if they want to continue
        printf "Continue with installation? [Y/n]: "
        read -r continue_install
        if [ "${continue_install:-Y}" != "Y" ] && [ "${continue_install:-Y}" != "y" ]; then
            print_error "Installation aborted by user"
            return 1
        fi

        print_info "Continuing with installation..."
    fi
}

# Set up Python virtual environment and install dependencies
setup_python_environment() {
    print_step "Setting up Python virtual environment..."

    # Create virtual environment if it doesn't exist
    if [ ! -d "$SCRIPT_DIR/venv" ]; then
        python3 -m venv "$SCRIPT_DIR/venv"
        print_success "Virtual environment created"
    else
        print_info "Using existing virtual environment"
    fi

    # Activate virtual environment and install dependencies
    source "$SCRIPT_DIR/venv/bin/activate"

    print_info "Installing Python dependencies..."
    if python3 -m pip install -r "$SCRIPT_DIR/requirements.txt" >/dev/null 2>&1; then
        print_success "Python dependencies installed"
    else
        print_error "Failed to install Python dependencies"
        return 1
    fi

    if [ "$DEV_MODE" = true ]; then
        print_info "Installing development dependencies..."
        if [ -f "$SCRIPT_DIR/requirements-dev.txt" ]; then
            python3 -m pip install -r "$SCRIPT_DIR/requirements-dev.txt" >/dev/null 2>&1
        fi
    fi
}

# Configure application settings
configure_application() {
    print_step "Configuring SharewareZ application..."

    # Copy configuration files
    if [ ! -f "$SCRIPT_DIR/config.py" ] || [ "$FORCE_INSTALL" = true ]; then
        cp "$SCRIPT_DIR/config.py.example" "$SCRIPT_DIR/config.py"
        print_success "Configuration file created"
    fi

    # Generate secret key
    SECRET_KEY=$(generate_secret_key)

    # Prompt for games directory if not specified
    if [ -z "$GAMES_DIR" ]; then
        echo
        print_info "Please specify the directory containing your game files:"
        read -p "Games directory path [/home/$USER/games]: " input_dir
        GAMES_DIR="${input_dir:-/home/$USER/games}"
    fi

    # Validate games directory
    if [ ! -d "$GAMES_DIR" ]; then
        print_warning "Games directory does not exist: $GAMES_DIR"
        read -p "Create this directory? [Y/n]: " create_dir
        case "${create_dir:-Y}" in
            [Yy]|[Yy][Ee][Ss]) create_it=true ;;
            *) create_it=false ;;
        esac
        if [ "$create_it" = true ]; then
            mkdir -p "$GAMES_DIR"
            print_success "Games directory created: $GAMES_DIR"
        else
            print_warning "You'll need to update the games directory later in .env"
        fi
    else
        print_success "Games directory exists: $GAMES_DIR"
    fi

    # Create .env file
    print_info "Creating environment configuration..."

    cat > "$SCRIPT_DIR/.env" << EOF
# SharewareZ Configuration - Generated by auto-installer $(date)

# Database connection
DATABASE_URL=postgresql://sharewarezuser:$DB_PASSWORD@localhost:5432/sharewarez

# Test database (only needed if running unit tests)
TEST_DATABASE_URL=postgresql://sharewarezuser:$DB_PASSWORD@localhost:5432/sharewareztest

# Game files directory
DATA_FOLDER_WAREZ=$GAMES_DIR

# Base folders for path resolution
BASE_FOLDER_WINDOWS=C:\\
BASE_FOLDER_POSIX=/

# Flask secret key (keep this secure!)
SECRET_KEY=$SECRET_KEY

# Upload directory for cover images and zips
UPLOAD_FOLDER=$SCRIPT_DIR/modules/static/library

# Development mode
DEV_MODE=$DEV_MODE
EOF

    # Set secure permissions on .env file
    chmod 600 "$SCRIPT_DIR/.env"
    print_success "Environment configuration created"

    # Make startup script executable
    chmod +x "$SCRIPT_DIR/startweb.sh"
    print_success "Startup script permissions set"
}

# Validate the installation
validate_installation() {
    print_step "Validating installation..."

    # Check if virtual environment exists and works
    if [ -d "$SCRIPT_DIR/venv" ]; then
        source "$SCRIPT_DIR/venv/bin/activate"

        # Test Flask app creation
        if python3 -c "from modules import create_app; app = create_app(); print('Flask app creation: OK')" >/dev/null 2>&1; then
            print_success "Flask application setup validated"
        else
            print_error "Flask application validation failed"
            return 1
        fi
    else
        print_error "Virtual environment not found"
        return 1
    fi

    # Check database connection
    if [ "$SKIP_DB" != true ]; then
        if test_database_connection >/dev/null 2>&1; then
            print_success "Database connection validated"
        else
            print_warning "Database connection validation failed"
            print_info "This may not prevent SharewareZ from functioning"
        fi
    fi

    # Check required files
    for file in ".env" "config.py" "startweb.sh" "requirements.txt"; do
        if [ -f "$SCRIPT_DIR/$file" ]; then
            print_success "Required file exists: $file"
        else
            print_error "Missing required file: $file"
            return 1
        fi
    done
}

# Show installation summary
show_summary() {
    echo
    echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
    echo -e "${WHITE}    Installation Completed Successfully!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
    echo
    echo -e "${CYAN}📌 Access URL:${NC} http://localhost:$CUSTOM_PORT"
    echo -e "${CYAN}📌 Games Directory:${NC} $GAMES_DIR"
    if [ "$SKIP_DB" != true ]; then
        echo -e "${CYAN}📌 Database:${NC} sharewarez (credentials stored in .env)"
    fi
    echo -e "${CYAN}📌 Start Command:${NC} ./startweb.sh"
    echo -e "${CYAN}📌 Stop:${NC} Press Ctrl+C"
    echo -e "${CYAN}📌 Reset Database:${NC} ./startweb.sh --force-setup"
    echo -e "${CYAN}📌 Log File:${NC} $LOG_FILE"
    echo

    # Ask if user wants to start the application
    read -p "Start SharewareZ now? [Y/n]: " start_now
    case "${start_now:-Y}" in
        [Yy]|[Yy][Ee][Ss])
            start_it=true
            ;;
        *)
            start_it=false
            ;;
    esac
    if [ "$start_it" = true ]; then
        echo
        print_info "Starting SharewareZ..."
        print_info "Open your browser to http://localhost:$CUSTOM_PORT when ready"
        print_info "Press Ctrl+C to stop the application"
        echo
        exec ./startweb.sh
    else
        echo
        print_info "To start SharewareZ later, run: ./startweb.sh"
        print_info "Then open your browser to: http://localhost:$CUSTOM_PORT"
    fi
}

# Main installation function
main() {
    # Initialize log file
    echo "SharewareZ Linux Auto-Installer - $(date)" > "$LOG_FILE"

    print_header

    # Parse command line arguments
    parse_arguments "$@"

    # Check permissions
    check_permissions

    # Detect distribution
    if ! detect_distribution; then
        exit 1
    fi

    # Check if already in SharewareZ directory
    if [ ! -f "$SCRIPT_DIR/startweb.sh" ] || [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
        print_error "This script must be run from the SharewareZ directory"
        print_info "Please clone the repository first:"
        print_info "  git clone https://github.com/axewater/sharewarez.git"
        print_info "  cd sharewarez"
        print_info "  ./install-linux.sh"
        exit 1
    fi

    # Backup existing configuration
    backup_existing_config

    # Install prerequisites
    install_prerequisites

    # Setup PostgreSQL
    if ! setup_postgresql; then
        exit 1
    fi

    # Setup Python environment
    if ! setup_python_environment; then
        exit 1
    fi

    # Configure application
    if ! configure_application; then
        exit 1
    fi

    # Validate installation
    if ! validate_installation; then
        exit 1
    fi

    # Show summary and optionally start
    show_summary
}

# Run main function if script is executed directly
if [ "${0##*/}" = "install-linux.sh" ] || [ "${0}" = "./install-linux.sh" ]; then
    main "$@"
fi