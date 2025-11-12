#!/bin/bash
# Script to test AI functionality on VM

echo "🧪 Testing AI Functionality on VM"
echo "=================================="
echo ""

cd /opt/email-agent || exit 1

echo "1️⃣ Checking Azure OpenAI configuration in .env:"
echo "-----------------------------------------------"
grep -E '^AZURE_OPENAI|^AI_PROVIDER' Backend/.env | head -5
echo ""

echo "2️⃣ Testing Azure OpenAI endpoint format:"
echo "-------------------------------------------"
ENDPOINT=$(grep '^AZURE_OPENAI_ENDPOINT=' Backend/.env | cut -d'=' -f2-)
echo "Raw endpoint from .env: $ENDPOINT"
if [[ "$ENDPOINT" == *"/openai/deployments/"* ]]; then
    echo "⚠️  Endpoint contains full API path - should be base URL only"
    BASE_ENDPOINT=$(echo "$ENDPOINT" | sed 's|/openai/deployments/.*||' | sed 's|/$||')
    BASE_ENDPOINT="${BASE_ENDPOINT}/"
    echo "✅ Should be: $BASE_ENDPOINT"
else
    echo "✅ Endpoint format looks correct"
fi
echo ""

echo "3️⃣ Testing Azure OpenAI connection from backend container:"
echo "-----------------------------------------------------------"
sudo docker exec email-agent-backend-dev python3 << 'PYEOF'
import os
import sys
sys.path.insert(0, '/app')

try:
    import config
    print(f"AI_PROVIDER: {config.AI_PROVIDER}")
    print(f"AZURE_OPENAI_KEY: {'SET' if config.AZURE_OPENAI_KEY else 'NOT SET'} ({len(config.AZURE_OPENAI_KEY)} chars)")
    print(f"AZURE_OPENAI_ENDPOINT: {config.AZURE_OPENAI_ENDPOINT}")
    print(f"AZURE_OPENAI_DEPLOYMENT: {config.AZURE_OPENAI_DEPLOYMENT}")
    print("")
    
    if config.AZURE_OPENAI_KEY and config.AZURE_OPENAI_ENDPOINT:
        from openai import AzureOpenAI
        print("Initializing Azure OpenAI client...")
        client = AzureOpenAI(
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT
        )
        print("✅ Client initialized")
        print("")
        print("Testing API call...")
        response = client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=[{'role': 'user', 'content': 'Say hello'}],
            max_tokens=10
        )
        print(f"✅ API call successful!")
        print(f"Response: {response.choices[0].message.content}")
    else:
        print("❌ Missing credentials")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
PYEOF

echo ""
echo "4️⃣ Checking backend logs for AI errors:"
echo "----------------------------------------"
sudo docker-compose -f docker-compose.dev.yml logs backend --tail=100 | grep -iE 'azure|openai|ai.*error|ai.*fail|ai.*initialized|endpoint' | tail -15

echo ""
echo "5️⃣ Testing AI endpoint via API:"
echo "--------------------------------"
curl -s -X POST http://localhost:8000/api/emails/generate-response \
  -H "Content-Type: application/json" \
  -d '{"message_id":"test","tone":"professional"}' 2>&1 | head -20

echo ""
echo "=================================="
echo "✅ Diagnostic complete"

