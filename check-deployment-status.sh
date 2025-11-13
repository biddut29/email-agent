#!/bin/bash

# Check deployment status and verify version files are present

VM_HOST="${VM_HOST:-74.225.21.182}"
VM_USER="${VM_USER:-bidduthossain}"
VM_PASSWORD="${VM_PASSWORD:-Biddut@0okmMKO)}"

echo "🔍 Checking deployment status on VM..."
echo ""

sshpass -p "$VM_PASSWORD" ssh -o StrictHostKeyChecking=no $VM_USER@$VM_HOST << 'CHECK_SCRIPT'
set -e

cd /opt/email-agent

echo "=== Git Status ==="
git log --oneline -5
echo ""

echo "=== Version Files Check ==="
if [ -f "Backend/__version__.py" ]; then
  echo "✅ Backend/__version__.py exists:"
  cat Backend/__version__.py
else
  echo "❌ Backend/__version__.py NOT FOUND"
fi
echo ""

if [ -f "Frontend/lib/version.ts" ]; then
  echo "✅ Frontend/lib/version.ts exists:"
  cat Frontend/lib/version.ts
else
  echo "❌ Frontend/lib/version.ts NOT FOUND"
fi
echo ""

echo "=== Container Status ==="
sudo docker-compose -f docker-compose.dev.yml ps
echo ""

echo "=== Backend Version Check ==="
echo "Checking /api/health endpoint for version..."
curl -s http://localhost:8000/api/health | python3 -m json.tool 2>/dev/null | grep -A 1 version || echo "Could not fetch version from API"
echo ""

echo "=== Frontend Build Check ==="
if sudo docker exec email-agent-frontend-dev ls /app/lib/version.ts 2>/dev/null; then
  echo "✅ version.ts exists in frontend container"
  sudo docker exec email-agent-frontend-dev cat /app/lib/version.ts
else
  echo "❌ version.ts NOT FOUND in frontend container"
  echo "Frontend may need to be rebuilt"
fi
echo ""

echo "=== Backend Module Check ==="
if sudo docker exec email-agent-backend-dev python3 -c "from __version__ import __version__; print('Backend version:', __version__)" 2>/dev/null; then
  echo "✅ Backend can import __version__"
else
  echo "❌ Backend cannot import __version__"
  echo "Backend may need to be restarted"
fi

CHECK_SCRIPT

echo ""
echo "✅ Status check complete!"

