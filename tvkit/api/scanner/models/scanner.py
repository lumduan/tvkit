"""
TradingView Scanner API Models.

This module provides Pydantic models for interacting with the TradingView
scanner API, including request payloads and response parsing.
"""

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


class SortConfig(BaseModel):
    """Configuration for sorting scanner results."""

    sort_by: str = Field(
        alias="sortBy", description="Field to sort by (e.g., 'name', 'close', 'volume')"
    )
    sort_order: Literal["asc", "desc"] = Field(
        alias="sortOrder",
        default="asc",
        description="Sort order: ascending or descending",
    )
    nulls_first: bool = Field(
        alias="nullsFirst",
        default=False,
        description="Whether to place null values first in results",
    )

    class Config:
        """Pydantic configuration."""

        populate_by_name = True


class ScannerOptions(BaseModel):
    """Options for scanner request."""

    lang: str = Field(
        default="en", description="Language code for response localization"
    )

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, v: str) -> str:
        """Validate language code format."""
        if not v or len(v) != 2:
            raise ValueError("Language code must be 2 characters")
        return v.lower()


class ScannerRequest(BaseModel):
    """Request model for TradingView scanner API."""

    columns: list[str] = Field(description="List of data columns to retrieve")
    ignore_unknown_fields: bool = Field(
        default=False, description="Whether to ignore unknown fields in response"
    )
    options: ScannerOptions = Field(
        default_factory=ScannerOptions, description="Additional options for the scanner"
    )
    range: tuple[int, int] = Field(
        description="Range of results to return [start, end]"
    )
    sort: SortConfig = Field(description="Sorting configuration")
    preset: str = Field(description="Scanner preset (e.g., 'all_stocks', 'crypto')")

    @field_validator("range")
    @classmethod
    def validate_range(cls, v: tuple[int, int]) -> tuple[int, int]:
        """Validate range values."""
        start, end = v
        if start < 0:
            raise ValueError("Range start must be non-negative")
        if end <= start:
            raise ValueError("Range end must be greater than start")
        if end - start > 10000:
            raise ValueError("Range cannot exceed 10,000 items")
        return v

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, v: list[str]) -> list[str]:
        """Validate column names."""
        if not v:
            raise ValueError("At least one column must be specified")

        # Comprehensive list of valid TradingView scanner columns
        valid_columns = {
            # Basic Information
            "name",
            "description",
            "logoid",
            "update_mode",
            "type",
            "typespecs",
            # Price Data
            "close",
            "pricescale",
            "minmov",
            "fractional",
            "minmove2",
            "currency",
            "change",
            # Performance Metrics
            "Perf.W",
            "Perf.1M",
            "Perf.3M",
            "Perf.6M",
            "Perf.YTD",
            "Perf.Y",
            "Perf.5Y",
            "Perf.10Y",
            "Perf.All",
            "Perf.1Y.MarketCap",
            # Volatility
            "Volatility.W",
            "Volatility.M",
            # Volume and Market Data
            "volume",
            "relative_volume_10d_calc",
            "market_cap_basic",
            "market",
            "sector",
            "sector.tr",
            # Currency and Fundamentals
            "fundamental_currency_code",
            # Valuation Ratios
            "price_earnings_ttm",
            "price_earnings_growth_ttm",
            "price_sales_current",
            "price_book_fq",
            "price_to_cash_f_operating_activities_ttm",
            "price_free_cash_flow_ttm",
            "price_to_cash_ratio",
            # Enterprise Value
            "enterprise_value_current",
            "enterprise_value_to_revenue_ttm",
            "enterprise_value_to_ebit_ttm",
            "enterprise_value_ebitda_ttm",
            # Earnings
            "earnings_per_share_diluted_ttm",
            "earnings_per_share_diluted_yoy_growth_ttm",
            # Dividends
            "dps_common_stock_prim_issue_fy",
            "dps_common_stock_prim_issue_fq",
            "dividends_yield_current",
            "dividends_yield",
            "dividend_payout_ratio_ttm",
            "dps_common_stock_prim_issue_yoy_growth_fy",
            "continuous_dividend_payout",
            "continuous_dividend_growth",
            # Margins and Returns
            "gross_margin_ttm",
            "operating_margin_ttm",
            "pre_tax_margin_ttm",
            "net_margin_ttm",
            "free_cash_flow_margin_ttm",
            "return_on_assets_fq",
            "return_on_equity_fq",
            "return_on_invested_capital_fq",
            "research_and_dev_ratio_ttm",
            "sell_gen_admin_exp_other_ratio_ttm",
            # Revenue and Income
            "total_revenue_ttm",
            "total_revenue_yoy_growth_ttm",
            "gross_profit_ttm",
            "oper_income_ttm",
            "net_income_ttm",
            "ebitda_ttm",
            # Balance Sheet
            "total_assets_fq",
            "total_current_assets_fq",
            "cash_n_short_term_invest_fq",
            "total_liabilities_fq",
            "total_debt_fq",
            "net_debt_fq",
            "total_equity_fq",
            "current_ratio_fq",
            "quick_ratio_fq",
            "debt_to_equity_fq",
            "cash_n_short_term_invest_to_total_debt_fq",
            # Cash Flow
            "cash_f_operating_activities_ttm",
            "cash_f_investing_activities_ttm",
            "cash_f_financing_activities_ttm",
            "free_cash_flow_ttm",
            "capital_expenditures_ttm",
            # Recommendations and Analysis
            "recommendation_mark",
            "Recommend.All",
            "Recommend.MA",
            "Recommend.Other",
            # Technical Indicators
            "RSI",
            "Mom",
            "AO",
            "CCI20",
            "Stoch.K",
            "Stoch.D",
            "MACD.macd",
            "MACD.signal",
            # Additional fields for compatibility
            "high",
            "low",
            "open",
            "change_abs",
        }

        # Allow all columns but warn about unknown ones
        unknown_columns = set(v) - valid_columns
        if unknown_columns:
            # In a real implementation, you might want to log this
            pass

        return v

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            tuple: list  # Convert tuple to list for JSON serialization
        }


