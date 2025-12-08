#!/bin/bash

# Learning Chatbot - Unified Service Startup Script

# This script starts all services using the langchain_env virtual environment

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/praneeth/Desktop/Learning_chatbot"
VENV_PATH="$HOME/langchain_env"
PYTHON_BIN="$VENV_PATH/bin/python"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Learning Chatbot - Service Manager                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}✗ Virtual environment not found at $VENV_PATH${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found virtual environment: $VENV_PATH${NC}"

# Check if .env file exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found at $PROJECT_DIR/.env${NC}"
    echo -e "${YELLOW}   Continuing without .env file (services may use config.yaml)${NC}"
else
    echo -e "${GREEN}✓ Found .env file${NC}"
    # Load environment variables
    cd "$PROJECT_DIR"
    set -a
    source .env
    set +a
fi

echo ""
echo -e "${CYAN}Checking system dependencies...${NC}"

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 1
    fi
    return 0
}

# Function to check service dependencies
check_dependencies() {
    echo -e "${BLUE}Checking Redis...${NC}"
    if systemctl is-active --quiet redis-server 2>/dev/null; then
        echo -e "${GREEN}✓ Redis is running${NC}"
    else
        echo -e "${YELLOW}⚠️  Redis is not running. Attempting to start...${NC}"
        if sudo systemctl start redis-server 2>/dev/null; then
            echo -e "${GREEN}✓ Redis started${NC}"
        else
            echo -e "${YELLOW}⚠️  Could not start Redis via systemctl. Please start manually if needed.${NC}"
        fi
    fi
    
    echo -e "${BLUE}Checking Cassandra...${NC}"
    if systemctl is-active --quiet cassandra 2>/dev/null; then
        echo -e "${GREEN}✓ Cassandra is running${NC}"
    else
        echo -e "${YELLOW}⚠️  Cassandra is not running. Attempting to start...${NC}"
        if sudo systemctl start cassandra 2>/dev/null; then
            echo -e "${GREEN}✓ Cassandra started${NC}"
            echo -e "${YELLOW}Waiting for Cassandra to be ready (30 seconds)...${NC}"
            sleep 30
        else
            echo -e "${YELLOW}⚠️  Could not start Cassandra via systemctl. Please start manually if needed.${NC}"
        fi
    fi
    
    echo -e "${BLUE}Checking PostgreSQL...${NC}"
    # For asyncpg, PostgreSQL might not be installed locally
    # User needs to have PostgreSQL accessible (local or Docker)
    echo -e "${YELLOW}⚠️  PostgreSQL check skipped (using asyncpg)${NC}"
    if [ ! -z "${POSTGRES_HOST:-}" ] && [ ! -z "${POSTGRES_PORT:-}" ]; then
        echo -e "${CYAN}   Make sure PostgreSQL is accessible at ${POSTGRES_HOST}:${POSTGRES_PORT}${NC}"
        if [ ! -z "${POSTGRES_DB:-}" ]; then
            echo -e "${CYAN}   Database: ${POSTGRES_DB}${NC}"
        fi
        if [ ! -z "${POSTGRES_USER:-}" ]; then
            echo -e "${CYAN}   User: ${POSTGRES_USER}${NC}"
        fi
    else
        echo -e "${CYAN}   Make sure PostgreSQL is accessible (check config.yaml)${NC}"
    fi
    
}

# Function to start a Python service
start_service() {
    local service_name=$1
    local service_dir=$2
    local api_file=$3
    local port=$4
    
    echo ""
    echo -e "${BLUE}Starting $service_name on port $port...${NC}"
    
    if ! check_port $port; then
        echo -e "${YELLOW}⚠️  Port $port is already in use${NC}"
        echo -e "${YELLOW}   Skipping $service_name${NC}"
        return 1
    fi
    
    cd "$PROJECT_DIR"
    
    # Set PYTHONPATH to include project root for imports
    export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
    
    # Start service in background
    nohup $PYTHON_BIN -m uvicorn "${service_dir}.${api_file}:app" --host 0.0.0.0 --port $port > "/tmp/chatbot_${service_name}.log" 2>&1 &
    local pid=$!
    echo $pid > "/tmp/chatbot_${service_name}.pid"
    
    # Wait a moment and check if process is still running
    sleep 2
    if kill -0 $pid 2>/dev/null; then
        echo -e "${GREEN}✓ $service_name started successfully (PID: $pid)${NC}"
        echo -e "${CYAN}   Log: /tmp/chatbot_${service_name}.log${NC}"
        return 0
    else
        echo -e "${RED}✗ $service_name failed to start${NC}"
        echo -e "${YELLOW}   Check log: /tmp/chatbot_${service_name}.log${NC}"
        return 1
    fi
}

# Function to stop all services
stop_all() {
    echo ""
    echo -e "${YELLOW}Stopping all services...${NC}"
    
    for pidfile in /tmp/chatbot_*.pid; do
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            service_name=$(basename "$pidfile" .pid | sed 's/chatbot_//')
            if kill -0 $pid 2>/dev/null; then
                kill $pid 2>/dev/null
                echo -e "${GREEN}✓ Stopped $service_name (PID: $pid)${NC}"
            fi
            rm -f "$pidfile"
        fi
    done
    
    echo -e "${GREEN}All services stopped${NC}"
}

