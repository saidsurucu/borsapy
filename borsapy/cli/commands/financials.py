"""
Financials command - Company financial statements (balance sheet, income, cashflow).
"""

from typing import Annotated, Literal

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import console, format_number, handle_error

FinancialType = Literal["balance", "income", "cashflow", "all"]
FinancialGroup = Literal["XI_29", "UFRS"]


def financials(
    symbol: Annotated[str, typer.Argument(help="Stock symbol (e.g., THYAO, AKBNK)")],
    balance: Annotated[
        bool,
        typer.Option("--balance", "-b", help="Show balance sheet"),
    ] = False,
    income: Annotated[
        bool,
        typer.Option("--income", "-i", help="Show income statement"),
    ] = False,
    cashflow: Annotated[
        bool,
        typer.Option("--cashflow", "-c", help="Show cash flow statement"),
    ] = False,
    quarterly: Annotated[
        bool,
        typer.Option("--quarterly", "-q", help="Show quarterly data instead of annual"),
    ] = False,
    ttm: Annotated[
        bool,
        typer.Option("--ttm", "-t", help="Show trailing 12 months (income/cashflow only)"),
    ] = False,
    group: Annotated[
        FinancialGroup | None,
        typer.Option("--group", "-g", help="Financial group: XI_29 (default) or UFRS (banks)"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Number of periods to show"),
    ] = 4,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get company financial statements.

    Shows balance sheet, income statement, and cash flow data from İş Yatırım.

    Financial groups:
        XI_29 - Standard format (default, for industrial companies)
        UFRS  - Bank format (use for banks like AKBNK, GARAN, ISCTR)

    Examples:
        borsapy financials THYAO                    # Summary (all statements)
        borsapy financials THYAO --balance          # Balance sheet
        borsapy financials THYAO --income           # Income statement
        borsapy financials THYAO --cashflow         # Cash flow statement
        borsapy financials THYAO --quarterly        # Quarterly data
        borsapy financials THYAO --ttm              # Trailing 12 months
        borsapy financials AKBNK --group UFRS      # Bank financials
        borsapy financials THYAO -b -q -n 8        # Last 8 quarterly balance sheets
        borsapy financials -o json
    """
    import borsapy as bp

    symbol = symbol.strip().upper()

    # If no specific statement requested, show all
    show_all = not any([balance, income, cashflow, ttm])

    with console.status(f"[bold green]Fetching financials for {symbol}..."):
        try:
            ticker = bp.Ticker(symbol)

            if ttm:
                # TTM data (income and cashflow only)
                ttm_income = ticker.get_ttm_income_stmt(financial_group=group)
                ttm_cashflow = ticker.get_ttm_cashflow(financial_group=group)

                if output == "json":
                    output_json({
                        "ttm_income_stmt": ttm_income.to_dict() if ttm_income is not None else None,
                        "ttm_cashflow": ttm_cashflow.to_dict() if ttm_cashflow is not None else None,
                    })
                elif output == "csv":
                    if ttm_income is not None:
                        console.print("[bold cyan]TTM Income Statement[/bold cyan]")
                        output_csv(ttm_income)
                    if ttm_cashflow is not None:
                        console.print("\n[bold cyan]TTM Cash Flow[/bold cyan]")
                        output_csv(ttm_cashflow)
                else:
                    if ttm_income is not None and not ttm_income.empty:
                        _print_financial_table(
                            ttm_income, f"{symbol} TTM Income Statement", limit
                        )
                    else:
                        console.print("[yellow]No TTM income data available[/yellow]")

                    if ttm_cashflow is not None and not ttm_cashflow.empty:
                        _print_financial_table(
                            ttm_cashflow, f"{symbol} TTM Cash Flow", limit
                        )
                    else:
                        console.print("[yellow]No TTM cashflow data available[/yellow]")
                return

            results = {}

            if balance or show_all:
                df = ticker.get_balance_sheet(quarterly=quarterly, financial_group=group)
                if df is not None and not df.empty:
                    results["balance_sheet"] = df

            if income or show_all:
                df = ticker.get_income_stmt(quarterly=quarterly, financial_group=group)
                if df is not None and not df.empty:
                    results["income_stmt"] = df

            if cashflow or show_all:
                df = ticker.get_cashflow(quarterly=quarterly, financial_group=group)
                if df is not None and not df.empty:
                    results["cashflow"] = df

            if not results:
                console.print(
                    f"[yellow]No financial data found for {symbol}[/yellow]"
                )
                console.print(
                    "[dim]Tip: For banks, try --group UFRS[/dim]"
                )
                raise typer.Exit(1)

        except Exception as e:
            handle_error(e, symbol)
            raise typer.Exit(1) from None

    # Output
    period_type = "Quarterly" if quarterly else "Annual"

    if output == "json":
        # Convert DataFrames to dicts
        json_out = {}
        for name, df in results.items():
            json_out[name] = df.to_dict()
        output_json(json_out)

    elif output == "csv":
        for name, df in results.items():
            console.print(f"\n[bold cyan]{name.replace('_', ' ').title()}[/bold cyan]")
            output_csv(df)

    else:
        # Rich table output
        for name, df in results.items():
            title = f"{symbol} {name.replace('_', ' ').title()} ({period_type})"
            if group:
                title += f" [{group}]"
            _print_financial_table(df, title, limit)


def _print_financial_table(df, title: str, limit: int) -> None:
    """Print a financial statement as a rich table."""
    from rich.table import Table

    table = Table(
        title=title,
        show_header=True,
        header_style="bold cyan",
    )

    # Get columns (periods) - limit to most recent
    columns = list(df.columns)[:limit]

    table.add_column("Item", style="bold", width=40)
    for col in columns:
        col_str = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
        table.add_column(col_str[:10], justify="right")

    # Add rows (limit to key items for readability)
    max_rows = 20  # Show at most 20 rows in table mode
    for i, (idx, row) in enumerate(df.iterrows()):
        if i >= max_rows:
            break

        row_data = [str(idx)[:40]]
        for col in columns:
            val = row.get(col)
            if val is None or (isinstance(val, float) and val != val):  # NaN check
                row_data.append("-")
            elif isinstance(val, (int, float)):
                # Format large numbers in millions
                if abs(val) >= 1e9:
                    row_data.append(f"{val / 1e9:.1f}B")
                elif abs(val) >= 1e6:
                    row_data.append(f"{val / 1e6:.1f}M")
                elif abs(val) >= 1e3:
                    row_data.append(f"{val / 1e3:.1f}K")
                else:
                    row_data.append(format_number(val))
            else:
                row_data.append(str(val))

        table.add_row(*row_data)

    output_table(table)

    if len(df) > max_rows:
        console.print(
            f"[dim]Showing {max_rows} of {len(df)} items. Use -o csv for full data.[/dim]"
        )
    console.print("")  # Spacing between tables