class StockData(BaseModel):
    """Model representing a single stock's data from scanner response."""

    name: str = Field(description="Stock symbol/ticker")
    close: Optional[float] = Field(default=None, description="Current/last close price")
    pricescale: Optional[int] = Field(default=None, description="Price scale factor")
    minmov: Optional[int] = Field(default=None, description="Minimum price movement")
    fractional: Optional[Union[str, bool]] = Field(
        default=None, description="Whether price is fractional"
    )
    minmove2: Optional[int] = Field(
        default=None, description="Secondary minimum movement"
    )
    currency: Optional[str] = Field(default=None, description="Currency code")
    change: Optional[float] = Field(default=None, description="Price change")
    volume: Optional[int] = Field(default=None, description="Trading volume")
    relative_volume_10d_calc: Optional[float] = Field(
        default=None, description="Relative volume compared to 10-day average"
    )
    market_cap_basic: Optional[int] = Field(
        default=None, description="Basic market capitalization"
    )
    fundamental_currency_code: Optional[str] = Field(
        default=None, description="Fundamental currency code"
    )
    price_earnings_ttm: Optional[float] = Field(
        default=None, description="Price-to-earnings ratio (trailing twelve months)"
    )
    earnings_per_share_diluted_ttm: Optional[float] = Field(
        default=None, description="Diluted earnings per share (TTM)"
    )
    earnings_per_share_diluted_yoy_growth_ttm: Optional[float] = Field(
        default=None, description="Year-over-year EPS growth (TTM)"
    )
    dividends_yield_current: Optional[float] = Field(
        default=None, description="Current dividend yield"
    )
    sector_tr: Optional[str] = Field(
        default=None, alias="sector.tr", description="Sector classification (TR)"
    )
    market: Optional[str] = Field(default=None, description="Market/exchange")
    sector: Optional[str] = Field(default=None, description="Sector classification")
    recommendation_mark: Optional[float] = Field(
        default=None, description="Analyst recommendation score"
    )

    @classmethod
    def from_scanner_row(cls, row_data: list[Any], columns: list[str]) -> "StockData":
        """
        Create StockData instance from scanner API row data.

        Args:
            row_data: List of values corresponding to requested columns
            columns: List of column names in the same order as row_data

        Returns:
            StockData instance with parsed values

        Raises:
            ValueError: If row_data and columns length mismatch

        Example:
            >>> columns = ["name", "close", "currency"]
            >>> row = ["AAPL", 150.25, "USD"]
            >>> stock = StockData.from_scanner_row(row, columns)
            >>> stock.name
            'AAPL'
        """
        if len(row_data) != len(columns):
            raise ValueError(
                f"Row data length ({len(row_data)}) doesn't match "
                f"columns length ({len(columns)})"
            )

        # Map row data to column names
        data_dict = dict(zip(columns, row_data))

        # Handle special column name mappings
        if "sector.tr" in data_dict:
            data_dict["sector_tr"] = data_dict.pop("sector.tr")

        # Convert "false"/"true" strings to boolean for fractional field
        if "fractional" in data_dict and isinstance(data_dict["fractional"], str):
            data_dict["fractional"] = data_dict["fractional"].lower() == "true"

        return cls(**data_dict)

    class Config:
        """Pydantic configuration."""

        populate_by_name = True
        extra = "allow"  # Allow additional fields from API


