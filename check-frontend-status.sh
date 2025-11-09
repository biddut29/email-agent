#!/bin/bash
# Frontend Status Check Script
# Run this on the VM to diagnose frontend issues

echo "=== Frontend Container Status ==="
cd /opt/email-agent || { echo "Error: /opt/email-agent not found"; exit 1; }
sudo docker-compose -f docker-compose.dev.yml ps frontend

echo ""
echo "=== Frontend Container Logs (last 50 lines) ==="
sudo docker-compose -f docker-compose.dev.yml logs --tail=50 frontend

echo ""
echo "=== Checking if port 3000 is listening ==="
if command -v ss &> /dev/null; then
  sudo ss -tlnp | grep ':3000' || echo "Port 3000 is NOT listening"
elif command -v netstat &> /dev/null; then
  sudo netstat -tlnp | grep ':3000' || echo "Port 3000 is NOT listening"
fi

echo ""
echo "=== Testing localhost:3000 from within VM ==="
curl -f -s --max-time 5 http://localhost:3000/ > /dev/null 2>&1 && echo "✅ Frontend is responding on localhost:3000" || echo "❌ Frontend is NOT responding on localhost:3000"

echo ""
echo "=== Checking if .next directory exists in container ==="
sudo docker exec email-agent-frontend-dev ls -la /app/.next 2>/dev/null | head -10 || echo "❌ .next directory not found in container"

echo ""
echo "=== Checking Nginx error logs ==="
sudo tail -20 /var/log/nginx/error.log 2>/dev/null || echo "Nginx error log not accessible"

echo ""
echo "=== Frontend Container Environment ==="
sudo docker exec email-agent-frontend-dev env | grep -E "NODE_ENV|NEXT_PUBLIC" || echo "Could not get environment variables"

