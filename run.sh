#!/bin/bash

# NEURA - Application Runner Script
# Usage: ./run.sh [command]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Print colored message
print_msg() {
    echo -e "${2}${1}${NC}"
}

print_header() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}     ${BLUE}NEURA${NC} - Where AI Comes Alive          ${CYAN}║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════╝${NC}"
    echo ""
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    print_msg "Checking prerequisites..." "$YELLOW"
    
    local missing=()
    
    if ! command_exists docker; then
        missing+=("docker")
    fi
    
    if ! command_exists docker-compose && ! docker compose version >/dev/null 2>&1; then
        missing+=("docker-compose")
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        print_msg "Missing required tools: ${missing[*]}" "$RED"
        print_msg "Please install them and try again." "$RED"
        exit 1
    fi
    
    print_msg "✓ All prerequisites met" "$GREEN"
}

# Setup environment
setup_env() {
    print_msg "Setting up environment..." "$YELLOW"
    
    if [ ! -f "$PROJECT_ROOT/.env.local" ]; then
        if [ -f "$PROJECT_ROOT/.env.example" ]; then
            cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env.local"
            print_msg "✓ Created .env.local from .env.example" "$GREEN"
            print_msg "  Please review and update the configuration" "$YELLOW"
        else
            print_msg "Creating default .env.local..." "$YELLOW"
            cat > "$PROJECT_ROOT/.env.local" << 'EOF'
# Environment
ENV=local
DEBUG=true

# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=neura
POSTGRES_USER=neura
POSTGRES_PASSWORD=neura_dev_password
DATABASE_URL=postgresql+asyncpg://neura:neura_dev_password@postgres:5432/neura

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# MinIO / S3
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=neura_minio
S3_SECRET_KEY=neura_minio_password
S3_BUCKET=neura-storage
S3_REGION=us-east-1

# JWT
JWT_SECRET_KEY=dev-secret-key-change-in-production-minimum-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# LLM
LLM_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1
GEMINI_API_KEY=

# TTS
TTS_PROVIDER=neura
TTS_MODEL_PATH=/app/models/tts

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# CORS
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
EOF
            print_msg "✓ Created default .env.local" "$GREEN"
        fi
    else
        print_msg "✓ .env.local already exists" "$GREEN"
    fi
}

# Start infrastructure services only
start_infra() {
    print_msg "Starting infrastructure services..." "$YELLOW"
    cd "$PROJECT_ROOT"
    docker compose up -d postgres redis minio
    print_msg "✓ Infrastructure services started" "$GREEN"
    print_msg "  PostgreSQL: localhost:5432" "$CYAN"
    print_msg "  Redis: localhost:6379" "$CYAN"
    print_msg "  MinIO: localhost:9000 (console: localhost:9001)" "$CYAN"
}

# Start all services in development mode
start_dev() {
    print_header
    check_prerequisites
    setup_env
    
    print_msg "Starting NEURA in development mode..." "$YELLOW"
    cd "$PROJECT_ROOT"
    
    docker compose up -d --build
    
    print_msg "" ""
    print_msg "✓ NEURA is starting up!" "$GREEN"
    print_msg "" ""
    print_msg "Services:" "$CYAN"
    print_msg "  Frontend:  http://localhost:3000" "$NC"
    print_msg "  Backend:   http://localhost:8000" "$NC"
    print_msg "  API Docs:  http://localhost:8000/docs" "$NC"
    print_msg "  MinIO:     http://localhost:9001" "$NC"
    print_msg "" ""
    print_msg "Run './run.sh logs' to view logs" "$YELLOW"
    print_msg "Run './run.sh stop' to stop all services" "$YELLOW"
}

# Start in production mode
start_prod() {
    print_header
    check_prerequisites
    
    if [ ! -f "$PROJECT_ROOT/.env.production" ]; then
        print_msg "Error: .env.production not found" "$RED"
        print_msg "Please create .env.production with production settings" "$YELLOW"
        exit 1
    fi
    
    print_msg "Starting NEURA in production mode..." "$YELLOW"
    cd "$PROJECT_ROOT"
    
    docker compose -f docker-compose.prod.yml up -d --build
    
    print_msg "✓ NEURA production started!" "$GREEN"
}

# Stop all services
stop_services() {
    print_msg "Stopping NEURA services..." "$YELLOW"
    cd "$PROJECT_ROOT"
    docker compose down
    print_msg "✓ All services stopped" "$GREEN"
}

# Stop and remove volumes
clean() {
    print_msg "Stopping and cleaning up NEURA..." "$YELLOW"
    cd "$PROJECT_ROOT"
    docker compose down -v --remove-orphans
    print_msg "✓ Cleanup complete" "$GREEN"
}

# View logs
view_logs() {
    cd "$PROJECT_ROOT"
    if [ -z "$2" ]; then
        docker compose logs -f
    else
        docker compose logs -f "$2"
    fi
}