class ScannerResponse(BaseModel):
    """Response model for TradingView scanner API."""

    data: list[StockData] = Field(description="List of stock data")
    total_count: Optional[int] = Field(
        default=None, description="Total number of available results"
    )
    next_page_token: Optional[str] = Field(
        default=None, description="Token for retrieving next page of results"
    )

    @classmethod
    def from_api_response(
        cls, response_data: dict[str, Any], columns: list[str]
    ) -> "ScannerResponse":
        """
        Create ScannerResponse from raw API response.

        Args:
            response_data: Raw response data from TradingView API
            columns: List of requested columns for parsing rows

        Returns:
            Parsed ScannerResponse instance

        Example:
            >>> response = {
            ...     "data": [{"s": "NASDAQ:AAPL", "d": ["AAPL", 150.25, "USD"]}],
            ...     "totalCount": 1
            ... }
            >>> columns = ["name", "close", "currency"]
            >>> scanner_response = ScannerResponse.from_api_response(response, columns)
        """
        # Parse rows into StockData instances
        stocks: list[StockData] = []
        if "data" in response_data:
            for item in response_data["data"]:
                try:
                    # Handle new API format: {"s": "NASDAQ:AAPL", "d": [data_array]}
                    if isinstance(item, dict) and "d" in item:
                        row_data: list[Any] = item["d"]
                        # Also extract symbol from "s" field if available
                        if "s" in item and columns and columns[0] == "name":
                            # Use the symbol from "s" field as the name
                            symbol_field: str = str(item["s"])
                            symbol: str = (
                                symbol_field.split(":")[-1]
                                if ":" in symbol_field
                                else symbol_field
                            )
                            # Replace first element (name) with the extracted symbol
                            row_data = [symbol] + row_data[1:]
                    else:
                        # Handle legacy format: direct array
                        row_data = (
                            list(item) if isinstance(item, (list, tuple)) else [item]
                        )

                    stock = StockData.from_scanner_row(row_data, columns)
                    stocks.append(stock)
                except Exception:
                    # Log error but continue processing other rows
                    # In production, you'd want proper logging here
                    continue

        return cls(
            data=stocks,
            total_count=response_data.get("totalCount"),
            next_page_token=response_data.get("nextPageToken"),
        )


