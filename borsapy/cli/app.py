"""
Main typer application for borsapy CLI.
"""

import typer

from borsapy.cli.commands import (
    auth,
    bonds,
    companies,
    compare,
    dividends,
    economic,
    eurobond,
    financials,
    fund,
    fx_rates,
    history,
    holders,
    index_cmd,
    inflation,
    news,
    price,
    quote,
    scan,
    screen,
    search,
    signals,
    splits,
    targets,
    tcmb,
    technical,
    viop,
    watch,
)

app = typer.Typer(
    name="borsapy",
    help="Turkish financial markets data CLI - BIST stocks, forex, crypto, and more.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        import borsapy

        typer.echo(f"borsapy {borsapy.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """
    borsapy - Turkish financial markets data CLI.

    Quick price lookup, historical data export, technical analysis, and more.
    """
    pass


# Register subcommands
app.add_typer(auth.app, name="auth")
app.command(name="price")(price.price)
app.command(name="quote")(quote.quote)
app.command(name="search")(search.search)
app.command(name="history")(history.history)
app.command(name="scan")(scan.scan)
app.command(name="screen")(screen.screen)
app.command(name="technical")(technical.technical)
app.command(name="compare")(compare.compare)
app.command(name="watch")(watch.watch)
app.command(name="economic")(economic.economic)

# New commands
app.command(name="news")(news.news)
app.command(name="dividends")(dividends.dividends)
app.command(name="splits")(splits.splits)
app.command(name="companies")(companies.companies)
app.command(name="bonds")(bonds.bonds)
app.command(name="tcmb")(tcmb.tcmb)
app.command(name="inflation")(inflation.inflation)
app.command(name="fund")(fund.fund)

# Batch 2 commands
app.command(name="eurobond")(eurobond.eurobond)
app.command(name="index")(index_cmd.index)
app.command(name="financials")(financials.financials)
app.command(name="signals")(signals.signals)
app.command(name="holders")(holders.holders)
app.command(name="targets")(targets.targets)
app.command(name="fx-rates")(fx_rates.fx_rates)
app.command(name="viop")(viop.viop)
