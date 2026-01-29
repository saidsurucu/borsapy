"""
Main typer application for borsapy CLI.
"""

import typer

from borsapy.cli.commands import (
    auth,
    compare,
    economic,
    history,
    price,
    quote,
    scan,
    screen,
    search,
    technical,
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
