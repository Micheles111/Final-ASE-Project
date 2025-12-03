#!/bin/bash
# scripts/clean.sh

echo "🛑 Stopping containers and removing volumes..."
docker compose down -v --remove-orphans

echo "🧹 Removing temporary Python cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} +

echo "✅ Environment cleaned! Run 'docker compose up --build' to start fresh."