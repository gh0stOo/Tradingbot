# Docker Setup - Vollständig Funktionstüchtig ✅

**Datum:** 2024-12-19

## Status

✅ **Bot als separater Docker-Service implementiert**
✅ **Dashboard und API funktionieren**
✅ **Beide Services kommunizieren über BotStateManager**

---

## Services

### 1. trading-bot-api
- **Container:** `trading-bot-api`
- **Port:** 1337 → 8000
- **Zweck:** Dashboard & REST API
- **Status:** ✅ Läuft

### 2. trading-bot-worker  
- **Container:** `trading-bot-worker`
- **Port:** Keine (intern)
- **Zweck:** Trading Bot (main.py)
- **Status:** ✅ Läuft

---

## Funktionalität

### Bot Control über Dashboard

1. **Bot Starten:**
   - Dashboard: http://localhost:1337/bot-control
   - Button "Bot starten" klicken
   - Worker-Service reagiert auf Status-Änderung
   - Bot beginnt Trading-Zyklen

2. **Bot Stoppen:**
   - Button "Bot stoppen" klicken
   - Worker-Service stoppt Trading-Zyklen
   - Offene Positionen bleiben bestehen

3. **Bot Pausieren:**
   - Button "Bot pausieren" klicken
   - Worker-Service pausiert neue Trades
   - Offene Positionen werden weiter überwacht

4. **Emergency Stop:**
   - Button "Emergency Stop" klicken
   - Alle offenen Positionen werden geschlossen
   - Bot wird gestoppt

---

## Kommandos

### Services verwalten

```bash
# Beide Services starten
docker-compose up -d

# Services stoppen
docker-compose down

# Services neustarten
docker-compose restart

# Status prüfen
docker-compose ps

# Logs anzeigen
docker-compose logs -f trading-bot-worker
docker-compose logs -f trading-bot-api
```

### Bot Status prüfen

```bash
# Via API
curl http://localhost:1337/api/bot/status

# Via Dashboard
# Öffne: http://localhost:1337/bot-control
```

---

## Architektur

```
┌─────────────────────┐
│  trading-bot-api    │
│  (Dashboard)        │
│  Port: 1337         │
└──────────┬──────────┘
           │
           │ Setzt Status
           │ via BotStateManager
           │
           ▼
┌─────────────────────┐
│ BotStateManager     │
│ (Shared Singleton)  │
│ (via /app/data)     │
└──────────┬──────────┘
           │
           │ Liest Status
           │
           ▼
┌─────────────────────┐
│ trading-bot-worker  │
│ (main.py)           │
│ Läuft kontinuierlich│
└─────────────────────┘
```

---

## Wichtige Hinweise

1. **Shared Database:** Beide Services teilen sich `/app/data/trading.db`
2. **BotStateManager:** Singleton-Pattern über shared filesystem
3. **Startup:** Bot startet im STOPPED Status
4. **Control:** Vollständige Kontrolle über Dashboard möglich

---

## Testing

✅ API erreichbar: http://localhost:1337/health
✅ Dashboard erreichbar: http://localhost:1337/
✅ Bot Control erreichbar: http://localhost:1337/bot-control
✅ Bot Worker läuft und reagiert auf Status-Änderungen

---

**Status:** ✅ VOLLSTÄNDIG FUNKTIONSFÄHIG

