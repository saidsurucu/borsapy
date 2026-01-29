"""
Fund command - Mutual fund data from TEFAS.
"""

from typing import Annotated, Literal

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import console, format_number, format_percent, handle_error

FundType = Literal["YAT", "EMK"]


def fund(
    fund_code: Annotated[
        str | None,
        typer.Argument(help="TEFAS fund code (e.g., YAY, TTE, AAK)"),
    ] = None,
    allocation: Annotated[
        bool,
        typer.Option("--allocation", "-a", help="Show asset allocation"),
    ] = False,
    holdings: Annotated[
        bool,
        typer.Option("--holdings", help="Show portfolio holdings (requires --api-key)"),
    ] = False,
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", help="OpenRouter API key for holdings parsing"),
    ] = None,
    risk: Annotated[
        bool,
        typer.Option("--risk", "-r", help="Show risk metrics"),
    ] = False,
    screen: Annotated[
        bool,
        typer.Option("--screen", help="Screen funds by criteria"),
    ] = False,
    compare: Annotated[
        list[str] | None,
        typer.Option("--compare", "-c", help="Compare multiple funds"),
    ] = None,
    fund_type: Annotated[
        FundType,
        typer.Option("--type", "-t", help="Fund type for screening"),
    ] = "YAT",
    min_return_1y: Annotated[
        float | None,
        typer.Option("--min-return-1y", help="Minimum 1-year return for screening"),
    ] = None,
    min_return_ytd: Annotated[
        float | None,
        typer.Option("--min-return-ytd", help="Minimum YTD return for screening"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Limit results"),
    ] = 20,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get mutual fund data from TEFAS.

    Examples:
        borsapy fund YAY                    # Fund info
        borsapy fund YAY --allocation       # Asset allocation
        borsapy fund YAY --holdings --api-key sk-or-...  # Portfolio holdings
        borsapy fund YAY --risk             # Risk metrics
        borsapy fund --screen --type YAT --min-return-1y 50
        borsapy fund --compare YAY TTE AFO
    """
    from rich.panel import Panel
    from rich.table import Table

    import borsapy as bp

    # Mode 1: Compare multiple funds
    if compare:
        with console.status("[bold green]Comparing funds..."):
            try:
                result = bp.compare_funds(list(compare))
            except Exception as e:
                handle_error(e)
                raise typer.Exit(1) from None

        if output == "json":
            output_json(result)
        else:
            # Show comparison table
            funds = result.get("funds", [])
            if not funds:
                console.print("[yellow]No funds found[/yellow]")
                raise typer.Exit(0)

            table = Table(
                title="Fund Comparison", show_header=True, header_style="bold cyan"
            )
            table.add_column("Code", style="bold")
            table.add_column("Name")
            table.add_column("1Y Return", justify="right")
            table.add_column("YTD", justify="right")
            table.add_column("Size (M TL)", justify="right")
            table.add_column("Risk", justify="center")

            for f in funds:
                return_1y = f.get("return_1y")
                return_ytd = f.get("return_ytd")
                fund_size = f.get("fund_size", 0)
                name = str(f.get("name", "-"))
                if len(name) > 30:
                    name = name[:27] + "..."

                table.add_row(
                    str(f.get("fund_code", "-")),
                    name,
                    format_percent(return_1y) if return_1y else "-",
                    format_percent(return_ytd) if return_ytd else "-",
                    format_number(fund_size / 1e6, 0) if fund_size else "-",
                    str(f.get("risk_value", "-")),
                )

            output_table(table)

            # Show rankings
            rankings = result.get("rankings", {})
            if rankings:
                console.print("\n[bold]Rankings:[/bold]")
                if rankings.get("by_return_1y"):
                    console.print(
                        f"  By 1Y Return: {' > '.join(rankings['by_return_1y'])}"
                    )
                if rankings.get("by_size"):
                    console.print(f"  By Size: {' > '.join(rankings['by_size'])}")
        return

    # Mode 2: Screen funds
    if screen:
        with console.status("[bold green]Screening funds..."):
            try:
                df = bp.screen_funds(
                    fund_type=fund_type,
                    min_return_1y=min_return_1y,
                    min_return_ytd=min_return_ytd,
                    limit=limit,
                )
            except Exception as e:
                handle_error(e)
                raise typer.Exit(1) from None

        if df is None or df.empty:
            console.print("[yellow]No funds matching criteria[/yellow]")
            raise typer.Exit(0)

        if output == "json":
            output_json(df)
        elif output == "csv":
            output_csv(df)
        else:
            table = Table(
                title="Fund Screening Results",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Code", style="bold")
            table.add_column("Name")
            table.add_column("1Y Return", justify="right")
            table.add_column("YTD", justify="right")
            table.add_column("Type")

            for _, row in df.head(limit).iterrows():
                name = str(row.get("name", "-"))
                if len(name) > 35:
                    name = name[:32] + "..."
                return_1y = row.get("return_1y")
                return_ytd = row.get("return_ytd")

                table.add_row(
                    str(row.get("fund_code", "-")),
                    name,
                    format_percent(return_1y) if return_1y else "-",
                    format_percent(return_ytd) if return_ytd else "-",
                    str(row.get("fund_type", "-")),
                )

            output_table(table)
        return

    # Mode 3: Single fund info (requires fund_code)
    if not fund_code:
        console.print(
            "[red]Please provide a fund code or use --screen/--compare options[/red]"
        )
        raise typer.Exit(1)

    fund_code = fund_code.strip().upper()

    with console.status(f"[bold green]Fetching {fund_code}..."):
        try:
            fund_obj = bp.Fund(fund_code)

            if allocation:
                # Show allocation
                df = fund_obj.allocation
                if df is None or df.empty:
                    console.print(
                        f"[yellow]No allocation data for {fund_code}[/yellow]"
                    )
                    raise typer.Exit(0)

                if output == "json":
                    output_json(df)
                elif output == "csv":
                    output_csv(df)
                else:
                    table = Table(
                        title=f"{fund_code} Asset Allocation",
                        show_header=True,
                        header_style="bold cyan",
                    )
                    table.add_column("Asset Type")
                    table.add_column("Asset Name")
                    table.add_column("Weight", justify="right")

                    # Group by asset type and show latest
                    latest_date = df["Date"].max() if "Date" in df.columns else None
                    if latest_date is not None:
                        df = df[df["Date"] == latest_date]

                    for _, row in df.iterrows():
                        weight = row.get("weight")
                        table.add_row(
                            str(row.get("asset_type", "-")),
                            str(row.get("asset_name", "-")),
                            format_percent(weight) if weight else "-",
                        )

                    output_table(table)
                return

            if holdings:
                # Show portfolio holdings
                if not api_key:
                    console.print(
                        "[red]--api-key is required for holdings. "
                        "Get your free API key at https://openrouter.ai/[/red]"
                    )
                    raise typer.Exit(1)

                df = fund_obj.get_holdings(api_key=api_key)
                if df is None or df.empty:
                    console.print(
                        f"[yellow]No holdings data for {fund_code}[/yellow]"
                    )
                    raise typer.Exit(0)

                if output == "json":
                    output_json(df)
                elif output == "csv":
                    output_csv(df)
                else:
                    table = Table(
                        title=f"{fund_code} Portfolio Holdings",
                        show_header=True,
                        header_style="bold cyan",
                    )
                    table.add_column("Symbol", style="bold")
                    table.add_column("Name")
                    table.add_column("Weight", justify="right")
                    table.add_column("Type")
                    table.add_column("Country")

                    for _, row in df.head(30).iterrows():
                        name = str(row.get("name", "-"))
                        if len(name) > 30:
                            name = name[:27] + "..."
                        weight = row.get("weight")
                        table.add_row(
                            str(row.get("symbol", "-")),
                            name,
                            format_percent(weight) if weight else "-",
                            str(row.get("type", "-")),
                            str(row.get("country", "-")),
                        )

                    output_table(table)

                    if len(df) > 30:
                        console.print(
                            f"[dim]Showing 30 of {len(df)} holdings. "
                            "Use -o csv for full list.[/dim]"
                        )
                return

            if risk:
                # Show risk metrics
                metrics = fund_obj.risk_metrics(period="1y")

                if output == "json":
                    output_json(metrics)
                else:
                    lines = [
                        f"[bold]Annualized Return:[/bold] {format_percent(metrics.get('annualized_return'))}",
                        f"[bold]Annualized Volatility:[/bold] {format_percent(metrics.get('annualized_volatility'))}",
                        "",
                        f"[bold]Sharpe Ratio:[/bold] {format_number(metrics.get('sharpe_ratio'))}",
                        f"[bold]Sortino Ratio:[/bold] {format_number(metrics.get('sortino_ratio'))}",
                        f"[bold]Max Drawdown:[/bold] {format_percent(metrics.get('max_drawdown'))}",
                        "",
                        f"[bold]Risk-Free Rate:[/bold] {format_percent(metrics.get('risk_free_rate'))}",
                        f"[bold]Trading Days:[/bold] {metrics.get('trading_days', 0)}",
                    ]
                    console.print(
                        Panel(
                            "\n".join(lines),
                            title=f"{fund_code} Risk Metrics (1Y)",
                            border_style="cyan",
                        )
                    )
                return

            # Default: Show fund info
            info = fund_obj.info

        except Exception as e:
            handle_error(e, fund_code)
            raise typer.Exit(1) from None

    if output == "json":
        output_json(info)
    else:
        # Create info panel
        name = info.get("name", "-")
        price = info.get("price")
        fund_size = info.get("fund_size", 0)
        investors = info.get("investor_count", 0)
        risk_val = info.get("risk_value")

        lines = [
            f"[bold]Name:[/bold] {name}",
            f"[bold]Price:[/bold] {format_number(price, 4)} TL",
            f"[bold]Fund Size:[/bold] {format_number(fund_size / 1e6, 0)} M TL",
            f"[bold]Investors:[/bold] {format_number(investors, 0)}",
            f"[bold]Risk Level:[/bold] {risk_val}/7" if risk_val else "",
            "",
            "[bold cyan]Returns[/bold cyan]",
            f"  Daily: {format_percent(info.get('daily_return'))}",
            f"  1M: {format_percent(info.get('return_1m'))}",
            f"  3M: {format_percent(info.get('return_3m'))}",
            f"  6M: {format_percent(info.get('return_6m'))}",
            f"  YTD: {format_percent(info.get('return_ytd'))}",
            f"  1Y: [green]{format_percent(info.get('return_1y'))}[/green]",
        ]

        if info.get("return_3y"):
            lines.append(f"  3Y: {format_percent(info.get('return_3y'))}")
        if info.get("return_5y"):
            lines.append(f"  5Y: {format_percent(info.get('return_5y'))}")

        console.print(
            Panel(
                "\n".join([line for line in lines if line]),
                title=f"{fund_code} Fund Info",
                border_style="cyan",
            )
        )
