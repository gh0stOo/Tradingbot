# Dashboard Usage Guide

**Datum:** 2024-12-19  
**Status:** Vollständig funktionsfähig

---

## Dashboard Übersicht

Das Trading Bot Dashboard ist eine vollständige Web-Interface zur Steuerung und Überwachung des Trading Bots.

**URL:** `http://localhost:8000` (wenn API Server läuft)

---

## Seiten

### 1. Dashboard (Hauptseite)
**URL:** `/`

**Features:**
- Bot Status Overview
- Live Performance Metrics (PnL, Win Rate, Active Trades, Equity)
- Active Trades Cards
- Quick Actions (Bot Control, Training, Backtesting, Emergency Stop)
- Live Charts (Daily Performance, Price Movement)

**Auto-Refresh:** Alle 10 Sekunden

---

### 2. Bot Control
**URL:** `/bot-control`

**Features:**
- Bot Status Panel (Status, Mode, Uptime, Last Execution)
- Control Buttons:
  - **Start Bot** - Setzt Status auf RUNNING
  - **Stop Bot** - Setzt Status auf STOPPED (Bot verlässt Loop)
  - **Pause Bot** - Setzt Status auf PAUSED (Bot wartet)
  - **Resume Bot** - Setzt Status auf RUNNING (Bot setzt fort)
  - **Emergency Stop** - Stoppt sofort und schließt alle Positionen
- Current Activity Display
- System Health Status

**Auto-Refresh:** Alle 5 Sekunden

---

### 3. KI Training
**URL:** `/training`

**Features:**
- Training Status Overview (Signal Predictor, Regime Classifier, GA, Online Learning)
- Manual Training Triggers:
  - Train Signal Predictor
  - Train Regime Classifier
  - Train Both Models
- Training Progress Bars
- Genetic Algorithm Control
- Training History

---

### 4. Backtesting
**URL:** `/backtesting`

**Features:**
- Backtest Form (Start/End Date, Initial Equity, Symbols)
- Running Backtests Display (mit Progress)
- Backtest Results List
- Backtest Details Modal

---

### 5. Live Trading
**URL:** `/live-trading`

**Features:**
- Active Positions Table
- Performance Overview (Today/Week/Month)
- Recent Signals Display
- Live Charts (PnL, Equity Curve)

---

### 6. Trade History
**URL:** `/trade-history`

**Features:**
- Trade List Table mit Filtern
- Filter Options:
  - Zeitraum (Alle, 7 Tage, 30 Tage, 90 Tage)
  - Symbol
  - Side (Buy/Sell)
  - Status (Gewonnen/Verloren)
- Trade Details Modal (mit Indikatoren und Market Context)

---

## API Endpoints

### Bot Control

#### GET /api/bot/status
**Beschreibung:** Bot Status abrufen

**Response:**
```json
{
  "status": "running",
  "mode": "PAPER",
  "uptime": "2h 30m",
  "lastExecution": "2024-12-19T10:30:00Z",
  "startTime": "2024-12-19T08:00:00Z",
  "error": null
}
```

#### POST /api/bot/start
**Beschreibung:** Bot starten (Status auf RUNNING setzen)

**Response:**
```json
{
  "success": true,
  "message": "Bot Status auf RUNNING gesetzt"
}
```

#### POST /api/bot/stop
**Beschreibung:** Bot stoppen (Status auf STOPPED setzen)

**Response:**
```json
{
  "success": true,
  "message": "Bot gestoppt"
}
```

#### POST /api/bot/pause
**Beschreibung:** Bot pausieren (Status auf PAUSED setzen)

**Response:**
```json
{
  "success": true,
  "message": "Bot pausiert"
}
```

#### POST /api/bot/resume
**Beschreibung:** Bot fortsetzen (Status auf RUNNING setzen)

**Response:**
```json
{
  "success": true,
  "message": "Bot fortgesetzt"
}
```

#### POST /api/bot/emergency-stop
**Beschreibung:** Emergency Stop - Stoppt Bot und schließt alle Positionen

**Response:**
```json
{
  "success": true,
  "message": "Emergency Stop ausgeführt. Alle Positionen wurden geschlossen."
}
```

---

### Training

#### GET /api/training/status
**Beschreibung:** Training Status aller Modelle

#### POST /api/training/signal-predictor
**Beschreibung:** Signal Predictor trainieren

#### POST /api/training/regime-classifier
**Beschreibung:** Regime Classifier trainieren

#### POST /api/training/both
**Beschreibung:** Beide Modelle trainieren

#### POST /api/training/genetic-algorithm
**Beschreibung:** GA Optimization starten

---

### Backtesting