# Function to check service status
check_status() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                    Service Status                          ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    services=(
        "User_Service:8001"
        "Chat_Service:8002"
        "Cache_Service:8003"
        "VectorStore_Service:8004"
        "RAG_Service:8005"
    )
    
    for service in "${services[@]}"; do
        IFS=':' read -r name port <<< "$service"
        printf "%-25s" "$name"
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
            echo -e "${GREEN}✓ Running on port $port${NC}"
        else
            echo -e "${RED}✗ Not running (port $port)${NC}"
        fi
    done
    
    echo ""
    echo -e "${CYAN}System Dependencies:${NC}"
    printf "%-25s" "Redis"
    if systemctl is-active --quiet redis-server 2>/dev/null; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${RED}✗ Not running${NC}"
    fi
    
    printf "%-25s" "Cassandra"
    if systemctl is-active --quiet cassandra 2>/dev/null; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${RED}✗ Not running${NC}"
    fi
}

# Function to view logs
view_logs() {
    local service=$1
    if [ -z "$service" ]; then
        echo -e "${YELLOW}Available logs:${NC}"
        ls -1 /tmp/chatbot_*.log 2>/dev/null | sed 's/\/tmp\/chatbot_/  - /' | sed 's/\.log$//'
        echo ""
        echo "Usage: $0 logs <service_name>"
        return
    fi
    
    local logfile="/tmp/chatbot_${service}.log"
    if [ -f "$logfile" ]; then
        echo -e "${BLUE}Showing logs for $service (press Ctrl+C to exit):${NC}"
        tail -f "$logfile"
    else
        echo -e "${RED}✗ Log file not found: $logfile${NC}"
    fi
}

# Main script
case "${1:-all}" in
    all)
        check_dependencies
        echo ""
        echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${BLUE}║              Starting All Services...                      ║${NC}"
        echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
        
        start_service "User_Service" "User" "user_api" 8001
        sleep 2
        
        start_service "Chat_Service" "Chat" "chat_api" 8002
        sleep 2
        
        start_service "Cache_Service" "Cache" "cache_api" 8003
        sleep 2
        
        start_service "VectorStore_Service" "VectorStore" "vectorstore_api" 8004
        sleep 2
        
        start_service "RAG_Service" "RAG" "rag_api" 8005
        
        check_status
        
        echo ""
        echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║          All Services Started Successfully!                ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${CYAN}API Endpoints:${NC}"
        echo -e "  User Service:        http://localhost:8001/docs"
        echo -e "  Chat Service:        http://localhost:8002/docs"
        echo -e "  Cache Service:       http://localhost:8003/docs"
        echo -e "  VectorStore Service: http://localhost:8004/docs"
        echo -e "  RAG Service:         http://localhost:8005/docs"
        echo ""
        echo -e "${CYAN}To stop all services: ${NC}$0 stop"
        echo -e "${CYAN}To check status:      ${NC}$0 status"
        echo -e "${CYAN}To view logs:         ${NC}$0 logs <service_name>"
        ;;
    
    user)
        start_service "User_Service" "User" "user_api" 8001
        ;;
    
    chat)
        start_service "Chat_Service" "Chat" "chat_api" 8002
        ;;
    
    cache)
        start_service "Cache_Service" "Cache" "cache_api" 8003
        ;;
    
    vectorstore)
        start_service "VectorStore_Service" "VectorStore" "vectorstore_api" 8004
        ;;
    
    rag)
        start_service "RAG_Service" "RAG" "rag_api" 8005
        ;;
    
    stop)
        stop_all
        ;;
    
    status)
        check_status
        ;;
    
    logs)
        view_logs "$2"
        ;;
    
    restart)
        stop_all
        sleep 2
        $0 all
        ;;
    
    *)
        echo -e "${BLUE}Learning Chatbot - Service Manager${NC}"
        echo ""
        echo "Usage: $0 {all|user|chat|cache|vectorstore|rag|stop|status|logs|restart}"
        echo ""
        echo "Commands:"
        echo -e "  ${GREEN}all${NC}          Start all services"
        echo -e "  ${GREEN}user${NC}         Start User Service (port 8001)"
        echo -e "  ${GREEN}chat${NC}         Start Chat Service (port 8002)"
        echo -e "  ${GREEN}cache${NC}        Start Cache Service (port 8003)"
        echo -e "  ${GREEN}vectorstore${NC}   Start VectorStore Service (port 8004)"
        echo -e "  ${GREEN}rag${NC}          Start RAG Service (port 8005)"
        echo -e "  ${GREEN}stop${NC}         Stop all services"
        echo -e "  ${GREEN}status${NC}       Check service status"
        echo -e "  ${GREEN}logs${NC}         View service logs (e.g., $0 logs User_Service)"
        echo -e "  ${GREEN}restart${NC}      Restart all services"
        echo ""
        exit 1
        ;;
esac
