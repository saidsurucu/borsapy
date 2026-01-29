"""
Output formatters for borsapy CLI.
"""

import csv
import json
import sys
from typing import Any, Literal

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from borsapy.cli.utils import format_change, format_number, format_percent, get_change_color

console = Console()

OutputFormat = Literal["table", "json", "csv"]


def output_table(table: Table) -> None:
    """Output a rich table to console."""
    console.print(table)


def output_json(data: Any) -> None:
    """Output data as JSON."""
    if isinstance(data, pd.DataFrame):
        data = data.to_dict(orient="records")
    elif isinstance(data, pd.Series):
        data = data.to_dict()
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def output_csv(data: pd.DataFrame | list[dict]) -> None:
    """Output data as CSV to stdout."""
    if isinstance(data, pd.DataFrame):
        data.to_csv(sys.stdout, index=True)
    elif isinstance(data, list) and data:
        writer = csv.DictWriter(sys.stdout, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)


def create_price_table(quotes: list[dict]) -> Table:
    """Create a price table for multiple symbols."""
    table = Table(title="Price Summary", show_header=True, header_style="bold cyan")
    table.add_column("Symbol", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("Change %", justify="right")
    table.add_column("Volume", justify="right")

    for q in quotes:
        change = q.get("change")
        change_pct = q.get("change_percent")
        color = get_change_color(change)

        table.add_row(
            q.get("symbol", "-"),
            format_number(q.get("last")),
            f"[{color}]{format_change(change)}[/{color}]",
            f"[{color}]{format_percent(change_pct)}[/{color}]",
            format_number(q.get("volume"), 0),
        )

    return table


def create_quote_panel(info: dict) -> Panel:
    """Create a detailed quote panel for a single symbol."""
    symbol = info.get("symbol", "Unknown")
    name = info.get("name", info.get("shortName", ""))

    # Build content
    lines = []

    # Price section
    last = info.get("last", info.get("regularMarketPrice"))
    change = info.get("change")
    change_pct = info.get("change_percent", info.get("regularMarketChangePercent"))
    color = get_change_color(change)

    lines.append(f"[bold]Price:[/bold] {format_number(last)} TL")
    if change is not None:
        lines.append(f"[bold]Change:[/bold] [{color}]{format_change(change)}[/{color}]")
    if change_pct is not None:
        lines.append(f"[bold]Change %:[/bold] [{color}]{format_percent(change_pct)}[/{color}]")

    # OHLC
    lines.append("")
    lines.append(f"[bold]Open:[/bold] {format_number(info.get('open'))}")
    lines.append(f"[bold]High:[/bold] {format_number(info.get('high'))}")
    lines.append(f"[bold]Low:[/bold] {format_number(info.get('low'))}")
    lines.append(f"[bold]Prev Close:[/bold] {format_number(info.get('prev_close', info.get('previousClose')))}")

    # Volume
    lines.append("")
    lines.append(f"[bold]Volume:[/bold] {format_number(info.get('volume'), 0)}")
    if info.get("amount"):
        lines.append(f"[bold]Amount:[/bold] {format_number(info.get('amount'), 0)} TL")

    # Fundamentals (if available)
    market_cap = info.get("market_cap", info.get("marketCap"))
    pe = info.get("pe_ratio", info.get("trailingPE"))
    pb = info.get("price_to_book", info.get("priceToBook"))
    div_yield = info.get("dividend_yield", info.get("dividendYield"))

    if any([market_cap, pe, pb, div_yield]):
        lines.append("")
        lines.append("[bold cyan]Fundamentals[/bold cyan]")
        if market_cap:
            lines.append(f"[bold]Market Cap:[/bold] {format_number(market_cap / 1e9, 2)} B TL")
        if pe:
            lines.append(f"[bold]P/E:[/bold] {format_number(pe)}")
        if pb:
            lines.append(f"[bold]P/B:[/bold] {format_number(pb)}")
        if div_yield:
            lines.append(f"[bold]Div Yield:[/bold] {format_percent(div_yield * 100)}")

    # 52-week range
    high_52 = info.get("high_52_week", info.get("fiftyTwoWeekHigh"))
    low_52 = info.get("low_52_week", info.get("fiftyTwoWeekLow"))
    if high_52 or low_52:
        lines.append("")
        lines.append(f"[bold]52W High:[/bold] {format_number(high_52)}")
        lines.append(f"[bold]52W Low:[/bold] {format_number(low_52)}")

    content = "\n".join(lines)
    title = f"[bold]{symbol}[/bold]"
    if name:
        title += f" - {name}"

    return Panel(content, title=title, border_style="cyan")


def create_history_table(df: pd.DataFrame, symbol: str) -> Table:
    """Create a table for historical OHLCV data."""
    table = Table(title=f"{symbol} Historical Data", show_header=True, header_style="bold cyan")
    table.add_column("Date", style="bold")
    table.add_column("Open", justify="right")
    table.add_column("High", justify="right")
    table.add_column("Low", justify="right")
    table.add_column("Close", justify="right")
    table.add_column("Volume", justify="right")

    # Show last 10 rows
    for idx, row in df.tail(10).iterrows():
        date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
        table.add_row(
            date_str,
            format_number(row.get("Open")),
            format_number(row.get("High")),
            format_number(row.get("Low")),
            format_number(row.get("Close")),
            format_number(row.get("Volume"), 0),
        )

    return table


def create_search_table(results: list[dict]) -> Table:
    """Create a search results table."""
    table = Table(title="Search Results", show_header=True, header_style="bold cyan")
    table.add_column("Symbol", style="bold")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Exchange")

    for r in results[:20]:  # Limit to 20 results
        table.add_row(
            r.get("symbol", "-"),
            r.get("name", r.get("description", "-"))[:50],
            r.get("type", "-"),
            r.get("exchange", "-"),
        )

    return table


def create_scan_table(results: pd.DataFrame) -> Table:
    """Create a scan results table."""
    table = Table(title="Scan Results", show_header=True, header_style="bold cyan")
    table.add_column("Symbol", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("Change %", justify="right")
    table.add_column("RSI", justify="right")
    table.add_column("Volume", justify="right")

    for _, row in results.head(20).iterrows():
        # change field is already percent change from scanner API
        change_pct = row.get("change_percent", row.get("change"))
        color = get_change_color(change_pct)
        rsi_val = row.get("rsi", row.get("rsi_14"))

        table.add_row(
            str(row.get("symbol", row.name if hasattr(row, "name") else "-")),
            format_number(row.get("close", row.get("price"))),
            f"[{color}]{format_percent(change_pct)}[/{color}]",
            format_number(rsi_val, 1) if rsi_val is not None else "-",
            format_number(row.get("volume"), 0),
        )

    return table


def create_screen_table(results: pd.DataFrame) -> Table:
    """Create a screen results table."""
    table = Table(title="Screen Results", show_header=True, header_style="bold cyan")
    table.add_column("Symbol", style="bold")
    table.add_column("Name")

    # Dynamically add columns based on available data
    columns = results.columns.tolist()

    # Check for criteria columns (criteria_X format from screener)
    criteria_cols = [c for c in columns if c.startswith("criteria_")]
    has_price = "price" in columns or "close" in columns
    has_market_cap = "market_cap" in columns
    has_pe = "pe_ratio" in columns
    has_div = "dividend_yield" in columns

    if has_price:
        table.add_column("Price", justify="right")
    if has_market_cap:
        table.add_column("Market Cap", justify="right")
    if has_pe:
        table.add_column("P/E", justify="right")
    if has_div:
        table.add_column("Div Yield", justify="right")

    # Add criteria columns with friendly names
    for col in criteria_cols[:3]:  # Max 3 criteria columns
        table.add_column(col.replace("criteria_", "Crit "), justify="right")

    for _, row in results.head(20).iterrows():
        row_data = [
            str(row.get("symbol", row.name if hasattr(row, "name") else "-")),
            str(row.get("name", "-"))[:25],
        ]

        if has_price:
            row_data.append(format_number(row.get("price", row.get("close"))))
        if has_market_cap:
            market_cap = row.get("market_cap", 0)
            row_data.append(f"{market_cap / 1e9:.1f}B" if market_cap and market_cap > 0 else "-")
        if has_pe:
            row_data.append(format_number(row.get("pe_ratio"), 1) if row.get("pe_ratio") else "-")
        if has_div:
            div = row.get("dividend_yield")
            row_data.append(format_percent(div * 100) if div else "-")

        # Add criteria values
        for col in criteria_cols[:3]:
            val = row.get(col)
            row_data.append(format_number(val) if val is not None else "-")

        table.add_row(*row_data)

    return table


def create_technical_table(indicators: dict, symbol: str) -> Table:
    """Create a technical indicators table."""
    table = Table(title=f"{symbol} Technical Indicators", show_header=True, header_style="bold cyan")
    table.add_column("Indicator", style="bold")
    table.add_column("Value", justify="right")
    table.add_column("Signal")

    for name, value in indicators.items():
        if isinstance(value, dict):
            # MACD, Bollinger, Stochastic, etc.
            for subname, subval in value.items():
                table.add_row(
                    f"{name}.{subname}",
                    format_number(subval) if subval is not None else "-",
                    "",
                )
        else:
            # Simple indicators like RSI, SMA, EMA
            signal = ""
            if name.lower() == "rsi" or name.lower().startswith("rsi"):
                if value and value < 30:
                    signal = "[green]Oversold[/green]"
                elif value and value > 70:
                    signal = "[red]Overbought[/red]"
            table.add_row(
                name,
                format_number(value) if value is not None else "-",
                signal,
            )

    return table


def create_compare_table(tickers: list[dict]) -> Table:
    """Create a comparison table for multiple tickers."""
    table = Table(title="Comparison", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="bold")

    # Add symbol columns
    for t in tickers:
        table.add_column(t.get("symbol", "-"), justify="right")

    # Metrics to compare
    metrics = [
        ("Price", "last"),
        ("Change %", "change_percent"),
        ("Volume", "volume"),
        ("Market Cap", "market_cap"),
        ("P/E", "pe_ratio"),
        ("P/B", "price_to_book"),
        ("Div Yield", "dividend_yield"),
        ("52W High", "high_52_week"),
        ("52W Low", "low_52_week"),
    ]

    for metric_name, metric_key in metrics:
        row = [metric_name]
        for t in tickers:
            val = t.get(metric_key)
            if val is None:
                row.append("-")
            elif metric_key == "change_percent":
                color = get_change_color(val)
                row.append(f"[{color}]{format_percent(val)}[/{color}]")
            elif metric_key == "market_cap":
                row.append(f"{val / 1e9:.1f}B" if val else "-")
            elif metric_key == "dividend_yield":
                row.append(format_percent(val * 100) if val else "-")
            elif metric_key == "volume":
                row.append(format_number(val, 0))
            else:
                row.append(format_number(val))
        table.add_row(*row)

    return table


def create_economic_table(events: pd.DataFrame) -> Table:
    """Create an economic calendar table."""
    table = Table(title="Economic Calendar", show_header=True, header_style="bold cyan")
    table.add_column("Date", style="bold")
    table.add_column("Time")
    table.add_column("Country")
    table.add_column("Event")
    table.add_column("Imp", justify="center")
    table.add_column("Actual", justify="right")
    table.add_column("Forecast", justify="right")
    table.add_column("Previous", justify="right")

    # Helper to get value with case-insensitive column name
    def get_col(row, *names):
        for name in names:
            if name in row.index:
                return row[name]
            # Try lowercase
            if name.lower() in row.index:
                return row[name.lower()]
            # Try title case
            if name.title() in row.index:
                return row[name.title()]
        return "-"

    for _, row in events.head(30).iterrows():
        importance = str(get_col(row, "Importance", "importance")).lower()
        imp_display = ""
        if importance == "high":
            imp_display = "[red]!!![/red]"
        elif importance == "medium":
            imp_display = "[yellow]!![/yellow]"
        elif importance == "low":
            imp_display = "[dim]![/dim]"

        date_val = get_col(row, "Date", "date")
        date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val)

        event_text = str(get_col(row, "Event", "event"))
        if len(event_text) > 40:
            event_text = event_text[:37] + "..."

        table.add_row(
            date_str,
            str(get_col(row, "Time", "time")),
            str(get_col(row, "Country", "country")),
            event_text,
            imp_display,
            str(get_col(row, "Actual", "actual")),
            str(get_col(row, "Forecast", "forecast")),
            str(get_col(row, "Previous", "previous")),
        )

    return table
