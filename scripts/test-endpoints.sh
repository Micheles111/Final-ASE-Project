#!/bin/bash
# scripts/test-endpoints.sh

echo "🔍 Testing Service Health..."

# Gateway (HTTPS)
echo -n "API Gateway: "
curl -k -s -o /dev/null -w "%{http_code}" https://localhost:5000/health
echo " (Expected: 200)"

# Frontend (HTTP)
echo -n "Frontend UI: "
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/
echo " (Expected: 200)"

# Auth Service Check (via Gateway)
echo -n "Auth Service: "
curl -k -s -o /dev/null -w "%{http_code}" https://localhost:5000/auth/health
echo " (Expected: 200)"

# Player Service Check (via Gateway)
echo -n "Player Service: "
curl -k -s -o /dev/null -w "%{http_code}" https://localhost:5000/players/health
echo " (Expected: 200)"

echo "✅ Quick check complete."