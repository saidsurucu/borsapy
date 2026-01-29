"""
TCMB command - Turkish Central Bank interest rates.
"""

from typing import Annotated, Literal

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import console, format_number, handle_error

TCMBRateType = Literal["policy", "overnight", "late_liquidity"]


def tcmb(
    rate_type: Annotated[
        TCMBRateType | None,
        typer.Option(
            "--type",
            "-t",
            help="Rate type",
        ),
    ] = None,
    history: Annotated[
        bool,
        typer.Option("--history", "-h", help="Show historical data"),
    ] = False,
    period: Annotated[
        str,
        typer.Option("--period", "-p", help="Period for history: 1y, 2y, 5y, max"),
    ] = "1y",
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get TCMB (Turkish Central Bank) interest rates.

    Examples:
        borsapy tcmb                        # Current rates
        borsapy tcmb --type overnight       # Overnight rates
        borsapy tcmb --history              # Policy rate history
        borsapy tcmb --history -t overnight # Overnight rate history
        borsapy tcmb -o json
    """
    from rich.panel import Panel
    from rich.table import Table

    import borsapy as bp

    with console.status("[bold green]Fetching TCMB rates..."):
        try:
            tcmb_obj = bp.TCMB()

            if history:
                # Show historical data
                rate_type = rate_type or "policy"
                df = tcmb_obj.history(rate_type=rate_type, period=period)

                if df is None or df.empty:
                    console.print(
                        f"[yellow]No history found for {rate_type}[/yellow]"
                    )
                    raise typer.Exit(0)

                if output == "json":
                    output_json(df.reset_index().to_dict(orient="records"))
                elif output == "csv":
                    output_csv(df.reset_index())
                else:
                    table = Table(
                        title=f"TCMB {rate_type.title()} Rate History",
                        show_header=True,
                        header_style="bold cyan",
                    )
                    table.add_column("Date", style="bold")
                    table.add_column("Borrowing", justify="right")
                    table.add_column("Lending", justify="right")

                    # Show last 20 entries
                    for idx, row in df.tail(20).iterrows():
                        date_str = (
                            idx.strftime("%Y-%m-%d")
                            if hasattr(idx, "strftime")
                            else str(idx)
                        )
                        borrowing = row.get("borrowing")
                        lending = row.get("lending")
                        table.add_row(
                            date_str,
                            f"{format_number(borrowing)}%" if borrowing else "-",
                            f"{format_number(lending)}%" if lending else "-",
                        )

                    output_table(table)

                    if len(df) > 20:
                        console.print(
                            f"[dim]Showing last 20 of {len(df)} entries. "
                            "Use -o csv for full history.[/dim]"
                        )
                return

            if rate_type:
                # Show specific rate type
                if rate_type == "policy":
                    rate = tcmb_obj.policy_rate
                    data = {"type": "policy", "lending": rate}
                elif rate_type == "overnight":
                    data = tcmb_obj.overnight
                    data["type"] = "overnight"
                else:  # late_liquidity
                    data = tcmb_obj.late_liquidity
                    data["type"] = "late_liquidity"

                if output == "json":
                    output_json(data)
                else:
                    lines = [f"[bold]Type:[/bold] {data.get('type', '-')}"]
                    if data.get("borrowing") is not None:
                        lines.append(
                            f"[bold]Borrowing:[/bold] {format_number(data['borrowing'])}%"
                        )
                    if data.get("lending") is not None:
                        lines.append(
                            f"[bold]Lending:[/bold] {format_number(data['lending'])}%"
                        )
                    console.print(
                        Panel(
                            "\n".join(lines),
                            title="TCMB Rate",
                            border_style="cyan",
                        )
                    )
                return

            # Show all current rates
            df = tcmb_obj.rates
            policy = tcmb_obj.policy_rate
            overnight = tcmb_obj.overnight
            late_liq = tcmb_obj.late_liquidity

        except Exception as e:
            handle_error(e)
            raise typer.Exit(1) from None

    # Output all rates
    if output == "json":
        output_json({
            "policy_rate": policy,
            "overnight": overnight,
            "late_liquidity": late_liq,
        })
    elif output == "csv":
        output_csv(df)
    else:
        # Create a nice panel showing all rates
        lines = [
            f"[bold cyan]Policy Rate (1-week repo):[/bold cyan] {format_number(policy)}%",
            "",
            "[bold cyan]Overnight Corridor:[/bold cyan]",
            f"  Borrowing: {format_number(overnight.get('borrowing'))}%",
            f"  Lending: {format_number(overnight.get('lending'))}%",
            "",
            "[bold cyan]Late Liquidity Window:[/bold cyan]",
            f"  Borrowing: {format_number(late_liq.get('borrowing'))}%",
            f"  Lending: {format_number(late_liq.get('lending'))}%",
        ]
        console.print(
            Panel(
                "\n".join(lines),
                title="TCMB Interest Rates",
                border_style="cyan",
            )
        )
