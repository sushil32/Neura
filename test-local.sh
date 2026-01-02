#!/bin/bash

# NEURA - Local Testing Script
# This script sets up and tests the NEURA application locally

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

print_header() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}     ${BLUE}NEURA${NC} - Local Testing Suite                    ${CYAN}║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}  $1${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_test() {
    echo -e "  ${YELLOW}▶${NC} $1"
}

print_pass() {
    echo -e "  ${GREEN}✓ PASS:${NC} $1"
    ((TESTS_PASSED++))
}

print_fail() {
    echo -e "  ${RED}✗ FAIL:${NC} $1"
    ((TESTS_FAILED++))
}

print_info() {
    echo -e "  ${CYAN}ℹ${NC} $1"
}

print_warn() {
    echo -e "  ${YELLOW}⚠${NC} $1"
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if a port is in use
port_in_use() {
    lsof -i :"$1" >/dev/null 2>&1
}

# Wait for a service to be ready
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=${3:-30}
    local attempt=1

    print_test "Waiting for $name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" >/dev/null 2>&1; then
            print_pass "$name is ready"
            return 0
        fi
        sleep 2
        ((attempt++))
    done
    
    print_fail "$name failed to start after $max_attempts attempts"
    return 1
}

# Check prerequisites
check_prerequisites() {
    print_section "Checking Prerequisites"
    
    # Docker
    print_test "Checking Docker..."
    if command_exists docker; then
        docker_version=$(docker --version)
        print_pass "Docker installed: $docker_version"
    else
        print_fail "Docker not installed"
        echo -e "  ${YELLOW}Install Docker: https://docs.docker.com/get-docker/${NC}"
        exit 1
    fi
    
    # Docker Compose
    print_test "Checking Docker Compose..."
    if docker compose version >/dev/null 2>&1; then
        compose_version=$(docker compose version --short)
        print_pass "Docker Compose installed: $compose_version"
    elif command_exists docker-compose; then
        compose_version=$(docker-compose --version)
        print_pass "Docker Compose installed: $compose_version"
    else
        print_fail "Docker Compose not installed"
        exit 1
    fi
    
    # Node.js (optional for local frontend dev)
    print_test "Checking Node.js..."
    if command_exists node; then
        node_version=$(node --version)
        print_pass "Node.js installed: $node_version"
    else
        print_warn "Node.js not installed (optional for Docker setup)"
    fi
    
    # Python (optional for local backend dev)
    print_test "Checking Python..."
    if command_exists python3; then
        python_version=$(python3 --version)
        print_pass "Python installed: $python_version"
    else
        print_warn "Python not installed (optional for Docker setup)"
    fi
    
    # Check disk space
    print_test "Checking disk space..."
    available_space=$(df -h . | awk 'NR==2 {print $4}')
    print_info "Available disk space: $available_space"
}

# Setup environment
setup_environment() {
    print_section "Setting Up Environment"
    
    cd "$PROJECT_ROOT"
    
    # Create .env.local if not exists
    print_test "Setting up environment file..."
    if [ ! -f ".env.local" ]; then
        cat > ".env.local" << 'EOF'
# Environment
ENV=local
DEBUG=true

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=neura
POSTGRES_USER=neura
POSTGRES_PASSWORD=neura_dev_password
DATABASE_URL=postgresql+asyncpg://neura:neura_dev_password@localhost:5432/neura

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# MinIO / S3
S3_ENDPOINT=http://localhost:9000
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
LMSTUDIO_BASE_URL=http://localhost:1234/v1
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
        print_pass "Created .env.local"
    else
        print_pass ".env.local already exists"
    fi
    
    # Create necessary directories
    print_test "Creating required directories..."
    mkdir -p backend/models frontend/public
    print_pass "Directories created"
}

# Start infrastructure
start_infrastructure() {
    print_section "Starting Infrastructure Services"
    
    cd "$PROJECT_ROOT"
    
    # Check if services are already running
    print_test "Checking for existing containers..."
    
    # Stop any existing containers
    docker compose down >/dev/null 2>&1 || true
    
    # Start infrastructure only
    print_test "Starting PostgreSQL, Redis, and MinIO..."
    docker compose up -d postgres redis minio
    
    # Wait for PostgreSQL
    print_test "Waiting for PostgreSQL..."
    local attempts=0
    while ! docker compose exec -T postgres pg_isready -U neura >/dev/null 2>&1; do
        sleep 2
        ((attempts++))
        if [ $attempts -ge 30 ]; then
            print_fail "PostgreSQL failed to start"
            return 1
        fi
    done
    print_pass "PostgreSQL is ready"
    
    # Wait for Redis
    print_test "Waiting for Redis..."
    attempts=0
    while ! docker compose exec -T redis redis-cli ping >/dev/null 2>&1; do
        sleep 2
        ((attempts++))
        if [ $attempts -ge 15 ]; then
            print_fail "Redis failed to start"
            return 1
        fi
    done
    print_pass "Redis is ready"
    
    # Wait for MinIO
    print_test "Waiting for MinIO..."
    sleep 5
    if curl -s http://localhost:9000/minio/health/live >/dev/null 2>&1; then
        print_pass "MinIO is ready"
    else
        print_warn "MinIO health check unavailable (may still work)"
    fi
}

# Test database connection
test_database() {
    print_section "Testing Database"
    
    cd "$PROJECT_ROOT"
    
    print_test "Testing PostgreSQL connection..."
    if docker compose exec -T postgres psql -U neura -d neura -c "SELECT 1;" >/dev/null 2>&1; then
        print_pass "PostgreSQL connection successful"
    else
        print_fail "PostgreSQL connection failed"
        return 1
    fi
    
    print_test "Testing Redis connection..."
    if docker compose exec -T redis redis-cli ping | grep -q "PONG"; then
        print_pass "Redis connection successful"
    else
        print_fail "Redis connection failed"
        return 1
    fi
}

# Start backend
start_backend() {
    print_section "Starting Backend"
    
    cd "$PROJECT_ROOT"
    
    print_test "Building backend container..."
    docker compose build backend >/dev/null 2>&1
    print_pass "Backend built"
    
    print_test "Starting backend service..."
    docker compose up -d backend
    
    # Wait for backend to be ready
    wait_for_service "http://localhost:8000/health" "Backend API" 60
}

# Test backend API
test_backend_api() {
    print_section "Testing Backend API"
    
    # Health check
    print_test "Testing health endpoint..."
    response=$(curl -s http://localhost:8000/health)
    if echo "$response" | grep -q "healthy"; then
        print_pass "Health endpoint working"
    else
        print_fail "Health endpoint failed"
    fi
    
    # Root endpoint
    print_test "Testing root endpoint..."
    response=$(curl -s http://localhost:8000/)
    if echo "$response" | grep -q "NEURA"; then
        print_pass "Root endpoint working"
    else
        print_fail "Root endpoint failed"
    fi
    
    # API docs
    print_test "Testing API docs..."
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)
    if [ "$response" = "200" ]; then
        print_pass "API docs accessible"
    else
        print_fail "API docs not accessible (HTTP $response)"
    fi
    
    # Test registration
    print_test "Testing user registration..."
    response=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
        -H "Content-Type: application/json" \
        -d '{"email":"test@example.com","password":"TestPass123!","name":"Test User"}')
    
    if echo "$response" | grep -q "access_token"; then
        print_pass "User registration working"
        ACCESS_TOKEN=$(echo "$response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    elif echo "$response" | grep -q "already registered"; then
        print_pass "User already exists (expected on re-run)"
        # Try to login instead
        response=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
            -H "Content-Type: application/json" \
            -d '{"email":"test@example.com","password":"TestPass123!"}')
        ACCESS_TOKEN=$(echo "$response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    else
        print_fail "User registration failed: $response"
    fi
    
    # Test authenticated endpoint
    if [ -n "$ACCESS_TOKEN" ]; then
        print_test "Testing authenticated endpoint..."
        response=$(curl -s http://localhost:8000/api/v1/users/me \
            -H "Authorization: Bearer $ACCESS_TOKEN")
        if echo "$response" | grep -q "email"; then
            print_pass "Authenticated endpoint working"
        else
            print_fail "Authenticated endpoint failed"
        fi
    fi
    
    # Test videos endpoint
    print_test "Testing videos endpoint..."
    if [ -n "$ACCESS_TOKEN" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/videos \
            -H "Authorization: Bearer $ACCESS_TOKEN")
        if [ "$response" = "200" ]; then
            print_pass "Videos endpoint working"
        else
            print_fail "Videos endpoint failed (HTTP $response)"
        fi
    fi
    
    # Test avatars endpoint
    print_test "Testing avatars endpoint..."
    if [ -n "$ACCESS_TOKEN" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/avatars \
            -H "Authorization: Bearer $ACCESS_TOKEN")
        if [ "$response" = "200" ]; then
            print_pass "Avatars endpoint working"
        else
            print_fail "Avatars endpoint failed (HTTP $response)"
        fi
    fi
}

# Start frontend
start_frontend() {
    print_section "Starting Frontend"
    
    cd "$PROJECT_ROOT"
    
    print_test "Building frontend container..."
    docker compose build frontend >/dev/null 2>&1
    print_pass "Frontend built"
    
    print_test "Starting frontend service..."
    docker compose up -d frontend
    
    # Wait for frontend to be ready
    wait_for_service "http://localhost:3000" "Frontend" 90
}

# Test frontend
test_frontend() {
    print_section "Testing Frontend"
    
    print_test "Testing homepage..."
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000)
    if [ "$response" = "200" ]; then
        print_pass "Homepage accessible"
    else
        print_fail "Homepage not accessible (HTTP $response)"
    fi
    
    print_test "Testing login page..."
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/login)
    if [ "$response" = "200" ]; then
        print_pass "Login page accessible"
    else
        print_fail "Login page not accessible (HTTP $response)"
    fi
    
    print_test "Testing register page..."
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/register)
    if [ "$response" = "200" ]; then
        print_pass "Register page accessible"
    else
        print_fail "Register page not accessible (HTTP $response)"
    fi
}

