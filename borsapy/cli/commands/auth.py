"""
Auth command - TradingView authentication.
"""

from typing import Annotated

import typer

from borsapy.cli.utils import console

app = typer.Typer(help="TradingView authentication for real-time data")


@app.command()
def login(
    username: Annotated[
        str | None,
        typer.Option("--username", "-u", help="TradingView username/email"),
    ] = None,
    password: Annotated[
        str | None,
        typer.Option("--password", "-p", help="TradingView password", hide_input=True),
    ] = None,
    session: Annotated[
        str | None,
        typer.Option("--session", "-s", help="Session cookie (alternative to username/password)"),
    ] = None,
    session_sign: Annotated[
        str | None,
        typer.Option("--session-sign", help="Session signature cookie"),
    ] = None,
) -> None:
    """
    Login to TradingView for real-time data access.

    Without authentication, data has ~15 minute delay.
    With TradingView Pro account, you get real-time data.

    Two authentication methods:
        1. Username/password: borsapy auth login -u email -p password
        2. Session cookies: borsapy auth login -s sessionid --session-sign signature

    To get session cookies:
        1. Login to tradingview.com in your browser
        2. Open Developer Tools (F12) → Application → Cookies
        3. Copy 'sessionid' and 'sessionid_sign' values

    Examples:
        borsapy auth login -u user@email.com -p mypassword
        borsapy auth login -s abc123... --session-sign xyz789...
    """
    import borsapy as bp

    try:
        if username and password:
            console.print("[bold]Logging in with username/password...[/bold]")
            bp.set_tradingview_auth(username=username, password=password)
            console.print("[green]Login successful![/green]")
        elif session:
            console.print("[bold]Setting session cookies...[/bold]")
            bp.set_tradingview_auth(session=session, session_sign=session_sign)
            console.print("[green]Session cookies set![/green]")
        else:
            # Prompt for credentials
            username = typer.prompt("TradingView username/email")
            password = typer.prompt("Password", hide_input=True)
            console.print("[bold]Logging in...[/bold]")
            bp.set_tradingview_auth(username=username, password=password)
            console.print("[green]Login successful![/green]")

        console.print("\n[dim]You now have access to real-time data.[/dim]")
        console.print("[dim]Session is valid for ~30 days.[/dim]")

    except Exception as e:
        console.print(f"[red]Login failed:[/red] {e}")
        raise typer.Exit(1) from None


@app.command()
def logout() -> None:
    """
    Logout from TradingView and clear credentials.

    Examples:
        borsapy auth logout
    """
    import borsapy as bp

    try:
        bp.clear_tradingview_auth()
        console.print("[green]Logged out successfully[/green]")
    except Exception as e:
        console.print(f"[red]Logout failed:[/red] {e}")
        raise typer.Exit(1) from None


@app.command()
def status() -> None:
    """
    Check TradingView authentication status.

    Examples:
        borsapy auth status
    """

    try:
        # Check if auth is configured by trying to access the internal state
        from borsapy._providers.tradingview import get_tradingview_provider

        provider = get_tradingview_provider()

        if provider._session_id:
            console.print("[green]Authenticated[/green]")
            console.print("[dim]Session ID is set. You have access to real-time data.[/dim]")
        else:
            console.print("[yellow]Not authenticated[/yellow]")
            console.print("[dim]Data will have ~15 minute delay.[/dim]")
            console.print("[dim]Use 'borsapy auth login' to authenticate.[/dim]")

    except Exception as e:
        console.print("[yellow]Not authenticated[/yellow]")
        console.print(f"[dim]{e}[/dim]")
