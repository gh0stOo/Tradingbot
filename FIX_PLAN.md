# 🔧 REPARATUR-PLAN - KRITISCHE FEHLER BEHEBEN

**Priorität:** Kritisch → Hoch → Mittel → Niedrig

---

## PHASE 1: KRITISCHE BLOCKER (MUSS ZUERST GEFIXT WERDEN)

### Fix 1.1: Position Sizing implementieren

**Dateien:** `src/core/strategy_allocator.py`, `src/core/risk_engine.py`, `src/trading/risk_manager.py`

**Was fehlt:**
- Position Sizing Logik die `quantity` basierend auf Risk-Parametern berechnet

**Implementierung:**

1. **PositionSizer Klasse erstellen** (`src/core/position_sizer.py`):
```python
class PositionSizer:
    def calculate_position_size(
        self,
        equity: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        max_risk_pct: Decimal,
        side: str
    ) -> Decimal:
        """
        Calculate position size based on risk percentage.
        
        Formula: quantity = (equity * risk_pct) / (entry_price - stop_loss)
        """
        if entry_price <= 0 or stop_loss <= 0:
            return Decimal("0")
        
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0:
            return Decimal("0")
        
        risk_amount = equity * max_risk_pct
        quantity = risk_amount / risk_per_unit
        
        return quantity
```

2. **In StrategyAllocator integrieren:**
```python
# In _create_order_intent()
if not signal.quantity or signal.quantity == 0:
    # Calculate position size
    position_sizer = PositionSizer()
    equity = self.trading_state.equity
    max_risk = Decimal(str(self.config.get("risk", {}).get("riskPct", 0.002)))
    
    quantity = position_sizer.calculate_position_size(
        equity=equity,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        max_risk_pct=max_risk,
        side=signal.side
    )
else:
    quantity = signal.quantity
```

**Testing:**
- Unit-Tests für PositionSizer
- Integration-Tests: Verify quantity > 0 für alle Signals

---

### Fix 1.2: Lookahead-Bias im Backtest beheben

**Dateien:** `src/backtesting/event_backtest.py:220-245`

**Problem:** `_get_klines_window` inkludiert aktuelle Candle

**Fix:**
```python
def _get_klines_window(
    self,
    data: pd.DataFrame,
    current_idx: int,
    window: int = 50
) -> List[List]:
    """Get klines window UP TO (but not including) current index"""
    start_idx = max(0, current_idx - window)
    end_idx = current_idx  # EXCLUDE current candle (no lookahead!)
    
    window_data = data.iloc[start_idx:end_idx]  # No +1!
    
    # ... rest of code
```

**Testing:**
- Backtest mit bekanntem Ergebnis
- Verify Strategien nutzen nur Daten bis idx-1

---

### Fix 1.3: Variable vor Initialisierung - Reihenfolge korrigieren

**Datei:** `src/main_event_driven.py:101-122`

**Fix:**
```python
# Initialize TradingState FIRST
initial_equity = Decimal(str(get_equity(config, bybit_client)))
trading_state = TradingState(initial_cash=initial_equity)

# THEN initialize StatePersistence
from core.state_persistence import StatePersistence
state_persistence = None
try:
    state_persistence = StatePersistence(db, trading_state)
    # ... rest
```

**Testing:**
- Bot muss ohne Fehler starten

---

### Fix 1.4: Idempotenz reparieren

**Dateien:** `src/core/order_executor.py:65-69`, `src/events/order_intent_event.py`

**Problem:** UUID wird jedes Mal neu generiert

**Fix:**

1. **OrderIntentEvent muss deterministische ID haben:**
```python
# In OrderIntentEvent creation (StrategyAllocator)
order_intent_id = f"{signal.event_id}_{signal.symbol}_{signal.side}_{int(signal.entry_price * 1000)}"
```

