"""
Entry point fortumblr-archiver CLI application.

This module provides the main entry point when running the package as a module:
    python -m tumblr_archiver
"""

import asyncio
import sys

import click

from .cli import cli as cli_command
from .commands import run_archive


def main() -> None:
    """Entry point for the CLI."""
    try:
        # Invoke the CLI command directly - Click handles --help, --version, etc.
        # The cli_command returns a config object when successful
        result = cli_command(standalone_mode=False)
        
        # If result is None or an int (exit code), it means Click handled it (--help, --version)
        if result is None or isinstance(result, int):
            sys.exit(0 if result is None else result)
        
        # Otherwise, we have a valid config object - run the archive operation
        try:
            exit_code = asyncio.run(run_archive(result))
            sys.exit(exit_code)
        except KeyboardInterrupt:
            click.echo("\n\nOperation cancelled by user.", err=True)
            sys.exit(130)
            
    except click.exceptions.Exit as e:
        # Click's explicit exit (from --help, --version, validation errors, etc.)
        sys.exit(e.exit_code)
    except click.exceptions.Abort:
        # User aborted (Ctrl+C during Click prompt)
        click.echo("\n\nAborted.", err=True)
        sys.exit(1)
    except SystemExit:
        # Re-raise SystemExit
        raise
    except Exception as e:
        # Unexpected error
        click.echo(f"Unexpected error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

