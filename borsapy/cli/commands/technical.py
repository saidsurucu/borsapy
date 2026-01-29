"""
Technical command - Technical indicators display.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import OutputFormat, create_technical_table, output_json, output_table
from borsapy.cli.utils import AssetType, console, get_asset, handle_error, parse_period


def technical(
    symbol: Annotated[str, typer.Argument(help="Symbol to analyze")],
    indicators: Annotated[
        list[str] | None,
        typer.Option("--indicator", "-i", help="Indicators to show (can specify multiple)"),
    ] = None,
    period: Annotated[
        str,
        typer.Option("--period", "-p", help="Time period for calculation"),
    ] = "3mo",
    asset_type: Annotated[
        AssetType | None,
        typer.Option("--type", "-t", help="Asset type (auto-detected if not specified)"),
    ] = None,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Display technical indicators for a symbol.

    Available indicators:
        rsi         - Relative Strength Index (14)
        sma         - Simple Moving Average (20)
        ema         - Exponential Moving Average (12)
        macd        - MACD (12, 26, 9)
        bollinger   - Bollinger Bands (20, 2)
        stochastic  - Stochastic Oscillator (14, 3)
        atr         - Average True Range (14)
        adx         - Average Directional Index (14)
        obv         - On-Balance Volume
        vwap        - Volume Weighted Average Price
        supertrend  - Supertrend (10, 3)

    Examples:
        borsapy technical THYAO
        borsapy technical THYAO --indicator rsi --indicator macd
        borsapy technical THYAO --indicator bollinger --period 6mo
        borsapy technical USD --type fx
    """
    symbol = symbol.strip().upper()
    period = parse_period(period)

    # Default indicators if none specified
    if not indicators:
        indicators = ["rsi", "sma", "ema", "macd", "bollinger", "stochastic", "atr"]

    with console.status(f"[bold green]Calculating indicators for {symbol}..."):
        try:
            asset = get_asset(symbol, asset_type)

            # Calculate indicators
            indicator_values = {}

            for ind in indicators:
                ind_lower = ind.lower()
                try:
                    if ind_lower == "rsi":
                        indicator_values["RSI (14)"] = asset.rsi(period=period)
                    elif ind_lower == "sma":
                        indicator_values["SMA (20)"] = asset.sma(period=period, sma_period=20)
                    elif ind_lower == "ema":
                        indicator_values["EMA (12)"] = asset.ema(period=period, ema_period=12)
                    elif ind_lower == "macd":
                        macd = asset.macd(period=period)
                        indicator_values["MACD"] = macd
                    elif ind_lower == "bollinger":
                        bb = asset.bollinger_bands(period=period)
                        indicator_values["Bollinger Bands"] = bb
                    elif ind_lower == "stochastic":
                        stoch = asset.stochastic(period=period)
                        indicator_values["Stochastic"] = stoch
                    elif ind_lower == "atr":
                        indicator_values["ATR (14)"] = asset.atr(period=period)
                    elif ind_lower == "adx":
                        indicator_values["ADX (14)"] = asset.adx(period=period)
                    elif ind_lower == "obv":
                        indicator_values["OBV"] = asset.obv(period=period)
                    elif ind_lower == "vwap":
                        indicator_values["VWAP"] = asset.vwap(period=period)
                    elif ind_lower == "supertrend":
                        st = asset.supertrend(period=period)
                        indicator_values["Supertrend"] = st
                    else:
                        console.print(f"[yellow]Unknown indicator: {ind}[/yellow]")
                except Exception as e:
                    indicator_values[ind.upper()] = f"Error: {e}"

        except Exception as e:
            handle_error(e, symbol)
            raise typer.Exit(1) from None

    if not indicator_values:
        console.print("[yellow]No indicators calculated[/yellow]")
        raise typer.Exit(1) from None

    # Output
    if output == "json":
        output_json({"symbol": symbol, "indicators": indicator_values})
    else:
        output_table(create_technical_table(indicator_values, symbol))
