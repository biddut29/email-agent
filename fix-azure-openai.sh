#!/bin/bash
# Script to fix Azure OpenAI configuration and install openai package

echo "🔧 Fixing Azure OpenAI Configuration"
echo "===================================="
echo ""

cd /opt/email-agent || exit 1

echo "1️⃣ Checking if openai package is installed:"
echo "--------------------------------------------"
if sudo docker exec email-agent-backend-dev python3 -c "import openai; print('✅ OpenAI version:', openai.__version__)" 2>/dev/null; then
    echo "✅ OpenAI package is already installed"
else
    echo "❌ OpenAI package NOT installed"
    echo ""
    echo "Installing openai package..."
    sudo docker exec email-agent-backend-dev pip install openai 2>&1 | tail -5
    echo ""
    if sudo docker exec email-agent-backend-dev python3 -c "import openai" 2>/dev/null; then
        echo "✅ OpenAI package installed successfully"
    else
        echo "❌ Failed to install openai package"
        exit 1
    fi
fi
echo ""

echo "2️⃣ Checking Azure OpenAI configuration:"
echo "-----------------------------------------"
sudo docker exec email-agent-backend-dev python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app')
import config
print("Configuration:")
print("  AI_PROVIDER:", config.AI_PROVIDER)
print("  AZURE_OPENAI_KEY:", "SET" if config.AZURE_OPENAI_KEY else "NOT SET", f"({len(config.AZURE_OPENAI_KEY)} chars)" if config.AZURE_OPENAI_KEY else "")
print("  AZURE_OPENAI_ENDPOINT:", config.AZURE_OPENAI_ENDPOINT)
print("  AZURE_OPENAI_DEPLOYMENT:", config.AZURE_OPENAI_DEPLOYMENT)
print("  AZURE_OPENAI_API_VERSION:", config.AZURE_OPENAI_API_VERSION)
print("")
if not config.AZURE_OPENAI_KEY or not config.AZURE_OPENAI_ENDPOINT:
    print("❌ Missing Azure OpenAI credentials")
    exit(1)
else:
    print("✅ Azure OpenAI credentials are configured")
PYEOF

echo ""
echo "3️⃣ Testing Azure OpenAI client initialization:"
echo "-----------------------------------------------"
sudo docker exec email-agent-backend-dev python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app')
import config
from openai import AzureOpenAI

print("Initializing Azure OpenAI client...")
try:
    client = AzureOpenAI(
        api_key=config.AZURE_OPENAI_KEY,
        api_version=config.AZURE_OPENAI_API_VERSION,
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT
    )
    print("✅ Client initialized successfully")
    print("")
    print("Testing API call...")
    response = client.chat.completions.create(
        model=config.AZURE_OPENAI_DEPLOYMENT,
        messages=[{'role': 'user', 'content': 'Say hello'}],
        max_tokens=5
    )
    print("✅ API call successful!")
    print("Response:", response.choices[0].message.content)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYEOF

if [ $? -eq 0 ]; then
    echo ""
    echo "4️⃣ Restarting backend to apply changes:"
    echo "---------------------------------------"
    sudo docker-compose -f docker-compose.dev.yml restart backend
    sleep 10
    echo "✅ Backend restarted"
    echo ""
    echo "5️⃣ Testing AI Agent after restart:"
    echo "-----------------------------------"
    sudo docker exec email-agent-backend-dev python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app')
from ai_agent import AIAgent
import config
agent = AIAgent(provider=config.AI_PROVIDER)
if agent.client:
    print("✅ AI Agent client is initialized - AI is working!")
else:
    print("❌ AI Agent client is still None")
PYEOF
fi

echo ""
echo "===================================="
echo "✅ Fix complete"

