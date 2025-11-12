#!/bin/bash
# Complete solution to fix AI issue on VM

echo "🔧 Solving AI Issue on VM"
echo "========================"
echo ""

cd /opt/email-agent || exit 1

echo "1️⃣ Installing openai package in Docker container..."
echo "----------------------------------------------------"
if sudo docker exec email-agent-backend-dev pip install openai 2>&1 | tail -3; then
    echo "✅ Package installation completed"
else
    echo "❌ Package installation failed"
    exit 1
fi
echo ""

echo "2️⃣ Verifying openai package installation..."
echo "--------------------------------------------"
if sudo docker exec email-agent-backend-dev python3 -c "import openai; print('✅ OpenAI version:', openai.__version__)" 2>&1; then
    echo "✅ Package is installed"
else
    echo "❌ Package verification failed"
    exit 1
fi
echo ""

echo "3️⃣ Restarting backend..."
echo "------------------------"
sudo docker-compose -f docker-compose.dev.yml restart backend
echo "✅ Backend restarted"
echo ""

echo "4️⃣ Waiting for backend to start..."
echo "-----------------------------------"
sleep 10
echo ""

echo "5️⃣ Testing AI Agent initialization..."
echo "-------------------------------------"
sudo docker exec email-agent-backend-dev python3 << 'PYEOF'
import sys
sys.path.insert(0, '/app')
print('=' * 60)
print('Testing AI Configuration')
print('=' * 60)
print('')

try:
    # Check openai package
    import openai
    print('✅ OpenAI package:', openai.__version__)
    print('')
    
    # Check config
    import config
    print('Configuration:')
    print('  AI_PROVIDER:', config.AI_PROVIDER)
    print('  AZURE_OPENAI_KEY:', 'SET' if config.AZURE_OPENAI_KEY else 'NOT SET')
    print('  AZURE_OPENAI_ENDPOINT:', config.AZURE_OPENAI_ENDPOINT)
    print('  AZURE_OPENAI_DEPLOYMENT:', config.AZURE_OPENAI_DEPLOYMENT)
    print('')
    
    # Test AI Agent
    from ai_agent import AIAgent
    print('Initializing AIAgent...')
    agent = AIAgent(provider=config.AI_PROVIDER)
    print('  Provider:', agent.provider)
    print('  Client:', 'SET ✅' if agent.client else 'NOT SET ❌')
    print('')
    
    if agent.client:
        print('Testing API call...')
        response = agent.client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=[{'role': 'user', 'content': 'Say hello'}],
            max_tokens=5
        )
        print('✅ API call successful!')
        print('Response:', response.choices[0].message.content)
        print('')
        print('=' * 60)
        print('✅ AI IS NOW WORKING!')
        print('=' * 60)
    else:
        print('=' * 60)
        print('❌ AI client is still None')
        print('Check logs for initialization errors')
        print('=' * 60)
except Exception as e:
    print('❌ Error:', e)
    import traceback
    traceback.print_exc()
PYEOF

echo ""
echo "6️⃣ Checking backend logs for AI initialization..."
echo "--------------------------------------------------"
sudo docker-compose -f docker-compose.dev.yml logs backend --tail=100 | grep -iE 'ai.*agent|azure.*openai|client.*initialized|test.*successful' | tail -10

echo ""
echo "========================"
echo "✅ Solution complete!"
echo ""
echo "If AI is working, you should now get real AI responses"
echo "instead of template responses when generating email replies."

