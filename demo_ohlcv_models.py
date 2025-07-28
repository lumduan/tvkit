"""
Demo script showing how to use the new OHLCV models with TradingView real-time data.

This script demonstrates:
1. Creating OHLCV models from raw TradingView data
2. Using the structured real-time data streaming
3. Accessing individual OHLCV fields in a type-safe manner
"""

import asyncio
import json
from typing import Any

from tvkit.api.websocket.stream.models.realtime import OHLCVBar, OHLCVResponse
from tvkit.api.websocket.stream.realtime_data import RealTimeData


def demo_ohlcv_parsing():
    """Demonstrate parsing TradingView response data into OHLCV models."""

    # Sample data from TradingView (like what you provided)
    sample_data: dict[str, Any] = {
        'm': 'du',
        'p': [
            'cs_wrouuzfexqom',
            {
                'sds_1': {
                    's': [
                        {
                            'i': 9,
                            'v': [1753692060.0, 118881.76, 118881.76, 118881.75, 118881.75, 0.95897]
                        }
                    ],
                    'ns': {'d': '', 'indexes': 'nochange'},
                    't': 's1',
                    'lbs': {'bar_close_time': 1753692120}
                }
            }
        ]
    }

    print("=" * 60)
    print("OHLCV Model Demo")
    print("=" * 60)

    # Parse the raw data into our structured model
    response = OHLCVResponse.model_validate(sample_data)

    print(f"Message Type: {response.message_type}")
    print(f"Session ID: {response.session_id}")
    print(f"Number of Series: {len(response.series_updates)}")

    # Extract OHLCV bars
    ohlcv_bars = response.ohlcv_bars
    print(f"Number of OHLCV bars: {len(ohlcv_bars)}")

    for i, bar in enumerate(ohlcv_bars):
        print(f"\n--- OHLCV Bar {i + 1} ---")
        print(f"Timestamp: {bar.timestamp}")
        print(f"Open:      ${bar.open:,.2f}")
        print(f"High:      ${bar.high:,.2f}")
        print(f"Low:       ${bar.low:,.2f}")
        print(f"Close:     ${bar.close:,.2f}")
        print(f"Volume:    {bar.volume:.5f}")

        # Calculate price change
        price_change = bar.close - bar.open
        print(f"Change:    ${price_change:+.2f}")

    print("\n" + "=" * 60)


async def demo_real_time_streaming():
    """Demonstrate real-time OHLCV streaming with structured data."""

    print("=" * 60)
    print("Real-Time OHLCV Streaming Demo")
    print("=" * 60)
    print("Note: This is a demo - it will connect to TradingView's live data")
    print("Press Ctrl+C to stop the stream")
    print("-" * 60)

    async with RealTimeData() as real_time_data:
        exchange_symbol = "BINANCE:BTCUSDT"

        count = 0
        max_bars = 5  # Limit for demo purposes

        try:
            async for ohlcv_bar in real_time_data.get_ohlcv(exchange_symbol):
                count += 1

                print(f"\n--- Live OHLCV Bar {count} ---")
                print(f"Symbol:    {exchange_symbol}")
                print(f"Timestamp: {ohlcv_bar.timestamp}")
                print(f"Open:      ${ohlcv_bar.open:,.2f}")
                print(f"High:      ${ohlcv_bar.high:,.2f}")
                print(f"Low:       ${ohlcv_bar.low:,.2f}")
                print(f"Close:     ${ohlcv_bar.close:,.2f}")
                print(f"Volume:    {ohlcv_bar.volume:.5f}")

                # Calculate some basic metrics
                price_change = ohlcv_bar.close - ohlcv_bar.open
                if ohlcv_bar.open > 0:
                    price_change_pct = (price_change / ohlcv_bar.open) * 100
                    print(f"Change:    ${price_change:+.2f} ({price_change_pct:+.2f}%)")

                spread = ohlcv_bar.high - ohlcv_bar.low
                print(f"Spread:    ${spread:.2f}")

                if count >= max_bars:
                    print(f"\nDemo complete! Processed {count} bars.")
                    break

        except KeyboardInterrupt:
            print("\nStream stopped by user.")
        except Exception as e:
            print(f"\nError occurred: {e}")


def demo_ohlcv_bar_creation():
    """Demonstrate creating OHLCV bars from array data."""

    print("=" * 60)
    print("OHLCV Bar Creation Demo")
    print("=" * 60)

    # Sample array data (TradingView format)
    array_data = [1753692060.0, 118881.76, 118881.76, 118881.75, 118881.75, 0.95897]

    print("Creating OHLCV bar from array data:")
    print(f"Raw array: {array_data}")

    # Create OHLCV bar from array
    ohlcv_bar = OHLCVBar.from_array(array_data)

    print(f"\nStructured OHLCV Bar:")
    print(f"Timestamp: {ohlcv_bar.timestamp}")
    print(f"Open:      {ohlcv_bar.open}")
    print(f"High:      {ohlcv_bar.high}")
    print(f"Low:       {ohlcv_bar.low}")
    print(f"Close:     {ohlcv_bar.close}")
    print(f"Volume:    {ohlcv_bar.volume}")

    # Demonstrate JSON serialization
    print(f"\nJSON representation:")
    print(json.dumps(ohlcv_bar.model_dump(), indent=2))


async def main():
    """Main demo function."""

    print("TradingView Kit - OHLCV Models Demo")
    print("This demo shows the new structured OHLCV data models.")
    print()

    # Demo 1: Parse sample data
    demo_ohlcv_parsing()

    # Demo 2: Create OHLCV bars from arrays
    demo_ohlcv_bar_creation()

    # Demo 3: Real-time streaming (commented out for safety)
    # Uncomment the line below to test real-time streaming
    # await demo_real_time_streaming()

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("To test real-time streaming, uncomment the streaming demo in main()")


if __name__ == "__main__":
    asyncio.run(main())
