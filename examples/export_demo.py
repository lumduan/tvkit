#!/usr/bin/env python3
"""
Export module demonstration script.

This example shows how to use the tvkit export module to fetch OHLCV data
and export it to various formats including Polars DataFrames, JSON, and CSV.
"""

import asyncio
import logging
from pathlib import Path

from tvkit.api.chart.ohlcv import OHLCV
from tvkit.export import DataExporter, ExportConfig, ExportFormat

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def demo_basic_exports():
    """Demonstrate basic export functionality."""
    logger.info("🚀 Starting basic export demonstration")

    # Fetch OHLCV data
    async with OHLCV() as client:
        logger.info("📈 Fetching OHLCV data for BINANCE:BTCUSDT...")
        bars = await client.get_historical_ohlcv(
            exchange_symbol="BINANCE:BTCUSDT",
            interval="60",
            bars_count=24,  # Last 24 hours
        )

        logger.info(f"✅ Fetched {len(bars)} OHLCV bars")

    # Initialize exporter
    exporter = DataExporter()

    # Export to Polars DataFrame
    logger.info("📊 Exporting to Polars DataFrame...")
    df = await exporter.to_polars(bars, add_analysis=True)
    logger.info(
        f"✅ Created Polars DataFrame with {len(df)} rows and {len(df.columns)} columns"
    )
    logger.info(f"   Columns: {df.columns}")

    # Show sample data
    print("\n📋 Sample DataFrame data:")
    print(
        df.select(
            [
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "return_pct",
                "sma_5",
            ]
        ).head(5)
    )

    # Export to JSON
    logger.info("\n💾 Exporting to JSON file...")
    json_file = await exporter.to_json(
        bars, "export/btc_1h_data.json", indent=2, timestamp_format="iso"
    )
    logger.info(f"✅ Exported to JSON: {json_file}")

    # Export to CSV
    logger.info("📄 Exporting to CSV file...")
    csv_file = await exporter.to_csv(
        bars, "export/btc_1h_data.csv", timestamp_format="iso"
    )
    logger.info(f"✅ Exported to CSV: {csv_file}")

    return df, json_file, csv_file


async def demo_advanced_polars_analysis():
    """Demonstrate advanced Polars analysis with exported data."""
    logger.info("\n🔬 Starting advanced Polars analysis demonstration")

    # Fetch more data for better analysis
    async with OHLCV() as client:
        logger.info("📈 Fetching extended OHLCV data...")
        bars = await client.get_historical_ohlcv(
            exchange_symbol="BINANCE:ETHUSDT",
            interval="10",
            bars_count=100,  # Last 100 15-minute bars
        )

        logger.info(f"✅ Fetched {len(bars)} OHLCV bars for analysis")

    # Export with analysis
    exporter = DataExporter()
    df = await exporter.to_polars(bars, add_analysis=True)

    # Perform additional analysis using Polars
    try:
        import polars as pl

        # Advanced analysis
        analysis_df = df.with_columns(
            [
                # Bollinger Bands
                (
                    pl.col("sma_5") + 2 * pl.col("close").rolling_std(window_size=5)
                ).alias("bb_upper"),
                (
                    pl.col("sma_5") - 2 * pl.col("close").rolling_std(window_size=5)
                ).alias("bb_lower"),
                # Price position within Bollinger Bands
                (
                    (pl.col("close") - pl.col("sma_5"))
                    / (2 * pl.col("close").rolling_std(window_size=5))
                ).alias("bb_position"),
                # Volume analysis
                (
                    pl.col("volume") / pl.col("volume").rolling_mean(window_size=10)
                ).alias("volume_ratio"),
                # High-Low spread
                ((pl.col("high") - pl.col("low")) / pl.col("close") * 100).alias(
                    "hl_spread_pct"
                ),
            ]
        )

        # Summary statistics
        stats = analysis_df.select(
            [
                pl.col("return_pct").mean().alias("avg_return"),
                pl.col("return_pct").std().alias("volatility"),
                pl.col("return_pct").min().alias("min_return"),
                pl.col("return_pct").max().alias("max_return"),
                pl.col("volume_ratio").mean().alias("avg_volume_ratio"),
                pl.col("hl_spread_pct").mean().alias("avg_hl_spread"),
                pl.count().alias("total_bars"),
            ]
        )

        print("\n📊 Advanced Analysis Results:")
        print(stats)

        # Export enhanced analysis
        enhanced_csv = await exporter.to_csv(
            bars, "export/eth_15m_enhanced_analysis.csv", timestamp_format="iso"
        )

        # Export the Polars DataFrame directly using its own methods
        if hasattr(analysis_df, "write_parquet"):
            parquet_path = Path("export/eth_15m_analysis.parquet")
            parquet_path.parent.mkdir(exist_ok=True)
            analysis_df.write_parquet(parquet_path)
            logger.info(f"✅ Exported enhanced analysis to Parquet: {parquet_path}")

        logger.info(f"✅ Exported enhanced analysis to CSV: {enhanced_csv}")

        return analysis_df

    except ImportError:
        logger.warning("⚠️  Polars not available for advanced analysis")
        return df


