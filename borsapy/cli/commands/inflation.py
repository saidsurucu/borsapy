"""
Inflation command - TCMB inflation data and calculator.
"""

from typing import Annotated, Literal

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import console, format_number, handle_error

InflationType = Literal["tufe", "ufe"]


def inflation(
    amount: Annotated[
        float | None,
        typer.Argument(help="Amount to calculate (TRY)"),
    ] = None,
    start: Annotated[
        str | None,
        typer.Option("--start", "-s", help="Start date (YYYY-MM) for calculation"),
    ] = None,
    end: Annotated[
        str | None,
        typer.Option("--end", "-e", help="End date (YYYY-MM) for calculation"),
    ] = None,
    history: Annotated[
        bool,
        typer.Option("--history", "-h", help="Show inflation history"),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Limit history rows"),
    ] = 12,
    inflation_type: Annotated[
        InflationType,
        typer.Option("--type", "-t", help="Inflation type (tufe=CPI, ufe=PPI)"),
    ] = "tufe",
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get inflation data or calculate inflation-adjusted values.

    Examples:
        borsapy inflation                              # Latest TUFE/UFE
        borsapy inflation 100000 -s 2020-01 -e 2024-01 # Calculate
        borsapy inflation --history                    # Last 12 months
        borsapy inflation --history -l 24              # Last 24 months
        borsapy inflation --history --type ufe         # UFE history
    """
    from rich.panel import Panel
    from rich.table import Table

    import borsapy as bp

    with console.status("[bold green]Fetching inflation data..."):
        try:
            inf = bp.Inflation()

            # Mode 1: Calculate inflation
            if amount is not None and start and end:
                result = inf.calculate(amount, start, end)

                if output == "json":
                    output_json(result)
                else:
                    initial = result.get("initial_value", amount)
                    final = result.get("final_value", 0)
                    total_change = result.get("total_change", 0)
                    years = result.get("total_years", 0)
                    months = result.get("total_months", 0)
                    avg_yearly = result.get("avg_yearly_inflation", 0)

                    lines = [
                        f"[bold]Start Date:[/bold] {result.get('start_date', start)}",
                        f"[bold]End Date:[/bold] {result.get('end_date', end)}",
                        "",
                        f"[bold]Initial Value:[/bold] {format_number(initial, 0)} TL",
                        f"[bold]Final Value:[/bold] [green]{format_number(final, 0)} TL[/green]",
                        "",
                        f"[bold]Total Change:[/bold] [yellow]+{format_number(total_change)}%[/yellow]",
                        f"[bold]Duration:[/bold] {years} years, {months % 12} months",
                        f"[bold]Avg Yearly:[/bold] {format_number(avg_yearly)}%",
                    ]
                    console.print(
                        Panel(
                            "\n".join(lines),
                            title="Inflation Calculator",
                            border_style="cyan",
                        )
                    )
                return

            # Mode 2: Show history
            if history:
                if inflation_type.lower() == "ufe":
                    df = inf.ufe(limit=limit)
                else:
                    df = inf.tufe(limit=limit)

                if df is None or df.empty:
                    console.print("[yellow]No inflation data found[/yellow]")
                    raise typer.Exit(0)

                if output == "json":
                    output_json(df.reset_index().to_dict(orient="records"))
                elif output == "csv":
                    output_csv(df.reset_index())
                else:
                    title = (
                        "TÜFE (CPI) History"
                        if inflation_type.lower() == "tufe"
                        else "ÜFE (PPI) History"
                    )
                    table = Table(
                        title=title, show_header=True, header_style="bold cyan"
                    )
                    table.add_column("Date", style="bold")
                    table.add_column("Month", justify="center")
                    table.add_column("Yearly", justify="right")
                    table.add_column("Monthly", justify="right")

                    for idx, row in df.iterrows():
                        date_str = (
                            idx.strftime("%Y-%m-%d")
                            if hasattr(idx, "strftime")
                            else str(idx)
                        )
                        yearly = row.get("YearlyInflation", row.get("yearly_inflation"))
                        monthly = row.get(
                            "MonthlyInflation", row.get("monthly_inflation")
                        )
                        year_month = row.get("YearMonth", row.get("year_month", "-"))

                        table.add_row(
                            date_str,
                            str(year_month),
                            f"[yellow]{format_number(yearly)}%[/yellow]",
                            f"{format_number(monthly)}%",
                        )

                    output_table(table)
                return

            # Mode 3: Show latest (default)
            tufe = inf.latest("tufe")
            ufe = inf.latest("ufe")

        except Exception as e:
            handle_error(e)
            raise typer.Exit(1) from None

    # Output latest
    if output == "json":
        output_json({"tufe": tufe, "ufe": ufe})
    else:
        lines = [
            "[bold cyan]TÜFE (CPI) - Consumer Price Index[/bold cyan]",
            f"  Date: {tufe.get('year_month', tufe.get('date', '-'))}",
            f"  Yearly: [yellow]{format_number(tufe.get('yearly_inflation'))}%[/yellow]",
            f"  Monthly: {format_number(tufe.get('monthly_inflation'))}%",
            "",
            "[bold cyan]ÜFE (PPI) - Producer Price Index[/bold cyan]",
            f"  Date: {ufe.get('year_month', ufe.get('date', '-'))}",
            f"  Yearly: [yellow]{format_number(ufe.get('yearly_inflation'))}%[/yellow]",
            f"  Monthly: {format_number(ufe.get('monthly_inflation'))}%",
        ]
        console.print(
            Panel("\n".join(lines), title="Latest Inflation Rates", border_style="cyan")
        )
