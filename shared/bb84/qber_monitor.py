"""QBER monitoring and intrusion detection for BB84.

Tracks quantum bit error rate over time, detects eavesdropping when
QBER exceeds configurable thresholds, and provides aggregate metrics
for dashboard display.
"""
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import Enum
from threading import Lock

from shared.bb84.protocol import BB84RoundResult


class QBEREvent(Enum):
    """Classification of a BB84 round outcome."""
    NORMAL = "normal"
    WARNING = "warning"
    INTRUSION_DETECTED = "intrusion_detected"
    KEY_REDISTRIBUTED = "key_redistributed"
    KEY_GENERATION_FAILED = "key_generation_failed"


@dataclass
class QBERSnapshot:
    """Point-in-time record of a BB84 round with classification."""
    timestamp: float
    qber: float
    event: QBEREvent
    sifted_bits: int
    final_key_bits: int
    detection_rate: float
    dark_count_fraction: float
    duration_seconds: float
    abort_reason: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d['event'] = self.event.value
        return d


class QBERMonitor:
    """Tracks QBER over time and triggers intrusion detection.

    Usage:
        monitor = QBERMonitor(threshold=0.11)
        monitor.add_listener(lambda snapshot: print(snapshot))

        # Feed BB84 round results
        monitor.record_round(result)

        # Get dashboard data
        summary = monitor.get_summary()
        history = monitor.get_history()
    """

    def __init__(self, threshold: float = 0.11,
                 warning_threshold: float = 0.05,
                 history_size: int = 100):
        self.threshold = threshold
        self.warning_threshold = warning_threshold
        self._history: deque[QBERSnapshot] = deque(maxlen=history_size)
        self._listeners: list[Callable[[QBERSnapshot], None]] = []
        self._lock = Lock()
        self._intrusion_count = 0
        self._total_rounds = 0
        self._successful_rounds = 0
        self._failed_rounds = 0
        self._total_sifted_bits = 0
        self._total_final_bits = 0

    def add_listener(self, callback: Callable[[QBERSnapshot], None]):
        """Register a callback invoked on each recorded round."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[QBERSnapshot], None]):
        """Unregister a previously added callback."""
        self._listeners = [listener for listener in self._listeners if listener is not callback]

    def record_round(self, result: BB84RoundResult) -> QBERSnapshot:
        """Process a BB84 round result and emit appropriate events.

        Classifies the result, updates aggregate stats, appends to
        history, and notifies all listeners.
        """
        # Classify the event
        if result.aborted:
            if result.qber >= self.threshold:
                event = QBEREvent.INTRUSION_DETECTED
            else:
                event = QBEREvent.KEY_GENERATION_FAILED
        elif result.qber >= self.warning_threshold:
            event = QBEREvent.WARNING
        else:
            event = QBEREvent.NORMAL

        # Compute detection rate from raw stats
        detection_rate = (result.detection_events / result.raw_bits_generated
                          if result.raw_bits_generated > 0 else 0.0)

        snapshot = QBERSnapshot(
            timestamp=time.time(),
            qber=result.qber,
            event=event,
            sifted_bits=result.sifted_bits,
            final_key_bits=result.final_key_bits,
            detection_rate=detection_rate,
            dark_count_fraction=result.dark_count_fraction,
            duration_seconds=result.duration_seconds,
            abort_reason=result.abort_reason,
        )

        with self._lock:
            self._history.append(snapshot)
            self._total_rounds += 1
            self._total_sifted_bits += result.sifted_bits
            self._total_final_bits += result.final_key_bits

            if result.aborted:
                self._failed_rounds += 1
                if event == QBEREvent.INTRUSION_DETECTED:
                    self._intrusion_count += 1
            else:
                self._successful_rounds += 1

        # Notify listeners
        for listener in self._listeners:
            listener(snapshot)

        return snapshot

    def get_history(self) -> list[QBERSnapshot]:
        """Return a copy of the QBER history."""
        with self._lock:
            return list(self._history)

    def get_summary(self) -> dict:
        """Return aggregate metrics for dashboard display."""
        with self._lock:
            history = list(self._history)

        recent_qbers = [s.qber for s in history[-10:]] if history else []
        avg_qber = sum(recent_qbers) / len(recent_qbers) if recent_qbers else 0.0

        latest = history[-1] if history else None

        return {
            'total_rounds': self._total_rounds,
            'successful_rounds': self._successful_rounds,
            'failed_rounds': self._failed_rounds,
            'intrusion_count': self._intrusion_count,
            'current_qber': latest.qber if latest else None,
            'average_qber_last_10': round(avg_qber, 6),
            'total_sifted_bits': self._total_sifted_bits,
            'total_final_bits': self._total_final_bits,
            'latest_event': latest.event.value if latest else None,
            'threshold': self.threshold,
            'warning_threshold': self.warning_threshold,
        }

    def reset(self):
        """Clear all history and counters."""
        with self._lock:
            self._history.clear()
            self._intrusion_count = 0
            self._total_rounds = 0
            self._successful_rounds = 0
            self._failed_rounds = 0
            self._total_sifted_bits = 0
            self._total_final_bits = 0
