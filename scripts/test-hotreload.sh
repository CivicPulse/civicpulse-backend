#!/bin/bash
# Test script to verify hot-reload functionality in Docker development environment

set -e

echo "🔥 Testing hot-reload functionality in Docker environment..."
echo ""

# Check if the web service is running
if ! docker compose ps web | grep -q "Up"; then
    echo "❌ Web service is not running. Please start it first with:"
    echo "   docker compose up -d"
    exit 1
fi

echo "📝 Creating a test file to trigger hot-reload..."

# Create a test view
TEST_FILE="civicpulse/test_hotreload.py"
cat > "$TEST_FILE" << 'EOF'
"""
Test file for hot-reload functionality.
This file should trigger Django's auto-reloader when saved.
"""

from django.http import JsonResponse

def test_hotreload_view(request):
    """Test view to verify hot-reload is working."""
    return JsonResponse({
        "message": "Hot-reload is working!",
        "timestamp": "$(date)"
    })
EOF

echo "✅ Created test file: $TEST_FILE"
echo ""
echo "📊 Monitor the web service logs to see the reload:"
echo "   docker compose logs -f web"
echo ""
echo "🔄 To see reload in action:"
echo "   1. Run: docker compose logs -f web"
echo "   2. Edit any Python file (e.g., civicpulse/models.py)"
echo "   3. Watch for auto-reload messages in the logs"
echo ""
echo "🧹 Cleanup test file:"
echo "   rm $TEST_FILE"
echo ""

# Clean up
rm -f "$TEST_FILE"
echo "✅ Test file cleaned up."
echo ""
echo "💡 Hot-reload works because:"
echo "   • Volume mount: '.:/app' maps your code into the container"
echo "   • Django runserver has --reload by default"
echo "   • File changes trigger immediate reload"
echo ""