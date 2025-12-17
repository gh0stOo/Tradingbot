"""
Bot State Machine

Zentrale State Machine für deterministisches Bot-Verhalten.
Verhindert Race Conditions und mehrfache gleichzeitige Trades.

States:
- IDLE: Bot wartet auf Signale
- EVALUATING: Bot evaluiert Strategien
- IN_POSITION: Bot hat offene Position(en)
- COOLDOWN: Bot wartet nach Trade-Exit
- ERROR: Bot hat einen Fehler festgestellt

Regeln:
- Nur EIN State zur Zeit
- Klare Übergänge zwischen States
- Strategien dürfen NUR im State EVALUATING geprüft werden
- Entry ist NUR aus IDLE erlaubt
- Exit erzwingt COOLDOWN
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging


class BotState(Enum):
    """Bot State Enum"""
    IDLE = "IDLE"
    EVALUATING = "EVALUATING"
    IN_POSITION = "IN_POSITION"
    COOLDOWN = "COOLDOWN"
    ERROR = "ERROR"


class BotStateMachine:
    """
    Zentrale State Machine für Trading Bot

    Erzwingt deterministisches Verhalten:
    - Maximal eine Strategie pro Trade
    - Keine gleichzeitigen Entries
    - Klare Cooldown-Perioden
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize State Machine

        Args:
            config: Bot configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.config = config

        # State tracking
        self.current_state = BotState.IDLE
        self.previous_state = None
        self.state_entered_at = datetime.utcnow()

        # Cooldown configuration
        self.cooldown_minutes = config.get("circuitBreaker", {}).get("cooldownMinutes", 60)
        self.cooldown_end_time: Optional[datetime] = None

        # Position tracking
        self.open_positions = 0
        self.max_positions = config.get("risk", {}).get("maxPositions", 3)

        # Error tracking
        self.error_message: Optional[str] = None
        self.error_count = 0

        self.logger.info(f"State Machine initialized. State: {self.current_state.value}")

    def get_state(self) -> BotState:
        """Get current state"""
        return self.current_state

    def can_evaluate_strategies(self) -> bool:
        """
        Check if bot can evaluate strategies

        Returns:
            True if bot is in IDLE state and can transition to EVALUATING
        """
        # Check if in cooldown
        if self.current_state == BotState.COOLDOWN:
            if self._is_cooldown_expired():
                self._transition_to(BotState.IDLE)
                return True
            return False

        # Check if at max positions
        if self.open_positions >= self.max_positions:
            return False

        # Can evaluate if IDLE
        return self.current_state == BotState.IDLE

    def can_enter_position(self) -> bool:
        """
        Check if bot can enter a position

        Returns:
            True if bot is in EVALUATING state
        """
        return (
            self.current_state == BotState.EVALUATING and
            self.open_positions < self.max_positions
        )

    def start_evaluation(self) -> bool:
        """
        Transition to EVALUATING state

        Returns:
            True if transition successful, False otherwise
        """
        if not self.can_evaluate_strategies():
            self.logger.debug(
                f"Cannot start evaluation. State: {self.current_state.value}, "
                f"Positions: {self.open_positions}/{self.max_positions}"
            )
            return False

        self._transition_to(BotState.EVALUATING)
        return True

    def enter_position(self, symbol: str) -> bool:
        """
        Transition to IN_POSITION state after successful entry

        Args:
            symbol: Symbol that was entered

        Returns:
            True if transition successful
        """
        if not self.can_enter_position():
            self.logger.warning(
                f"Cannot enter position for {symbol}. State: {self.current_state.value}"
            )
            return False

        self.open_positions += 1
        self.logger.info(f"Position entered: {symbol}. Total positions: {self.open_positions}")

        # If at max positions, go to IN_POSITION, otherwise back to IDLE
        if self.open_positions >= self.max_positions:
            self._transition_to(BotState.IN_POSITION)
        else:
            self._transition_to(BotState.IDLE)

        return True

    def exit_position(self, symbol: str, force_cooldown: bool = True) -> bool:
        """
        Handle position exit

        Args:
            symbol: Symbol that was exited
            force_cooldown: If True, enter cooldown after exit

        Returns:
            True if transition successful
        """
        if self.open_positions > 0:
            self.open_positions -= 1
            self.logger.info(f"Position exited: {symbol}. Remaining positions: {self.open_positions}")

        # If no more positions and cooldown requested, enter cooldown
        if self.open_positions == 0 and force_cooldown:
            self._start_cooldown()
        # If still have positions but below max, go to IDLE
        elif self.open_positions < self.max_positions:
            self._transition_to(BotState.IDLE)

        return True

    def cancel_evaluation(self) -> bool:
        """
        Cancel evaluation and return to IDLE

        Returns:
            True if transition successful
        """
        if self.current_state == BotState.EVALUATING:
            self._transition_to(BotState.IDLE)
            return True
        return False

    def set_error(self, error_message: str) -> None:
        """
        Set error state

        Args:
            error_message: Error message
        """
        self.error_message = error_message
        self.error_count += 1
        self.logger.error(f"State Machine ERROR: {error_message}")
        self._transition_to(BotState.ERROR)

    def clear_error(self) -> bool:
        """
        Clear error state and return to IDLE

        Returns:
            True if transition successful
        """
        if self.current_state == BotState.ERROR:
            self.error_message = None
            self._transition_to(BotState.IDLE)
            self.logger.info("Error state cleared, returned to IDLE")
            return True
        return False

    def update_position_count(self, count: int) -> None:
        """
        Update open position count from external source

        Args:
            count: Current number of open positions
        """
        if count != self.open_positions:
            self.logger.debug(f"Position count updated: {self.open_positions} -> {count}")
            self.open_positions = count

            # Auto-transition based on position count
            if count == 0 and self.current_state == BotState.IN_POSITION:
                self._transition_to(BotState.IDLE)
            elif count >= self.max_positions and self.current_state != BotState.IN_POSITION:
                self._transition_to(BotState.IN_POSITION)

    def get_status(self) -> Dict[str, Any]:
        """
        Get current state machine status

        Returns:
            Status dictionary
        """
        return {
            "state": self.current_state.value,
            "previousState": self.previous_state.value if self.previous_state else None,
            "stateEnteredAt": self.state_entered_at.isoformat(),
            "timeSinceStateChange": (datetime.utcnow() - self.state_entered_at).total_seconds(),
            "openPositions": self.open_positions,
            "maxPositions": self.max_positions,
            "canEvaluate": self.can_evaluate_strategies(),
            "canEnter": self.can_enter_position(),
            "inCooldown": self.current_state == BotState.COOLDOWN,
            "cooldownEndsAt": self.cooldown_end_time.isoformat() if self.cooldown_end_time else None,
            "errorMessage": self.error_message,
            "errorCount": self.error_count
        }

    def _transition_to(self, new_state: BotState) -> None:
        """
        Transition to new state

        Args:
            new_state: New state to transition to
        """
        if new_state == self.current_state:
            return

        self.previous_state = self.current_state
        self.current_state = new_state
        self.state_entered_at = datetime.utcnow()

        self.logger.info(
            f"State transition: {self.previous_state.value} -> {new_state.value}"
        )

    def _start_cooldown(self) -> None:
        """Start cooldown period"""
        self.cooldown_end_time = datetime.utcnow() + timedelta(minutes=self.cooldown_minutes)
        self._transition_to(BotState.COOLDOWN)
        self.logger.info(f"Cooldown started. Ends at: {self.cooldown_end_time.isoformat()}")

    def _is_cooldown_expired(self) -> bool:
        """
        Check if cooldown period has expired

        Returns:
            True if cooldown expired
        """
        if not self.cooldown_end_time:
            return True

        return datetime.utcnow() >= self.cooldown_end_time
