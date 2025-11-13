#!/bin/bash
# Script to check configuration on VM

echo "🔍 Checking VM Configuration..."
echo "=================================="
echo ""

# Check if .env files exist
echo "📁 Checking .env files:"
if [ -f "/opt/email-agent/Backend/.env" ]; then
    echo "✅ Backend/.env exists"
    echo "   Size: $(ls -lh /opt/email-agent/Backend/.env | awk '{print $5}')"
    echo "   First few lines (non-empty, non-comment):"
    grep -v "^#" /opt/email-agent/Backend/.env | grep -v "^$" | head -5 | sed 's/^/     /'
else
    echo "❌ Backend/.env does NOT exist"
fi

if [ -f "/opt/email-agent/Backend/.env.dev" ]; then
    echo "✅ Backend/.env.dev exists"
else
    echo "⚠️  Backend/.env.dev does NOT exist (optional)"
fi

echo ""

# Check Docker containers
echo "🐳 Checking Docker containers:"
cd /opt/email-agent 2>/dev/null || { echo "❌ Cannot access /opt/email-agent"; exit 1; }
sudo docker-compose -f docker-compose.dev.yml ps 2>/dev/null || echo "⚠️  Docker Compose not running"

echo ""

# Check if containers are using .env files
echo "📋 Checking container environment variables:"
echo "Backend container env vars (sample):"
sudo docker exec email-agent-backend-dev env 2>/dev/null | grep -E "AZURE_OPENAI|GOOGLE_CLIENT|MONGODB_URI" | head -5 || echo "❌ Cannot access backend container"

echo ""

# Check backend logs for config loading
echo "📝 Checking backend logs for config loading:"
sudo docker-compose -f docker-compose.dev.yml logs backend 2>/dev/null | grep -iE "config|env|azure|google" | tail -10 || echo "⚠️  Cannot access logs"

echo ""

# Test backend health
echo "🏥 Testing backend health:"
curl -s http://localhost:8000/api/health 2>/dev/null | head -3 || echo "❌ Backend not responding"

echo ""
echo "=================================="
echo "✅ Configuration check complete"

