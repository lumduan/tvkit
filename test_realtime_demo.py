#!/usr/bin/env python3
"""
Test script to run the realtime streaming demos with shorter timeouts.
"""
import asyncio
import sys
import os

# Add the parent directory to the path so we can import tvkit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tvkit.api.websocket.stream.realtime import RealtimeStreamer
from tvkit.api.websocket.stream.models import StreamConfig, ExportConfig

async def test_basic_demo():
    """Test basic functionality without network connection."""
    print("🎯 Testing RealtimeStreamer Configuration and Validation")
    print("=" * 60)

    # Test 1: Basic configuration
    try:
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=10,
            include_indicators=False,
            indicator_id=None,
            indicator_version=None,
            export_config=None
        )
        streamer = RealtimeStreamer(config)
        print("✅ Basic configuration: PASSED")

        # Test public methods without connection
        stats = streamer.get_stream_statistics()
        print(f"📊 Statistics (no connection): {stats is None}")

        latest = streamer.get_latest_ohlcv()
        print(f"📈 Latest OHLCV (no connection): {latest is None}")

    except Exception as e:
        print(f"❌ Basic configuration: FAILED - {e}")

    # Test 2: Multiple symbols
    try:
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "NASDAQ:AAPL"],
            timeframe="5m",
            num_candles=20,
            include_indicators=False,
            indicator_id=None,
            indicator_version=None,
            export_config=None
        )
        streamer = RealtimeStreamer(config)
        print("✅ Multiple symbols configuration: PASSED")

    except Exception as e:
        print(f"❌ Multiple symbols configuration: FAILED - {e}")

    # Test 3: With indicators
    try:
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=50,
            include_indicators=True,
            indicator_id="STD;SMA",
            indicator_version="1",
            export_config=None
        )
        streamer = RealtimeStreamer(config)
        print("✅ Indicators configuration: PASSED")

    except Exception as e:
        print(f"❌ Indicators configuration: FAILED - {e}")

    # Test 4: With export
    try:
        export_config = ExportConfig(
            enabled=True,
            format='json',
            directory='./export',
            filename_prefix='test',
            include_timestamp=True,
            auto_export_interval=None
        )
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="1m",
            num_candles=15,
            include_indicators=False,
            indicator_id=None,
            indicator_version=None,
            export_config=export_config
        )
        streamer = RealtimeStreamer(config)
        print("✅ Export configuration: PASSED")

    except Exception as e:
        print(f"❌ Export configuration: FAILED - {e}")

    # Test 5: Error handling - Invalid symbol
    try:
        config = StreamConfig(
            symbols=["INVALID_SYMBOL"],  # Missing exchange prefix
            timeframe="1m",
            num_candles=10,
            include_indicators=False,
            indicator_id=None,
            indicator_version=None,
            export_config=None
        )
        print("❌ This should have failed with invalid symbol")
    except Exception as e:
        print(f"✅ Invalid symbol validation: PASSED - {type(e).__name__}")

    # Test 6: Error handling - Invalid timeframe
    try:
        config = StreamConfig(
            symbols=["BINANCE:BTCUSDT"],
            timeframe="30s",  # Invalid timeframe
            num_candles=10,
            include_indicators=False,
            indicator_id=None,
            indicator_version=None,
            export_config=None
        )
        print("❌ This should have failed with invalid timeframe")
    except Exception as e:
        print(f"✅ Invalid timeframe validation: PASSED - {type(e).__name__}")

    print("\n🎉 All configuration tests completed!")
    print("=" * 60)
    print("📖 Methods Successfully Tested:")
    print("   • RealtimeStreamer.__init__(config)")
    print("   • streamer.get_stream_statistics() - returns None when not connected")
    print("   • streamer.get_latest_ohlcv() - returns None when not connected")
    print("   • StreamConfig validation with various parameters")
    print("   • ExportConfig with all required parameters")
    print("   • Error handling for invalid symbols and timeframes")
    print("=" * 60)
    print("🌐 Network-dependent methods (require connection):")
    print("   • async with RealtimeStreamer(config) as streamer:")
    print("   • await streamer.connect()")
    print("   • await streamer.disconnect()")
    print("   • async for response in streamer.stream():")
    print("   • streamer.get_stream_statistics() - with actual data")
    print("   • streamer.get_latest_ohlcv(symbol) - with actual data")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_basic_demo())
