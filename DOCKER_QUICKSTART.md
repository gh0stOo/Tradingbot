# Docker Quick Start

## 🚀 Schnellstart

### Windows (PowerShell)

```powershell
# 1. Container bauen und starten
docker-compose up -d --build

# 2. Logs anzeigen
docker-compose logs -f

# 3. Dashboard öffnen
# http://localhost:1337
```

### Oder mit Script:

```powershell
.\docker-start.ps1
```

---

## 📋 Wichtige Befehle

### Container starten
```bash
docker-compose up -d
```

### Container stoppen
```bash
docker-compose down
```

### Logs anzeigen
```bash
docker-compose logs -f
```

### Container Status
```bash
docker-compose ps
```

---

## 🌐 Zugriff

- **Dashboard:** http://localhost:1337
- **API Health:** http://localhost:1337/health
- **API Docs:** http://localhost:1337/docs (wenn aktiviert)

---

## 📁 Volumes

Folgende Verzeichnisse werden persistent gespeichert:

- `./data` - Database
- `./logs` - Log-Dateien
- `./config/config.yaml` - Config (read-only)

---

## 🔧 Konfiguration

Die Config wird aus `config/config.yaml` geladen.

Nach Config-Änderungen:
```bash
docker-compose restart
```

---

**Weitere Details:** Siehe `DOCKER_SETUP.md`

