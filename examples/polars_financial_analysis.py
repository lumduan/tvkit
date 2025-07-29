#!/usr/bin/env python3
"""
Enhanced example showcasing Polars usage with RealtimeStreamer for financial data analysis.

This example demonstrates how to use Polars DataFrames for advanced financial data
analysis with the real-time streaming data from TradingView.
"""

import asyncio
import logging
from pathlib import Path
import polars as pl

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def demonstrate_polars_financial_analysis():
    """Demonstrate Polars capabilities for financial data analysis."""
    logger.info("🔬 Demonstrating Polars financial analysis capabilities...")

    # Create sample OHLCV data similar to what we'd get from the streamer
    sample_data = [
        {
            "timestamp": 1672531200.0,
            "open": 16500.25,
            "high": 16650.75,
            "low": 16480.10,
            "close": 16620.50,
            "volume": 125000.0,
        },
        {
            "timestamp": 1672531260.0,
            "open": 16620.50,
            "high": 16700.25,
            "low": 16600.00,
            "close": 16680.75,
            "volume": 135000.0,
        },
        {
            "timestamp": 1672531320.0,
            "open": 16680.75,
            "high": 16720.50,
            "low": 16650.25,
            "close": 16705.30,
            "volume": 142000.0,
        },
        {
            "timestamp": 1672531380.0,
            "open": 16705.30,
            "high": 16750.80,
            "low": 16695.10,
            "close": 16730.45,
            "volume": 138000.0,
        },
        {
            "timestamp": 1672531440.0,
            "open": 16730.45,
            "high": 16780.25,
            "low": 16720.90,
            "close": 16765.60,
            "volume": 151000.0,
        },
        {
            "timestamp": 1672531500.0,
            "open": 16765.60,
            "high": 16800.30,
            "low": 16750.15,
            "close": 16785.40,
            "volume": 146000.0,
        },
        {
            "timestamp": 1672531560.0,
            "open": 16785.40,
            "high": 16820.75,
            "low": 16770.25,
            "close": 16810.90,
            "volume": 159000.0,
        },
        {
            "timestamp": 1672531620.0,
            "open": 16810.90,
            "high": 16850.60,
            "low": 16800.45,
            "close": 16835.20,
            "volume": 163000.0,
        },
        {
            "timestamp": 1672531680.0,
            "open": 16835.20,
            "high": 16870.40,
            "low": 16825.10,
            "close": 16855.75,
            "volume": 157000.0,
        },
        {
            "timestamp": 1672531740.0,
            "open": 16855.75,
            "high": 16890.25,
            "low": 16840.60,
            "close": 16875.30,
            "volume": 169000.0,
        },
    ]

    # Create Polars DataFrame
    df = pl.DataFrame(sample_data)

    # Financial analysis using Polars
    financial_df = (
        df.with_columns(
            [
                # Convert timestamp to datetime
                (pl.col("timestamp") * 1000)
                .cast(pl.Datetime(time_unit="ms"))
                .alias("datetime"),
                # Calculate returns
                ((pl.col("close") - pl.col("open")) / pl.col("open") * 100).alias(
                    "return_pct"
                ),
                # Calculate typical price
                ((pl.col("high") + pl.col("low") + pl.col("close")) / 3).alias(
                    "typical_price"
                ),
                # Calculate true range (for volatility analysis)
                (pl.col("high") - pl.col("low")).alias("true_range"),
                # Calculate VWAP components
                (
                    (pl.col("high") + pl.col("low") + pl.col("close"))
                    / 3
                    * pl.col("volume")
                ).alias("vwap_numerator"),
            ]
        )
        .with_columns(
            [
                # Moving averages
                pl.col("close").rolling_mean(window_size=3).alias("sma_3"),
                pl.col("close").rolling_mean(window_size=5).alias("sma_5"),
                # Volume moving average
                pl.col("volume").rolling_mean(window_size=3).alias("vol_ma_3"),
                # Price momentum
                (pl.col("close") - pl.col("close").shift(3)).alias("momentum_3"),
                # Cumulative VWAP calculation
                pl.col("vwap_numerator").cum_sum().alias("cum_vwap_num"),
                pl.col("volume").cum_sum().alias("cum_volume"),
            ]
        )
        .with_columns(
            [
                # Final VWAP calculation
                (pl.col("cum_vwap_num") / pl.col("cum_volume")).alias("vwap"),
                # Bollinger band components (simplified)
                pl.col("close").rolling_std(window_size=5).alias("price_std_5"),
            ]
        )
        .with_columns(
            [
                # Bollinger bands
                (pl.col("sma_5") + 2 * pl.col("price_std_5")).alias("bb_upper"),
                (pl.col("sma_5") - 2 * pl.col("price_std_5")).alias("bb_lower"),
                # RSI components (simplified calculation)
                pl.when(pl.col("return_pct") > 0)
                .then(pl.col("return_pct"))
                .otherwise(0)
                .alias("gain"),
                pl.when(pl.col("return_pct") < 0)
                .then(pl.col("return_pct").abs())
                .otherwise(0)
                .alias("loss"),
            ]
        )
    )

    # Display results
    logger.info("📊 Enhanced Financial DataFrame with Polars:")
    print(
        financial_df.select(
            [
                "datetime",
                "close",
                "return_pct",
                "sma_3",
                "sma_5",
                "vwap",
                "bb_upper",
                "bb_lower",
                "momentum_3",
            ]
        )
    )

    # Performance statistics
    stats = financial_df.select(
        [
            pl.col("return_pct").mean().alias("avg_return"),
            pl.col("return_pct").std().alias("volatility"),
            pl.col("return_pct").max().alias("max_return"),
            pl.col("return_pct").min().alias("min_return"),
            pl.col("volume").mean().alias("avg_volume"),
            pl.col("true_range").mean().alias("avg_true_range"),
        ]
    )

    logger.info("📈 Performance Statistics:")
    print(stats)

    return financial_df


