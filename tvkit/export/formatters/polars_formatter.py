"""
Polars DataFrame formatter for data export operations.

This module provides export functionality using Polars DataFrames,
offering high-performance data processing and analysis capabilities.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Union

if TYPE_CHECKING:
    import polars as pl
else:
    try:
        import polars as pl
    except ImportError:
        pl = None  # type: ignore[assignment]

from ..models import (
    ExportConfig,
    ExportFormat,
    ExportMetadata,
    ExportResult,
    OHLCVExportData,
    ScannerExportData,
)
from .base_formatter import BaseFormatter

logger = logging.getLogger(__name__)


class PolarsFormatter(BaseFormatter):
    """Polars DataFrame formatter for high-performance data export."""

    def __init__(self, config: ExportConfig) -> None:
        """
        Initialize Polars formatter.

        Args:
            config: Export configuration settings

        Raises:
            ImportError: If Polars is not installed
        """
        if not TYPE_CHECKING and pl is None:
            raise ImportError(
                "Polars is required for PolarsFormatter. Install with: uv add polars"
            )

        super().__init__(config)

    def supports_format(self, format_type: str) -> bool:
        """Check if this formatter supports the given format."""
        return format_type.lower() == ExportFormat.POLARS.value

    async def export_ohlcv(
        self, data: List[OHLCVExportData], file_path: Union[Path, str, None] = None
    ) -> ExportResult:
        """
        Export OHLCV data as Polars DataFrame.

        Args:
            data: List of OHLCV data records
            file_path: Not used for Polars format (returns DataFrame directly)

        Returns:
            ExportResult with Polars DataFrame in the data field
        """
        try:
            self._validate_data(data)

            # Convert to dictionaries for Polars DataFrame creation
            records: List[Dict[str, Any]] = []
            for item in data:
                record: Dict[str, Any] = {
                    "timestamp": self._prepare_timestamp(item.timestamp),
                    "open": float(item.open),
                    "high": float(item.high),
                    "low": float(item.low),
                    "close": float(item.close),
                    "volume": float(item.volume),
                }

                # Add optional fields if present
                if item.symbol:
                    record["symbol"] = item.symbol
                if item.interval:
                    record["interval"] = item.interval

                records.append(record)

            # Create Polars DataFrame
            assert pl is not None  # Already checked in __init__
            df: pl.DataFrame = pl.DataFrame(records)

            # Apply timestamp conversion if needed
            if self.config.timestamp_format == "datetime" and "timestamp" in df.columns:
                # Convert Unix timestamps to datetime if they're numeric
                if df["timestamp"].dtype in [pl.Float64, pl.Int64]:
                    df = df.with_columns(
                        [
                            (pl.col("timestamp") * 1000)
                            .cast(pl.Datetime(time_unit="ms"))
                            .alias("timestamp")
                        ]
                    )

            # Add financial analysis columns based on config options
            if self.config.options.get("add_analysis", False):
                df = self._add_financial_analysis(df)

            # Create metadata
            symbol: str = data[0].symbol if data and data[0].symbol else "unknown"
            metadata: ExportMetadata = ExportMetadata(
                source="ohlcv",
                symbol=symbol,
                interval=data[0].interval if data and data[0].interval else None,
                record_count=len(data),
                format=ExportFormat.POLARS,
            )

            return ExportResult(success=True, metadata=metadata, data=df)

        except Exception as e:
            logger.error(f"Failed to export OHLCV data to Polars: {e}")

            metadata = ExportMetadata(
                source="ohlcv",
                record_count=len(data) if data else 0,
                format=ExportFormat.POLARS,
            )

            return ExportResult(success=False, metadata=metadata, error_message=str(e))

    async def export_scanner(
        self, data: List[ScannerExportData], file_path: Union[Path, str, None] = None
    ) -> ExportResult:
        """
        Export scanner data as Polars DataFrame.

        Args:
            data: List of scanner data records
            file_path: Not used for Polars format (returns DataFrame directly)

        Returns:
            ExportResult with Polars DataFrame in the data field
        """
        try:
            self._validate_data(data)

            # Convert scanner data to flat records
            records: List[Dict[str, Any]] = []
            for item in data:
                record: Dict[str, Any] = {"name": item.name}

                # Flatten the data dictionary
                for key, value in item.data.items():
                    record[key] = value

                # Add export timestamp if metadata is included
                if self.config.include_metadata:
                    record["export_timestamp"] = item.export_timestamp.isoformat()

                records.append(record)

            # Create Polars DataFrame
            assert pl is not None  # Already checked in __init__
            df: pl.DataFrame = pl.DataFrame(records)

            # Create metadata
            metadata: ExportMetadata = ExportMetadata(
                source="scanner", record_count=len(data), format=ExportFormat.POLARS
            )

            return ExportResult(success=True, metadata=metadata, data=df)

        except Exception as e:
            logger.error(f"Failed to export scanner data to Polars: {e}")

            metadata = ExportMetadata(
                source="scanner",
                record_count=len(data) if data else 0,
                format=ExportFormat.POLARS,
            )

            return ExportResult(success=False, metadata=metadata, error_message=str(e))

    def _add_financial_analysis(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Add financial analysis columns to OHLCV DataFrame.

        Args:
            df: Input DataFrame with OHLCV data

        Returns:
            DataFrame with additional analysis columns
        """
        try:
            assert pl is not None  # Already checked in __init__
            analysis_df: pl.DataFrame = (
                df.with_columns(
                    [
                        # Price calculations
                        (
                            (pl.col("close") - pl.col("open")) / pl.col("open") * 100
                        ).alias("return_pct"),
                        ((pl.col("high") + pl.col("low") + pl.col("close")) / 3).alias(
                            "typical_price"
                        ),
                        (pl.col("high") - pl.col("low")).alias("true_range"),
                        # VWAP components
                        (
                            (pl.col("high") + pl.col("low") + pl.col("close"))
                            / 3
                            * pl.col("volume")
                        ).alias("vwap_numerator"),
                    ]
                )
                .with_columns(
                    [
                        # Moving averages (if enough data)
                        pl.col("close")
                        .rolling_mean(window_size=min(5, len(df)))
                        .alias("sma_5"),
                        pl.col("close")
                        .rolling_mean(window_size=min(10, len(df)))
                        .alias("sma_10"),
                        pl.col("volume")
                        .rolling_mean(window_size=min(5, len(df)))
                        .alias("vol_ma_5"),
                        # Cumulative VWAP calculation
                        pl.col("vwap_numerator").cum_sum().alias("cum_vwap_num"),
                        pl.col("volume").cum_sum().alias("cum_volume"),
                    ]
                )
                .with_columns(
                    [
                        # Final VWAP
                        (pl.col("cum_vwap_num") / pl.col("cum_volume")).alias("vwap"),
                        # Price momentum (if enough data)
                        (
                            pl.col("close") - pl.col("close").shift(min(3, len(df) - 1))
                        ).alias("momentum_3")
                        if len(df) > 3
                        else pl.lit(0).alias("momentum_3"),
                    ]
                )
            )

            return analysis_df

        except Exception as e:
            logger.warning(f"Failed to add financial analysis columns: {e}")
            return df

    async def export_to_file(
        self,
        df: pl.DataFrame,
        file_path: Union[Path, str],
        format_type: str = "parquet",
    ) -> bool:
        """
        Export Polars DataFrame to file.

        Args:
            df: DataFrame to export
            file_path: Output file path
            format_type: File format ('parquet', 'csv', 'json')

        Returns:
            True if export successful
        """
        try:
            path: Path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            if format_type.lower() == "parquet":
                df.write_parquet(path)
            elif format_type.lower() == "csv":
                df.write_csv(path)
            elif format_type.lower() == "json":
                df.write_json(path)
            else:
                raise ValueError(f"Unsupported file format: {format_type}")

            logger.info(f"Successfully exported DataFrame to {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export DataFrame to file: {e}")
            return False
