# Docker Services Setup

**Datum:** 2024-12-19

## Services

Das Docker-Setup besteht jetzt aus zwei Services:

### 1. trading-bot-api (Dashboard & API Server)

- **Container Name:** `trading-bot-api`
- **Port:** 1337 (Host) → 8000 (Container)
- **Command:** `python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000`
- **Zweck:** 
  - Stellt das Web-Dashboard bereit
  - Bietet REST API Endpunkte
  - Bot Control Endpunkte

### 2. trading-bot-worker (Trading Bot)

- **Container Name:** `trading-bot-worker`
- **Port:** Keine (intern)
- **Command:** `python src/main.py`
- **Zweck:**
  - Führt den eigentlichen Trading Bot aus
  - Verarbeitet Trading-Logik
  - Reagiert auf BotStateManager Status-Änderungen

## Shared Volumes

Beide Services teilen sich:
- `./config/config.yaml` - Konfiguration (read-only)
- `./data` - Datenbank und persistente Daten
- `./logs` - Log-Dateien

## Kommunikation

- Beide Services sind im gleichen Docker-Network (`trading-bot-network`)
- Verwenden beide den gleichen `BotStateManager` (Singleton über shared data)
- API-Service kann Bot-Status setzen, Worker reagiert darauf

## Starten

```bash
# Beide Services starten
docker-compose up -d

# Nur API starten
docker-compose up -d trading-bot-api

# Nur Bot starten
docker-compose up -d trading-bot-worker

# Logs anzeigen
docker-compose logs -f trading-bot-worker
docker-compose logs -f trading-bot-api

# Beide Services stoppen
docker-compose down
```

## Status prüfen

```bash
# Alle Services
docker-compose ps

# Bot Worker Logs
docker-compose logs trading-bot-worker --tail=50

# API Logs
docker-compose logs trading-bot-api --tail=50
```

## Wichtige Hinweise

1. **Bot Status:** Der Bot-Worker überwacht kontinuierlich den `BotStateManager` Status
2. **Startup:** Der Bot startet im STOPPED Status und wartet auf Start-Befehl via Dashboard
3. **Restart Policy:** Beide Services haben `restart: unless-stopped`
4. **Datenbank:** Beide Services teilen sich die gleiche SQLite-Datenbank (via shared volume)

