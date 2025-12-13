# Project Handoff – Trading Bot

## 1. Projektziel
Python-basierter Krypto-Trading-Bot für Bybit, der die Top-50 Coins analysiert, technische Indikatoren auswertet, multiple Strategien kombiniert und automatisch Trades in Paper- und Live-Modus ausführt. Integration mit Notion (Trade-Logging) und Discord (Benachrichtigungen). Dashboard für Monitoring und Bot-Kontrolle. Machine-Learning-Integration für Signal-Prediction und Regime-Classification optional aktivierbar.

## 2. Aktueller Stand
- Docker-Setup: 2 Services (`trading-bot-api`, `trading-bot-worker`) laufen
- Dashboard: Neon/Cyberpunk-Design implementiert, Bot-Status-Steuerung funktioniert
- BotStateManager: Zentrale Status-Verwaltung (RUNNING/STOPPED/PAUSED/ERROR)
- API-Server: FastAPI mit Dashboard-Routes und Bot-Control-Endpunkten
- Trading-Logik: Market-Data, Indicators, Strategies, Risk-Management, Order-Management
- Position-Manager: Exit-Management, Monitoring, Auto-Close
- ML-Module: Signal-Predictor, Regime-Classifier, Online-Learning (optional)
- Backtesting: Framework vorhanden
- Datenbank: SQLite über `data/database.py`
- Notion-Integration: Trade-Logging implementiert
- Discord: Webhook-Integration vorhanden

## 3. Architektur (Kurzfassung)
- `main.py`: Entry-Point, kontinuierliche Loop, reagiert auf BotStateManager
- `trading/`: Bot, MarketData, Indicators, Strategies, RiskManager, OrderManager, PositionManager
- `integrations/`: BybitClient, NotionIntegration, RateLimiter
- `data/`: Database, DataCollector, PositionTracker
- `ml/`: SignalPredictor, RegimeClassifier, WeightOptimizer, BacktestRunner
- `api/`: FastAPI-Server, Dashboard-Routes, Bot-Control-Routes
- `dashboard/`: Templates (Jinja2), Static (CSS/JS), BotStateManager
- `utils/`: ConfigLoader, Logger, Exceptions, Retry-Logic
- `monitoring/`: HealthCheck, Alerting

## 4. Verbindliche Entscheidungen
- Python 3.11, FastAPI für API, Jinja2 für Templates
- Docker: 2 Services (API + Worker), Shared Volumes für `/app/data` und `/app/logs`
- Bot startet im STOPPED-Status, wird via Dashboard API gesteuert
- Import-Stil: Absolute Imports (`from integrations.bybit import BybitClient`, nicht relative)
- Konfiguration: YAML (`config/config.yaml`), Environment-Variablen für Secrets
- Datenbank: SQLite, Pfad via `TRADING_DB_PATH` Environment-Variable
- Status-Management: BotStateManager als Singleton über shared filesystem
- Trading-Modi: PAPER (simuliert) und LIVE (echte Orders auf Bybit)
- Notion/Discord: Immer aktiv, auch im Paper-Modus

## 5. Coding- & Architekturkonventionen
- Sprache: Deutsch für UI/Logs, Englisch für Code/Variablen
- Error-Handling: Custom Exceptions (`TradingBotError`, `BybitAPIError`, etc.), Retry-Logic mit Exponential Backoff
- Logging: Structured Logging über `utils/logger.py`
- Type Hints: Verwendet, aber nicht strikt enforced
- Async: FastAPI-Routes async, Trading-Logik synchron
- Threading: Position-Manager verwendet Threading für Monitoring-Loop
- Rate Limiting: Token-Bucket-Algorithmus in `integrations/rate_limiter.py`
- Keine relativen Imports: Nur absolute (`from utils.X import Y`, nie `from ..utils.X import Y`)

## 6. Offene TODOs (priorisiert)
1. Bot-Worker startet nicht: Import-Fehler mit relativen Imports müssen behoben werden
2. ML-Features aktivieren: Signal-Predictor und Regime-Classifier in `config.yaml` aktivieren
3. Dashboard-Seiten anpassen: `/bot-control`, `/training`, `/backtesting` auf Neon-Design migrieren
4. Health-Checks: Monitoring-Endpunkte testen und validieren
5. Docker: Bot-Worker muss stabil laufen (aktuell Restart-Loop)

## 7. Explizit NICHT erneut analysieren
- n8n-Workflow-Analyse (nicht mehr relevant, Bot ist eigenständig)
- Strategy-Logik-Details (Strategien sind implementiert, nur Parameter-Tuning nötig)
- Bybit-API-Wrapper-Struktur (fertig, nur neue Endpunkte hinzufügen)
- Risk-Management-Berechnungen (implementiert, nur Thresholds anpassen)
- Datenbankschema (Schema ist stabil, nur Migrationen bei Schema-Änderungen)
- Docker-Compose-Struktur (2-Service-Setup ist final)

