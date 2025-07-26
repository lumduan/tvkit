"""
Utility functions for real-time data streaming and export operations.

This module provides utilities for data export, file management, and OHLCV conversion
that were previously in the temp folder but are now production-ready.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import asyncio
import logging

import polars as pl
from decimal import Decimal

from .models import OHLCVData, ExportConfig

# Configure logging
logger: logging.Logger = logging.getLogger(__name__)


def ensure_export_directory(path: str = '/export') -> None:
    """
    Check if the export directory exists, and create it if it does not.

    Args:
        path: The path to the export directory. Defaults to '/export'.

    Raises:
        OSError: If there is an error creating the directory.
    """
    if not os.path.exists(path):
        try:
            os.makedirs(path)
            logger.info(f"Directory {path} created.")
        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            raise OSError(f"Failed to create directory {path}") from e


def generate_export_filepath(
    symbol: str,
    data_category: str,
    timeframe: str,
    file_extension: str
) -> str:
    """
    Generate a file path for exporting data, including the current timestamp.

    This function constructs a file path based on the provided symbol, data category,
    and file extension. The generated path will include a timestamp to ensure uniqueness.

    Args:
        symbol: The symbol to include in the file name, formatted in lowercase.
        data_category: The category of data being exported, which will be prefixed in the file name.
        timeframe: Timeframe of report like (e.g., '1M', '1W').
        file_extension: The file extension for the export file (e.g., '.json', '.csv').

    Returns:
        The generated file path, structured as:
        '/export/{data_category}_{symbol}_{timeframe}_{timestamp}{file_extension}'

    Example:
        >>> generate_export_filepath('BTCUSDT', 'ohlc', '1m', '.json')
        '/export/ohlc_btcusdt_1m_20250725-134201.json'
    """
    timestamp: str = datetime.now().strftime("%Y%m%d-%H%M%S")
    symbol_lower: str = symbol.lower().replace(':', '')

    filename: str = f"{data_category}_{symbol_lower}_{timeframe}_{timestamp}{file_extension}"
    return f"/export/{filename}"


async def save_json_file(data: List[Dict[str, Any]], filepath: str) -> bool:
    """
    Asynchronously save data to a JSON file.

    Args:
        data: List of dictionaries containing the data to save.
        filepath: The file path where the JSON will be saved.

    Returns:
        True if successful, False otherwise.

    Raises:
        IOError: If file writing fails.
    """
    try:
        # Ensure directory exists
        directory: str = os.path.dirname(filepath)
        if directory:
            ensure_export_directory(directory)

        # Use asyncio to write file asynchronously
        def write_file() -> None:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        await asyncio.get_event_loop().run_in_executor(None, write_file)
        logger.info(f"JSON data saved to {filepath}")
        return True

    except Exception as e:
        logger.error(f"Error saving JSON file {filepath}: {e}")
        raise IOError(f"Failed to save JSON file {filepath}") from e


async def save_csv_file(data: List[Dict[str, Any]], filepath: str) -> bool:
    """
    Asynchronously save data to a CSV file using Polars.

    Args:
        data: List of dictionaries containing the data to save.
        filepath: The file path where the CSV will be saved.

    Returns:
        True if successful, False otherwise.

    Raises:
        IOError: If file writing fails.
    """
    try:
        # Ensure directory exists
        directory: str = os.path.dirname(filepath)
        if directory:
            ensure_export_directory(directory)

        # Use asyncio to write file asynchronously
        def write_file() -> None:
            df: pl.DataFrame = pl.DataFrame(data)
            df.write_csv(filepath)

        await asyncio.get_event_loop().run_in_executor(None, write_file)
        logger.info(f"CSV data saved to {filepath}")
        return True

    except Exception as e:
        logger.error(f"Error saving CSV file {filepath}: {e}")
        raise IOError(f"Failed to save CSV file {filepath}") from e


async def save_parquet_file(data: List[Dict[str, Any]], filepath: str) -> bool:
    """
    Asynchronously save data to a Parquet file using Polars.

    Args:
        data: List of dictionaries containing the data to save.
        filepath: The file path where the Parquet will be saved.

    Returns:
        True if successful, False otherwise.

    Raises:
        IOError: If file writing fails.
    """
    try:
        # Ensure directory exists
        directory: str = os.path.dirname(filepath)
        if directory:
            ensure_export_directory(directory)

        # Use asyncio to write file asynchronously
        def write_file() -> None:
            df: pl.DataFrame = pl.DataFrame(data)
            df.write_parquet(filepath)

        await asyncio.get_event_loop().run_in_executor(None, write_file)
        logger.info(f"Parquet data saved to {filepath}")
        return True

    except Exception as e:
        logger.error(f"Error saving Parquet file {filepath}: {e}")
        raise IOError(f"Failed to save Parquet file {filepath}") from e


async def export_data(
    data: List[OHLCVData],
    config: ExportConfig,
    symbol: str,
    timeframe: str = '1m'
) -> bool:
    """
    Export OHLCV data according to the provided export configuration.

    Args:
        data: List of OHLCV data objects to export.
        config: Export configuration specifying format and options.
        symbol: Trading symbol for filename generation.
        timeframe: Data timeframe for filename generation.

    Returns:
        True if export was successful, False otherwise.

    Raises:
        ValueError: If export format is not supported.
        IOError: If file writing fails.
    """
    if not config.enabled or not data:
        return False

    # Convert OHLCV data to dictionaries
    data_dicts: List[Dict[str, Any]] = [item.to_dict() for item in data]

    # Generate filepath
    prefix: str = config.filename_prefix or 'ohlcv'
    extension_map: Dict[str, str] = {
        'json': '.json',
        'csv': '.csv',
        'parquet': '.parquet'
    }

    if config.format not in extension_map:
        raise ValueError(f"Unsupported export format: {config.format}")

    extension: str = extension_map[config.format]

    if config.include_timestamp:
        filepath: str = generate_export_filepath(symbol, prefix, timeframe, extension)
    else:
        symbol_clean: str = symbol.lower().replace(':', '')
        filepath = f"{config.directory}/{prefix}_{symbol_clean}_{timeframe}{extension}"

    # Export based on format
    if config.format == 'json':
        return await save_json_file(data_dicts, filepath)
    elif config.format == 'csv':
        return await save_csv_file(data_dicts, filepath)
    elif config.format == 'parquet':
        return await save_parquet_file(data_dicts, filepath)

    return False


class OHLCVConverter:
    """
    Converter for OHLCV data between different timeframes.

    This class provides functionality to convert OHLCV data from one timeframe
    to another using aggregation methods.
    """

    def __init__(self, target_timeframe: str):
        """
        Initialize the OHLCV converter with a target timeframe.

        Args:
            target_timeframe: The target timeframe to convert to (e.g., '1m', '1h', '1d').

        Raises:
            ValueError: If the target timeframe is not supported.
        """
        self.timeframes: Dict[str, int] = self._load_timeframes()
        self._validate_timeframe(target_timeframe)
        self.target_timeframe: str = target_timeframe
        self.target_interval: int = self._timeframe_to_minutes(timeframe=target_timeframe)

    def _load_timeframes(self) -> Dict[str, int]:
        """
        Load supported timeframes and their minute equivalents.

        Returns:
            Dictionary mapping timeframe strings to minute values.
        """
        return {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "2h": 120,
            "4h": 240,
            "1d": 1440,
            "1w": 10080,
            "1M": 302400  # Approximate, 30.4 days
        }

    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """
        Convert a given timeframe string to its equivalent in minutes.

        Args:
            timeframe: The timeframe to convert (e.g., '1m', '1h', '1d', '1w', '1M').

        Returns:
            The equivalent value in minutes.

        Raises:
            ValueError: If timeframe is not supported.
        """
        minutes: Optional[int] = self.timeframes.get(timeframe)
        if minutes is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return minutes

    def _validate_timeframe(self, timeframe: str) -> None:
        """
        Validate the specified timeframe against the list of supported timeframes.

        Args:
            timeframe: The timeframe to validate.

        Raises:
            ValueError: If the specified timeframe is not in the list of supported timeframes.
        """
        if timeframe not in self.timeframes:
            valid_tf: str = ', '.join(self.timeframes.keys())
            raise ValueError(f"Invalid timeframe '{timeframe}'. Supported: {valid_tf}")

    def convert_ohlcv_data(self, data: List[OHLCVData]) -> List[OHLCVData]:
        """
        Convert a list of OHLCV data to the target timeframe.

        Args:
            data: List of OHLCV data in the original timeframe.

        Returns:
            List of OHLCV data converted to the target timeframe.

        Raises:
            ValueError: If data is empty or conversion is not possible.
        """
        if not data:
            raise ValueError("Cannot convert empty data")

        # Sort data by timestamp
        sorted_data: List[OHLCVData] = sorted(data, key=lambda x: x.timestamp)

        # Group data by target timeframe intervals
        grouped_data: Dict[int, List[OHLCVData]] = {}

        for item in sorted_data:
            # Calculate the interval start time
            interval_start: int = (item.timestamp // (self.target_interval * 60)) * (self.target_interval * 60)

            if interval_start not in grouped_data:
                grouped_data[interval_start] = []
            grouped_data[interval_start].append(item)

        # Convert each group to a single OHLCV entry
        converted_data: List[OHLCVData] = []

        for interval_start, group in sorted(grouped_data.items()):
            if not group:
                continue

            # Calculate OHLCV values for the interval
            open_price: Decimal = group[0].open
            close_price: Decimal = group[-1].close
            high_price: Decimal = max(item.high for item in group)
            low_price: Decimal = min(item.low for item in group)
            total_volume: Decimal = sum((item.volume for item in group), Decimal('0'))

            # Create new OHLCV data point
            converted_item: OHLCVData = OHLCVData(
                index=len(converted_data),
                timestamp=interval_start,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=total_volume
            )

            converted_data.append(converted_item)

        return converted_data


def generate_session_id(length: int = 12) -> str:
    """
    Generate a random session identifier.

    Args:
        length: Length of the session ID. Defaults to 12.

    Returns:
        Random alphanumeric session identifier.
    """
    import string
    import secrets

    alphabet: str = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def validate_symbols_async(symbols: List[str], validation_url: str) -> List[str]:
    """
    Asynchronously validate a list of trading symbols.

    Args:
        symbols: List of symbols in 'EXCHANGE:SYMBOL' format.
        validation_url: URL template for symbol validation.

    Returns:
        List of valid symbols.

    Raises:
        ValueError: If symbol format is invalid.
        httpx.RequestError: If validation request fails.
    """
    import httpx

    valid_symbols: List[str] = []

    async with httpx.AsyncClient() as client:
        for symbol in symbols:
            if ':' not in symbol:
                raise ValueError(f"Invalid symbol format '{symbol}'. Must be like 'BINANCE:BTCUSDT'")

            exchange, symbol_name = symbol.split(':', 1)

            try:
                response = await client.get(
                    validation_url.format(exchange=exchange, symbol=symbol_name),
                    timeout=10.0
                )
                response.raise_for_status()

                # If we get here, symbol is valid
                valid_symbols.append(symbol)
                logger.debug(f"Symbol {symbol} validated successfully")

            except httpx.HTTPError as e:
                logger.warning(f"Symbol {symbol} validation failed: {e}")
                continue

    return valid_symbols
