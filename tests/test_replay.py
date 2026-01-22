"""Tests for borsapy replay functionality."""

import time
from datetime import datetime

import pandas as pd
import pytest


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range("2024-01-01", periods=10)
    data = {
        "Open": [100, 102, 104, 103, 105, 107, 106, 108, 110, 109],
        "High": [105, 107, 108, 107, 110, 112, 111, 113, 115, 114],
        "Low": [98, 100, 102, 101, 103, 105, 104, 106, 108, 107],
        "Close": [103, 105, 106, 105, 108, 110, 109, 111, 113, 112],
        "Volume": [1000, 1200, 1100, 900, 1500, 1300, 1400, 1200, 1600, 1100],
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def large_ohlcv():
    """Create large OHLCV data for memory tests."""
    dates = pd.date_range("2020-01-01", periods=1000)
    data = {
        "Open": list(range(100, 1100)),
        "High": list(range(105, 1105)),
        "Low": list(range(95, 1095)),
        "Close": list(range(102, 1102)),
        "Volume": [1000] * 1000,
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def replay_session(sample_ohlcv):
    """Create ReplaySession with sample data."""
    from borsapy.replay import ReplaySession

    return ReplaySession("THYAO", df=sample_ohlcv, speed=0)


# =============================================================================
# Unit Tests - ReplaySession Initialization
# =============================================================================


class TestReplaySessionInit:
    """Tests for ReplaySession initialization."""

    def test_init_basic(self, sample_ohlcv):
        """Test basic initialization."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO", df=sample_ohlcv)

        assert session.symbol == "THYAO"
        assert session.total_candles == 10
        assert session.speed == 1.0

    def test_init_speed(self, sample_ohlcv):
        """Test initialization with custom speed."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO", df=sample_ohlcv, speed=10.0)

        assert session.speed == 10.0

    def test_init_negative_speed_clamped(self, sample_ohlcv):
        """Test that negative speed is clamped to 0."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO", df=sample_ohlcv, speed=-5.0)

        assert session.speed == 0.0

    def test_init_no_data(self):
        """Test initialization without data."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO")

        assert session.total_candles == 0

    def test_init_missing_columns(self):
        """Test initialization with missing columns."""
        from borsapy.replay import ReplaySession

        df = pd.DataFrame({"Open": [100], "Close": [105]})  # Missing High, Low

        with pytest.raises(ValueError, match="missing required columns"):
            ReplaySession("THYAO", df=df)

    def test_symbol_uppercase(self, sample_ohlcv):
        """Test symbol is converted to uppercase."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("thyao", df=sample_ohlcv)

        assert session.symbol == "THYAO"


# =============================================================================
# Unit Tests - Replay Generator
# =============================================================================


class TestReplay:
    """Tests for replay generator."""

    def test_replay_basic(self, replay_session):
        """Test basic replay."""
        candles = list(replay_session.replay())

        assert len(candles) == 10

    def test_replay_candle_structure(self, replay_session):
        """Test candle dict structure."""
        candles = list(replay_session.replay())
        candle = candles[0]

        assert "timestamp" in candle
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
        assert "volume" in candle
        assert "_index" in candle
        assert "_total" in candle
        assert "_progress" in candle

    def test_replay_values_correct(self, replay_session, sample_ohlcv):
        """Test candle values match DataFrame."""
        candles = list(replay_session.replay())

        assert candles[0]["open"] == 100
        assert candles[0]["close"] == 103
        assert candles[0]["volume"] == 1000

        assert candles[-1]["open"] == 109
        assert candles[-1]["close"] == 112

    def test_replay_index_progression(self, replay_session):
        """Test _index increments correctly."""
        candles = list(replay_session.replay())

        for i, candle in enumerate(candles):
            assert candle["_index"] == i

    def test_replay_total_constant(self, replay_session):
        """Test _total is constant throughout replay."""
        candles = list(replay_session.replay())

        for candle in candles:
            assert candle["_total"] == 10

    def test_replay_progress(self, replay_session):
        """Test progress calculation."""
        candles = list(replay_session.replay())

        assert candles[0]["_progress"] == 0.1  # 1/10
        assert candles[-1]["_progress"] == 1.0  # 10/10

    def test_replay_empty_data(self):
        """Test replay with no data."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO")
        candles = list(session.replay())

        assert len(candles) == 0

    def test_replay_generator_memory_efficient(self, large_ohlcv):
        """Test that replay is memory efficient (generator)."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO", df=large_ohlcv, speed=0)

        # Should be able to iterate without loading all into memory
        count = 0
        for candle in session.replay():
            count += 1
            if count >= 100:  # Only process first 100
                break

        assert count == 100


# =============================================================================
# Unit Tests - Filtered Replay
# =============================================================================


class TestReplayFiltered:
    """Tests for filtered replay."""

    def test_filter_by_start_date(self, sample_ohlcv):
        """Test filtering by start date."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO", df=sample_ohlcv, speed=0)
        candles = list(session.replay_filtered(start_date="2024-01-05"))

        assert len(candles) == 6  # Jan 5-10

    def test_filter_by_end_date(self, sample_ohlcv):
        """Test filtering by end date."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO", df=sample_ohlcv, speed=0)
        candles = list(session.replay_filtered(end_date="2024-01-05"))

        assert len(candles) == 5  # Jan 1-5

    def test_filter_by_date_range(self, sample_ohlcv):
        """Test filtering by date range."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO", df=sample_ohlcv, speed=0)
        candles = list(
            session.replay_filtered(start_date="2024-01-03", end_date="2024-01-07")
        )

        assert len(candles) == 5  # Jan 3-7

    def test_filter_datetime_objects(self, sample_ohlcv):
        """Test filtering with datetime objects."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO", df=sample_ohlcv, speed=0)
        candles = list(
            session.replay_filtered(
                start_date=datetime(2024, 1, 3), end_date=datetime(2024, 1, 7)
            )
        )

        assert len(candles) == 5

    def test_filter_updates_index_and_total(self, sample_ohlcv):
        """Test that filtered replay updates _index and _total."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO", df=sample_ohlcv, speed=0)
        candles = list(
            session.replay_filtered(start_date="2024-01-03", end_date="2024-01-07")
        )

        # Should have its own indices
        assert candles[0]["_index"] == 0
        assert candles[-1]["_index"] == 4
        assert candles[0]["_total"] == 5

    def test_filter_empty_result(self, sample_ohlcv):
        """Test filter that results in no candles."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO", df=sample_ohlcv, speed=0)
        candles = list(
            session.replay_filtered(start_date="2025-01-01")  # Future date
        )

        assert len(candles) == 0


# =============================================================================
# Unit Tests - Callbacks
# =============================================================================


class TestCallbacks:
    """Tests for callback functionality."""

    def test_on_candle_callback(self, replay_session):
        """Test on_candle callback is called."""
        received = []

        def callback(candle):
            received.append(candle["close"])

        replay_session.on_candle(callback)
        list(replay_session.replay())

        assert len(received) == 10
        assert received[0] == 103

    def test_multiple_callbacks(self, replay_session):
        """Test multiple callbacks."""
        counts = [0, 0]

        def callback1(candle):
            counts[0] += 1

        def callback2(candle):
            counts[1] += 1

        replay_session.on_candle(callback1)
        replay_session.on_candle(callback2)
        list(replay_session.replay())

        assert counts[0] == 10
        assert counts[1] == 10

    def test_remove_callback(self, replay_session):
        """Test removing callback."""
        count = [0]

        def callback(candle):
            count[0] += 1

        replay_session.on_candle(callback)
        replay_session.remove_callback(callback)
        list(replay_session.replay())

        assert count[0] == 0

    def test_callback_exception_ignored(self, replay_session):
        """Test that callback exceptions don't stop replay."""

        def bad_callback(candle):
            raise ValueError("Test error")

        replay_session.on_candle(bad_callback)

        # Should complete without raising
        candles = list(replay_session.replay())
        assert len(candles) == 10

    def test_callback_on_filtered(self, sample_ohlcv):
        """Test callback works with filtered replay."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO", df=sample_ohlcv, speed=0)
        received = []

        def callback(candle):
            received.append(candle["close"])

        session.on_candle(callback)
        list(session.replay_filtered(start_date="2024-01-05"))

        assert len(received) == 6


# =============================================================================
# Unit Tests - Stats
# =============================================================================


class TestStats:
    """Tests for stats functionality."""

    def test_stats_basic(self, replay_session):
        """Test basic stats."""
        stats = replay_session.stats()

        assert stats["symbol"] == "THYAO"
        assert stats["total_candles"] == 10
        assert stats["speed"] == 0
        assert stats["current_index"] == 0

    def test_stats_progress(self, replay_session):
        """Test stats during replay."""
        gen = replay_session.replay()

        # Consume half
        for _ in range(5):
            next(gen)

        stats = replay_session.stats()
        assert stats["current_index"] == 4  # 0-indexed, last consumed

    def test_stats_dates(self, replay_session):
        """Test stats includes dates."""
        stats = replay_session.stats()

        assert stats["start_date"] is not None
        assert stats["end_date"] is not None

    def test_stats_no_data(self):
        """Test stats with no data."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO")
        stats = session.stats()

        assert stats["total_candles"] == 0
        assert stats["start_date"] is None
        assert stats["end_date"] is None


