# Docker Setup Guide

**Datum:** 2024-12-19  
**Port:** 1337 (lokal) → 8000 (Container)

---

## Voraussetzungen

- Docker installiert
- Docker Compose installiert (optional, aber empfohlen)

---

## Schnellstart

### 1. Container bauen

```bash
docker-compose build
```

### 2. Container starten

```bash
docker-compose up -d
```

### 3. Logs anzeigen

```bash
docker-compose logs -f
```

### 4. Dashboard öffnen

Öffne im Browser:
```
http://localhost:1337
```

---

## Docker Befehle

### Container starten

```bash
docker-compose up -d
```

### Container stoppen

```bash
docker-compose down
```

### Container neustarten

```bash
docker-compose restart
```

### Logs anzeigen

```bash
# Alle Logs
docker-compose logs

# Live Logs (Follow)
docker-compose logs -f

# Nur Trading Bot Logs
docker-compose logs trading-bot
```

### Container Status

```bash
docker-compose ps
```

### Container Shell öffnen

```bash
docker-compose exec trading-bot bash
```

### Container neu bauen

```bash
docker-compose build --no-cache
docker-compose up -d
```

---

## Manuelles Docker (ohne docker-compose)

### 1. Image bauen

```bash
docker build -t trading-bot .
```

### 2. Container starten

```bash
docker run -d \
  --name trading-bot \
  -p 1337:8000 \
  -v $(pwd)/config/config.yaml:/app/config/config.yaml:ro \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e PYTHONUNBUFFERED=1 \
  -e PYTHONPATH=/app/src \
  trading-bot
```

### 3. Container stoppen

```bash
docker stop trading-bot
docker rm trading-bot
```

---

## Konfiguration

### Config File

Die Config-Datei wird als Volume gemountet (read-only):
```
./config/config.yaml:/app/config/config.yaml:ro
```

**Wichtig:** Änderungen an der Config erfordern Container-Neustart:
```bash
docker-compose restart
```

### Daten-Persistenz

Die folgenden Verzeichnisse werden persistent gespeichert:
- `./data` - Database und Daten
- `./logs` - Log-Dateien

### Environment Variables

Du kannst Environment Variables in `docker-compose.yml` setzen:

```yaml
environment:
  - PYTHONUNBUFFERED=1
  - PYTHONPATH=/app/src
  - TRADING_DB_PATH=/app/data/trading.db
  # Weitere Variablen hier
```

---

## Ports

- **Host Port:** 1337
- **Container Port:** 8000
- **Mapping:** 1337:8000

Ändere den Host-Port in `docker-compose.yml` wenn gewünscht:
```yaml
ports:
  - "1337:8000"  # Ändere 1337 zu deinem gewünschten Port
```

---

## Troubleshooting

### Container startet nicht

**Prüfe Logs:**
```bash
docker-compose logs trading-bot
```

**Häufige Probleme:**
1. Port bereits belegt → Ändere Port in docker-compose.yml
2. Config File fehlt → Stelle sicher dass `config/config.yaml` existiert
3. Dependencies fehlen → Prüfe `requirements.txt`

### Container läuft, aber Dashboard nicht erreichbar

**Prüfe Container Status:**
```bash
docker-compose ps
```

**Prüfe ob Port richtig gemappt ist:**
```bash
docker port trading-bot
```

**Teste Health Endpoint:**
```bash
curl http://localhost:1337/health
```

### Config-Änderungen werden nicht übernommen

**Neustart erforderlich:**
```bash
docker-compose restart
```

### Daten gehen verloren

**Stelle sicher dass Volumes gemountet sind:**
```yaml
volumes:
  - ./data:/app/data
  - ./logs:/app/logs
```

### Container baut nicht

**Lösche Cache und baue neu:**
```bash
docker-compose build --no-cache
```

---

## Production Setup

### Für Production:

1. **Umgebungsvariablen für Secrets:**
   ```yaml
   environment:
     - BYBIT_API_KEY=${BYBIT_API_KEY}
     - BYBIT_API_SECRET=${BYBIT_API_SECRET}
     - NOTION_API_KEY=${NOTION_API_KEY}
   ```

2. **Health Checks aktivieren:**
   ```yaml
   healthcheck:
     test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health')"]
     interval: 30s
     timeout: 10s
     retries: 3
   ```

3. **Resource Limits:**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 2G
       reservations:
         cpus: '1'
         memory: 1G
   ```

4. **Restart Policy:**
   ```yaml
   restart: unless-stopped
   ```

---

## Verzeichnisstruktur

```
.
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── requirements.txt
├── config/
│   └── config.yaml
├── data/          # Wird gemountet (persistent)
├── logs/          # Wird gemountet (persistent)
└── src/
    └── ...
```

---

## Nützliche Befehle

### Container-Status prüfen

```bash
docker-compose ps
```

### Container-Logs in Echtzeit

```bash
docker-compose logs -f trading-bot
```

### In Container einloggen

```bash
docker-compose exec trading-bot bash
```

### Container-Stats

```bash
docker stats trading-bot
```

### Container-Stop und Cleanup

```bash
docker-compose down
```

### Alle Container und Images löschen

```bash
docker-compose down -v  # Entfernt auch Volumes
docker rmi trading-bot  # Entfernt Image
```

---

## Bot starten im Container

Der Container startet automatisch den API-Server. Um den Trading Bot zu starten, musst du entweder:

1. **Im Container ausführen:**
   ```bash
   docker-compose exec trading-bot python src/main.py
   ```

2. **Oder als separater Service in docker-compose.yml:**

```yaml
services:
  trading-bot-api:
    # ... API Server Config ...
  
  trading-bot-worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: python src/main.py
    volumes:
      - ./config/config.yaml:/app/config/config.yaml:ro
      - ./data:/app/data
    environment:
      - PYTHONPATH=/app/src
    depends_on:
      - trading-bot-api
```

---

**Status:** ✅ Docker Setup vollständig konfiguriert

