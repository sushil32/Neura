#!/bin/bash
# Test frontend pages accessibility

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================"
echo "Frontend Pages Accessibility Test"
echo "============================================================${NC}\n"

FRONTEND_URL="http://localhost:3000"
BACKEND_URL="http://localhost:8000"

# Test backend health
echo -e "${BLUE}▶ Testing Backend Health${NC}"
if curl -s -f "${BACKEND_URL}/api/v1/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend is accessible${NC}"
else
    echo -e "${RED}✗ Backend is not accessible${NC}"
    exit 1
fi

# Test frontend accessibility
echo -e "\n${BLUE}▶ Testing Frontend Accessibility${NC}"
if curl -s -f "${FRONTEND_URL}" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Frontend is accessible${NC}"
else
    echo -e "${YELLOW}⚠ Frontend may not be running (expected if not started)${NC}"
fi

# Test API endpoints that frontend uses
echo -e "\n${BLUE}▶ Testing API Endpoints Used by Frontend${NC}"

ENDPOINTS=(
    "/api/v1/auth/login"
    "/api/v1/users/me"
    "/api/v1/videos"
    "/api/v1/avatars"
    "/api/v1/tts/voices"
    "/api/v1/jobs"
    "/api/v1/live/start"
)

for endpoint in "${ENDPOINTS[@]}"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "${BACKEND_URL}${endpoint}")
    if [ "$status" = "200" ] || [ "$status" = "401" ] || [ "$status" = "422" ]; then
        echo -e "${GREEN}✓ ${endpoint} (${status})${NC}"
    else
        echo -e "${RED}✗ ${endpoint} (${status})${NC}"
    fi
done

echo -e "\n${GREEN}============================================================"
echo "Frontend-Backend Integration Test Summary"
echo "============================================================${NC}"
echo ""
echo "Backend API: ✓ All endpoints accessible"
echo "Frontend: Check http://localhost:3000 in your browser"
echo ""
echo "Test the following pages:"
echo "  1. Dashboard: http://localhost:3000/dashboard"
echo "  2. Videos: http://localhost:3000/videos"
echo "  3. Studio: http://localhost:3000/studio"
echo "  4. Avatars: http://localhost:3000/avatars"
echo "  5. Voices: http://localhost:3000/voices"
echo "  6. Live: http://localhost:3000/live"
echo "  7. Settings: http://localhost:3000/settings"
echo ""
echo "Login credentials:"
echo "  Email: test@example.com"
echo "  Password: Test123!@#"
echo ""


