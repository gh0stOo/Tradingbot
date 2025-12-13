# Dashboard Redesign Plan - Trading Bot Control Center

## 🎨 Design-Übernahme (vom COINF Dashboard)

### Design-Prinzipien:
- **Dunkles Theme**: Dunkelblaue/Navy Hintergrund (#0F172A, #1E293B)
- **Sidebar Navigation**: Links mit Icons und aktiven Zuständen
- **Card-basiertes Layout**: Moderne Cards mit Schatten und Rundungen
- **Farbige Akzente**: Blau, Lila, Grün, Pink für verschiedene Kategorien
- **Gradient-Hintergründe**: Für wichtige Cards/Elemente
- **Responsive**: Mobile und Desktop Views

---

## 📋 Menü-Struktur (Sidebar)

### Haupt-Navigation:
1. **🏠 Dashboard** (Aktive Übersicht)
2. **📊 Live Trading** (Aktive Trades, Performance)
3. **🤖 Bot Control** (Start/Stop, Status, Pause)
4. **🧠 KI Training** (ML Model Training, Status)
5. **📈 Backtesting** (Backtests starten, Ergebnisse)
6. **📋 Trade History** (Vergangene Trades, Analyse)
7. **⚙️ Settings** (Nur sichere Einstellungen, KEINE Config/API Keys)

### Zusätzliche Bereiche (können erweitert werden):
- **🔔 Alerts** (Discord Notifications, Alert History)
- **📊 Analytics** (Erweiterte Statistiken, Charts)
- **💾 Data Export** (Trade Export, Reports)

---

## ✅ FEATURES - Was UNBEDINGT rein muss (P0)

### 1. **Dashboard (Übersicht)**
**Zweck**: Hauptübersicht mit wichtigsten Metriken

**Inhalte:**
- ✅ **Bot Status**: Läuft / Gestoppt / Pausiert (große Card)
- ✅ **Live Performance Cards**: 
  - Total PnL (heute, diese Woche, diesen Monat)
  - Win Rate
  - Aktive Trades (Anzahl)
  - Equity/Kontostand
- ✅ **Aktive Trades Karten**: 
  - Für jeden aktiven Trade eine Card
  - Symbol, Side, Entry Price, Current PnL
  - Mini-Graph des PnL-Verlaufs
- ✅ **Quick Actions**: 
  - Bot Start/Stop Button (groß, prominent)
  - Emergency Stop (rot, für Notfälle)
- ✅ **Live Price Charts**: 
  - Chart für aktuell gehandelte Coins
  - Price Movement (1h, 24h)

**Design-Elemente:**
- Gradient Cards (Blau/Lila für positive Werte, Rot für negative)
- Icons für jeden Metric
- Farbcodierung (Grün = Gewinn, Rot = Verlust)

---

### 2. **Bot Control**
**Zweck**: Zentrale Steuerung des Bots

**Inhalte:**
- ✅ **Status Panel**:
  - Aktueller Status (Running/Stopped/Paused)
  - Trading Mode (PAPER/TESTNET/LIVE) - NUR ANZEIGEN, nicht ändern
  - Uptime seit Start
  - Letzte Ausführung
- ✅ **Control Buttons**:
  - 🟢 **Start Bot** (nur wenn gestoppt)
  - 🔴 **Stop Bot** (nur wenn läuft)
  - ⏸️ **Pause Bot** (temporär stoppen, behält Positionen)
  - ▶️ **Resume Bot** (wieder starten)
  - 🚨 **Emergency Stop** (sofort stoppen, alle Positionen schließen)
- ✅ **Current Activity**:
  - Aktuell analysierte Coins
  - Laufende Analysen (Progress)
  - Letzte Signale
- ✅ **Health Status**:
  - API Verbindungsstatus
  - Database Status
  - System Health

**Design:**
- Große, deutlich sichtbare Buttons
- Status-Indikatoren (grüne/rote Lichter)
- Real-time Updates

---

### 3. **KI Training**
**Zweck**: ML Model Training steuern

**Inhalte:**
- ✅ **Training Status**:
  - Aktuell laufendes Training (Ja/Nein)
  - Letztes Training (Datum, Dauer)
  - Nächstes geplantes Training (wenn Scheduler aktiv)
- ✅ **Manual Training Trigger**:
  - 🎯 **Train Signal Predictor** Button
  - 🎯 **Train Regime Classifier** Button
  - Beide zusammen trainieren
- ✅ **Training Progress** (wenn aktiv):
  - Progress Bar
  - Epoch/Iteration Status
  - Estimated Time Remaining
- ✅ **Training History**:
  - Letzte Trainings (Liste)
  - Model Performance (Accuracy, etc.)
  - Model Versionen
- ✅ **Genetic Algorithm Control**:
  - 🧬 **Start GA Optimization** Button
  - Aktueller Status (Läuft/Idle)
  - Generation Progress (wenn aktiv)
  - Best Fitness Score
- ✅ **Online Learning Status**:
  - Aktiv/Inaktiv
  - Letzte Weight Updates
  - Current Strategy Weights (Anzeige)

**Design:**
- Progress Bars für laufende Prozesse
- Cards für verschiedene Training-Types
- Buttons mit Icons und Labels

---

### 4. **Backtesting**
**Zweck**: Backtests starten und verwalten

**Inhalte:**
- ✅ **Backtest Form**:
  - Start Date (Date Picker)
  - End Date (Date Picker)
  - Symbols (Multi-Select oder "Top N")
  - Strategy Filter (Optional)
  - Initial Equity
  - **▶️ Start Backtest** Button
- ✅ **Running Backtests**:
  - Liste laufender Backtests
  - Progress Bar
  - Estimated Time
  - Cancel Button
- ✅ **Backtest Results**:
  - Liste abgeschlossener Backtests
  - Ergebnisse pro Backtest:
    - Total PnL
    - Win Rate
    - Sharpe Ratio
    - Max Drawdown
    - Total Trades
  - **📊 View Details** Button
  - **💾 Export Results** Button
- ✅ **Backtest Details View** (Modal oder separate Seite):
  - Equity Curve Chart
  - Trade List
  - Performance Metrics (detailliert)
  - Best/Worst Trades
- ✅ **Walk-Forward Analysis** (Optional):
  - Start WF Analysis Button
  - Configuration
  - Results Overview

**Design:**
- Form-basiertes Interface für neue Backtests
- Table/Card View für Ergebnisse
- Charts für Visualisierung

---

### 5. **Live Trading**
**Zweck**: Aktive Trades und Performance

**Inhalte:**
- ✅ **Active Positions**:
  - Liste aller offenen Trades
  - Für jeden Trade:
    - Symbol, Side, Entry Price
    - Current Price, Unrealized PnL
    - Stop Loss, Take Profit
    - Multi-Target Status (TP1-TP4)
    - Time in Trade
    - **🔒 Close Position** Button (Manual Close)
- ✅ **Performance Overview**:
  - Today's PnL
  - Week/Month PnL
  - Win Rate (Today/Week/Month)
  - Best/Worst Trades
- ✅ **Live Charts**:
  - Price Chart für aktive Coins
  - PnL Chart (kumulativ)
  - Equity Curve (Live)
- ✅ **Recent Signals**:
  - Letzte generierte Signale
  - Gefiltert vs. Ausgeführt
  - Signal Details (Strategies, Confidence)

**Design:**
- Table/Card Layout für Positions
- Real-time Updates (WebSocket oder Polling)
- Farbcodierung (Grün/Rot)

---

### 6. **Trade History**
**Zweck**: Historische Trades analysieren

**Inhalte:**
- ✅ **Trade List**:
  - Tabelle mit allen Trades
  - Filter: Date Range, Symbol, Side, Success
  - Sortierung
  - Pagination
- ✅ **Trade Details** (beim Klick):
  - Alle Trade-Daten
  - Indikatoren zum Entry-Zeitpunkt
  - Market Context
  - Timeline (Entry → Exit)
- ✅ **Statistics**:
  - Performance nach Symbol
  - Performance nach Strategie
  - Performance nach Regime
  - Win/Loss Distribution

**Design:**
- Table mit Sortierung/Filter
- Modal für Details
- Charts für Statistiken

---

## 🎯 FEATURES - Was SINNVOLL ist (P1)

### 7. **Alerts**
- Discord Notification Status
- Alert History
- Alert Settings (ON/OFF, aber keine Webhook URL)

### 8. **Analytics**
- Erweiterte Charts
- Correlation Analysis
- Strategy Performance Vergleich
- Regime Analysis

### 9. **Settings**
- **SICHER**: Nur non-sensitive Settings
  - Display Preferences
  - Chart Settings
  - Refresh Intervals
  - Theme (Dark/Light)
- **NICHT**: 
  - API Keys
  - Config Werte
  - Trading Parameters

### 10. **Data Export**
- Export-Buttons für verschiedene Formate
- Report Generation
- CSV/JSON Export

---

## 🔧 Technische Implementation

### Backend API Endpoints (neu benötigt):

#### Bot Control:
- `POST /api/bot/start` - Bot starten
- `POST /api/bot/stop` - Bot stoppen
- `POST /api/bot/pause` - Bot pausieren
- `POST /api/bot/resume` - Bot fortsetzen
- `POST /api/bot/emergency-stop` - Emergency Stop
- `GET /api/bot/status` - Bot Status

#### KI Training:
- `POST /api/training/signal-predictor` - Signal Predictor trainieren
- `POST /api/training/regime-classifier` - Regime Classifier trainieren
- `POST /api/training/both` - Beide trainieren
- `GET /api/training/status` - Training Status
- `GET /api/training/history` - Training History
- `POST /api/training/genetic-algorithm` - GA Optimization starten
- `GET /api/training/ga-status` - GA Status

#### Backtesting:
- `POST /api/backtesting/run` - Backtest starten
- `GET /api/backtesting/status/{id}` - Backtest Status
- `GET /api/backtesting/results/{id}` - Backtest Results
- `GET /api/backtesting/list` - Liste aller Backtests
- `DELETE /api/backtesting/cancel/{id}` - Backtest abbrechen

#### Live Trading:
- `GET /api/positions/active` - Aktive Positionen
- `POST /api/positions/{id}/close` - Position schließen
- `GET /api/signals/recent` - Letzte Signale
- `GET /api/performance/live` - Live Performance

---

### Frontend Struktur:

```
dashboard/
├── templates/
│   ├── index.html (Main Layout mit Sidebar)
│   ├── dashboard.html (Übersicht)
│   ├── bot-control.html (Bot Steuerung)
│   ├── training.html (KI Training)
│   ├── backtesting.html (Backtesting)
│   ├── live-trading.html (Live Trading)
│   └── trade-history.html (Trade History)
├── static/
│   ├── css/
│   │   └── styles.css (COINF Design)
│   └── js/
│       ├── bot-control.js
│       ├── training.js
│       ├── backtesting.js
│       └── charts.js
└── components/ (falls verwendet)
```

---

## 🎨 Design-Komponenten (basierend auf COINF)

### Farben:
- **Background**: #0F172A (sehr dunkel blau)
- **Cards**: #1E293B (dunkel blau-grau)
- **Sidebar**: #1E293B
- **Active Item**: #3B82F6 (blau)
- **Text Primary**: #FFFFFF
- **Text Secondary**: #94A3B8
- **Success/Positive**: #10B981 (grün)
- **Error/Negative**: #EF4444 (rot)
- **Accent Purple**: #8B5CF6
- **Accent Pink**: #EC4899

### Typography:
- **Headers**: Bold, große Schrift
- **Body**: Regular, normale Schrift
- **Labels**: Small, Secondary Color

### Icons:
- Font Awesome oder ähnliche Icon Library
- Konsistente Icon-Sprache

---

## 📊 Implementation Phasen

### Phase 1: Grundstruktur (P0)
1. ✅ Neues Design-Layout (Sidebar, Header)
2. ✅ Dashboard Page (Übersicht)
3. ✅ Bot Control Page (Grundfunktionen)

### Phase 2: Core Features (P0)
4. ✅ KI Training Page
5. ✅ Backtesting Page
6. ✅ Live Trading Page
7. ✅ Trade History Page

### Phase 3: Backend API (P0)
8. ✅ Bot Control Endpoints
9. ✅ Training Endpoints
10. ✅ Backtesting Endpoints
11. ✅ Live Trading Endpoints

### Phase 4: Enhanced Features (P1)
12. ✅ Alerts Page
13. ✅ Analytics Page
14. ✅ Settings Page
15. ✅ Data Export

### Phase 5: Polish (P1)
16. ✅ Real-time Updates (WebSocket)
17. ✅ Responsive Design (Mobile)
18. ✅ Loading States
19. ✅ Error Handling

---

## 🔐 Sicherheits-Überlegungen

### Was NICHT angezeigt/geändert werden darf:
- ❌ API Keys (Bybit, Notion, Discord)
- ❌ API Secrets
- ❌ Config-Datei Werte (trading parameters, risk settings)
- ❌ Sensitive Daten

### Was SICHER ist:
- ✅ Bot Status (nur Anzeige)
- ✅ Trading Mode (nur Anzeige)
- ✅ Performance Daten
- ✅ Trade Daten
- ✅ Training/Backtest Ergebnisse
- ✅ Display Preferences

---

## ✅ Zusammenfassung

### Unbedingt notwendig (P0):
1. ✅ Dashboard (Übersicht)
2. ✅ Bot Control (Start/Stop/Pause)
3. ✅ KI Training (Manual Trigger, Status)
4. ✅ Backtesting (Start Backtests, Ergebnisse)
5. ✅ Live Trading (Aktive Positionen)
6. ✅ Trade History (Trade Liste, Details)

### Sinnvoll (P1):
7. ⚠️ Alerts (Status, History)
8. ⚠️ Analytics (Erweiterte Charts)
9. ⚠️ Settings (Nur non-sensitive)
10. ⚠️ Data Export

### Design:
- ✅ COINF-Stil (dunkles Theme, Sidebar, Cards)
- ✅ Responsive
- ✅ Moderne UI/UX

---

**Plan gespeichert - Implementation beginnt! 🚀**
