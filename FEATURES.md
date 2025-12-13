# Trading Bot - Komplette Feature-Übersicht

## 📊 Übersicht

Dieser Crypto Trading Bot ist ein vollständig automatisierter Algorithmic Trading Bot für Kryptowährungen auf der Bybit Exchange. Er analysiert kontinuierlich die Top-Kryptowährungen, erkennt Trading-Signale basierend auf technischer Analyse und führt Trades automatisch aus.

---

## 🎯 Hauptfunktionen

### 1. Automatische Marktanalyse
- **Top 50 Coins Analyse**: Analysiert automatisch die Top 50 Kryptowährungen nach 24h Handelsvolumen
- **Multi-Timeframe Analyse**: Verwendet 3 verschiedene Timeframes (1min, 5min, 15min) gleichzeitig
- **Real-time Marktdaten**: Echtzeit-Datenabfrage von Bybit API
- **Volumen-Filter**: Filtert Coins nach Mindestvolumen (Standard: 5M USDT/24h)

### 2. Market Regime Detection (Marktphasen-Erkennung)
- **Trending Markets**: Erkennt Trend-Märkte (bullish/bearish)
- **Ranging Markets**: Erkennt Seitwärts-Märkte
- **Volatile Markets**: Erkennt volatile Marktphasen
- **Adaptive Strategien**: Passt Strategien automatisch an die erkannte Marktphase an

### 3. Technische Indikatoren (10+ Indikatoren)

#### Trend-Indikatoren:
- **EMA** (Exponential Moving Average): 8, 21, 50, 200 Perioden
- **SMA** (Simple Moving Average)
- **MACD** (Moving Average Convergence Divergence): Fast/Slow/Signal
- **ADX** (Average Directional Index): Trend-Stärke

#### Momentum-Indikatoren:
- **RSI** (Relative Strength Index): 14 Perioden
- **Stochastic Oscillator**: 14 Perioden

#### Volatilitäts-Indikatoren:
- **ATR** (Average True Range): 14 Perioden
- **Bollinger Bands**: 20 Perioden, 2 Standardabweichungen
- **Volatility** (Standard Deviation)

#### Volume-Indikatoren:
- **VWAP** (Volume Weighted Average Price)

### 4. Candlestick Pattern Recognition (Kerzenmuster-Erkennung)

Erkennt folgende Candlestick Patterns:
- **Bullish Engulfing** (Aufwärtstrend-Umkehrung)
- **Bearish Engulfing** (Abwärtstrend-Umkehrung)
- **Hammer** (Bullish Reversal)
- **Shooting Star** (Bearish Reversal)
- **Doji** (Indecision)
- **Three White Soldiers** (Strong Bullish)
- **Three Black Crows** (Strong Bearish)

### 5. 8 Kern-Strategien (Trading-Strategien)

#### Trend-Following Strategien (für Trending Markets):
1. **EMA Trend Strategy**: 
   - Signale basierend auf EMA-Kreuzungen
   - Long: Price > EMA8 > EMA21 in uptrend
   - Short: Price < EMA8 < EMA21 in downtrend

2. **MACD Trend Strategy**:
   - MACD Crossover-Signale
   - Positive Histogram für Longs
   - Negative Histogram für Shorts

3. **ADX Trend Strength**:
   - Starke Trends (ADX > 30)
   - Bestätigung durch Regime-Detection

#### Mean Reversion Strategien (für Ranging Markets):
4. **RSI Mean Reversion**:
   - Oversold (< 30) = Long Signal
   - Overbought (> 70) = Short Signal

5. **Bollinger Mean Reversion**:
   - Long bei unterem Band
   - Short bei oberem Band

#### Volatility-basierte Strategien:
6. **Volatility Breakout**:
   - Breakout-Erkennung bei hoher Volatilität
   - ATR-basierte Signale

7. **Volume Profile**:
   - Volume-Spike Erkennung
   - Trend-Bestätigung durch Volumen

#### Multi-Timeframe Strategie:
8. **Multi-Timeframe Analysis**:
   - Alignment über M1, M5, M15
   - Konfirmation über mehrere Timeframes

### 6. Ensemble Decision Making (Signal-Kombination)

- **Weighted Confidence**: Jede Strategie hat individuelles Gewicht
- **Signal Aggregation**: Kombiniert Signale aller aktiven Strategien
- **Quality Score**: Berechnet Gesamtqualität des Signals
- **Confidence Threshold**: Mindest-Konfidenz für Trade-Execution
- **Agreement Ratio**: Misst Übereinstimmung zwischen Strategien

### 7. Risikomanagement

