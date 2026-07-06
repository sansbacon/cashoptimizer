from __future__ import annotations

from pathlib import Path

import click


class CLIValidationError(click.ClickException):
    exit_code = 2


class CLINoSolutionError(click.ClickException):
    exit_code = 3


def ensure_file_exists(path: Path) -> None:
    if not path.exists() or not path.is_file():
        raise CLIValidationError(f"File not found: {path}")


def ensure_positive_int(value: int, field_name: str) -> None:
    if value <= 0:
        raise CLIValidationError(f"{field_name} must be > 0")


def normalize_runtime_error(exc: Exception) -> click.ClickException:
    msg = str(exc)
    if "No feasible lineup found" in msg:
        return CLINoSolutionError(msg)
    if isinstance(exc, ValueError):
        return CLIValidationError(msg)
    return click.ClickException(msg)
