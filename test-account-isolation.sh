#!/bin/bash

# Test Account Isolation
# This script tests if the session-based account isolation is working

echo "🧪 Testing Account Isolation..."
echo ""

# Replace these with your actual session tokens
ACCOUNT_2_TOKEN=".eJw9yTsKgDAMANCrSGaVtGLFTh7CXWIbSsG2IHES7-5ncH3vB..."  # biddutagentai@gmail.com
ACCOUNT_3_TOKEN=".eJw9yTsKgDAMANCrSGaVxKpoJw_hLrENUrAVJE7i3f0Mru-dw..."  # biddutagent@gmail.com

echo "📧 Testing Account 3 (biddutagent@gmail.com) session..."
curl -s "http://localhost:8000/api/auth/me" \
  -H "Cookie: session_token=$ACCOUNT_3_TOKEN" | jq .

echo ""
echo "📬 Fetching emails for Account 3..."
curl -s "http://localhost:8000/api/mongodb/emails?limit=5&date_from=2025-10-17" \
  -H "Cookie: session_token=$ACCOUNT_3_TOKEN" | jq '.emails | length, .[0].subject'

echo ""
echo "📊 Email count for Account 3..."
curl -s "http://localhost:8000/api/mongodb/emails/count?date_from=2025-10-17" \
  -H "Cookie: session_token=$ACCOUNT_3_TOKEN" | jq .

echo ""
echo "✅ Test complete! Check if the emails belong to the correct account."

