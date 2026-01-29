"""
FX Rates command - Bank and institution rates for currencies and metals.
"""

from typing import Annotated

import typer

from borsapy.cli.formatters import OutputFormat, output_csv, output_json, output_table
from borsapy.cli.utils import console, format_number, handle_error


def fx_rates(
    symbol: Annotated[
        str | None,
        typer.Argument(help="Currency (USD, EUR) or metal symbol (gram-altin, gram-gumus)"),
    ] = None,
    bank: Annotated[
        str | None,
        typer.Option("--bank", "-b", help="Filter by specific bank"),
    ] = None,
    institution: Annotated[
        str | None,
        typer.Option("--institution", "-i", help="Filter by specific institution (for metals)"),
    ] = None,
    list_banks: Annotated[
        bool,
        typer.Option("--banks", help="List supported banks"),
    ] = False,
    list_institutions: Annotated[
        bool,
        typer.Option("--institutions", help="List supported metal institutions"),
    ] = False,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format"),
    ] = "table",
) -> None:
    """
    Get bank and institution rates for currencies and metals.

    For currencies (USD, EUR, GBP, etc.): Shows buying/selling rates from 36+ banks.
    For metals (gram-altin, gram-gumus, etc.): Shows rates from banks and jewelers.

    Examples:
        borsapy fx-rates USD                      # All bank USD rates
        borsapy fx-rates EUR --bank akbank        # Akbank EUR rate
        borsapy fx-rates gram-altin               # Gold rates from all institutions
        borsapy fx-rates gram-gumus --institution kapalicarsi
        borsapy fx-rates --banks                  # List supported banks
        borsapy fx-rates --institutions           # List metal institutions
        borsapy fx-rates -o json
    """
    from rich.panel import Panel
    from rich.table import Table

    import borsapy as bp

    with console.status("[bold green]Fetching rate data..."):
        try:
            if list_banks:
                # List supported banks
                banks_list = bp.banks()

                if output == "json":
                    output_json(banks_list)
                elif output == "csv":
                    print("\n".join(banks_list))
                else:
                    table = Table(
                        title="Supported Banks (36+)",
                        show_header=True,
                        header_style="bold cyan",
                    )
                    table.add_column("Bank Code", style="bold")

                    for b in sorted(banks_list):
                        table.add_row(b)

                    output_table(table)
                    console.print(f"\n[dim]Total: {len(banks_list)} banks[/dim]")
                return

            if list_institutions:
                # List supported metal institutions
                institutions_list = bp.metal_institutions()

                if output == "json":
                    output_json(institutions_list)
                elif output == "csv":
                    print("\n".join(institutions_list))
                else:
                    table = Table(
                        title="Supported Metal Institutions",
                        show_header=True,
                        header_style="bold cyan",
                    )
                    table.add_column("Institution", style="bold")
                    table.add_column("Type")

                    # Categorize institutions
                    jewelers = ["kapalicarsi", "harem", "altinkaynak"]
                    for inst in sorted(institutions_list):
                        inst_type = "Jeweler" if inst.lower() in jewelers else "Bank"
                        table.add_row(inst, inst_type)

                    output_table(table)
                    console.print(f"\n[dim]Total: {len(institutions_list)} institutions[/dim]")
                    console.print(
                        "\n[dim]Supported assets: gram-altin, gram-gumus, ons-altin, "
                        "gram-platin, gram-paladyum[/dim]"
                    )
                return

            if not symbol:
                console.print(
                    "[yellow]Please provide a symbol or use --banks/--institutions[/yellow]"
                )
                console.print(
                    "\n[dim]Examples:\n"
                    "  borsapy fx-rates USD            # Currency bank rates\n"
                    "  borsapy fx-rates gram-altin     # Metal institution rates\n"
                    "  borsapy fx-rates --banks        # List banks\n"
                    "  borsapy fx-rates --institutions # List metal institutions[/dim]"
                )
                raise typer.Exit(1)

            # Determine if it's a metal or currency
            metal_symbols = {
                "gram-altin", "gram-gumus", "ons-altin",
                "gram-platin", "gram-paladyum"
            }
            is_metal = symbol.lower() in metal_symbols

            fx = bp.FX(symbol)

            if is_metal:
                # Metal institution rates
                if institution:
                    # Single institution
                    rate = fx.institution_rate(institution)

                    if not rate:
                        console.print(
                            f"[yellow]No rate found for {institution}[/yellow]"
                        )
                        raise typer.Exit(0)

                    if output == "json":
                        output_json(rate)
                    else:
                        buy = rate.get("buy", rate.get("bid"))
                        sell = rate.get("sell", rate.get("ask"))
                        spread = None
                        if buy and sell:
                            spread = ((sell - buy) / buy) * 100

                        content = (
                            f"[bold]Institution:[/bold] {institution}\n"
                            f"[bold]Asset:[/bold] {symbol}\n"
                            f"[bold]Buy:[/bold] {format_number(buy)} TL\n"
                            f"[bold]Sell:[/bold] {format_number(sell)} TL"
                        )
                        if spread:
                            content += f"\n[bold]Spread:[/bold] {format_number(spread)}%"

                        console.print(
                            Panel(content, title=f"{symbol} - {institution}", border_style="cyan")
                        )
                else:
                    # All institutions
                    df = fx.institution_rates

                    if df is None or df.empty:
                        console.print(
                            f"[yellow]No institution rates found for {symbol}[/yellow]"
                        )
                        raise typer.Exit(0)

                    if output == "json":
                        output_json(df)
                    elif output == "csv":
                        output_csv(df)
                    else:
                        table = Table(
                            title=f"{symbol.upper()} Institution Rates",
                            show_header=True,
                            header_style="bold cyan",
                        )
                        table.add_column("Institution", style="bold")
                        table.add_column("Buy", justify="right")
                        table.add_column("Sell", justify="right")
                        table.add_column("Spread", justify="right")

                        for _, row in df.iterrows():
                            inst = row.get("institution", row.get("institution_name", "-"))
                            buy = row.get("buy", row.get("bid"))
                            sell = row.get("sell", row.get("ask"))
                            spread = row.get("spread")

                            if spread is None and buy and sell:
                                spread = ((sell - buy) / buy) * 100

                            table.add_row(
                                str(inst),
                                f"{format_number(buy)} TL",
                                f"{format_number(sell)} TL",
                                f"{format_number(spread)}%" if spread else "-",
                            )

                        output_table(table)
                        console.print(f"\n[dim]Total: {len(df)} institutions[/dim]")

            else:
                # Currency bank rates
                if bank:
                    # Single bank
                    rate = fx.bank_rate(bank)

                    if not rate:
                        console.print(
                            f"[yellow]No rate found for {bank}[/yellow]"
                        )
                        raise typer.Exit(0)

                    if output == "json":
                        output_json(rate)
                    else:
                        buy = rate.get("buy", rate.get("bid"))
                        sell = rate.get("sell", rate.get("ask"))
                        spread = rate.get("spread")
                        if spread is None and buy and sell:
                            spread = ((sell - buy) / buy) * 100

                        content = (
                            f"[bold]Bank:[/bold] {rate.get('bank_name', bank)}\n"
                            f"[bold]Currency:[/bold] {symbol.upper()}\n"
                            f"[bold]Buy:[/bold] {format_number(buy)} TL\n"
                            f"[bold]Sell:[/bold] {format_number(sell)} TL"
                        )
                        if spread:
                            content += f"\n[bold]Spread:[/bold] {format_number(spread)}%"

                        console.print(
                            Panel(content, title=f"{symbol.upper()} - {bank}", border_style="cyan")
                        )
                else:
                    # All banks
                    df = fx.bank_rates

                    if df is None or df.empty:
                        console.print(
                            f"[yellow]No bank rates found for {symbol}[/yellow]"
                        )
                        raise typer.Exit(0)

                    if output == "json":
                        output_json(df)
                    elif output == "csv":
                        output_csv(df)
                    else:
                        table = Table(
                            title=f"{symbol.upper()} Bank Rates",
                            show_header=True,
                            header_style="bold cyan",
                        )
                        table.add_column("Bank", style="bold")
                        table.add_column("Name")
                        table.add_column("Buy", justify="right")
                        table.add_column("Sell", justify="right")
                        table.add_column("Spread", justify="right")

                        for _, row in df.iterrows():
                            bank_code = row.get("bank", "-")
                            bank_name = row.get("bank_name", "-")
                            buy = row.get("buy", row.get("bid"))
                            sell = row.get("sell", row.get("ask"))
                            spread = row.get("spread")

                            if spread is None and buy and sell:
                                spread = ((sell - buy) / buy) * 100

                            table.add_row(
                                str(bank_code),
                                str(bank_name)[:20],
                                f"{format_number(buy)}",
                                f"{format_number(sell)}",
                                f"{format_number(spread)}%" if spread else "-",
                            )

                        output_table(table)
                        console.print(f"\n[dim]Total: {len(df)} banks[/dim]")

        except Exception as e:
            handle_error(e, symbol if symbol else None)
            raise typer.Exit(1) from None