#### Position Sizing:
- **Fixed Risk**: Fester Prozentsatz pro Trade (Standard: 2% des Equity)
- **ATR-basierte Positionierung**: Position-Größe basierend auf Volatilität
- **Kelly Criterion**: Optional aktivierbar für optimale Position-Größe
  - Dynamische Anpassung basierend auf Win Rate
  - Fractional Kelly (Standard: 25%)

#### Stop-Loss & Take-Profit:
- **ATR-basierte Stop-Loss**: Dynamischer SL basierend auf ATR (Standard: 2x ATR)
- **ATR-basierte Take-Profit**: Dynamischer TP basierend auf ATR (Standard: 4x ATR)
- **Multi-Target Exits**: Bis zu 3 Take-Profit Levels
  - TP1: 1.5x ATR (33% der Position)
  - TP2: 3.0x ATR (33% der Position)
  - TP3: 5.0x ATR (34% der Position)

#### Risk-Reward Ratio:
- **Minimum R:R**: 2:1 (Standard)
- **Automatische Filterung**: Trades mit zu schlechtem R:R werden abgelehnt

#### Exposure Limits:
- **Max Positions**: Maximale Anzahl gleichzeitiger Positionen (Standard: 3)
- **Max Exposure**: Maximale Exposure pro Trade (Standard: 50% des Equity)
- **Leverage Control**: Maximale Leverage (Standard: 10x)

### 8. Circuit Breaker (Sicherheitssystem)

Automatischer Stopp bei:
- **Max Loss Streak**: Zu viele Verlust-Trades hintereinander (Standard: 3)
- **Max Daily Drawdown**: Täglicher Drawdown überschreitet Limit (Standard: 5%)
- **Cooldown**: Automatische Pause nach Circuit Breaker (Standard: 60 Minuten)

### 9. Market Filters (Markt-Filter)

#### BTC Crash Protection:
- **BTC Price Monitoring**: Überwacht BTC-Preis
- **Crash Detection**: Blockiert Trades bei BTC-Crash (Threshold: -3%)

#### Funding Rate Filter:
- **Funding Rate Range**: Filtert extreme Funding Rates
- **Confidence Adjustment**: Reduziert Confidence bei extremen Rates

#### Correlation Filter:
- **Max Correlation**: Verhindert zu ähnliche Positionen (Config: 0.70)

### 10. Order Execution

#### Trading Modes:
- **PAPER Mode**: Simuliertes Trading ohne echte Orders
  - Slippage-Simulation (0.02%)
  - PnL-Berechnung
  - Kein Risiko für echtes Kapital

- **LIVE Mode**: Echte Orders auf Bybit
  - Market Orders
  - Stop-Loss & Take-Profit Orders
  - Vollständige Order-Management

- **TESTNET Mode**: Testnet für Safe Testing

#### Order Features:
- **Market Orders**: Sofortige Ausführung
- **Stop-Loss Orders**: Automatische Stop-Loss Setzung
- **Take-Profit Orders**: Automatische Take-Profit Setzung
- **Multi-Target Orders**: Separate TP Orders für verschiedene Targets
- **Price Rounding**: Automatische Rundung auf Tick-Size
- **Quantity Rounding**: Automatische Rundung auf Lot-Size

### 11. Integrationen

#### Bybit Exchange:
- **Market Data**: Ticker, Klines, Instruments Info
- **Trading API**: Order Placement, Balance Query
- **Rate Limiting**: Automatisches Rate Limit Management
- **Authentication**: HMAC-SHA256 Signature

#### Notion Integration:
- **Signal Logging**: Alle Trading-Signale werden geloggt
- **Execution Logging**: Alle Trade-Ausführungen werden dokumentiert
- **Daily Statistics**: Tägliche Performance-Statistiken
- **3 Separate Databases**: Signals, Executions, Daily Stats

#### n8n Integration (via REST API):
- **Webhook Endpoints**: POST Trade Signals
- **Discord Notifications**: Automatische Benachrichtigungen über n8n
- **Custom Workflows**: Flexible Integration in bestehende n8n Workflows

### 12. REST API (FastAPI)

#### Endpoints:
- `POST /api/v1/trade/signal` - Empfängt Trade-Signale (für n8n)
- `POST /api/v1/trade/execute` - Führt Trade aus
- `GET /api/v1/health` - Health Check
- `GET /api/v1/status` - Bot Status

#### Features:
- **Pydantic Models**: Type-safe Request/Response
- **Async Support**: Asynchrone Verarbeitung
- **Error Handling**: Strukturierte Fehlerbehandlung
- **CORS Support**: Cross-Origin Requests

### 13. Configuration System