# =============================================================================
# Unit Tests - Progress and Reset
# =============================================================================


class TestProgress:
    """Tests for progress tracking."""

    def test_progress_property(self, replay_session):
        """Test progress property."""
        assert replay_session.progress == 0.0

        gen = replay_session.replay()
        for _ in range(5):
            next(gen)

        assert replay_session.progress == 0.4  # 4/10

    def test_progress_complete(self, replay_session):
        """Test progress after complete replay."""
        list(replay_session.replay())

        # After completing, current_index should be at last
        assert replay_session.progress == 0.9  # 9/10 (0-indexed)

    def test_progress_no_data(self):
        """Test progress with no data."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO")
        assert session.progress == 0.0


class TestReset:
    """Tests for reset functionality."""

    def test_reset(self, replay_session):
        """Test reset functionality."""
        # Consume some candles
        gen = replay_session.replay()
        for _ in range(5):
            next(gen)

        replay_session.reset()

        assert replay_session._current_index == 0
        assert replay_session._start_time is None


# =============================================================================
# Unit Tests - Speed Control
# =============================================================================


class TestSpeedControl:
    """Tests for speed control."""

    def test_speed_zero_no_delay(self, sample_ohlcv):
        """Test speed=0 results in no delay."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO", df=sample_ohlcv, speed=0)

        start = time.time()
        list(session.replay())
        elapsed = time.time() - start

        assert elapsed < 1.0  # Should be nearly instant

    def test_realtime_injection_delay(self, sample_ohlcv):
        """Test realtime_injection creates delays."""
        from borsapy.replay import ReplaySession

        # Create 3 candles, 1 day apart
        dates = pd.date_range("2024-01-01", periods=3, freq="1D")
        df = pd.DataFrame(
            {
                "Open": [100, 101, 102],
                "High": [105, 106, 107],
                "Low": [98, 99, 100],
                "Close": [103, 104, 105],
            },
            index=dates,
        )

        # Speed=86400 means 1 day passes in 1 second
        session = ReplaySession(
            "THYAO", df=df, speed=86400, realtime_injection=True
        )

        start = time.time()
        list(session.replay())
        elapsed = time.time() - start

        # With 3 candles and speed=86400, should take ~2 seconds (2 intervals)
        assert elapsed >= 1.5
        assert elapsed < 5.0  # But not too long