2. **OrderExecutor nutzt Intent-ID:**
```python
def execute_approved_order(self, approval_event: RiskApprovalEvent) -> Optional[OrderSubmissionEvent]:
    intent = approval_event.original_intent
    
    # Use intent event_id as base for client_order_id (deterministic!)
    client_order_id = f"{intent.event_id}_{int(time.time() * 1000)}"  # Add timestamp for uniqueness within same intent
    
    # Better: Use intent_id from approval_event
    client_order_id = f"INTENT_{approval_event.order_intent_id}"
    
    # Check idempotency
    existing_order = self.trading_state.get_order(client_order_id)
    if existing_order and existing_order.status in ["submitted", "filled"]:
        # Order already exists, return existing
        return OrderSubmissionEvent(...)
```

**Alternative:** Store mapping `intent_id -> client_order_id` in TradingState

**Testing:**
- Retry same intent multiple times
- Verify only one order created

---

### Fix 1.5: Equity Update nach State-Mutation

**Datei:** `src/core/trading_state.py`

**Fix:**
```python
def add_position(...) -> bool:
    with self._lock:
        # ... add position logic ...
        self._open_positions[symbol] = position
        self._update_exposure(symbol, quantity * entry_price)
        self._update_equity()  # ADD THIS
        self._notify_listeners()
        return True

def remove_position(...) -> Optional[Position]:
    with self._lock:
        # ... remove position logic ...
        self._daily_pnl += realized_pnl
        self._trades_today += 1
        self._update_equity()  # ADD THIS
        self._notify_listeners()
        return position

def debit_cash(...) -> bool:
    with self._lock:
        # ... debit logic ...
        self._cash -= amount
        self._update_equity()  # ADD THIS
        return True

def credit_cash(...) -> None:
    with self._lock:
        self._cash += amount
        self._update_equity()  # ADD THIS
```

**Testing:**
- Verify equity is always current after mutations
- Risk checks use correct equity

---

### Fix 1.6: Daily Stats Reset implementieren

**Datei:** `src/main_event_driven.py` (Main Loop)

**Fix:**
```python
# In main loop
last_reset_date = datetime.utcnow().date()

while True:
    # ... existing code ...
    
    # Check if new day (UTC)
    current_date = datetime.utcnow().date()
    if current_date != last_reset_date:
        logger.info("New day detected, resetting daily stats")
        trading_state.reset_daily_stats()
        risk_engine._reset_daily_counters_if_needed()  # Reset internal counters
        strategy_allocator._reset_daily_counters_if_needed()
        last_reset_date = current_date
    
    # ... rest of loop ...
```

**Testing:**
- Verify daily stats reset at UTC midnight
- Verify limits work correctly after reset

---

## PHASE 2: HOHE RISIKEN (Nächste Priorität)

### Fix 2.1: Stop-Loss Validierung

**Dateien:** `src/core/risk_engine.py:_check_risk_per_trade`

**Fix:**
```python
def _check_risk_per_trade(...) -> Dict:
    # ... existing checks ...
    
    # Validate stop loss is reasonable
    if side == "Buy":
        if stop_loss >= entry_price:
            return {"passed": False, "reason": "Stop loss must be below entry price for long"}
        if stop_loss <= 0:
            return {"passed": False, "reason": "Stop loss must be positive"}
    else:  # Sell
        if stop_loss <= entry_price:
            return {"passed": False, "reason": "Stop loss must be above entry price for short"}
        if stop_loss <= 0:
            return {"passed": False, "reason": "Stop loss must be positive"}
    
    # Check stop loss distance is reasonable (not too wide)
    risk_per_unit = abs(entry_price - stop_loss)
    risk_pct_of_price = risk_per_unit / entry_price
    
    if risk_pct_of_price > Decimal("0.20"):  # Max 20% risk
        return {"passed": False, "reason": f"Stop loss too wide: {float(risk_pct_of_price * 100):.2f}% of price"}
    
    # ... rest of checks ...
```

---

### Fix 2.2: Slippage in Paper Trading

**Dateien:** `src/core/order_executor.py:_execute_paper_order`

**Fix:**
```python
def _execute_paper_order(...) -> OrderSubmissionEvent:
    # Simulate slippage
    slippage_model = SlippageModel()  # Already exists
    slippage = slippage_model.calculate_slippage(
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=order.price,
        volume_24h=0  # Could fetch from market data
    )
    
    if order.side == "Buy":
        filled_price = order.price + slippage
    else:
        filled_price = order.price - slippage
    
    # ... rest of code ...
```