# Common scanner presets for convenience
class ScannerPresets:
    """Common scanner preset configurations."""

    ALL_STOCKS = "all_stocks"


class Columns:
    """Available column names for TradingView scanner API."""

    # Basic Information
    NAME = "name"
    DESCRIPTION = "description"
    LOGOID = "logoid"
    UPDATE_MODE = "update_mode"
    TYPE = "type"
    TYPESPECS = "typespecs"

    # Price Data
    CLOSE = "close"
    PRICESCALE = "pricescale"
    MINMOV = "minmov"
    FRACTIONAL = "fractional"
    MINMOVE2 = "minmove2"
    CURRENCY = "currency"
    CHANGE = "change"

    # Performance Metrics
    PERF_W = "Perf.W"
    PERF_1M = "Perf.1M"
    PERF_3M = "Perf.3M"
    PERF_6M = "Perf.6M"
    PERF_YTD = "Perf.YTD"
    PERF_Y = "Perf.Y"
    PERF_5Y = "Perf.5Y"
    PERF_10Y = "Perf.10Y"
    PERF_ALL = "Perf.All"
    PERF_1Y_MARKET_CAP = "Perf.1Y.MarketCap"

    # Volatility
    VOLATILITY_W = "Volatility.W"
    VOLATILITY_M = "Volatility.M"

    # Volume and Market Data
    VOLUME = "volume"
    RELATIVE_VOLUME_10D_CALC = "relative_volume_10d_calc"
    MARKET_CAP_BASIC = "market_cap_basic"
    MARKET = "market"
    SECTOR = "sector"
    SECTOR_TR = "sector.tr"

    # Currency and Fundamentals
    FUNDAMENTAL_CURRENCY_CODE = "fundamental_currency_code"

    # Valuation Ratios
    PRICE_EARNINGS_TTM = "price_earnings_ttm"
    PRICE_EARNINGS_GROWTH_TTM = "price_earnings_growth_ttm"
    PRICE_SALES_CURRENT = "price_sales_current"
    PRICE_BOOK_FQ = "price_book_fq"
    PRICE_TO_CASH_F_OPERATING_ACTIVITIES_TTM = (
        "price_to_cash_f_operating_activities_ttm"
    )
    PRICE_FREE_CASH_FLOW_TTM = "price_free_cash_flow_ttm"
    PRICE_TO_CASH_RATIO = "price_to_cash_ratio"

    # Enterprise Value
    ENTERPRISE_VALUE_CURRENT = "enterprise_value_current"
    ENTERPRISE_VALUE_TO_REVENUE_TTM = "enterprise_value_to_revenue_ttm"
    ENTERPRISE_VALUE_TO_EBIT_TTM = "enterprise_value_to_ebit_ttm"
    ENTERPRISE_VALUE_EBITDA_TTM = "enterprise_value_ebitda_ttm"

    # Earnings
    EARNINGS_PER_SHARE_DILUTED_TTM = "earnings_per_share_diluted_ttm"
    EARNINGS_PER_SHARE_DILUTED_YOY_GROWTH_TTM = (
        "earnings_per_share_diluted_yoy_growth_ttm"
    )

    # Dividends
    DPS_COMMON_STOCK_PRIM_ISSUE_FY = "dps_common_stock_prim_issue_fy"
    DPS_COMMON_STOCK_PRIM_ISSUE_FQ = "dps_common_stock_prim_issue_fq"
    DIVIDENDS_YIELD_CURRENT = "dividends_yield_current"
    DIVIDENDS_YIELD = "dividends_yield"
    DIVIDEND_PAYOUT_RATIO_TTM = "dividend_payout_ratio_ttm"
    DPS_COMMON_STOCK_PRIM_ISSUE_YOY_GROWTH_FY = (
        "dps_common_stock_prim_issue_yoy_growth_fy"
    )
    CONTINUOUS_DIVIDEND_PAYOUT = "continuous_dividend_payout"
    CONTINUOUS_DIVIDEND_GROWTH = "continuous_dividend_growth"

    # Margins and Returns
    GROSS_MARGIN_TTM = "gross_margin_ttm"
    OPERATING_MARGIN_TTM = "operating_margin_ttm"
    PRE_TAX_MARGIN_TTM = "pre_tax_margin_ttm"
    NET_MARGIN_TTM = "net_margin_ttm"
    FREE_CASH_FLOW_MARGIN_TTM = "free_cash_flow_margin_ttm"
    RETURN_ON_ASSETS_FQ = "return_on_assets_fq"
    RETURN_ON_EQUITY_FQ = "return_on_equity_fq"
    RETURN_ON_INVESTED_CAPITAL_FQ = "return_on_invested_capital_fq"
    RESEARCH_AND_DEV_RATIO_TTM = "research_and_dev_ratio_ttm"
    SELL_GEN_ADMIN_EXP_OTHER_RATIO_TTM = "sell_gen_admin_exp_other_ratio_ttm"

    # Revenue and Income
    TOTAL_REVENUE_TTM = "total_revenue_ttm"
    TOTAL_REVENUE_YOY_GROWTH_TTM = "total_revenue_yoy_growth_ttm"
    GROSS_PROFIT_TTM = "gross_profit_ttm"
    OPER_INCOME_TTM = "oper_income_ttm"
    NET_INCOME_TTM = "net_income_ttm"
    EBITDA_TTM = "ebitda_ttm"

    # Balance Sheet
    TOTAL_ASSETS_FQ = "total_assets_fq"
    TOTAL_CURRENT_ASSETS_FQ = "total_current_assets_fq"
    CASH_N_SHORT_TERM_INVEST_FQ = "cash_n_short_term_invest_fq"
    TOTAL_LIABILITIES_FQ = "total_liabilities_fq"
    TOTAL_DEBT_FQ = "total_debt_fq"
    NET_DEBT_FQ = "net_debt_fq"
    TOTAL_EQUITY_FQ = "total_equity_fq"
    CURRENT_RATIO_FQ = "current_ratio_fq"
    QUICK_RATIO_FQ = "quick_ratio_fq"
    DEBT_TO_EQUITY_FQ = "debt_to_equity_fq"
    CASH_N_SHORT_TERM_INVEST_TO_TOTAL_DEBT_FQ = (
        "cash_n_short_term_invest_to_total_debt_fq"
    )

    # Cash Flow
    CASH_F_OPERATING_ACTIVITIES_TTM = "cash_f_operating_activities_ttm"
    CASH_F_INVESTING_ACTIVITIES_TTM = "cash_f_investing_activities_ttm"
    CASH_F_FINANCING_ACTIVITIES_TTM = "cash_f_financing_activities_ttm"
    FREE_CASH_FLOW_TTM = "free_cash_flow_ttm"
    CAPITAL_EXPENDITURES_TTM = "capital_expenditures_ttm"

    # Recommendations and Analysis
    RECOMMENDATION_MARK = "recommendation_mark"
    RECOMMEND_ALL = "Recommend.All"
    RECOMMEND_MA = "Recommend.MA"
    RECOMMEND_OTHER = "Recommend.Other"

    # Technical Indicators
    RSI = "RSI"
    MOM = "Mom"
    AO = "AO"
    CCI20 = "CCI20"
    STOCH_K = "Stoch.K"
    STOCH_D = "Stoch.D"
    MACD_MACD = "MACD.macd"
    MACD_SIGNAL = "MACD.signal"


