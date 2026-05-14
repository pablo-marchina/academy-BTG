#!/bin/bash
# Script de deploy para BTG Intelligence
# Uso: ./scripts/deploy.sh [dev|prod]

set -e

ENV=${1:-dev}
COMPOSE_FILE="docker-compose.yml"

echo "=== BTG Intelligence Deploy ($ENV) ==="

if [ "$ENV" = "prod" ]; then
    export COMPOSE_FILE="docker-compose.prod.yml"
fi

echo "1. Verificando dependencias..."
if ! command -v docker &> /dev/null; then
    echo "Erro: Docker nao instalado"
    exit 1
fi

echo "2. Carregando variaveis de ambiente..."
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "3. Construindo imagens..."
docker compose -f $COMPOSE_FILE build

echo "4. Parando servicos existentes..."
docker compose -f $COMPOSE_FILE down --remove-orphans

echo "5. Iniciando servicos..."
docker compose -f $COMPOSE_FILE up -d

echo "6. Aguardando healthchecks..."
sleep 10
docker compose -f $COMPOSE_FILE ps

echo ""
echo "=== Deploy concluido ==="
echo "Dashboard: http://localhost:8501"
echo "API: http://localhost:8000/docs"
echo "Logs: docker compose logs -f"
