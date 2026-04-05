#!/bin/bash
# Sample curl commands for testing the Company State RAG Trading Bot API
# Usage: bash sample_curl_commands.sh

BASE_URL="http://127.0.0.1:8000"

echo "================================"
echo "Company State RAG Trading Bot API Tests"
echo "================================"
echo ""

# Test 1: Health Check
echo "[1] Health Check"
curl -X GET "$BASE_URL/health" | jq .
echo ""
echo ""

# Test 2: Ingest News - Apple Earnings
echo "[2] Ingest News - Apple Earnings"
RESPONSE=$(curl -s -X POST "$BASE_URL/ingest_news" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "sample_apple_earnings",
    "source": "Bloomberg",
    "published_at": "2024-02-13T09:30:00Z",
    "title": "Apple Beats Q1 2024 Earnings, Raises Guidance",
    "content": "Apple Inc. reported Q1 2024 earnings that exceeded analyst expectations, with revenue of $84.3 billion, up 5% year-over-year. EPS came in at $2.18, beating estimates of $2.10. CEO Tim Cook stated: \"We are optimistic about the iPhone 15 Pro demand and our services business continues to grow.\" The company raised full-year revenue guidance to $380-390 billion. Stock ticker: AAPL. Analysts are raising price targets on the strong results."
  }')
echo "$RESPONSE" | jq .
NEWS_ID=$(echo "$RESPONSE" | jq -r '.news_id')
echo "Extracted News ID: $NEWS_ID"
echo ""
echo ""

# Test 3: Ingest News - Google Regulatory
echo "[3] Ingest News - Google Regulatory Investigation"
RESPONSE=$(curl -s -X POST "$BASE_URL/ingest_news" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "sample_google_regulatory",
    "source": "Reuters",
    "published_at": "2024-02-13T14:00:00Z",
    "title": "Google Faces Regulatory Scrutiny Over AI Search",
    "content": "Alphabet Inc. (ticker: GOOGL) is facing renewed regulatory scrutiny from the SEC regarding its AI-powered search features. Regulators are concerned about potential antitrust issues and user privacy implications. An investigation has been announced by the Department of Justice. Google stated it is cooperating fully with regulators. This could significantly impact Google'\''s ability to roll out advanced AI features."
  }')
echo "$RESPONSE" | jq .
NEWS_ID_2=$(echo "$RESPONSE" | jq -r '.news_id')
echo "Extracted News ID: $NEWS_ID_2"
echo ""
echo ""

# Test 4: Analyze News - Apple
echo "[4] Analyze News - Apple"
curl -s -X POST "$BASE_URL/analyze_news/sample_apple_earnings" | jq .
echo ""
echo ""

# Test 5: Analyze News - Google
echo "[5] Analyze News - Google"
curl -s -X POST "$BASE_URL/analyze_news/sample_google_regulatory" | jq .
echo ""
echo ""

# Test 6: Get State - AAPL
echo "[6] Get Current State - AAPL"
curl -s -X GET "$BASE_URL/state/AAPL" | jq .
echo ""
echo ""

# Test 7: Get State - GOOGL
echo "[7] Get Current State - GOOGL"
curl -s -X GET "$BASE_URL/state/GOOGL" | jq .
echo ""
echo ""

# Test 8: Get Events - AAPL (Open)
echo "[8] Get Events - AAPL (Open Events Only)"
curl -s -X GET "$BASE_URL/events/AAPL?status=open" | jq .
echo ""
echo ""

# Test 9: Get Events - GOOGL (All)
echo "[9] Get Events - GOOGL (All Events)"
curl -s -X GET "$BASE_URL/events/GOOGL" | jq .
echo ""
echo ""

# Test 10: Get Audit Record
echo "[10] Get Audit Record #1"
curl -s -X GET "$BASE_URL/audit/1" | jq .
echo ""
echo ""

echo "================================"
echo "All tests completed!"
echo "================================"