# Common column sets for convenience
class ColumnSets:
    """Predefined column sets for common use cases."""

    BASIC = ["name", "close", "currency", "change", "volume"]

    DETAILED = [
        "name",
        "close",
        "pricescale",
        "minmov",
        "fractional",
        "minmove2",
        "currency",
        "change",
        "volume",
        "relative_volume_10d_calc",
        "market_cap_basic",
        "fundamental_currency_code",
        "price_earnings_ttm",
        "earnings_per_share_diluted_ttm",
        "earnings_per_share_diluted_yoy_growth_ttm",
        "dividends_yield_current",
        "sector.tr",
        "market",
        "sector",
        "recommendation_mark",
    ]

    FUNDAMENTALS = [
        "name",
        "close",
        "currency",
        "market_cap_basic",
        "price_earnings_ttm",
        "earnings_per_share_diluted_ttm",
        "dividends_yield_current",
        "sector",
        "recommendation_mark",
    ]

    TECHNICAL = [
        "name",
        "close",
        "currency",
        "change",
        "volume",
        "relative_volume_10d_calc",
        "high",
        "low",
        "open",
    ]

    PERFORMANCE = [
        "name",
        "close",
        "currency",
        "Perf.W",
        "Perf.1M",
        "Perf.3M",
        "Perf.6M",
        "Perf.YTD",
        "Perf.Y",
        "Perf.5Y",
        "Perf.10Y",
        "Perf.All",
        "Volatility.W",
        "Volatility.M",
    ]

    VALUATION = [
        "name",
        "close",
        "currency",
        "market_cap_basic",
        "price_earnings_ttm",
        "price_earnings_growth_ttm",
        "price_sales_current",
        "price_book_fq",
        "enterprise_value_current",
        "enterprise_value_to_revenue_ttm",
    ]

    DIVIDENDS = [
        "name",
        "close",
        "currency",
        "dividends_yield_current",
        "dividends_yield",
        "dividend_payout_ratio_ttm",
        "dps_common_stock_prim_issue_fy",
        "continuous_dividend_payout",
        "continuous_dividend_growth",
    ]

    PROFITABILITY = [
        "name",
        "close",
        "currency",
        "gross_margin_ttm",
        "operating_margin_ttm",
        "net_margin_ttm",
        "return_on_assets_fq",
        "return_on_equity_fq",
        "return_on_invested_capital_fq",
    ]

    FINANCIAL_STRENGTH = [
        "name",
        "close",
        "currency",
        "total_assets_fq",
        "total_debt_fq",
        "net_debt_fq",
        "current_ratio_fq",
        "quick_ratio_fq",
        "debt_to_equity_fq",
    ]

    CASH_FLOW = [
        "name",
        "close",
        "currency",
        "cash_f_operating_activities_ttm",
        "free_cash_flow_ttm",
        "free_cash_flow_margin_ttm",
        "capital_expenditures_ttm",
    ]

    TECHNICAL_INDICATORS = [
        "name",
        "close",
        "currency",
        "RSI",
        "Mom",
        "AO",
        "CCI20",
        "Stoch.K",
        "Stoch.D",
        "MACD.macd",
        "MACD.signal",
        "Recommend.All",
        "Recommend.MA",
    ]

    # Comprehensive set with all major categories
    COMPREHENSIVE = [
        "name",
        "description",
        "close",
        "currency",
        "change",
        "volume",
        "market_cap_basic",
        "price_earnings_ttm",
        "earnings_per_share_diluted_ttm",
        "dividends_yield_current",
        "sector",
        "market",
        "recommendation_mark",
        "Perf.YTD",
        "Perf.Y",
        "gross_margin_ttm",
        "return_on_equity_fq",
        "free_cash_flow_ttm",
        "debt_to_equity_fq",
        "RSI",
    ]

    # Complete comprehensive set with all available TradingView scanner columns
    COMPREHENSIVE_FULL = [
        "name",
        "description",
        "logoid",
        "update_mode",
        "type",
        "typespecs",
        "close",
        "pricescale",
        "minmov",
        "fractional",
        "minmove2",
        "currency",
        "change",
        "Perf.W",
        "Perf.1M",
        "Perf.3M",
        "Perf.6M",
        "Perf.YTD",
        "Perf.Y",
        "Perf.5Y",
        "Perf.10Y",
        "Perf.All",
        "Perf.1Y.MarketCap",
        "Volatility.W",
        "Volatility.M",
        "volume",
        "relative_volume_10d_calc",
        "market_cap_basic",
        "market",
        "sector",
        "sector.tr",
        "fundamental_currency_code",
        "price_earnings_ttm",
        "price_earnings_growth_ttm",
        "price_sales_current",
        "price_book_fq",
        "price_to_cash_f_operating_activities_ttm",
        "price_free_cash_flow_ttm",
        "price_to_cash_ratio",
        "enterprise_value_current",
        "enterprise_value_to_revenue_ttm",
        "enterprise_value_to_ebit_ttm",
        "enterprise_value_ebitda_ttm",
        "earnings_per_share_diluted_ttm",
        "earnings_per_share_diluted_yoy_growth_ttm",
        "dps_common_stock_prim_issue_fy",
        "dps_common_stock_prim_issue_fq",
        "dividends_yield_current",
        "dividends_yield",
        "dividend_payout_ratio_ttm",
        "dps_common_stock_prim_issue_yoy_growth_fy",
        "continuous_dividend_payout",
        "continuous_dividend_growth",
        "gross_margin_ttm",
        "operating_margin_ttm",
        "pre_tax_margin_ttm",
        "net_margin_ttm",
        "free_cash_flow_margin_ttm",
        "return_on_assets_fq",
        "return_on_equity_fq",
        "return_on_invested_capital_fq",
        "research_and_dev_ratio_ttm",
        "sell_gen_admin_exp_other_ratio_ttm",
        "total_revenue_ttm",
        "total_revenue_yoy_growth_ttm",
        "gross_profit_ttm",
        "oper_income_ttm",
        "net_income_ttm",
        "ebitda_ttm",
        "total_assets_fq",
        "total_current_assets_fq",
        "cash_n_short_term_invest_fq",
        "total_liabilities_fq",
        "total_debt_fq",
        "net_debt_fq",
        "total_equity_fq",
        "current_ratio_fq",
        "quick_ratio_fq",
        "debt_to_equity_fq",
        "cash_n_short_term_invest_to_total_debt_fq",
        "cash_f_operating_activities_ttm",
        "cash_f_investing_activities_ttm",
        "cash_f_financing_activities_ttm",
        "free_cash_flow_ttm",
        "capital_expenditures_ttm",
        "recommendation_mark",
        "Recommend.All",
        "Recommend.MA",
        "Recommend.Other",
        "RSI",
        "Mom",
        "AO",
        "CCI20",
        "Stoch.K",
        "Stoch.D",
        "MACD.macd",
        "MACD.signal",
        "high",
        "low",
        "open",
        "change_abs",
    ]


def create_scanner_request(
    columns: Optional[list[str]] = None,
    preset: str = ScannerPresets.ALL_STOCKS,
    sort_by: str = "name",
    sort_order: Literal["asc", "desc"] = "asc",
    range_start: int = 0,
    range_end: int = 1000,
    language: str = "en",
) -> ScannerRequest:
    """
    Create a scanner request with sensible defaults.

    Args:
        columns: List of columns to request (defaults to DETAILED)
        preset: Scanner preset to use
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        range_start: Start index for results
        range_end: End index for results
        language: Language code for response

    Returns:
        Configured ScannerRequest instance

    Example:
        >>> request = create_scanner_request(
        ...     columns=ColumnSets.BASIC,
        ...     sort_by="volume",
        ...     sort_order="desc",
        ...     range_end=50
        ... )
    """
    if columns is None:
        columns = ColumnSets.DETAILED

    return ScannerRequest(
        columns=columns,
        preset=preset,
        range=(range_start, range_end),
        sort=SortConfig(sortBy=sort_by, sortOrder=sort_order),
        options=ScannerOptions(lang=language),
    )


if __name__ == "__main__":
    # Example usage
    print("Creating scanner request with default settings...")
    print("Columns:", ColumnSets.BASIC)
