from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

_RICH_OUTPUT = False


def configure_output(rich_output: bool) -> None:
    global _RICH_OUTPUT
    _RICH_OUTPUT = bool(rich_output)


def emit(payload: Any, as_json: bool) -> None:
    if as_json:
        print(_to_json(payload))
    else:
        print(_to_text(payload))


def _to_json(payload: Any) -> str:
    return json.dumps(_normalize(payload), indent=2, sort_keys=True)


def _to_text(payload: Any) -> str:
    norm = _normalize(payload)
    if _RICH_OUTPUT:
        rich_text = _to_rich_text(norm)
        if rich_text is not None:
            return rich_text
    if isinstance(norm, dict):
        lines = []
        for key, value in norm.items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)
    return str(norm)


def _to_rich_text(payload: Any) -> str | None:
    try:
        from rich import box
        from rich.console import Console
        from rich.table import Table
    except Exception:
        return None

    console = Console(record=True, force_terminal=False, width=140)

    if isinstance(payload, dict):
        table = Table(title="Result", box=box.ASCII)
        table.add_column("Field")
        table.add_column("Value")
        for key, value in payload.items():
            table.add_row(str(key), _stringify_value(value))
        console.print(table)
        return console.export_text(clear=True).rstrip()

    if isinstance(payload, list) and payload and all(isinstance(item, dict) for item in payload):
        columns = sorted({k for row in payload for k in row.keys()})
        table = Table(title="Result Rows", box=box.ASCII)
        for col in columns:
            table.add_column(str(col))
        for row in payload:
            table.add_row(*[_stringify_value(row.get(col)) for col in columns])
        console.print(table)
        return console.export_text(clear=True).rstrip()

    return None


def _stringify_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return {k: _normalize(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    return value