# Run database migrations
run_migrations() {
    print_msg "Running database migrations..." "$YELLOW"
    cd "$PROJECT_ROOT"
    docker compose exec backend alembic upgrade head
    print_msg "✓ Migrations complete" "$GREEN"
}

# Create new migration
create_migration() {
    if [ -z "$2" ]; then
        print_msg "Error: Please provide a migration message" "$RED"
        print_msg "Usage: ./run.sh migrate:create 'migration message'" "$YELLOW"
        exit 1
    fi
    
    print_msg "Creating migration: $2" "$YELLOW"
    cd "$PROJECT_ROOT"
    docker compose exec backend alembic revision --autogenerate -m "$2"
    print_msg "✓ Migration created" "$GREEN"
}

# Run backend shell
backend_shell() {
    print_msg "Opening backend shell..." "$YELLOW"
    cd "$PROJECT_ROOT"
    docker compose exec backend /bin/bash
}

# Run tests
run_tests() {
    print_msg "Running tests..." "$YELLOW"
    cd "$PROJECT_ROOT"
    docker compose exec backend pytest -v
}

# Check service status
check_status() {
    print_msg "Service Status:" "$CYAN"
    cd "$PROJECT_ROOT"
    docker compose ps
}

# Build images
build_images() {
    print_msg "Building Docker images..." "$YELLOW"
    cd "$PROJECT_ROOT"
    docker compose build
    print_msg "✓ Build complete" "$GREEN"
}

# Install frontend dependencies locally
install_frontend() {
    print_msg "Installing frontend dependencies..." "$YELLOW"
    cd "$PROJECT_ROOT/frontend"
    npm install
    print_msg "✓ Frontend dependencies installed" "$GREEN"
}

# Install backend dependencies locally
install_backend() {
    print_msg "Installing backend dependencies..." "$YELLOW"
    cd "$PROJECT_ROOT/backend"
    pip install -r requirements.txt
    print_msg "✓ Backend dependencies installed" "$GREEN"
}

# Run frontend locally (without Docker)
run_frontend_local() {
    print_msg "Starting frontend locally..." "$YELLOW"
    cd "$PROJECT_ROOT/frontend"
    npm run dev
}

# Run backend locally (without Docker)
run_backend_local() {
    print_msg "Starting backend locally..." "$YELLOW"
    cd "$PROJECT_ROOT/backend"
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
}

# Show help
show_help() {
    print_header
    echo "Usage: ./run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  ${GREEN}start${NC}              Start all services in development mode"
    echo "  ${GREEN}start:prod${NC}         Start all services in production mode"
    echo "  ${GREEN}start:infra${NC}        Start only infrastructure (DB, Redis, MinIO)"
    echo "  ${GREEN}stop${NC}               Stop all services"
    echo "  ${GREEN}restart${NC}            Restart all services"
    echo "  ${GREEN}clean${NC}              Stop services and remove volumes"
    echo "  ${GREEN}status${NC}             Show service status"
    echo "  ${GREEN}logs [service]${NC}     View logs (optionally for specific service)"
    echo "  ${GREEN}build${NC}              Build Docker images"
    echo ""
    echo "  ${GREEN}migrate${NC}            Run database migrations"
    echo "  ${GREEN}migrate:create${NC}     Create new migration"
    echo "  ${GREEN}shell${NC}              Open backend shell"
    echo "  ${GREEN}test${NC}               Run tests"
    echo ""
    echo "  ${GREEN}install:frontend${NC}   Install frontend dependencies locally"
    echo "  ${GREEN}install:backend${NC}    Install backend dependencies locally"
    echo "  ${GREEN}local:frontend${NC}     Run frontend locally (without Docker)"
    echo "  ${GREEN}local:backend${NC}      Run backend locally (without Docker)"
    echo ""
    echo "  ${GREEN}setup${NC}              Setup environment files"
    echo "  ${GREEN}help${NC}               Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./run.sh start           # Start development environment"
    echo "  ./run.sh logs backend    # View backend logs"
    echo "  ./run.sh migrate         # Run migrations"
    echo ""
}

# Main command handler
case "${1:-}" in
    start)
        start_dev
        ;;
    start:prod)
        start_prod
        ;;
    start:infra)
        start_infra
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        start_dev
        ;;
    clean)
        clean
        ;;
    status)
        check_status
        ;;
    logs)
        view_logs "$@"
        ;;
    build)
        build_images
        ;;
    migrate)
        run_migrations
        ;;
    migrate:create)
        create_migration "$@"
        ;;
    shell)
        backend_shell
        ;;
    test)
        run_tests
        ;;
    install:frontend)
        install_frontend
        ;;
    install:backend)
        install_backend
        ;;
    local:frontend)
        run_frontend_local
        ;;
    local:backend)
        run_backend_local
        ;;
    setup)
        setup_env
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        ;;
esac

