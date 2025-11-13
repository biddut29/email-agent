#!/bin/bash
# Script to fix Azure OpenAI endpoint on VM

echo "🔧 Fixing Azure OpenAI endpoint on VM..."
echo ""

cd /opt/email-agent || exit 1

# Current endpoint (full API URL - incorrect)
CURRENT_ENDPOINT=$(grep '^AZURE_OPENAI_ENDPOINT=' Backend/.env | cut -d'=' -f2-)

echo "Current endpoint: $CURRENT_ENDPOINT"
echo ""

# Extract base endpoint (remove /openai/deployments/... path)
BASE_ENDPOINT="https://email-agent-test-ai-foundry.cognitiveservices.azure.com/"

echo "Updating to base endpoint: $BASE_ENDPOINT"
echo ""

# Update .env file
sed -i "s|AZURE_OPENAI_ENDPOINT=.*|AZURE_OPENAI_ENDPOINT=$BASE_ENDPOINT|" Backend/.env
sed -i "s|AZURE_OPENAI_ENDPOINT=.*|AZURE_OPENAI_ENDPOINT=$BASE_ENDPOINT|" Backend/.env.dev

echo "✅ Endpoint updated in both .env and .env.dev files"
echo ""

# Verify
echo "📋 Updated endpoint:"
grep '^AZURE_OPENAI_ENDPOINT=' Backend/.env
echo ""

# Recreate backend container
echo "🔄 Recreating backend container..."
sudo docker-compose -f docker-compose.dev.yml up -d --force-recreate backend

echo ""
echo "✅ Backend container recreated with fixed endpoint"
echo ""
echo "🧪 Testing Azure OpenAI connection..."
sleep 5

sudo docker exec email-agent-backend-dev python3 << 'PYEOF'
import os
from openai import AzureOpenAI

key = os.getenv('AZURE_OPENAI_KEY')
endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4.1-mini')
api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-12-01-preview')

print(f'Key: {"SET" if key else "NOT SET"}')
print(f'Endpoint: {endpoint}')
print(f'Deployment: {deployment}')

if key and endpoint:
    try:
        client = AzureOpenAI(
            api_key=key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        print('✅ Client initialized successfully')
        
        response = client.chat.completions.create(
            model=deployment,
            messages=[{'role': 'user', 'content': 'Say hello'}],
            max_tokens=10
        )
        print(f'✅ API call successful: {response.choices[0].message.content}')
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
else:
    print('❌ Missing credentials')
PYEOF

