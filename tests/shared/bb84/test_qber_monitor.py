"""Tests for the QBER monitor and intrusion detection."""

from shared.bb84.protocol import BB84RoundResult
from shared.bb84.qber_monitor import QBEREvent, QBERMonitor, QBERSnapshot


def _make_result(qber=0.03, aborted=False, abort_reason=None,
                 sifted_bits=200, final_key_bits=128):
    return BB84RoundResult(
        key=b'\x00' * 16 if not aborted else None,
        qber=qber,
        is_secure=qber < 0.11,
        raw_bits_generated=4096,
        sifted_bits=sifted_bits,
        final_key_bits=final_key_bits if not aborted else 0,
        detection_events=400,
        dark_count_fraction=0.001,
        multi_photon_fraction=0.0,
        aborted=aborted,
        abort_reason=abort_reason,
        duration_seconds=0.5,
    )


class TestQBERMonitor:
    def test_normal_event(self):
        monitor = QBERMonitor()
        result = _make_result(qber=0.03)
        snapshot = monitor.record_round(result)
        assert snapshot.event == QBEREvent.NORMAL

    def test_warning_event(self):
        monitor = QBERMonitor()
        result = _make_result(qber=0.08)
        snapshot = monitor.record_round(result)
        assert snapshot.event == QBEREvent.WARNING

    def test_intrusion_detected(self):
        monitor = QBERMonitor()
        result = _make_result(qber=0.25, aborted=True,
                              abort_reason="QBER exceeds threshold")
        snapshot = monitor.record_round(result)
        assert snapshot.event == QBEREvent.INTRUSION_DETECTED

    def test_key_generation_failed(self):
        monitor = QBERMonitor()
        result = _make_result(qber=0.02, aborted=True,
                              abort_reason="Insufficient sifted bits")
        snapshot = monitor.record_round(result)
        assert snapshot.event == QBEREvent.KEY_GENERATION_FAILED

    def test_history_bounded(self):
        monitor = QBERMonitor(history_size=5)
        for _ in range(10):
            monitor.record_round(_make_result())
        history = monitor.get_history()
        assert len(history) == 5

    def test_listener_called(self):
        monitor = QBERMonitor()
        snapshots = []
        monitor.add_listener(lambda s: snapshots.append(s))
        monitor.record_round(_make_result())
        assert len(snapshots) == 1
        assert isinstance(snapshots[0], QBERSnapshot)

    def test_remove_listener(self):
        monitor = QBERMonitor()
        snapshots = []
        callback = lambda s: snapshots.append(s)
        monitor.add_listener(callback)
        monitor.remove_listener(callback)
        monitor.record_round(_make_result())
        assert len(snapshots) == 0

    def test_summary_aggregate_stats(self):
        monitor = QBERMonitor()
        monitor.record_round(_make_result(qber=0.02))
        monitor.record_round(_make_result(qber=0.04))
        monitor.record_round(_make_result(qber=0.25, aborted=True,
                                          abort_reason="QBER exceeds threshold"))

        summary = monitor.get_summary()
        assert summary['total_rounds'] == 3
        assert summary['successful_rounds'] == 2
        assert summary['failed_rounds'] == 1
        assert summary['intrusion_count'] == 1
        assert summary['threshold'] == 0.11

    def test_reset(self):
        monitor = QBERMonitor()
        monitor.record_round(_make_result())
        monitor.reset()
        summary = monitor.get_summary()
        assert summary['total_rounds'] == 0
        assert len(monitor.get_history()) == 0

    def test_snapshot_to_dict(self):
        monitor = QBERMonitor()
        snapshot = monitor.record_round(_make_result(qber=0.03))
        d = snapshot.to_dict()
        assert d['qber'] == 0.03
        assert d['event'] == 'normal'
        assert 'timestamp' in d
