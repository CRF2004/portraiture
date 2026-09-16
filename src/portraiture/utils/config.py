from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


def parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None", "~"}:
        return None
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value.strip("'\"")


def parse_simple_yaml(text: str) -> dict[str, Any]:
    lines = []
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        lines.append((indent, raw_line.strip()))

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines):
            return {}, index

        is_list = lines[index][1].startswith("- ")
        container: Any = [] if is_list else {}

        while index < len(lines):
            current_indent, content = lines[index]
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ValueError(f"Invalid indentation near line: {content}")

            if is_list:
                if not content.startswith("- "):
                    break
                container.append(parse_scalar(content[2:].strip()))
                index += 1
                continue

            if content.startswith("- "):
                raise ValueError(f"Unexpected list item near line: {content}")

            key, _, value = content.partition(":")
            key = key.strip()
            value = value.strip()
            index += 1
            if value == "":
                if index >= len(lines) or lines[index][0] <= current_indent:
                    container[key] = {}
                else:
                    nested, index = parse_block(index, lines[index][0])
                    container[key] = nested
            else:
                container[key] = parse_scalar(value)

        return container, index

    parsed, _ = parse_block(0, lines[0][0] if lines else 0)
    if not isinstance(parsed, dict):
        raise ValueError("Top-level YAML config must be a mapping.")
    return parsed


def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text)
    return parse_simple_yaml(text)
