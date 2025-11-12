#!/bin/bash
# Script to check Docker container environment variables

echo "🔍 Docker Container Environment Check"
echo "======================================"
echo ""

cd /opt/email-agent || exit 1

echo "1️⃣ Checking Backend Container Environment Variables:"
echo "------------------------------------------------------"
sudo docker exec email-agent-backend-dev env | grep -E '^AI_PROVIDER|^AZURE_OPENAI' | sort
echo ""

echo "2️⃣ Checking if variables are set (not empty):"
echo "-----------------------------------------------"
sudo docker exec email-agent-backend-dev sh -c '
echo "AI_PROVIDER: [${AI_PROVIDER:-NOT SET}]"
if [ -n "$AZURE_OPENAI_KEY" ]; then
    echo "AZURE_OPENAI_KEY: SET (${#AZURE_OPENAI_KEY} chars)"
else
    echo "AZURE_OPENAI_KEY: NOT SET"
fi
echo "AZURE_OPENAI_ENDPOINT: [${AZURE_OPENAI_ENDPOINT:-NOT SET}]"
echo "AZURE_OPENAI_DEPLOYMENT: [${AZURE_OPENAI_DEPLOYMENT:-NOT SET}]"
echo "AZURE_OPENAI_API_VERSION: [${AZURE_OPENAI_API_VERSION:-NOT SET}]"
'
echo ""

echo "3️⃣ Testing Python config loading from container:"
echo "--------------------------------------------------"
sudo docker exec email-agent-backend-dev python3 << 'PYEOF'
import os
print("Environment variables (from Docker):")
print("  AI_PROVIDER:", os.getenv('AI_PROVIDER', 'NOT SET'))
azure_key = os.getenv('AZURE_OPENAI_KEY', '')
print("  AZURE_OPENAI_KEY:", f'SET ({len(azure_key)} chars)' if azure_key else 'NOT SET')
azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', '')
print("  AZURE_OPENAI_ENDPOINT:", azure_endpoint[:60] if azure_endpoint else 'NOT SET')
print("  AZURE_OPENAI_DEPLOYMENT:", os.getenv('AZURE_OPENAI_DEPLOYMENT', 'NOT SET'))
print("  AZURE_OPENAI_API_VERSION:", os.getenv('AZURE_OPENAI_API_VERSION', 'NOT SET'))
print("")
print("Loading config module (reads from .env files):")
import sys
sys.path.insert(0, '/app')
import config
print("Config module values (from .env files):")
print("  AI_PROVIDER:", config.AI_PROVIDER)
print("  AZURE_OPENAI_KEY:", f'SET ({len(config.AZURE_OPENAI_KEY)} chars)' if config.AZURE_OPENAI_KEY else 'NOT SET')
print("  AZURE_OPENAI_ENDPOINT:", config.AZURE_OPENAI_ENDPOINT[:60] if config.AZURE_OPENAI_ENDPOINT else 'NOT SET')
print("  AZURE_OPENAI_DEPLOYMENT:", config.AZURE_OPENAI_DEPLOYMENT)
print("  AZURE_OPENAI_API_VERSION:", config.AZURE_OPENAI_API_VERSION)
print("")
print("Comparison:")
env_has_key = bool(os.getenv('AZURE_OPENAI_KEY'))
config_has_key = bool(config.AZURE_OPENAI_KEY)
if env_has_key != config_has_key:
    print("  ⚠️  Mismatch: Docker env has key:", env_has_key, "but config module has key:", config_has_key)
else:
    print("  ✅ Docker env and config module match")
PYEOF

echo ""
echo "4️⃣ Checking .env files on host:"
echo "--------------------------------"
echo "Backend/.env (should be primary):"
if [ -f "Backend/.env" ]; then
    grep -E '^AI_PROVIDER|^AZURE_OPENAI' Backend/.env | sed 's/=.*/=***/' | head -6
else
    echo "  ❌ Backend/.env does NOT exist!"
fi
echo ""
echo "Backend/.env.dev (override file):"
if [ -f "Backend/.env.dev" ]; then
    grep -E '^AI_PROVIDER|^AZURE_OPENAI' Backend/.env.dev | sed 's/=.*/=***/' | head -6
else
    echo "  (Backend/.env.dev does not exist - this is OK)"
fi
echo ""

echo "5️⃣ Checking docker-compose env_file configuration:"
echo "---------------------------------------------------"
echo "Backend service env_file:"
grep -A 10 'backend:' docker-compose.dev.yml | grep -A 5 'env_file:' | grep -E 'env_file|\.env'
echo ""

echo "6️⃣ Testing AI Agent initialization:"
echo "------------------------------------"
sudo docker exec email-agent-backend-dev python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app')
try:
    import config
    from ai_agent import AIAgent
    
    print("Initializing AIAgent with provider:", config.AI_PROVIDER)
    ai_agent = AIAgent(provider=config.AI_PROVIDER)
    
    print(f"  Provider: {ai_agent.provider}")
    print(f"  Client: {'SET ✅' if ai_agent.client else 'NOT SET ❌'}")
    print(f"  Azure Deployment: {ai_agent.azure_deployment}")
    
    if ai_agent.client:
        print("")
        print("✅ AI client is initialized - AI should work!")
    else:
        print("")
        print("❌ AI client is None - will use template responses")
        print("")
        print("Diagnosis:")
        print("  - Check if AZURE_OPENAI_KEY is set in .env")
        print("  - Check if AZURE_OPENAI_ENDPOINT is set in .env")
        print("  - Check if AI_PROVIDER is 'azure'")
        print("  - Check backend logs for initialization errors")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
PYEOF

echo ""
echo "======================================"
echo "✅ Check complete"

