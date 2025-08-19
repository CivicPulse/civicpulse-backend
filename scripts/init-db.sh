#!/bin/bash
# Database initialization script for Docker development environment

set -e

echo "🔧 Initializing CivicPulse database..."

# Use Django management command for setup
python manage.py setup_development

echo "✅ Database initialization complete!"
echo ""