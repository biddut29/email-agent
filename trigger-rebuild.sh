#!/bin/bash

# Trigger a rebuild on the VM to pick up version changes

VM_HOST="${VM_HOST:-74.225.21.182}"
VM_USER="${VM_USER:-bidduthossain}"
VM_PASSWORD="${VM_PASSWORD:-Biddut@0okmMKO)}"

echo "🔄 Triggering rebuild on VM..."
echo ""

sshpass -p "$VM_PASSWORD" ssh -o StrictHostKeyChecking=no $VM_USER@$VM_HOST << 'REBUILD_SCRIPT'
set -e

cd /opt/email-agent

echo "📥 Pulling latest code..."
git fetch origin
git checkout dev
git reset --hard origin/dev

echo ""
echo "🔨 Rebuilding frontend (to include version.ts)..."
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
export NEXT_PUBLIC_API_URL=https://emailagent.duckdns.org

sudo docker-compose -f docker-compose.dev.yml build --no-cache frontend

echo ""
echo "🔄 Recreating frontend container..."
sudo docker-compose -f docker-compose.dev.yml up -d --force-recreate frontend

echo ""
echo "🔄 Restarting backend (to pick up __version__.py)..."
sudo docker-compose -f docker-compose.dev.yml restart backend

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

echo ""
echo "✅ Rebuild complete!"
echo ""
echo "Checking versions..."
echo "Backend version:"
curl -s http://localhost:8000/api/health | python3 -m json.tool 2>/dev/null | grep version || echo "Could not fetch"

REBUILD_SCRIPT

echo ""
echo "✅ Rebuild triggered!"