# Start Celery workers
start_workers() {
    print_section "Starting Background Workers"
    
    cd "$PROJECT_ROOT"
    
    print_test "Starting Celery worker..."
    docker compose up -d celery-worker
    sleep 5
    
    if docker compose ps celery-worker | grep -q "Up"; then
        print_pass "Celery worker started"
    else
        print_warn "Celery worker may not be fully running"
    fi
    
    print_test "Starting Celery beat..."
    docker compose up -d celery-beat
    sleep 3
    
    if docker compose ps celery-beat | grep -q "Up"; then
        print_pass "Celery beat started"
    else
        print_warn "Celery beat may not be fully running"
    fi
}

# Show summary
show_summary() {
    print_section "Test Summary"
    
    echo ""
    echo -e "  ${GREEN}Passed: $TESTS_PASSED${NC}"
    echo -e "  ${RED}Failed: $TESTS_FAILED${NC}"
    echo ""
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}╔════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║          All tests passed successfully!            ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}"
    else
        echo -e "${YELLOW}╔════════════════════════════════════════════════════╗${NC}"
        echo -e "${YELLOW}║     Some tests failed. Check the output above.     ║${NC}"
        echo -e "${YELLOW}╚════════════════════════════════════════════════════╝${NC}"
    fi
    
    echo ""
    echo -e "${CYAN}Application URLs:${NC}"
    echo -e "  Frontend:     ${GREEN}http://localhost:3000${NC}"
    echo -e "  Backend API:  ${GREEN}http://localhost:8000${NC}"
    echo -e "  API Docs:     ${GREEN}http://localhost:8000/docs${NC}"
    echo -e "  MinIO Console:${GREEN}http://localhost:9001${NC}"
    echo ""
    echo -e "${CYAN}Useful commands:${NC}"
    echo -e "  View logs:    ${YELLOW}docker compose logs -f${NC}"
    echo -e "  Stop all:     ${YELLOW}docker compose down${NC}"
    echo -e "  Restart:      ${YELLOW}docker compose restart${NC}"
    echo ""
}

