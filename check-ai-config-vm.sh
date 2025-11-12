#!/bin/bash
# Script to check AI configuration and diagnose why template responses are used

echo "🔍 AI Configuration Diagnostic"
echo "=============================="
echo ""

cd /opt/email-agent || exit 1

echo "1️⃣ Checking Backend/.env for AI configuration:"
echo "-----------------------------------------------"
if [ -f "Backend/.env" ]; then
    echo "✅ Backend/.env exists"
    echo ""
    echo "AI-related variables:"
    grep -E '^AI_PROVIDER|^AZURE_OPENAI' Backend/.env | sed 's/=.*/=***/' | head -6
else
    echo "❌ Backend/.env does NOT exist!"
fi
echo ""

echo "2️⃣ Checking backend container environment:"
echo "---------------------------------------------"
sudo docker exec email-agent-backend-dev env 2>/dev/null | grep -E '^AI_PROVIDER|^AZURE_OPENAI' | sed 's/=.*/=***/' | head -6
echo ""

echo "3️⃣ Testing AI Agent initialization from container:"
echo "---------------------------------------------------"
sudo docker exec email-agent-backend-dev python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app')
print("Testing AI Agent initialization...")
print("=" * 60)
try:
    import config
    print(f"Config loaded:")
    print(f"  AI_PROVIDER: {config.AI_PROVIDER}")
    print(f"  AZURE_OPENAI_KEY: {'SET' if config.AZURE_OPENAI_KEY else 'NOT SET'} ({len(config.AZURE_OPENAI_KEY) if config.AZURE_OPENAI_KEY else 0} chars)")
    print(f"  AZURE_OPENAI_ENDPOINT: {config.AZURE_OPENAI_ENDPOINT}")
    print(f"  AZURE_OPENAI_DEPLOYMENT: {config.AZURE_OPENAI_DEPLOYMENT}")
    print("")
    
    # Try to initialize AI Agent
    from ai_agent import AIAgent
    print("Initializing AIAgent...")
    ai_agent = AIAgent(provider=config.AI_PROVIDER)
    print(f"  Provider: {ai_agent.provider}")
    print(f"  Client: {'SET' if ai_agent.client else 'NOT SET (None)'}")
    print(f"  Azure Deployment: {ai_agent.azure_deployment}")
    print("")
    
    if ai_agent.client:
        print("✅ AI Agent client is initialized - AI should work!")
    else:
        print("❌ AI Agent client is None - will use template responses")
        print("")
        print("Possible reasons:")
        print("  1. AZURE_OPENAI_KEY is missing or empty")
        print("  2. AZURE_OPENAI_ENDPOINT is missing or empty")
        print("  3. AI_PROVIDER doesn't match 'azure'")
        print("  4. Client initialization failed (check logs)")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
PYEOF

echo ""
echo "4️⃣ Checking backend logs for AI initialization:"
echo "-------------------------------------------------"
sudo docker-compose -f docker-compose.dev.yml logs backend --tail=200 | grep -iE 'ai.*agent|azure.*openai|provider|endpoint|client.*initialized|test.*successful|ai.*client.*none|template.*response' | tail -20

echo ""
echo "5️⃣ Testing generate_response with a test email:"
echo "-----------------------------------------------"
sudo docker exec email-agent-backend-dev python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app')
try:
    from ai_agent import AIAgent
    import config
    
    print("Creating test email...")
    test_email = {
        'subject': 'Test',
        'from': 'test@example.com',
        'text_body': 'How are you?',
        'to': 'test@example.com'
    }
    
    print("Initializing AI Agent...")
    ai_agent = AIAgent(provider=config.AI_PROVIDER)
    
    print(f"Client status: {'SET' if ai_agent.client else 'NOT SET'}")
    print("")
    print("Generating response...")
    response = ai_agent.generate_response(test_email, tone="professional")
    print("")
    print("Response:")
    print("-" * 60)
    print(response)
    print("-" * 60)
    print("")
    if "template" in response.lower() or "thank you" in response.lower():
        print("⚠️  This looks like a template response, not AI-generated")
    else:
        print("✅ This looks like an AI-generated response")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
PYEOF

echo ""
echo "=============================="
echo "✅ Diagnostic complete"

