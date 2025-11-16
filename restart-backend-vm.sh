#!/bin/bash
# Script to restart backend on VM via SSH

VM_HOST="${VM_HOST:-74.225.21.182}"
VM_USER="${VM_USER:-bidduthossain}"
VM_PASSWORD="${VM_PASSWORD:-Biddut@0okmMKO)}"

echo "🔄 Restarting backend on VM: $VM_HOST"

sshpass -p "$VM_PASSWORD" ssh -o StrictHostKeyChecking=no $VM_USER@$VM_HOST << 'RESTART_SCRIPT'
  cd /opt/email-agent
  
  echo "📦 Pulling latest code from dev branch..."
  git fetch origin dev
  git reset --hard origin/dev
  
  echo "🔄 Recreating backend container..."
  sudo docker-compose -f docker-compose.dev.yml up -d --force-recreate --no-deps backend
  
  echo "⏳ Waiting for backend to start..."
  sleep 10
  
  echo "📊 Backend container status:"
  sudo docker-compose -f docker-compose.dev.yml ps backend
  
  echo ""
  echo "📋 Backend logs (last 20 lines):"
  sudo docker-compose -f docker-compose.dev.yml logs --tail=20 backend
  
  echo ""
  echo "✅ Backend restart complete!"
RESTART_SCRIPT

echo "✅ Done!"


