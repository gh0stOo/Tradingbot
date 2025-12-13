# Discord Integration - Trade Notifications

## ✅ Implementierung

Der Bot sendet jetzt **direkt Discord-Nachrichten** für:
1. **Jedes Trading-Signal** (bei jeder Analyse, wenn ein Signal erkannt wird)
2. **Nach Trade-Execution** (wenn ein Trade erfolgreich ausgeführt wurde)

---

## 📨 Nachrichten-Formate

### 1. Signal-Nachricht (bei jeder Analyse mit Signal)

**Erscheint:** Sofort wenn ein Trading-Signal erkannt wird (vor Execution)

**Format:**
```
🚀 New Trading Signal

Symbol: BTCUSDT
Side: 🟢 Buy
Price: $50,000.0000
Confidence: 75.5%

Quantity: 0.1000
Stop Loss: $49,000.0000
Take Profit: $52,000.0000

Multi-Target Exits:
  TP1: $51,500.0000 (25%)
  TP2: $53,000.0000 (25%)
  TP3: $55,000.0000 (25%)
  TP4: $58,000.0000 (25%)

Strategies: emaTrend, macdTrend, volumeProfile
Market Regime: Trending
Mode: 📄 PAPER
```

**Farbe:** 
- 🟢 Grün (0x00ff00) für Buy-Signale
- 🔴 Rot (0xff0000) für Sell-Signale

---

### 2. Execution-Nachricht (nach Trade-Ausführung)

**Erscheint:** Nach erfolgreicher Trade-Execution

**Format:**
```
✅ Trade Executed

Symbol: BTCUSDT
Side: 🟢 Buy
Price: $50,000.0000
Confidence: 75.5%

Order ID: PAPER_1234567890_abc123
Status: ✅ Executed Successfully

Quantity: 0.1000
Stop Loss: $49,000.0000
Take Profit: $52,000.0000

Multi-Target Exits:
  TP1: $51,500.0000 (25%)
  TP2: $53,000.0000 (25%)
  TP3: $55,000.0000 (25%)
  TP4: $58,000.0000 (25%)

Strategies: emaTrend, macdTrend, volumeProfile
Market Regime: Trending
Mode: 📄 PAPER
```

**Bei Fehler:**
```
❌ Trade Execution Failed

Symbol: BTCUSDT
Side: 🟢 Buy
Price: $50,000.0000

Order ID: N/A
Error: ❌ Insufficient balance

...
```

---

## 🔧 Konfiguration

### Discord Webhook in config.yaml

```yaml
alerts:
  enabled: true
  discordWebhook: "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"
```

**Status:** ✅ Bereits konfiguriert mit deiner Webhook-URL

---

## 🎯 Verhalten

### Signal-Nachricht wird gesendet:
- ✅ Bei **jeder Analyse**, wenn ein Signal erkannt wird (Buy/Sell)
- ✅ **Vor** der Trade-Execution
- ✅ Auch wenn der Trade später nicht ausgeführt wird (z.B. wegen Filter)

### Execution-Nachricht wird gesendet:
- ✅ Nur wenn `execution.success = true`
- ✅ **Nach** erfolgreicher Trade-Execution
- ✅ Enthält Order ID und Execution-Details

---

## 📊 Beispiel-Discord-Embed

Die Nachrichten werden als Discord Embeds gesendet mit:

- **Titel:** "🚀 New Trading Signal" oder "✅ Trade Executed"
- **Farbe:** Grün (Buy) oder Rot (Sell)
- **Felder:**
  - Symbol, Side, Price
  - Confidence, Quantity
  - Stop Loss, Take Profit
  - Multi-Target Exits (wenn aktiviert)
  - Strategies verwendet
  - Market Regime
  - Trading Mode (PAPER/TESTNET/LIVE)
- **Footer:** "Crypto Trading Bot"
- **Timestamp:** UTC Zeit

---

## ✅ Status

- ✅ **Signal-Nachrichten:** Implementiert und aktiv
- ✅ **Execution-Nachrichten:** Implementiert und aktiv
- ✅ **Discord Webhook:** Konfiguriert
- ✅ **Multi-Target Exits:** Werden in Nachrichten angezeigt
- ✅ **Trading Mode:** Wird angezeigt (PAPER/TESTNET/LIVE)

---

## 🚀 Nächste Schritte

1. **Bot starten:**
   ```bash
   python src/main.py
   ```

2. **Discord beobachten:**
   - Bei jedem Signal erscheint eine Nachricht
   - Nach Execution erscheint eine weitere Nachricht

3. **Testen:**
   - Bot läuft im PAPER Mode (sicher)
   - Signale werden sofort in Discord gepostet
   - Executions werden nach erfolgreicher Ausführung gepostet

---

## 📝 Hinweise

- **Keine Signale?** → Der Bot sendet nur Signale wenn ein Trade-Signal erkannt wird (nicht bei "Hold")
- **Keine Executions?** → Execution-Nachrichten erscheinen nur wenn der Trade erfolgreich ausgeführt wurde
- **Beide Nachrichten?** → Ja, du bekommst sowohl Signal- als auch Execution-Nachricht (wenn ausgeführt)

---

**Viel Erfolg! 🚀**