async def demo_custom_configuration():
    """Demonstrate custom export configurations."""
    logger.info("\n⚙️  Starting custom configuration demonstration")

    # Fetch sample data
    async with OHLCV() as client:
        bars = await client.get_historical_ohlcv(
            exchange_symbol="BINANCE:ADAUSDT", interval="5m", bars_count=50
        )

    exporter = DataExporter()

    # Custom JSON export with specific timestamp format
    json_config = ExportConfig(
        format=ExportFormat.JSON,
        timestamp_format="unix",  # Keep as Unix timestamp
        include_metadata=True,
        options={"indent": 4, "sort_keys": False, "ensure_ascii": True},
    )

    result = await exporter.export_ohlcv_data(
        bars, ExportFormat.JSON, "export/ada_custom_config.json", config=json_config
    )

    logger.info(f"✅ Custom JSON export: {result.file_path}")
    logger.info(f"   Records: {result.metadata.record_count}")
    logger.info(f"   Format: {result.metadata.format}")

    # Custom CSV export with different delimiter
    csv_config = ExportConfig(
        format=ExportFormat.CSV,
        timestamp_format="datetime",
        include_metadata=False,  # Skip metadata file
        options={
            "delimiter": ";",  # Use semicolon instead of comma
        },
    )

    result = await exporter.export_ohlcv_data(
        bars, ExportFormat.CSV, "export/ada_semicolon.csv", config=csv_config
    )

    logger.info(f"✅ Custom CSV export: {result.file_path}")

    return result


async def demo_error_handling():
    """Demonstrate error handling in export operations."""
    logger.info("\n🚨 Starting error handling demonstration")

    exporter = DataExporter()

    # Try to export empty data
    try:
        await exporter.to_json([], "export/empty_data.json")
    except Exception as e:
        logger.info(f"✅ Correctly caught empty data error: {e}")

    # Try to use unsupported format
    try:
        ExportConfig(format="unsupported_format")
    except Exception as e:
        logger.info(f"✅ Correctly caught unsupported format error: {e}")

    # Test with invalid file path (read-only directory)
    try:
        # Create minimal test data
        from tvkit.api.chart.models.ohlcv import OHLCVBar

        test_bars = [
            OHLCVBar(
                timestamp=1672531200.0,
                open=100.0,
                high=105.0,
                low=95.0,
                close=102.0,
                volume=1000.0,
            )
        ]

        # This should work fine - just demonstrating valid path
        result = await exporter.to_json(test_bars, "export/test_error_handling.json")
        logger.info(f"✅ Error handling test completed successfully: {result}")

    except Exception as e:
        logger.info(f"ℹ️  Error handling test caught: {e}")


async def main():
    """Run all export demonstrations."""
    logger.info("🌟 Starting tvkit Export Module Demonstration")
    logger.info("=" * 60)

    # Ensure export directory exists
    Path("export").mkdir(exist_ok=True)

    try:
        # Run demonstrations
        await demo_basic_exports()

        await demo_advanced_polars_analysis()

        # await demo_custom_configuration()

        # await demo_error_handling()

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("🎉 Export module demonstration completed successfully!")
        logger.info("\n📁 Generated files:")

        export_dir = Path("export")
        if export_dir.exists():
            for file_path in export_dir.glob("*"):
                if file_path.is_file():
                    size_kb = file_path.stat().st_size / 1024
                    logger.info(f"   • {file_path.name} ({size_kb:.1f} KB)")

        logger.info("\n✨ Key features demonstrated:")
        logger.info("   • OHLCV data export to multiple formats")
        logger.info("   • Polars DataFrame integration with financial analysis")
        logger.info("   • Custom export configurations")
        logger.info("   • Error handling and validation")
        logger.info("   • Automated file organization")

    except Exception as e:
        logger.error(f"❌ Demonstration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
