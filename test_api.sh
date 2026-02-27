#!/bin/bash

# Quick Start Script - Test the API locally
# Usage: ./test_api.sh

echo "🧪 Testing Plan-Execute Agent API"
echo "=================================="

# Base URL
BASE_URL="http://localhost:8000"

echo -e "\n1️⃣  Testing root endpoint..."
curl -s $BASE_URL/ | python -m json.tool

echo -e "\n\n2️⃣  Testing health check..."
curl -s $BASE_URL/health | python -m json.tool

echo -e "\n\n3️⃣  Testing task execution (simple math)..."
curl -s -X POST $BASE_URL/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Calculate the compound interest on $10,000 at 5% annual rate for 3 years",
    "user_id": "test_user"
  }' | python -m json.tool

echo -e "\n\n4️⃣  Testing task execution (research task)..."
curl -s -X POST $BASE_URL/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Search for the latest developments in Large Language Models and summarize the key trends",
    "user_id": "test_user"
  }' | python -m json.tool

echo -e "\n\n✅ Testing complete!"
