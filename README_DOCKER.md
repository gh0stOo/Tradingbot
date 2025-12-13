# Trading Bot - Docker Quick Start

## Schnellstart

### 1. Container starten

**Windows (PowerShell):**
```powershell
.\docker-start.ps1
```

**Linux/Mac:**
```bash
chmod +x docker-start.sh
./docker-start.sh
```

**Oder manuell:**
```bash
docker-compose up -d --build
```

### 2. Dashboard öffnen

Öffne im Browser:
```
http://localhost:1337
```

### 3. Logs anzeigen

```bash
docker-compose logs -f
```

### 4. Container stoppen

```bash
docker-compose down
```

---

## Port

- **Lokal:** http://localhost:1337
- **Container:** Port 8000

---

## Weitere Informationen

Siehe `DOCKER_SETUP.md` für detaillierte Anleitung.