#### POST /api/backtesting/run
**Beschreibung:** Backtest starten

**Body:**
```json
{
  "start_date": "2024-11-01T00:00:00Z",
  "end_date": "2024-12-01T23:59:59Z",
  "initial_equity": 10000.0,
  "symbols": ["BTCUSDT", "ETHUSDT"]  // Optional, null = Top N
}
```

#### GET /api/backtesting/list
**Beschreibung:** Liste aller Backtests

#### GET /api/backtesting/status/{id}
**Beschreibung:** Backtest Status

#### GET /api/backtesting/results/{id}
**Beschreibung:** Backtest Results

---

## Bot Betrieb

### Bot Starten

1. **Bot-Prozess starten:**
   ```bash
   python src/main.py
   ```

2. **Bot läuft kontinuierlich:**
   - Loop-Interval: Standard 5 Minuten (300 Sekunden)
   - Konfigurierbar in `config.yaml`: `trading.loopInterval`

3. **Bot Status:**
   - Beim Start: Status = RUNNING
   - Bot führt kontinuierlich Trading Cycles aus

### Bot Steuern über Dashboard

1. **Bot Pausieren:**
   - Dashboard: Bot Control → "Pausieren" Button
   - API: POST /api/bot/pause
   - Bot wartet, führt keine Trades aus, Positionen bleiben offen

2. **Bot Fortsetzen:**
   - Dashboard: Bot Control → "Fortsetzen" Button
   - API: POST /api/bot/resume
   - Bot setzt Trading fort

3. **Bot Stoppen:**
   - Dashboard: Bot Control → "Bot Stoppen" Button
   - API: POST /api/bot/stop
   - Bot verlässt Loop, Prozess läuft weiter

4. **Emergency Stop:**
   - Dashboard: Bot Control → "Emergency Stop" Button
   - API: POST /api/bot/emergency-stop
   - Bot stoppt sofort und schließt alle Positionen

---

## Konfiguration

### Loop Interval

In `config.yaml`:
```yaml
trading:
  loopInterval: 300  # Sekunden zwischen Cycles (Standard: 300 = 5 Minuten)
```

### API Server

In `config.yaml`:
```yaml
api:
  enabled: true
  baseUrl: "http://localhost:8000"
```

---

## Troubleshooting

### Bot reagiert nicht auf Dashboard Commands

**Problem:** Bot Status ändert sich nicht

**Lösung:**
1. Prüfe ob Bot-Prozess läuft: `python src/main.py`
2. Prüfe Bot State Manager: Status sollte über API abrufbar sein
3. Prüfe Logs für Fehler

### Bot läuft nicht kontinuierlich

**Problem:** Bot führt nur einmal aus und endet

**Lösung:**
- Stelle sicher, dass main.py die neue Loop-Struktur hat
- Prüfe ob `while True` Loop vorhanden ist

### Dashboard zeigt falschen Status

**Problem:** Status stimmt nicht überein

**Lösung:**
1. Refresh Dashboard
2. Prüfe API: GET /api/bot/status
3. Prüfe Bot Logs

---

## Workflow Beispiele

### Beispiel 1: Bot Starten und Überwachen

1. Starte Bot: `python src/main.py`
2. Öffne Dashboard: `http://localhost:8000`
3. Gehe zu "Bot Control"
4. Status sollte "Läuft" zeigen
5. Gehe zu "Dashboard" für Live-Metriken

### Beispiel 2: Bot Pausieren für Wartung

1. Dashboard → Bot Control
2. Klicke "Pausieren"
3. Bot Status ändert zu "Pausiert"
4. Führe Wartung durch
5. Klicke "Fortsetzen"
6. Bot setzt Trading fort

### Beispiel 3: Emergency Stop

1. Dashboard → Bot Control
2. Klicke "Emergency Stop"
3. Bestätige Warnung
4. Bot stoppt sofort
5. Alle Positionen werden geschlossen

---

## Best Practices

1. **Bot Status überwachen:**
   - Regelmäßig Dashboard prüfen
   - Auf Error-Status achten
   - Last Execution überwachen

2. **Pause statt Stop:**
   - Verwende Pause für kurze Unterbrechungen
   - Positionen bleiben erhalten
   - Schneller Resume möglich

3. **Emergency Stop nur im Notfall:**
   - Emergency Stop schließt alle Positionen
   - Nur bei kritischen Situationen verwenden

4. **Monitoring:**
   - Nutze Live Trading Seite für aktive Positionen
   - Trade History für Analyse
   - Performance Metrics im Dashboard

---

**Status:** ✅ Dashboard vollständig funktionsfähig und dokumentiert

