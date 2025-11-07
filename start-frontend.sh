#!/bin/bash

echo "🚀 Starting Email Agent Frontend..."
echo "==================================="

cd Frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Start the development server
echo ""
echo "✅ Starting Next.js development server on http://localhost:3000"
echo ""
npm run dev

