#!/bin/bash
# scripts/inspect-db.sh

echo "Connecting to PostgreSQL Database 'escoba_db'..."
# Use 'docker compose exec' to use the service name instead of the container ID
docker compose exec postgres psql -U admin -d escoba_db