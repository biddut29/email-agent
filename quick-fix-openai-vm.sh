#!/bin/bash
# Quick fix: Install openai package in running container

echo "🔧 Quick Fix: Installing openai package in Docker container"
echo "=========================================================="
echo ""

cd /opt/email-agent || exit 1

echo "Installing openai package..."
sudo docker exec email-agent-backend-dev pip install openai 2>&1 | tail -3

echo ""
echo "Restarting backend..."
sudo docker-compose -f docker-compose.dev.yml restart backend

echo ""
echo "Waiting for backend to start..."
sleep 10

echo ""
echo "Testing AI Agent..."
sudo docker exec email-agent-backend-dev python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app')
from ai_agent import AIAgent
import config
agent = AIAgent(provider=config.AI_PROVIDER)
if agent.client:
    print("✅ AI is working!")
else:
    print("❌ Still not working")
PYEOF

echo ""
echo "✅ Quick fix complete"
echo ""
echo "Note: This fix is temporary. For a permanent fix, rebuild the Docker image:"
echo "  sudo docker-compose -f docker-compose.dev.yml build backend"
echo "  sudo docker-compose -f docker-compose.dev.yml up -d backend"