def demonstrate_polars_aggregations():
    """Demonstrate Polars aggregation capabilities for trading analysis."""
    logger.info("📋 Demonstrating Polars aggregations for trading analysis...")

    # Create sample data for multiple timeframes
    minute_data = []
    base_time = 1672531200.0
    base_price = 16500.0

    for i in range(60):  # 1 hour of minute data
        price_change = (i % 10 - 5) * 2.5  # Simulate price movement
        current_price = base_price + price_change

        minute_data.append(
            {
                "timestamp": base_time + (i * 60),
                "open": current_price,
                "high": current_price + abs(price_change) + 5,
                "low": current_price - abs(price_change) - 3,
                "close": current_price + price_change,
                "volume": 100000 + (i * 1000),
                "symbol": "BTCUSDT",
                "exchange": "BINANCE",
            }
        )

    df = pl.DataFrame(minute_data)

    # Convert to different timeframes using Polars aggregations
    df_with_time = df.with_columns(
        [
            (pl.col("timestamp") * 1000)
            .cast(pl.Datetime(time_unit="ms"))
            .alias("datetime"),
            pl.col("timestamp")
            .map_elements(lambda x: int(x // 300) * 300, return_dtype=pl.Int64)
            .alias("period_5m"),
        ]
    )

    # Aggregate to 5-minute timeframe
    df_5m = (
        df_with_time.group_by("period_5m")
        .agg(
            [
                pl.col("open").first().alias("open"),
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume"),
                pl.col("datetime").first().alias("datetime"),
                pl.col("symbol").first().alias("symbol"),
                pl.col("exchange").first().alias("exchange"),
            ]
        )
        .sort("period_5m")
    )

    logger.info("🕐 5-minute aggregated data:")
    print(df_5m.select(["datetime", "open", "high", "low", "close", "volume"]).head(5))

    # Cross-symbol analysis (if we had multiple symbols)
    summary_stats = df_with_time.group_by(["symbol", "exchange"]).agg(
        [
            pl.col("close").mean().alias("avg_price"),
            pl.col("volume").sum().alias("total_volume"),
            pl.col("high").max().alias("day_high"),
            pl.col("low").min().alias("day_low"),
            pl.count().alias("data_points"),
        ]
    )

    logger.info("📊 Summary statistics by symbol:")
    print(summary_stats)

    return df_5m


def demonstrate_polars_export_formats():
    """Demonstrate different export formats available with Polars."""
    logger.info("💾 Demonstrating Polars export capabilities...")

    # Create sample data
    data = [
        {
            "timestamp": 1672531200.0,
            "symbol": "BTCUSDT",
            "price": 16500.25,
            "volume": 125000.0,
        },
        {
            "timestamp": 1672531260.0,
            "symbol": "BTCUSDT",
            "price": 16620.50,
            "volume": 135000.0,
        },
        {
            "timestamp": 1672531320.0,
            "symbol": "ETHUSDT",
            "price": 1200.75,
            "volume": 85000.0,
        },
        {
            "timestamp": 1672531380.0,
            "symbol": "ETHUSDT",
            "price": 1205.30,
            "volume": 92000.0,
        },
    ]

    df = pl.DataFrame(data)

    # Export to various formats
    export_dir = Path("export")
    export_dir.mkdir(exist_ok=True)

    # CSV export
    csv_path = export_dir / "polars_demo.csv"
    df.write_csv(csv_path)
    logger.info(f"✅ Exported to CSV: {csv_path}")

    # JSON export
    json_path = export_dir / "polars_demo.json"
    df.write_json(json_path)
    logger.info(f"✅ Exported to JSON: {json_path}")

    # Parquet export (efficient binary format)
    parquet_path = export_dir / "polars_demo.parquet"
    df.write_parquet(parquet_path)
    logger.info(f"✅ Exported to Parquet: {parquet_path}")

    # Read back and verify
    df_from_parquet = pl.read_parquet(parquet_path)
    logger.info("🔍 Data read back from Parquet:")
    print(df_from_parquet)

    return df


async def main():
    """Run all Polars demonstration examples."""
    logger.info("🚀 Starting Polars Financial Analysis Demonstrations")
    logger.info("=" * 60)

    # Run demonstrations
    demonstrate_polars_financial_analysis()
    print("\n" + "-" * 60 + "\n")

    demonstrate_polars_aggregations()
    print("\n" + "-" * 60 + "\n")

    demonstrate_polars_export_formats()

    logger.info("\n" + "=" * 60)
    logger.info("🎉 All Polars demonstrations completed successfully!")
    logger.info("📌 Key benefits of using Polars:")
    logger.info("   • Faster performance than pandas")
    logger.info("   • Built-in lazy evaluation")
    logger.info("   • Memory efficient operations")
    logger.info("   • Native support for multiple data formats")
    logger.info("   • Excellent for financial time series analysis")


if __name__ == "__main__":
    asyncio.run(main())