#### YAML-basierte Konfiguration:
- **Trading Settings**: Mode, Schedule, Universe
- **Risk Parameters**: Alle Risk-Parameter konfigurierbar
- **Strategy Weights**: Individuelle Gewichtung jeder Strategie
- **Multi-Target Settings**: TP-Levels und Größen
- **Filter Settings**: Alle Filter-Thresholds
- **Environment Overrides**: .env Datei für Secrets

### 14. Logging & Monitoring

#### Logging:
- **Structured Logging**: Strukturierte Log-Ausgaben
- **Log Files**: Persistente Log-Dateien in `logs/`
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Trade Logging**: Alle Trades werden geloggt

#### Error Handling:
- **Exception Handling**: Umfassende Fehlerbehandlung
- **Error Logging**: Detaillierte Error-Logs
- **Graceful Degradation**: Bot läuft weiter auch bei einzelnen Fehlern

### 15. Utilities

#### Config Loader:
- **YAML Parsing**: Lädt Konfiguration aus YAML
- **Environment Variables**: Unterstützung für .env Overrides
- **Default Values**: Sensible Defaults
- **Validation**: Konfigurations-Validierung

#### Logger Setup:
- **File & Console Logging**: Doppelte Ausgabe
- **Rotation**: Automatische Log-Rotation
- **Formatting**: Strukturiertes Format

---

## 🔧 Technische Details

### Technologie-Stack:
- **Python 3.8+**
- **pandas**: Datenverarbeitung
- **numpy**: Numerische Berechnungen
- **FastAPI**: REST API
- **requests**: HTTP Requests
- **PyYAML**: Konfigurations-Parsing
- **python-dotenv**: Environment Variables

### Datenquellen:
- **Bybit API v5**: Market Data & Trading
- **Bybit Public Endpoints**: Ticker, Klines, Instruments
- **Bybit Private Endpoints**: Orders, Balance

### Architektur:
- **Modular Design**: Klare Trennung der Komponenten
- **Strategy Pattern**: Erweiterbare Strategien
- **Dependency Injection**: Lose Kopplung
- **Type Hints**: Type Safety

---

## 📈 Performance-Features

### Effizienz:
- **Batch Processing**: Verarbeitung mehrerer Coins
- **Rate Limiting**: API Rate Limit Management
- **Caching**: Potenzial für Indikator-Caching (in Arbeit)

### Skalierbarkeit:
- **Configurable Universe**: Anpassbare Anzahl an Coins
- **Parallel Processing**: Potenzial für Parallelisierung (geplant)
- **Async Support**: Asynchrone API-Calls

---

## 🚀 Geplante Features (aus Analyse-Plan)

### Kurzfristig:
- **Position Tracking**: Vollständiges Position-Management
- **PnL Tracking**: Real-time PnL Berechnung
- **TP4 Support**: 4. Take-Profit Level
- **Dashboard Web-Interface**: Performance-Dashboard mit Statistiken
  - Win Rate, Max Drawdown, Sharpe Ratio
  - Tägliche/Wöchentliche/Monatliche Performance
  - JSON Export (alle/30 Tage/7 Tage)

### Mittelfristig:
- **Backtesting Framework**: Strategie-Testing auf historischen Daten
- **Correlation Filter**: Vollständige Implementierung
- **Adaptive Risk Management**: Volatility-adjusted Position Sizing
- **Limit Orders**: Unterstützung für Limit Orders

### Langfristig:
- **Machine Learning**: ML-basierte Signal-Erkennung
- **Portfolio Optimization**: Optimale Portfolio-Allokation
- **Multi-Exchange Support**: Unterstützung für weitere Exchanges

---

## 📝 Zusammenfassung

Der Trading Bot bietet:

✅ **10+ Technische Indikatoren**  
✅ **8 Kern-Strategien** (Trend, Mean Reversion, Volatility)  
✅ **Market Regime Detection** (Trending/Ranging/Volatile)  
✅ **7 Candlestick Patterns**  
✅ **Multi-Timeframe Analysis** (M1, M5, M15)  
✅ **Ensemble Decision Making** mit weighted confidence  
✅ **Umfassendes Risikomanagement** (Kelly, ATR-basiert, Multi-Target)  
✅ **Circuit Breaker** Sicherheitssystem  
✅ **Market Filters** (BTC Crash, Funding Rate, Correlation)  
✅ **Paper & Live Trading** Modes  
✅ **Bybit Integration** (vollständig)  
✅ **Notion Integration** (3 Databases)  
✅ **REST API** für n8n Integration  
✅ **Konfigurierbar** via YAML  
✅ **Logging & Monitoring**  

**Total: 15+ Hauptfunktionen mit 50+ Unter-Features**

