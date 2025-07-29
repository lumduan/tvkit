#!/usr/bin/env python3
"""
Example usage script for the RealtimeStreamer class.

This script demonstrates how to use the async RealtimeStreamer to get real-time
market data from TradingView with different configurations.
"""

import asyncio
import logging
from datetime import datetime
from typing import List

from tvkit.api.chart.realtime import RealtimeStreamer
from tvkit.api.chart.models import StreamConfig, ExportConfig, StreamerResponse
from tvkit.api.chart.exceptions import StreamingError

# Configure logging for the example
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_basic_streaming():
    """Example of basic real-time streaming without export."""
    logger.info("Starting basic streaming example...")

    # Create basic configuration
    config = StreamConfig(
        symbols=["BINANCE:BTCUSDT", "NASDAQ:AAPL"],
        timeframe="1m",
        num_candles=50
    )

    try:
        # Use async context manager for automatic connection management
        async with RealtimeStreamer(config) as streamer:
            logger.info("Connected to TradingView WebSocket")

            # Stream data for a limited time
            count = 0
            max_messages = 10

            async for response in streamer.stream():
                count += 1

                if response.data_type == 'ohlcv' and response.ohlcv_data:
                    latest_candle = response.ohlcv_data[-1]
                    logger.info(
                        f"OHLCV {response.symbol}: "
                        f"O:{latest_candle.open} H:{latest_candle.high} "
                        f"L:{latest_candle.low} C:{latest_candle.close} "
                        f"V:{latest_candle.volume}"
                    )

                elif response.data_type == 'trade' and response.trade_data:
                    trade = response.trade_data
                    logger.info(
                        f"Trade {trade.symbol}: "
                        f"Price:{trade.price} Volume:{trade.volume}"
                    )

                # Stop after receiving enough messages
                if count >= max_messages:
                    logger.info("Received enough messages, stopping...")
                    break

    except StreamingError as e:
        logger.error(f"Streaming error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


async def example_streaming_with_export():
    """Example of real-time streaming with data export."""
    logger.info("Starting streaming with export example...")

    # Create export configuration
    export_config = ExportConfig(
        enabled=True,
        format='json',
        directory='/export',
        include_timestamp=True,
        auto_export_interval=30  # Export every 30 seconds
    )

    # Create configuration with export
    config = StreamConfig(
        symbols=["BINANCE:BTCUSDT", "BINANCE:ETHUSDT"],
        timeframe="5m",
        num_candles=100,
        include_indicators=False,
        export_config=export_config
    )

    try:
        async with RealtimeStreamer(config) as streamer:
            logger.info("Connected with export configuration")

            # Stream for a limited time
            start_time = datetime.now()
            duration_minutes = 1  # Stream for 1 minute

            async for response in streamer.stream():
                # Check elapsed time
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > duration_minutes * 60:
                    logger.info("Streaming duration completed")
                    break

                # Process different data types
                if response.data_type == 'ohlcv' and response.ohlcv_data:
                    logger.info(f"Received {len(response.ohlcv_data)} OHLCV candles for {response.symbol}")

                    # Get latest candle
                    latest = response.ohlcv_data[-1]
                    logger.info(f"Latest {response.symbol}: Close={latest.close} Volume={latest.volume}")

                # Print statistics periodically
                if int(elapsed) % 15 == 0:
                    stats = streamer.get_stream_statistics()
                    if stats:
                        logger.info(f"Stream stats: {stats}")

    except StreamingError as e:
        logger.error(f"Streaming error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


async def example_error_handling():
    """Example demonstrating proper error handling and recovery."""
    logger.info("Starting error handling example...")

    config = StreamConfig(
        symbols=["BINANCE:BTCUSDT"],
        timeframe="1m",
        num_candles=10
    )

    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            async with RealtimeStreamer(config) as streamer:
                logger.info(f"Connection attempt {retry_count + 1}")

                message_count = 0
                async for response in streamer.stream():
                    message_count += 1
                    logger.info(f"Received message {message_count}: {response.data_type}")

                    if message_count >= 5:
                        break

                # If we get here, streaming was successful
                logger.info("Streaming completed successfully")
                break

        except StreamingError as e:
            retry_count += 1
            logger.warning(f"Streaming error (attempt {retry_count}): {e}")

            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.error("Max retries exceeded, giving up")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            break


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())
async def main():
    """Main function to run streaming examples."""
    logger.info("TradingView Real-time Streaming Examples")
    logger.info("=" * 50)

    try:
        # Run basic example
        await example_basic_streaming()

        # Wait between examples
        await asyncio.sleep(2)

        # Run export example (uncomment to test)
        # await example_streaming_with_export()

        # Run error handling example (uncomment to test)
        # await example_error_handling()

    except KeyboardInterrupt:
        logger.info("Streaming interrupted by user")
    except Exception as e:
        logger.error(f"Example execution error: {e}")

    logger.info("Examples completed")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())

    # Configure for real-time streaming (no export)
    export_config = ExportConfig(export_result=False)
    stream_config = StreamConfig(
        timeframe='1m',
        numb_price_candles=10
    )

    async with RealtimeStreamer(
        export_config=export_config,
        stream_config=stream_config
    ) as streamer:
        try:
            # Stream Bitcoin data from Binance
            result = await streamer.stream(exchange="BINANCE", symbol="BTCUSDT")

            # Since export_result=False, result is an async generator
            if hasattr(result, '__aiter__'):
                packet_count = 0
                async for packet in result:  # type: ignore
                    packet_count += 1
                    logger.info(f"Received packet {packet_count}: {packet}")

                    # Stop after 5 packets for demo
                    if packet_count >= 5:
                        break

        except Exception as e:
            logger.error(f"Error in basic streaming: {e}")


