# Crypto Trading Bot

Ein professioneller Trading Bot für Kryptowährungen mit ML-Integration, Backtesting und umfassendem Risk Management.

## Features

### Core Features
- **Multi-Strategy Trading**: 8 verschiedene Trading-Strategien (EMA Trend, MACD, RSI Mean Reversion, etc.)
- **Market Regime Detection**: Automatische Erkennung von Trending, Ranging und Volatile Markets
- **Ensemble Decision Making**: Kombination mehrerer Strategien mit Confidence Scoring
- **Risk Management**: 
  - Position Sizing mit Kelly Criterion
  - Multi-Target Exits (TP1-TP4)
  - Circuit Breaker
  - Adaptive Risk Management (volatilitäts- und regime-basiert)
- **Order Management**: 
  - Paper Trading Simulation
  - Live Trading via Bybit API
  - Erweiterte Order Types (Limit, Stop, OCO, Trailing Stop)
- **Position Management**: 
  - Automatisches Exit-Management
  - Unrealized PnL Tracking
  - Multi-Target Support

### Performance & Optimierung
- **Parallel Processing**: Parallele Verarbeitung mehrerer Coins
- **Indicator Caching**: Optimierte Indikator-Berechnung mit Caching
- **Rate Limiting**: Token Bucket Algorithmus für API-Calls
- **Slippage Modeling**: Realistische Slippage-Berechnung basierend auf Liquidität

### Data & Analytics
- **SQLite Database**: Trade-Historie und Performance-Tracking
- **Notion Integration**: Automatisches Logging von Trades
- **Dashboard**: Web-Interface mit Performance-Statistiken
- **Backtesting Framework**: Walk-Forward Analysis und Performance-Metriken

### Machine Learning
- **Feature Engineering**: 30+ Features für ML-Models
- **Signal Predictor**: XGBoost-basierte Signal-Vorhersage
- **Regime Classifier**: Random Forest für Regime-Klassifikation
- **Online Learning**: Kontinuierliche Anpassung (Phase 3)

### Monitoring & Alerting
- **Health Checks**: API, Database, Position Tracker
- **Alert System**: Discord/Email Alerts bei Anomalien
- **Performance Monitoring**: Win Rate, Drawdown, Loss Streak Tracking

## Architektur

```
src/
├── trading/          # Core Trading Logic
│   ├── bot.py       # Main Trading Bot
│   ├── strategies.py # Trading Strategies
│   ├── indicators.py # Technical Indicators
│   ├── risk_manager.py # Risk Management
│   ├── order_manager.py # Order Execution
│   └── ...
├── integrations/     # External Integrations
│   ├── bybit.py     # Bybit API Client
│   └── notion.py    # Notion API
├── data/            # Data Management
│   ├── database.py  # SQLite Database
│   └── position_tracker.py # Position Tracking
├── ml/              # Machine Learning
│   ├── features.py  # Feature Engineering
│   ├── signal_predictor.py # Signal Prediction
│   └── regime_classifier.py # Regime Classification
├── backtesting/     # Backtesting Framework
├── monitoring/      # Monitoring & Alerting
└── api/             # REST API für n8n Integration
```

## Installation

1. **Dependencies installieren**:
```bash
pip install -r requirements.txt
```

2. **Konfiguration**:
- Kopiere `config/config.example.yaml` zu `config/config.yaml`
- Fülle API-Keys und Einstellungen aus

3. **Datenbank initialisieren**:
```bash
python scripts/init_database.py
```

## Verwendung

### Paper Trading
```bash
python src/main.py
```

### Live Trading
- Stelle sicher, dass `config.yaml` auf `LIVE` oder `TESTNET` gesetzt ist
- API-Keys müssen konfiguriert sein

### Backtesting
```bash
python scripts/run_backtest.py --symbol BTCUSDT --start 2024-01-01 --end 2024-12-31
```

### Dashboard starten
```bash
python src/api/server.py
```
Dann im Browser öffnen: `http://localhost:8000`

## Konfiguration

### Trading Mode
- `PAPER`: Simulation ohne echtes Geld
- `TESTNET`: Bybit Testnet
- `LIVE`: Live Trading (VORSICHT!)

### Risk Management
- `riskPct`: Prozent des Equities pro Trade (default: 2%)
- `kelly.enabled`: Kelly Criterion aktivieren
- `circuitBreaker`: Automatisches Stoppen bei Verlusten

### Strategien
Strategie-Gewichtungen können in `config.yaml` angepasst werden.

## Testing

```bash
# Alle Tests ausführen
python -m pytest tests/

# Spezifische Tests
python -m pytest tests/test_strategies.py
python -m pytest tests/test_risk_manager.py
```

## Dokumentation

- Siehe `FEATURES.md` für detaillierte Feature-Liste
- API-Dokumentation: `docs/API_DOCUMENTATION.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`

## Sicherheit

- **Niemals API-Keys committen!**
- Verwende Environment Variables für Secrets
- Teste immer zuerst im Paper Mode
- Starte mit kleinen Positionen

## License

Proprietär - Alle Rechte vorbehalten
