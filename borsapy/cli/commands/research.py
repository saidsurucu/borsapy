"""Run reproducible, source-linked BIST 100 value research."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from borsapy.exceptions import BorsapyError
from borsapy.value_research import run_value_research


def research(
    symbols: Annotated[
        str | None, typer.Option(help="Comma-separated current BIST 100 subset")
    ] = None,
    output_dir: Annotated[Path, typer.Option(help="Report and cache directory")] = Path(
        "output/research"
    ),
    workers: Annotated[int, typer.Option(min=1, max=4)] = 4,
    min_peers: Annotated[int, typer.Option(min=3)] = 3,
):
    """Compare sector peers with KAP-verified inflation bases; write HTML, CSV and JSON."""
    console = Console(stderr=True)

    def progress(done, total, symbol):
        console.print(f"[{done}/{total}] {symbol}", markup=False)

    try:
        result = run_value_research(
            symbols.split(",") if symbols else None,
            max_workers=workers,
            min_peers=min_peers,
            cache_dir=output_dir / "cache",
            progress=progress,
        )
        paths = result.save(output_dir)
    except (ValueError, RuntimeError, BorsapyError) as error:
        console.print(str(error), markup=False)
        raise typer.Exit(1) from error
    for kind, path in paths.items():
        console.print(f"{kind.upper()}: {path.resolve()}", markup=False)
