#!/bin/bash
# Docker Start Script für Trading Bot

echo "🐳 Trading Bot Docker Setup"
echo "============================"
echo ""

# Prüfe ob Docker läuft
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker ist nicht gestartet. Bitte starte Docker Desktop."
    exit 1
fi

echo "✅ Docker läuft"
echo ""

# Prüfe ob docker-compose verfügbar ist
if ! command -v docker-compose &> /dev/null; then
    echo "⚠️  docker-compose nicht gefunden. Verwende 'docker compose' (neuere Version)"
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Baue Container
echo "🔨 Baue Docker Container..."
$DOCKER_COMPOSE build

if [ $? -ne 0 ]; then
    echo "❌ Build fehlgeschlagen"
    exit 1
fi

echo "✅ Container gebaut"
echo ""

# Starte Container
echo "🚀 Starte Trading Bot Container..."
$DOCKER_COMPOSE up -d

if [ $? -ne 0 ]; then
    echo "❌ Container start fehlgeschlagen"
    exit 1
fi

echo "✅ Container gestartet"
echo ""

# Warte kurz auf Health Check
echo "⏳ Warte auf Health Check..."
sleep 5

# Prüfe Status
echo "📊 Container Status:"
$DOCKER_COMPOSE ps

echo ""
echo "✅ Trading Bot läuft auf http://localhost:1337"
echo ""
echo "📝 Nützliche Befehle:"
echo "  - Logs anzeigen: $DOCKER_COMPOSE logs -f"
echo "  - Container stoppen: $DOCKER_COMPOSE down"
echo "  - Container neustarten: $DOCKER_COMPOSE restart"
echo ""

