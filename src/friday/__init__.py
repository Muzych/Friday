"""Friday, a Bub-powered agent workspace."""

from __future__ import annotations


def main() -> None:
    """Run the Bub CLI with Friday's project plugin installed."""
    from bub.__main__ import app

    app()