---

### Fix 2.3: Leverage konfigurierbar machen

**Dateien:** `src/core/order_executor.py`, `config/config.yaml`

**Fix:**

1. **Config:**
```yaml
trading:
  leverage: 10  # Default leverage
  # Per-asset leverage can be configured
```

2. **OrderExecutor:**
```python
def __init__(...):
    # ...
    self.leverage = Decimal(str(config.get("trading", {}).get("leverage", 10)))

def _execute_paper_order(...):
    # ...
    margin_required = notional_value / self.leverage
```

---

### Fix 2.4: Signal Timestamp setzen

**Dateien:** `src/strategies/*.py`

**Fix:**
```python
signal = SignalEvent(
    symbol=market_event.symbol,
    side="Buy",
    # ...
    timestamp=market_event.timestamp,  # ADD THIS
    # ...
)
```

---

## PHASE 3: TECHNISCHE SCHULD

### Fix 3.1: Magic Numbers in Config

**Dateien:** Alle Strategy-Dateien

**Fix:**
- Alle Magic Numbers in `config.yaml` verschieben
- Defaults in Config definieren

---

### Fix 3.2: Exception Handling verbessern

**Dateien:** Überall

**Fix:**
- Spezifische Exceptions statt `Exception`
- Retry-Logik für kritische Operations
- Circuit-Breaker bei wiederholten Fehlern

---

### Fix 3.3: API Response Validierung

**Dateien:** `src/integrations/bybit.py`, `src/core/order_executor.py`

**Fix:**
```python
def _validate_order_response(self, response: Dict) -> bool:
    if not response:
        return False
    
    ret_code = response.get("retCode", 0)
    if ret_code != 0:
        error_msg = response.get("retMsg", "Unknown error")
        logger.error(f"Bybit API error: {ret_code} - {error_msg}")
        return False
    
    if "result" not in response:
        return False
    
    return True
```

---

## PHASE 4: STRATEGISCHE VERBESSERUNGEN

### Fix 4.1: Multi-Target Exits

**Dateien:** `src/core/trading_state.py:Position`

**Fix:**
```python
@dataclass
class Position:
    # ... existing fields ...
    take_profit_1: Decimal
    take_profit_2: Optional[Decimal] = None
    take_profit_3: Optional[Decimal] = None
    take_profit_4: Optional[Decimal] = None
    
    tp1_filled: bool = False
    tp2_filled: bool = False
    tp3_filled: bool = False
    tp4_filled: bool = False
```

---

### Fix 4.2: Regime-basierte Strategy-Deaktivierung

**Dateien:** `src/strategies/*.py`

**Fix:**
```python
def generate_signals(self, market_event: MarketEvent) -> List[SignalEvent]:
    # Check if strategy should trade in current regime
    regime = market_event.regime  # From MarketEvent
    allowed_regimes = self.config.get("allowedRegimes", ["trending", "ranging", "volatile"])
    
    if regime not in allowed_regimes:
        return []  # Don't trade in this regime
    
    # ... rest of signal generation ...
```

---

## TESTING CHECKLIST

Nach jedem Fix:

- [ ] Unit-Tests schreiben
- [ ] Integration-Tests
- [ ] Backtest läuft ohne Lookahead-Bias
- [ ] Bot startet ohne Fehler
- [ ] Position Sizing funktioniert
- [ ] Keine Duplikat-Orders bei Retries
- [ ] Daily Reset funktioniert
- [ ] Equity ist immer aktuell

---

## PRIORITÄTS-REIHENFOLGE

1. **Fix 1.1-1.6** (Phase 1) - KRITISCH, muss zuerst
2. **Fix 2.1-2.4** (Phase 2) - Hohe Priorität
3. **Fix 3.1-3.3** (Phase 3) - Technische Schuld
4. **Fix 4.1-4.2** (Phase 4) - Strategische Verbesserungen

**Geschätzte Zeit:**
- Phase 1: 2-3 Tage
- Phase 2: 1-2 Tage
- Phase 3: 1 Tag
- Phase 4: 2-3 Tage

**Gesamt: ~1-2 Wochen für produktionsreifen Bot**

