"""Tests for utils/signal.py - Observer pattern implementation."""

import pytest
from utils.signal import Signal


class TestSignalConnect:

    def test_connect_and_emit(self):
        sig = Signal()
        results = []
        sig.connect(lambda x: results.append(x))
        sig.emit(42)
        assert results == [42]

    def test_multiple_callbacks(self):
        sig = Signal()
        results = []
        sig.connect(lambda: results.append("a"))
        sig.connect(lambda: results.append("b"))
        sig.emit()
        assert results == ["a", "b"]

    def test_emit_with_kwargs(self):
        sig = Signal()
        results = []
        sig.connect(lambda name="": results.append(name))
        sig.emit(name="test")
        assert results == ["test"]

    def test_handler_count(self):
        sig = Signal()
        assert sig.handler_count == 0
        sig.connect(lambda: None)
        assert sig.handler_count == 1
        sig.connect(lambda: None)
        assert sig.handler_count == 2


class TestSignalDisconnect:

    def test_disconnect_existing(self):
        sig = Signal()
        cb = lambda: None  # noqa: E731
        sig.connect(cb)
        assert sig.disconnect(cb) is True
        assert sig.handler_count == 0

    def test_disconnect_nonexistent(self):
        sig = Signal()
        assert sig.disconnect(lambda: None) is False

    def test_disconnect_prevents_future_emit(self):
        sig = Signal()
        results = []
        cb = lambda: results.append("called")  # noqa: E731
        sig.connect(cb)
        sig.disconnect(cb)
        sig.emit()
        assert results == []


class TestSignalClear:

    def test_clear_removes_all(self):
        sig = Signal()
        sig.connect(lambda: None)
        sig.connect(lambda: None)
        sig.clear()
        assert sig.handler_count == 0

    def test_clear_then_emit_safe(self):
        sig = Signal()
        results = []
        sig.connect(lambda: results.append(1))
        sig.clear()
        sig.emit()
        assert results == []


class TestSignalErrorHandling:

    def test_callback_error_doesnt_stop_others(self, capsys):
        sig = Signal()
        results = []
        sig.connect(lambda: (_ for _ in ()).throw(RuntimeError("boom")))  # raises
        sig.connect(lambda: results.append("ok"))
        sig.emit()
        # Second callback should still run despite first raising
        assert results == ["ok"]
        captured = capsys.readouterr()
        assert "Error in signal callback" in captured.out


class TestSignalEmitNoCallbacks:

    def test_emit_with_no_callbacks(self):
        sig = Signal()
        sig.emit()  # should not raise
        sig.emit(1, 2, 3, key="val")  # should not raise
