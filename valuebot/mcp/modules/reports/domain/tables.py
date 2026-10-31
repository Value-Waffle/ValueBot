"""Table grid extraction and GFM rendering.

sec-parser's ``table_to_markdown`` loses colspan structure, omits the GFM
delimiter row and mutates the parse tree. This module reads the table source
HTML first and builds a real grid.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

MAX_TABLE_CELLS = 5000
MAX_TABLE_COLS = 60
MAX_CELL_CHARS = 500
_WS = re.compile(r"\s+")


def _clean(value: str) -> str:
    text = str(value or "").replace("\u00a0", " ")
    text = _WS.sub(" ", text).strip()
    return text[:MAX_CELL_CHARS]


def extract_grid(html: str) -> tuple[list[list[str]], int]:
    """Return ``(grid, header_rows)`` from a table HTML fragment."""
    soup = BeautifulSoup(html or "", "lxml")
    table = soup.find("table")
    if table is None:
        return [], 1

    pending: dict[int, int] = {}
    raw_rows: list[list[str]] = []
    for row_tag in table.find_all("tr"):
        cells = row_tag.find_all(["td", "th"], recursive=False)
        if not cells and not pending:
            continue
        row: list[str] = []
        column = 0
        cell_iter = iter(cells)
        while True:
            if pending.get(column, 0) > 0:
                row.append("")
                pending[column] -= 1
                column += 1
                continue
            cell = next(cell_iter, None)
            if cell is None:
                break
            text = _clean(cell.get_text(" "))
            try:
                colspan = max(1, int(cell.get("colspan", 1)))
                rowspan = max(1, int(cell.get("rowspan", 1)))
            except (TypeError, ValueError):
                colspan, rowspan = 1, 1
            row.append(text)
            row.extend([""] * (colspan - 1))
            if rowspan > 1:
                for offset in range(colspan):
                    pending[column + offset] = max(
                        pending.get(column + offset, 0), rowspan - 1
                    )
            column += colspan
            if len(row) > MAX_TABLE_COLS:
                break
        trailing = max((key for key, value in pending.items() if value > 0), default=-1)
        while len(row) <= trailing:
            row.append("")
            if pending.get(len(row) - 1, 0) > 0:
                pending[len(row) - 1] -= 1
        raw_rows.append(row)

    if not raw_rows:
        return [], 1

    width = max(len(row) for row in raw_rows)
    grid = [row + [""] * (width - len(row)) for row in raw_rows]
    grid = _trim(grid)

    header_rows = 1
    for index, row in enumerate(grid[:3]):
        if any(_is_numeric(cell) for cell in row):
            header_rows = max(1, index)
            break
    return grid, min(header_rows, 3)


def _is_numeric(value: str) -> bool:
    text = str(value or "").strip().replace(",", "").replace("$", "").replace("%", "")
    text = text.strip("()")
    if not text or text in {"-", "—", "–"}:
        return False
    return bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text))


def _trim(grid: list[list[str]]) -> list[list[str]]:
    if not grid:
        return grid
    while grid and not any(cell for cell in grid[0]):
        grid.pop(0)
    while grid and not any(cell for cell in grid[-1]):
        grid.pop()
    if not grid:
        return grid
    width = len(grid[0])
    while width and not any(row[width - 1] for row in grid):
        width -= 1
    return [row[:width] for row in grid]


def render_markdown(
    grid: list[list[str]] | tuple[tuple[str, ...], ...],
    header_rows: int,
    *,
    columns: list[int] | None = None,
    row_offset: int = 0,
    max_rows: int = 40,
) -> str:
    rows = [list(row) for row in grid]
    if not rows:
        return ""
    width = len(rows[0])
    if columns:
        selected = [index for index in columns if 0 <= index < width]
    else:
        selected = list(range(width))
    if not selected:
        selected = list(range(width))

    header_rows = max(1, min(int(header_rows), len(rows)))
    offset = max(0, int(row_offset))
    limit = max(1, int(max_rows))

    header_block = rows[:header_rows]
    body = rows[header_rows:]
    sliced_body = body[offset : offset + limit]

    def line(values: list[str]) -> str:
        cells = []
        for index in selected:
            text = values[index] if index < len(values) else ""
            text = str(text).replace("\\", "\\\\").replace("|", "\\|")
            text = text.replace("\n", " ").replace("\r", " ")
            cells.append(text)
        return "| " + " | ".join(cells) + " |"

    output: list[str] = []
    for row in header_block:
        output.append(line(row))
    output.append("| " + " | ".join("---" for _ in selected) + " |")
    for row in sliced_body:
        output.append(line(row))
    if not sliced_body:
        output.append(line([""] * width))
    return "\n".join(output)


def caption_for(elements: list[dict], index: int) -> str:
    for position in range(index - 1, max(-1, index - 6), -1):
        element = elements[position]
        if element.get("type") in {"TitleElement", "TextElement", "SupplementaryText"}:
            text = _clean(element.get("text") or "")
            if text:
                return text[:160]
    return ""


def table_row_count(grid) -> int:
    return max(0, len(grid))