# =============================================================================
# Unit Tests - set_data
# =============================================================================


class TestSetData:
    """Tests for set_data method."""

    def test_set_data(self, sample_ohlcv):
        """Test setting data after initialization."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO")
        assert session.total_candles == 0

        session.set_data(sample_ohlcv)
        assert session.total_candles == 10

    def test_set_data_validates(self):
        """Test set_data validates DataFrame."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO")
        df = pd.DataFrame({"Open": [100], "Close": [105]})

        with pytest.raises(ValueError, match="missing required columns"):
            session.set_data(df)


# =============================================================================
# Unit Tests - create_replay function
# =============================================================================


class TestCreateReplay:
    """Tests for create_replay convenience function."""

    def test_create_replay_returns_session(self):
        """Test create_replay returns ReplaySession."""
        from borsapy.replay import ReplaySession, create_replay

        # This may fail if network is unavailable
        try:
            session = create_replay("THYAO", period="1mo", speed=0)
            assert isinstance(session, ReplaySession)
            assert session.symbol == "THYAO"
            assert session.total_candles > 0
        except Exception:
            pytest.skip("Network unavailable or API error")

    def test_create_replay_with_speed(self):
        """Test create_replay with custom speed."""
        from borsapy.replay import create_replay

        try:
            session = create_replay("THYAO", period="1mo", speed=100)
            assert session.speed == 100
        except Exception:
            pytest.skip("Network unavailable or API error")

    def test_create_replay_invalid_symbol(self):
        """Test create_replay with invalid symbol."""
        from borsapy.replay import create_replay

        try:
            with pytest.raises(ValueError, match="No historical data"):
                create_replay("INVALIDSYMBOL123", period="1mo")
        except Exception:
            pytest.skip("Network unavailable or API error")


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.integration
class TestReplayIntegration:
    """Integration tests for replay (require network)."""

    def test_replay_real_data(self):
        """Test replay with real data from TradingView."""
        from borsapy.replay import create_replay

        try:
            session = create_replay("THYAO", period="1mo", speed=0)

            candles = list(session.replay())

            assert len(candles) > 0
            assert candles[0]["close"] > 0
            assert isinstance(candles[0]["timestamp"], datetime)

        except Exception:
            pytest.skip("Network unavailable or API error")

    def test_replay_with_callbacks_real_data(self):
        """Test replay callbacks with real data."""
        from borsapy.replay import create_replay

        try:
            session = create_replay("THYAO", period="1mo", speed=0)

            closes = []

            def on_candle(candle):
                closes.append(candle["close"])

            session.on_candle(on_candle)
            list(session.replay())

            assert len(closes) > 0
            assert all(c > 0 for c in closes)

        except Exception:
            pytest.skip("Network unavailable or API error")

    def test_replay_filtered_real_data(self):
        """Test filtered replay with real data."""
        from borsapy.replay import create_replay

        try:
            session = create_replay("THYAO", period="3mo", speed=0)

            # Get first and last dates
            stats = session.stats()
            start_date = stats["start_date"]
            end_date = stats["end_date"]

            if start_date and end_date:
                # Filter to middle portion
                mid_date = start_date + (end_date - start_date) / 2

                candles_filtered = list(session.replay_filtered(start_date=mid_date))
                candles_all = list(session.replay())

                assert len(candles_filtered) < len(candles_all)

        except Exception:
            pytest.skip("Network unavailable or API error")


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_single_candle(self):
        """Test replay with single candle."""
        from borsapy.replay import ReplaySession

        df = pd.DataFrame(
            {"Open": [100], "High": [105], "Low": [98], "Close": [103], "Volume": [1000]},
            index=pd.date_range("2024-01-01", periods=1),
        )

        session = ReplaySession("THYAO", df=df, speed=0)
        candles = list(session.replay())

        assert len(candles) == 1
        assert candles[0]["_index"] == 0
        assert candles[0]["_total"] == 1
        assert candles[0]["_progress"] == 1.0

    def test_no_volume_column(self):
        """Test replay without Volume column."""
        from borsapy.replay import ReplaySession

        df = pd.DataFrame(
            {"Open": [100], "High": [105], "Low": [98], "Close": [103]},
            index=pd.date_range("2024-01-01", periods=1),
        )

        session = ReplaySession("THYAO", df=df, speed=0)
        candles = list(session.replay())

        assert candles[0]["volume"] == 0

    def test_iteration_order(self, sample_ohlcv):
        """Test candles are yielded in chronological order."""
        from borsapy.replay import ReplaySession

        session = ReplaySession("THYAO", df=sample_ohlcv, speed=0)
        candles = list(session.replay())

        timestamps = [c["timestamp"] for c in candles]
        assert timestamps == sorted(timestamps)
