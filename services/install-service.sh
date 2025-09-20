#!/bin/bash

# CubeGame Service Installation Script
# This script installs and manages the CubeGame systemd service

SERVICE_NAME="cubegame"
SERVICE_FILE="${SERVICE_NAME}.service"
SYSTEMD_DIR="/etc/systemd/system"
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should not be run as root directly."
        print_status "Use: sudo $0 [command]"
        exit 1
    fi
}

install_service() {
    print_status "Installing CubeGame service..."
    
    # Check if service file exists
    if [[ ! -f "$CURRENT_DIR/$SERVICE_FILE" ]]; then
        print_error "Service file $SERVICE_FILE not found in $CURRENT_DIR"
        exit 1
    fi
    
    # Copy service file
    print_status "Copying service file to $SYSTEMD_DIR..."
    sudo cp "$CURRENT_DIR/$SERVICE_FILE" "$SYSTEMD_DIR/"
    
    if [[ $? -ne 0 ]]; then
        print_error "Failed to copy service file"
        exit 1
    fi
    
    # Reload systemd
    print_status "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    
    # Set appropriate permissions
    sudo chmod 644 "$SYSTEMD_DIR/$SERVICE_FILE"
    
    print_success "Service installed successfully!"
    print_status "You can now use: sudo systemctl start $SERVICE_NAME"
}

enable_service() {
    print_status "Enabling $SERVICE_NAME service to start on boot..."
    sudo systemctl enable "$SERVICE_NAME"
    
    if [[ $? -eq 0 ]]; then
        print_success "Service enabled successfully!"
    else
        print_error "Failed to enable service"
        exit 1
    fi
}

disable_service() {
    print_status "Disabling $SERVICE_NAME service from starting on boot..."
    sudo systemctl disable "$SERVICE_NAME"
    
    if [[ $? -eq 0 ]]; then
        print_success "Service disabled successfully!"
    else
        print_error "Failed to disable service"
        exit 1
    fi
}

start_service() {
    print_status "Starting $SERVICE_NAME service..."
    sudo systemctl start "$SERVICE_NAME"
    
    if [[ $? -eq 0 ]]; then
        print_success "Service started successfully!"
        sleep 2
        service_status
    else
        print_error "Failed to start service"
        print_status "Check logs with: sudo journalctl -u $SERVICE_NAME -xe"
        exit 1
    fi
}

stop_service() {
    print_status "Stopping $SERVICE_NAME service..."
    sudo systemctl stop "$SERVICE_NAME"
    
    if [[ $? -eq 0 ]]; then
        print_success "Service stopped successfully!"
    else
        print_error "Failed to stop service"
        exit 1
    fi
}

restart_service() {
    print_status "Restarting $SERVICE_NAME service..."
    sudo systemctl restart "$SERVICE_NAME"
    
    if [[ $? -eq 0 ]]; then
        print_success "Service restarted successfully!"
        sleep 2
        service_status
    else
        print_error "Failed to restart service"
        print_status "Check logs with: sudo journalctl -u $SERVICE_NAME -xe"
        exit 1
    fi
}

service_status() {
    print_status "Service status:"
    sudo systemctl status "$SERVICE_NAME" --no-pager
}

service_logs() {
    print_status "Recent service logs:"
    sudo journalctl -u "$SERVICE_NAME" -n 20 --no-pager
}

follow_logs() {
    print_status "Following service logs (Ctrl+C to stop):"
    sudo journalctl -u "$SERVICE_NAME" -f
}

uninstall_service() {
    print_status "Uninstalling $SERVICE_NAME service..."
    
    # Stop service if running
    sudo systemctl stop "$SERVICE_NAME" 2>/dev/null
    
    # Disable service
    sudo systemctl disable "$SERVICE_NAME" 2>/dev/null
    
    # Remove service file
    sudo rm -f "$SYSTEMD_DIR/$SERVICE_FILE"
    
    # Reload systemd
    sudo systemctl daemon-reload
    
    print_success "Service uninstalled successfully!"
}

show_usage() {
    echo "CubeGame Service Management Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  install     Install the service"
    echo "  uninstall   Remove the service"
    echo "  enable      Enable service to start on boot"
    echo "  disable     Disable service from starting on boot"
    echo "  start       Start the service"
    echo "  stop        Stop the service"
    echo "  restart     Restart the service"
    echo "  status      Show service status"
    echo "  logs        Show recent logs"
    echo "  follow      Follow logs in real-time"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 install          # Install the service"
    echo "  $0 start            # Start the service"
    echo "  $0 enable           # Enable auto-start on boot"
    echo "  $0 status           # Check if service is running"
    echo "  $0 logs             # View recent logs"
}

# Main script logic
check_root

case "${1:-help}" in
    install)
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    enable)
        enable_service
        ;;
    disable)
        disable_service
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        service_status
        ;;
    logs)
        service_logs
        ;;
    follow)
        follow_logs
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        print_error "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac
