#!/bin/bash

# PostgreSQL Setup Helper Script

# This script helps you set up PostgreSQL for the User Service

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Load environment variables from .env file if it exists
ENV_FILE="$(dirname "$0")/.env"
if [ -f "$ENV_FILE" ]; then
    echo -e "${CYAN}Loading database credentials from .env file...${NC}"
    # Export variables from .env file
    export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

# Set default values if not found in .env
POSTGRES_DB="${POSTGRES_DB:-chatbot_users}"
POSTGRES_USERNAME="${POSTGRES_USERNAME:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"

echo -e "${GREEN}Using Database Configuration:${NC}"
echo -e "  Database: ${POSTGRES_DB}"
echo -e "  Username: ${POSTGRES_USERNAME}"
echo ""

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          PostgreSQL Setup for User Service                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${CYAN}You have several options to set up PostgreSQL:${NC}"
echo ""

echo -e "${GREEN}Option 1: Install PostgreSQL locally${NC}"
echo "  sudo apt update"
echo "  sudo apt install postgresql postgresql-contrib"
echo "  sudo systemctl start postgresql"
echo "  sudo systemctl enable postgresql"
echo ""
echo "  Then create the database:"
echo "  sudo -u postgres psql -c \"CREATE DATABASE ${POSTGRES_DB};\""
echo "  sudo -u postgres psql -c \"ALTER USER ${POSTGRES_USERNAME} PASSWORD '${POSTGRES_PASSWORD}';\""
echo ""

echo -e "${GREEN}Option 2: Use Docker (if Docker is installed)${NC}"
echo "  docker run -d \\"
echo "    --name chatbot-postgres \\"
echo "    -e POSTGRES_USER=${POSTGRES_USERNAME} \\"
echo "    -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \\"
echo "    -e POSTGRES_DB=${POSTGRES_DB} \\"
echo "    -p 5432:5432 \\"
echo "    postgres:15"
echo ""

echo -e "${GREEN}Option 3: Use PostgreSQL from Docker Compose${NC}"
echo "  Create a docker-compose.yml file with PostgreSQL service"
echo ""

echo -e "${YELLOW}Note: Your .env file currently has:${NC}"
echo "  POSTGRES_USERNAME=${POSTGRES_USERNAME}"
echo "  POSTGRES_PASSWORD=${POSTGRES_PASSWORD}"
echo "  POSTGRES_DB=${POSTGRES_DB}"
echo ""
echo -e "${CYAN}The script will preserve these settings in your .env file.${NC}"
echo ""

read -p "Do you want to install PostgreSQL locally now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Installing PostgreSQL...${NC}"
    sudo apt update
    sudo apt install -y postgresql postgresql-contrib
    
    echo -e "${BLUE}Starting PostgreSQL...${NC}"
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    
    echo -e "${BLUE}Creating database and user...${NC}"
    sudo -u postgres psql -c "CREATE DATABASE ${POSTGRES_DB};" 2>/dev/null || echo "Database already exists"
    sudo -u postgres psql -c "ALTER USER ${POSTGRES_USERNAME} PASSWORD '${POSTGRES_PASSWORD}';"
    
    # Allow local connections with password
    echo -e "${BLUE}Configuring PostgreSQL for password authentication...${NC}"
    PG_VERSION=$(ls /etc/postgresql/)
    PG_HBA="/etc/postgresql/${PG_VERSION}/main/pg_hba.conf"
    
    if [ -f "$PG_HBA" ]; then
        sudo sed -i 's/local   all             postgres                                peer/local   all             postgres                                md5/' "$PG_HBA"
        sudo sed -i 's/host    all             all             127.0.0.1\/32            scram-sha-256/host    all             all             127.0.0.1\/32            md5/' "$PG_HBA"
        sudo systemctl restart postgresql
    fi
    
    # Update .env file
    if [ -f "$ENV_FILE" ]; then
        echo -e "${BLUE}Updating .env file...${NC}"
        # Backup existing .env
        cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        
        # Update or add PostgreSQL variables
        if grep -q "^POSTGRES_DB=" "$ENV_FILE"; then
            sed -i "s|^POSTGRES_DB=.*|POSTGRES_DB=${POSTGRES_DB}|" "$ENV_FILE"
        else
            echo "POSTGRES_DB=${POSTGRES_DB}" >> "$ENV_FILE"
        fi
        
        if grep -q "^POSTGRES_USERNAME=" "$ENV_FILE"; then
            sed -i "s|^POSTGRES_USERNAME=.*|POSTGRES_USERNAME=${POSTGRES_USERNAME}|" "$ENV_FILE"
        else
            echo "POSTGRES_USERNAME=${POSTGRES_USERNAME}" >> "$ENV_FILE"
        fi
        
        if grep -q "^POSTGRES_PASSWORD=" "$ENV_FILE"; then
            sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|" "$ENV_FILE"
        else
            echo "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" >> "$ENV_FILE"
        fi
        
        echo -e "${GREEN}✓ .env file updated${NC}"
    else
        echo -e "${YELLOW}⚠️  .env file not found. Creating one...${NC}"
        cat > "$ENV_FILE" <<EOF
# PostgreSQL Configuration
POSTGRES_DB=${POSTGRES_DB}
POSTGRES_USERNAME=${POSTGRES_USERNAME}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
EOF
        echo -e "${GREEN}✓ Created .env file with default values${NC}"
    fi
    
    echo -e "${GREEN}✓ PostgreSQL setup complete!${NC}"
    echo -e "${CYAN}You can now run: ./start_services.sh user${NC}"
else
    echo -e "${YELLOW}Skipping PostgreSQL installation.${NC}"
    echo -e "${CYAN}Please set up PostgreSQL using one of the options above.${NC}"
fi
