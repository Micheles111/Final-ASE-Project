#!/bin/bash
# scripts/inspect-db.sh

echo "🔌 Connecting to PostgreSQL Database 'escoba_db'..."
# Usa 'docker compose exec' per usare il nome del servizio invece dell'ID del container
docker compose exec postgres psql -U admin -d escoba_db