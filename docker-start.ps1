# Docker Start Script für Trading Bot (PowerShell)

Write-Host "🐳 Trading Bot Docker Setup" -ForegroundColor Cyan
Write-Host "============================" -ForegroundColor Cyan
Write-Host ""

# Prüfe ob Docker läuft
try {
    docker info | Out-Null
    Write-Host "✅ Docker läuft" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker ist nicht gestartet. Bitte starte Docker Desktop." -ForegroundColor Red
    exit 1
}

Write-Host ""

# Prüfe ob docker-compose verfügbar ist
try {
    docker-compose version | Out-Null
    $DOCKER_COMPOSE = "docker-compose"
    Write-Host "✅ docker-compose gefunden" -ForegroundColor Green
} catch {
    try {
        docker compose version | Out-Null
        $DOCKER_COMPOSE = "docker compose"
        Write-Host "✅ docker compose gefunden" -ForegroundColor Green
    } catch {
        Write-Host "❌ Docker Compose nicht gefunden" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""

# Baue Container
Write-Host "🔨 Baue Docker Container..." -ForegroundColor Yellow
& $DOCKER_COMPOSE.Split(' ') build

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Build fehlgeschlagen" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Container gebaut" -ForegroundColor Green
Write-Host ""

# Starte Container
Write-Host "🚀 Starte Trading Bot Container..." -ForegroundColor Yellow
& $DOCKER_COMPOSE.Split(' ') up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Container start fehlgeschlagen" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Container gestartet" -ForegroundColor Green
Write-Host ""

# Warte kurz auf Health Check
Write-Host "⏳ Warte auf Health Check..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Prüfe Status
Write-Host "📊 Container Status:" -ForegroundColor Cyan
& $DOCKER_COMPOSE.Split(' ') ps

Write-Host ""
Write-Host "✅ Trading Bot läuft auf http://localhost:1337" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Nützliche Befehle:" -ForegroundColor Cyan
Write-Host "  - Logs anzeigen: $DOCKER_COMPOSE logs -f"
Write-Host "  - Container stoppen: $DOCKER_COMPOSE down"
Write-Host "  - Container neustarten: $DOCKER_COMPOSE restart"
Write-Host ""

