"""
Signals command - TradingView technical analysis signals.
"""

from typing import Annotated, Literal

import typer

from borsapy.cli.formatters import OutputFormat, output_json, output_table
from borsapy.cli.utils import AssetType, console, get_asset, handle_error

SignalInterval = Literal["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1W", "1M"]


def signals(
    symbol: Annotated[str, typer.Argument(help="Symbol to analyze")],
    interval: Annotated[
        SignalInterval,
        typer.Option("--interval", "-i", help="Timeframe for signals"),
    ] = "1d",
    all_timeframes: Annotated[
        bool,
        typer.Option("--all", "-a", help="Show signals for all timeframes"),
    ] = False,
    detail: Annotated[
        bool,
        typer.Option("--detail", "-d", help="Show oscillator and MA details"),
    ] = False,
    asset_type: Annotated[
        AssetType | None,
        typer.Option("--type", "-t", help="Asset type (auto-detected)"),
    ] = None,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get TradingView technical analysis signals.

    Shows BUY/SELL/NEUTRAL signals based on oscillators and moving averages.

    Supported timeframes: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1W, 1M

    Examples:
        borsapy signals THYAO                 # Daily signals
        borsapy signals THYAO --interval 1h   # Hourly signals
        borsapy signals THYAO --all           # All timeframes
        borsapy signals THYAO --detail        # Oscillator + MA details
        borsapy signals USD --type fx         # FX signals
        borsapy signals BTCTRY                # Crypto signals
        borsapy signals -o json
    """
    from rich.panel import Panel
    from rich.table import Table

    symbol = symbol.strip().upper()

    with console.status(f"[bold green]Fetching TA signals for {symbol}..."):
        try:
            asset = get_asset(symbol, asset_type)

            if all_timeframes:
                # Show all timeframes
                all_signals = asset.ta_signals_all_timeframes()

                if output == "json":
                    output_json(all_signals)
                else:
                    table = Table(
                        title=f"{symbol} TA Signals - All Timeframes",
                        show_header=True,
                        header_style="bold cyan",
                    )
                    table.add_column("Interval", style="bold")
                    table.add_column("Summary")
                    table.add_column("Buy", justify="right", style="green")
                    table.add_column("Sell", justify="right", style="red")
                    table.add_column("Neutral", justify="right")
                    table.add_column("Oscillators")
                    table.add_column("MAs")

                    timeframe_order = [
                        "1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1W", "1M"
                    ]

                    for tf in timeframe_order:
                        if tf not in all_signals:
                            continue

                        sig = all_signals[tf]
                        summary = sig.get("summary", {})
                        osc = sig.get("oscillators", {})
                        ma = sig.get("moving_averages", {})

                        rec = summary.get("recommendation", "-")
                        rec_color = _get_signal_color(rec)

                        osc_rec = osc.get("recommendation", "-")
                        osc_color = _get_signal_color(osc_rec)

                        ma_rec = ma.get("recommendation", "-")
                        ma_color = _get_signal_color(ma_rec)

                        table.add_row(
                            tf,
                            f"[{rec_color}]{rec}[/{rec_color}]",
                            str(summary.get("buy", 0)),
                            str(summary.get("sell", 0)),
                            str(summary.get("neutral", 0)),
                            f"[{osc_color}]{osc_rec}[/{osc_color}]",
                            f"[{ma_color}]{ma_rec}[/{ma_color}]",
                        )

                    output_table(table)
                return

            # Single interval
            sig = asset.ta_signals(interval=interval)

            if output == "json":
                output_json(sig)
            else:
                summary = sig.get("summary", {})
                osc = sig.get("oscillators", {})
                ma = sig.get("moving_averages", {})

                # Main summary
                rec = summary.get("recommendation", "-")
                rec_color = _get_signal_color(rec)
                buy = summary.get("buy", 0)
                sell = summary.get("sell", 0)
                neutral = summary.get("neutral", 0)

                content = (
                    f"[bold]Recommendation:[/bold] [{rec_color}][bold]{rec}[/bold][/{rec_color}]\n"
                    f"[bold]Buy:[/bold] [green]{buy}[/green]  "
                    f"[bold]Sell:[/bold] [red]{sell}[/red]  "
                    f"[bold]Neutral:[/bold] {neutral}\n\n"
                )

                # Oscillators summary
                osc_rec = osc.get("recommendation", "-")
                osc_color = _get_signal_color(osc_rec)
                content += (
                    f"[bold cyan]Oscillators:[/bold cyan] [{osc_color}]{osc_rec}[/{osc_color}] "
                    f"(Buy: {osc.get('buy', 0)}, Sell: {osc.get('sell', 0)}, Neutral: {osc.get('neutral', 0)})\n"
                )

                # Moving Averages summary
                ma_rec = ma.get("recommendation", "-")
                ma_color = _get_signal_color(ma_rec)
                content += (
                    f"[bold cyan]Moving Averages:[/bold cyan] [{ma_color}]{ma_rec}[/{ma_color}] "
                    f"(Buy: {ma.get('buy', 0)}, Sell: {ma.get('sell', 0)}, Neutral: {ma.get('neutral', 0)})"
                )

                console.print(
                    Panel(
                        content,
                        title=f"{symbol} TA Signals ({interval})",
                        border_style="cyan",
                    )
                )

                if detail:
                    # Oscillator details
                    osc_compute = osc.get("compute", {})
                    osc_values = osc.get("values", {})

                    if osc_compute:
                        table = Table(
                            title="Oscillator Signals",
                            show_header=True,
                            header_style="bold cyan",
                        )
                        table.add_column("Indicator", style="bold")
                        table.add_column("Signal")
                        table.add_column("Value", justify="right")

                        for ind, signal in osc_compute.items():
                            sig_color = _get_signal_color(signal)
                            # Try to find corresponding value
                            val_key = ind if ind in osc_values else f"{ind}.macd"
                            val = osc_values.get(val_key, osc_values.get(ind))
                            val_str = f"{val:.2f}" if isinstance(val, (int, float)) else "-"

                            table.add_row(
                                ind,
                                f"[{sig_color}]{signal}[/{sig_color}]",
                                val_str,
                            )

                        output_table(table)

                    # MA details
                    ma_compute = ma.get("compute", {})
                    ma_values = ma.get("values", {})

                    if ma_compute:
                        table = Table(
                            title="Moving Average Signals",
                            show_header=True,
                            header_style="bold cyan",
                        )
                        table.add_column("Indicator", style="bold")
                        table.add_column("Signal")
                        table.add_column("Value", justify="right")

                        for ind, signal in ma_compute.items():
                            sig_color = _get_signal_color(signal)
                            val = ma_values.get(ind)
                            val_str = f"{val:.2f}" if isinstance(val, (int, float)) else "-"

                            table.add_row(
                                ind,
                                f"[{sig_color}]{signal}[/{sig_color}]",
                                val_str,
                            )

                        output_table(table)

        except Exception as e:
            handle_error(e, symbol)
            raise typer.Exit(1) from None


def _get_signal_color(signal: str) -> str:
    """Get color for signal text."""
    signal_lower = signal.lower() if signal else ""
    if "buy" in signal_lower:
        return "green"
    elif "sell" in signal_lower:
        return "red"
    else:
        return "yellow"
