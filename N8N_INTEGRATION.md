# n8n Integration Guide

## Übersicht

Der Trading Bot sendet Trade-Signale über eine REST API, die von n8n abgefangen werden kann, um Discord-Benachrichtigungen zu senden.

## Setup

### 1. Bot API Server starten

```bash
# Terminal 1: Start API Server
python src/api/server.py
```

Der Server läuft standardmäßig auf `http://localhost:8000`

### 2. Trading Bot starten

```bash
# Terminal 2: Start Bot
python src/main.py
```

Der Bot sendet automatisch Signale an den API Server, wenn Trades generiert werden.

## n8n Workflow Setup

### Schritt 1: HTTP Request Node (Webhook)

1. **Node hinzufügen**: "Webhook" Node
2. **HTTP Method**: POST
3. **Path**: `/api/v1/trade/signal`
4. **Response Mode**: "When Last Node Finishes"

### Schritt 2: Data Processing

Nach dem Webhook-Node:
- **Code Node** oder **Set Node** um die Daten zu verarbeiten

Erwartetes Request Body Format:
```json
{
  "symbol": "BTCUSDT",
  "side": "Buy",
  "price": 50000.0,
  "confidence": 0.75,
  "strategies": ["emaTrend", "macdTrend"],
  "regime": "trending",
  "orderId": "PAPER_1234567890_abc123",
  "qty": 0.1,
  "stopLoss": 49000.0,
  "takeProfit": 52000.0
}
```

### Schritt 3: Discord Notification

1. **Discord Node** hinzufügen
2. **Operation**: "Send Message"
3. **Webhook URL**: Deine Discord Webhook URL
4. **Message Format**:

```json
{
  "embeds": [{
    "title": "🚀 New Trading Signal",
    "color": "{{ $json.side === 'Buy' ? 3066993 : 15158332 }}",
    "fields": [
      {"name": "Symbol", "value": "{{ $json.symbol }}", "inline": true},
      {"name": "Side", "value": "{{ $json.side }}", "inline": true},
      {"name": "Price", "value": "{{ $json.price }}", "inline": true},
      {"name": "Confidence", "value": "{{ ($json.confidence * 100).toFixed(1) }}%", "inline": true},
      {"name": "Qty", "value": "{{ $json.qty }}", "inline": true},
      {"name": "Stop Loss", "value": "{{ $json.stopLoss }}", "inline": true},
      {"name": "Take Profit", "value": "{{ $json.takeProfit }}", "inline": true},
      {"name": "Regime", "value": "{{ $json.regime }}", "inline": true},
      {"name": "Strategies", "value": "{{ $json.strategies.join(', ') }}", "inline": false},
      {"name": "Order ID", "value": "{{ $json.orderId }}", "inline": false}
    ],
    "timestamp": "{{ new Date().toISOString() }}",
    "footer": {"text": "Crypto Trading Bot"}
  }]
}
```

## Workflow Beispiel (JSON)

```json
{
  "name": "Trading Bot Discord Notifications",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "trade-signal",
        "responseMode": "responseNode"
      },
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300]
    },
    {
      "parameters": {
        "jsCode": "// Extract data from webhook\nconst data = $input.first().json.body || $input.first().json;\n\nreturn [{\n  json: {\n    symbol: data.symbol,\n    side: data.side,\n    price: data.price,\n    confidence: data.confidence,\n    strategies: data.strategies || [],\n    regime: data.regime,\n    orderId: data.orderId,\n    qty: data.qty,\n    stopLoss: data.stopLoss,\n    takeProfit: data.takeProfit\n  }\n}];"
      },
      "name": "Process Signal",
      "type": "n8n-nodes-base.code",
      "position": [450, 300]
    },
    {
      "parameters": {
        "url": "=YOUR_DISCORD_WEBHOOK_URL",
        "method": "POST",
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ { \"embeds\": [{ \"title\": \"🚀 New Trading Signal\", \"color\": $json.side === 'Buy' ? 3066993 : 15158332, \"fields\": [{ \"name\": \"Symbol\", \"value\": $json.symbol, \"inline\": true }, { \"name\": \"Side\", \"value\": $json.side, \"inline\": true }, { \"name\": \"Price\", \"value\": String($json.price), \"inline\": true }, { \"name\": \"Confidence\", \"value\": String(Math.round($json.confidence * 100)) + '%', \"inline\": true }], \"timestamp\": new Date().toISOString() }] } }}"
      },
      "name": "Discord Notification",
      "type": "n8n-nodes-base.httpRequest",
      "position": [650, 300]
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ { \"success\": true, \"received\": true } }}"
      },
      "name": "Respond to Webhook",
      "type": "n8n-nodes-base.respondToWebhook",
      "position": [850, 300]
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "Process Signal", "type": "main", "index": 0}]]
    },
    "Process Signal": {
      "main": [[{"node": "Discord Notification", "type": "main", "index": 0}]]
    },
    "Discord Notification": {
      "main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]
    }
  }
}
```

## Alternative: Local Testing

Für lokales Testing ohne n8n:

```bash
# Test API endpoint manually
curl -X POST http://localhost:8000/api/v1/trade/signal \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "side": "Buy",
    "price": 50000,
    "confidence": 0.75,
    "strategies": ["emaTrend", "macdTrend"],
    "regime": "trending",
    "orderId": "TEST_123"
  }'
```

## API Endpoints

- `POST /api/v1/trade/signal` - Empfängt Trade-Signale vom Bot
- `GET /api/v1/health` - Health Check
- `GET /api/v1/status` - Bot Status

## Troubleshooting

1. **API Server läuft nicht**: Starte `python src/api/server.py`
2. **Bot sendet keine Signale**: Prüfe ob Bot läuft und ob Trades generiert werden
3. **n8n erhält keine Requests**: Prüfe Firewall/Port 8000
4. **Discord-Notification fehlt**: Prüfe Webhook URL in n8n