async def example_export_streaming():
    """Example of streaming with data export to files."""
    logger.info("Starting export streaming example...")

    # Configure for export
    export_config = ExportConfig(
        export_result=True,
        export_type='json'  # or 'csv'
    )
    stream_config = StreamConfig(
        timeframe='5m',
        numb_price_candles=20
    )

    async with RealtimeStreamer(
        export_config=export_config,
        stream_config=stream_config
    ) as streamer:
        try:
            # Stream Ethereum data from Binance
            result = await streamer.stream(exchange="BINANCE", symbol="ETHUSDT")

            # Since export_result=True, result is a StreamData object
            if isinstance(result, StreamData):
                logger.info(f"Successfully exported data:")
                logger.info(f"  - OHLC data points: {len(result.ohlc)}")
                logger.info(f"  - Indicator data points: {len(result.indicator)}")

                # Show first OHLC data point if available
                if result.ohlc:
                    first_ohlc = result.ohlc[0]
                    logger.info(f"  - First OHLC: {first_ohlc}")

        except Exception as e:
            logger.error(f"Error in export streaming: {e}")


async def example_with_indicators():
    """Example of streaming with technical indicators."""
    logger.info("Starting indicator streaming example...")

    export_config = ExportConfig(export_result=True, export_type='json')
    stream_config = StreamConfig(
        timeframe='1m',
        numb_price_candles=30
    )
    # Configure indicators (example - replace with actual indicator IDs)
    indicator_config = IndicatorConfig(
        indicator_id="RSI@tv-basicstudies",
        indicator_version="1"
    )

    async with RealtimeStreamer(
        export_config=export_config,
        stream_config=stream_config,
        indicator_config=indicator_config
    ) as streamer:
        try:
            # Stream Apple stock data from NASDAQ
            result = await streamer.stream(exchange="NASDAQ", symbol="AAPL")

            if isinstance(result, StreamData):
                logger.info(f"Successfully exported data with indicators:")
                logger.info(f"  - OHLC data points: {len(result.ohlc)}")
                logger.info(f"  - Indicator data points: {len(result.indicator)}")

        except Exception as e:
            logger.error(f"Error in indicator streaming: {e}")


async def example_multiple_symbols():
    """Example of validating multiple symbols."""
    logger.info("Starting multiple symbol validation example...")

    streamer = RealtimeStreamer()

    try:
        # Validate multiple symbols at once
        symbols = ["BINANCE:BTCUSDT", "NASDAQ:AAPL", "NYSE:TSLA"]
        is_valid = await streamer.validate_symbols(symbols)
        logger.info(f"Symbols validation result: {is_valid}")

    except ValueError as e:
        logger.error(f"Symbol validation error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


async def main():
    """Run all examples."""
    logger.info("=== RealtimeStreamer Examples ===")

    # Run examples one by one
    await example_basic_streaming()
    await asyncio.sleep(2)  # Brief pause between examples

    await example_export_streaming()
    await asyncio.sleep(2)

    await example_with_indicators()
    await asyncio.sleep(2)

    await example_multiple_symbols()

    logger.info("=== All examples completed ===")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Examples interrupted by user")
    except Exception as e:
        logger.error(f"Failed to run examples: {e}")