# Cleanup function
cleanup() {
    print_section "Cleanup"
    
    cd "$PROJECT_ROOT"
    
    print_test "Stopping all services..."
    docker compose down
    print_pass "Services stopped"
}

# Run full test
run_full_test() {
    print_header
    
    check_prerequisites
    setup_environment
    start_infrastructure
    test_database
    start_backend
    test_backend_api
    start_frontend
    test_frontend
    start_workers
    
    show_summary
}

# Run quick test (infrastructure only)
run_quick_test() {
    print_header
    
    check_prerequisites
    setup_environment
    start_infrastructure
    test_database
    
    echo ""
    echo -e "${GREEN}Infrastructure is ready!${NC}"
    echo -e "You can now run backend/frontend manually for development."
    echo ""
}

# Show help
show_help() {
    print_header
    echo "Usage: ./test-local.sh [command]"
    echo ""
    echo "Commands:"
    echo "  ${GREEN}full${NC}        Run full test suite (default)"
    echo "  ${GREEN}quick${NC}       Quick test (infrastructure only)"
    echo "  ${GREEN}backend${NC}     Test backend only"
    echo "  ${GREEN}frontend${NC}    Test frontend only"
    echo "  ${GREEN}cleanup${NC}     Stop and cleanup all services"
    echo "  ${GREEN}help${NC}        Show this help"
    echo ""
}

# Main
case "${1:-full}" in
    full)
        run_full_test
        ;;
    quick)
        run_quick_test
        ;;
    backend)
        print_header
        check_prerequisites
        setup_environment
        start_infrastructure
        start_backend
        test_backend_api
        show_summary
        ;;
    frontend)
        print_header
        check_prerequisites
        start_frontend
        test_frontend
        show_summary
        ;;
    cleanup)
        print_header
        cleanup
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        ;;
esac

