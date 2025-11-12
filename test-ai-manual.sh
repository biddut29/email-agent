#!/bin/bash
# Manual AI test script for VM

echo "🧪 Manual AI Test Script"
echo "========================"
echo ""

# Test 1: Check .env file
echo "1️⃣ Checking Backend/.env file:"
echo "-------------------------------"
cd /opt/email-agent
if [ -f "Backend/.env" ]; then
    echo "✅ Backend/.env exists"
    echo ""
    echo "Azure OpenAI config:"
    grep -E '^AZURE_OPENAI|^AI_PROVIDER' Backend/.env | sed 's/=.*/=***/' | head -5
else
    echo "❌ Backend/.env does NOT exist!"
    exit 1
fi
echo ""

# Test 2: Check container environment
echo "2️⃣ Checking container environment:"
echo "-----------------------------------"
sudo docker exec email-agent-backend-dev env 2>/dev/null | grep -E '^AZURE_OPENAI|^AI_PROVIDER' | sed 's/=.*/=***/' | head -5
echo ""

# Test 3: Test AI from container
echo "3️⃣ Testing AI from backend container:"
echo "--------------------------------------"
sudo docker exec email-agent-backend-dev python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app')
print("Testing AI Configuration...")
print("=" * 50)
try:
    import config
    print(f"AI_PROVIDER: {config.AI_PROVIDER}")
    print(f"AZURE_OPENAI_KEY: {'SET' if config.AZURE_OPENAI_KEY else 'NOT SET'} ({len(config.AZURE_OPENAI_KEY) if config.AZURE_OPENAI_KEY else 0} chars)")
    print(f"AZURE_OPENAI_ENDPOINT: {config.AZURE_OPENAI_ENDPOINT}")
    print(f"AZURE_OPENAI_DEPLOYMENT: {config.AZURE_OPENAI_DEPLOYMENT}")
    print("")
    
    if config.AZURE_OPENAI_KEY and config.AZURE_OPENAI_ENDPOINT:
        print("Initializing Azure OpenAI client...")
        from openai import AzureOpenAI
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
            max_tokens=5
        )
        print(f"✅ API call successful!")
        print(f"Response: {response.choices[0].message.content}")
        print("")
        print("=" * 50)
        print("✅ AI IS WORKING!")
    else:
        print("❌ Missing credentials")
        print("   Key:", "SET" if config.AZURE_OPENAI_KEY else "NOT SET")
        print("   Endpoint:", "SET" if config.AZURE_OPENAI_ENDPOINT else "NOT SET")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
PYEOF

echo ""
echo "4️⃣ Checking backend logs for AI initialization:"
echo "-------------------------------------------------"
sudo docker-compose -f docker-compose.dev.yml logs backend --tail=200 | grep -iE 'ai.*agent|azure|openai|provider|endpoint|initialized|test.*successful' | tail -15

echo ""
echo "5️⃣ Testing AI endpoint via API:"
echo "---------------------------------"
curl -s -X POST http://localhost:8000/api/emails/generate-response \
  -H "Content-Type: application/json" \
  -d '{"message_id":"test","tone":"professional"}' 2>&1 | head -10

echo ""
echo "========================"
echo "✅ Test complete"

