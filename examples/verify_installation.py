#!/usr/bin/env python3
"""
TVKit Installation Verification Script

Run this script to verify that TVKit is properly installed and working.
Perfect for troubleshooting installation issues.

Usage:
    uv run python examples/verify_installation.py
    python examples/verify_installation.py
"""

import sys
import asyncio
import importlib
from typing import Dict, Any, List


def check_python_version() -> Dict[str, Any]:
    """Check Python version compatibility."""
    version_info = sys.version_info
    version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"

    is_compatible = version_info >= (3, 11)

    return {
        "test": "Python Version",
        "version": version_str,
        "compatible": is_compatible,
        "status": "✅ Compatible" if is_compatible else "⚠️  Outdated",
        "details": "Python 3.11+ recommended for best performance"
        if not is_compatible
        else "Good to go!",
    }


def check_package_imports() -> List[Dict[str, Any]]:
    """Check if all required packages can be imported."""
    packages = [
        ("tvkit", "Core TVKit package"),
        ("tvkit.quickstart", "Quick start utilities"),
        ("pydantic", "Data validation"),
        ("websockets", "WebSocket support"),
        ("httpx", "HTTP client"),
        ("polars", "Data processing"),
        ("pandas", "Alternative data processing"),
        ("matplotlib", "Plotting"),
        ("seaborn", "Statistical plotting"),
    ]

    results = []
    for package, description in packages:
        try:
            importlib.import_module(package)
            results.append(
                {
                    "test": f"Import {package}",
                    "description": description,
                    "status": "✅ Available",
                    "success": True,
                }
            )
        except ImportError as e:
            results.append(
                {
                    "test": f"Import {package}",
                    "description": description,
                    "status": f"❌ Failed: {e}",
                    "success": False,
                }
            )

    return results


async def check_basic_functionality() -> Dict[str, Any]:
    """Test basic TVKit functionality."""
    try:
        from tvkit import get_stock_price

        # Try to get a stock price
        result = await get_stock_price("NASDAQ:AAPL")

        # Verify the result structure
        expected_keys = [
            "symbol",
            "price",
            "open",
            "high",
            "low",
            "volume",
            "timestamp",
            "date",
        ]
        missing_keys = [key for key in expected_keys if key not in result]

        if missing_keys:
            return {
                "test": "Basic Functionality",
                "status": f"⚠️  Partial - Missing keys: {missing_keys}",
                "success": False,
                "details": f"Got result but missing expected keys: {missing_keys}",
            }

        return {
            "test": "Basic Functionality",
            "status": "✅ Working",
            "success": True,
            "details": f"Successfully fetched Apple stock price: ${result['price']:.2f}",
        }

    except Exception as e:
        return {
            "test": "Basic Functionality",
            "status": f"❌ Failed: {str(e)}",
            "success": False,
            "details": "Could not fetch basic stock data. Check internet connection.",
        }


async def check_advanced_features() -> List[Dict[str, Any]]:
    """Test advanced TVKit features."""
    results = []

    # Test 1: Quick start functions
    try:
        from tvkit import compare_stocks, POPULAR_STOCKS

        # Test with a small subset
        comparison = await compare_stocks(POPULAR_STOCKS[:2], days=5)

        if len(comparison) > 0:
            results.append(
                {
                    "test": "Stock Comparison",
                    "status": "✅ Working",
                    "success": True,
                    "details": f"Successfully compared {len(comparison)} stocks",
                }
            )
        else:
            results.append(
                {
                    "test": "Stock Comparison",
                    "status": "⚠️  Empty result",
                    "success": False,
                    "details": "Function ran but returned no data",
                }
            )

    except Exception as e:
        results.append(
            {
                "test": "Stock Comparison",
                "status": f"❌ Failed: {str(e)}",
                "success": False,
                "details": "Could not perform stock comparison",
            }
        )

    # Test 2: Export functionality
    try:
        from tvkit import DataExporter, get_historical_data

        # Get some test data
        test_data = await get_historical_data("NASDAQ:AAPL", 5)

        if test_data:
            exporter = DataExporter()
            await exporter.to_polars(test_data)

            results.append(
                {
                    "test": "Data Export",
                    "status": "✅ Working",
                    "success": True,
                    "details": f"Successfully exported {len(test_data)} bars to Polars DataFrame",
                }
            )
        else:
            results.append(
                {
                    "test": "Data Export",
                    "status": "⚠️  No data",
                    "success": False,
                    "details": "Could not get test data for export",
                }
            )

    except Exception as e:
        results.append(
            {
                "test": "Data Export",
                "status": f"❌ Failed: {str(e)}",
                "success": False,
                "details": "Export functionality not working",
            }
        )

    return results


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'=' * 50}")
    print(f"🔍 {title}")
    print("=" * 50)


def print_result(result: Dict[str, Any]):
    """Print a test result."""
    print(f"{result['status']} {result['test']}")
    if "details" in result:
        print(f"   {result['details']}")


async def main():
    """Run all verification tests."""
    print("🚀 TVKit Installation Verification")
    print("Testing your TVKit installation...")

    all_passed = True

    # Test 1: Python Version
    print_section("Python Version Check")
    python_result = check_python_version()
    print_result(python_result)
    if not python_result["compatible"]:
        all_passed = False

    # Test 2: Package Imports
    print_section("Package Import Tests")
    import_results = check_package_imports()

    core_packages = ["tvkit", "pydantic", "websockets", "httpx", "polars"]

    for result in import_results:
        print_result(result)
        # Only mark as failed if it's a core package
        package_name = result["test"].replace("Import ", "")
        if not result["success"] and package_name in core_packages:
            all_passed = False

    # Test 3: Basic Functionality
    print_section("Basic Functionality Test")
    basic_result = await check_basic_functionality()
    print_result(basic_result)
    if not basic_result["success"]:
        all_passed = False

    # Test 4: Advanced Features
    print_section("Advanced Features Test")
    advanced_results = await check_advanced_features()
    for result in advanced_results:
        print_result(result)
        # Advanced features are optional, so don't fail overall test

    # Final Summary
    print_section("Final Results")

    if all_passed:
        print("🎉 All core tests passed! TVKit is properly installed and working.")
        print()
        print("📚 Next Steps:")
        print("   • Try the quick tutorial: uv run python examples/quick_tutorial.py")
        print("   • Use the CLI: python -m tvkit price NASDAQ:AAPL")
        print(
            "   • Explore examples: uv run python examples/historical_and_realtime_data.py"
        )
    else:
        print("⚠️  Some tests failed. TVKit may not work correctly.")
        print()
        print("🔧 Troubleshooting:")
        print("   • Update Python to 3.11+ if needed")
        print("   • Reinstall TVKit: pip install --upgrade tvkit")
        print("   • Check internet connection")
        print("   • Try: uv add tvkit (if using uv)")

    print()
    print("📞 Need help? Visit: https://github.com/lumduan/tvkit/issues")


if __name__ == "__main__":
    asyncio.run(main())
