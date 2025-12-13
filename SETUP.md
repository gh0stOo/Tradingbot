# Setup Guide

## Installation

1. **Install Python 3.10+**

2. **Install Dependencies**
```bash
cd crypto_trading_bot
pip install -r requirements.txt
```

3. **Configure Environment**
```bash
# Copy example env file
cp .env.example .env

# Edit .env with your credentials
# - BYBIT_API_KEY (for LIVE mode)
# - BYBIT_API_SECRET (for LIVE mode)
# - NOTION_API_KEY
# - NOTION_DB_SIGNALS, NOTION_DB_EXECUTIONS, NOTION_DB_DAILY_STATS
```

4. **Configure config.yaml**
Edit `config/config.yaml` to adjust:
- Trading mode (PAPER/LIVE)
- Universe selection
- Risk parameters
- Strategy weights

## Running

### Paper Mode (Default)
```bash
python src/main.py
```

### With API Server (for n8n)
Terminal 1 - Bot:
```bash
python src/main.py
```

Terminal 2 - API Server:
```bash
python src/api/server.py
```

The API server runs on `http://localhost:8000` by default.

## n8n Workflow Setup

1. Create HTTP Request node listening to: `POST http://localhost:8000/api/v1/trade/signal`

2. Process the signal data:
   - Extract: symbol, side, price, confidence, strategies, orderId

3. Send Discord notification with trade details

## Testing

Run unit tests:
```bash
python -m pytest tests/
```

Or run individual test files:
```bash
python tests/test_indicators.py
python tests/test_strategies.py
python tests/test_risk_manager.py
```

