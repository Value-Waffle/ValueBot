"""Build the synthetic valuebot trees shared by the contract and E2E tests.

Everything is materialised under caller-provided temporary roots, so no test
touches the real ValueWaffle data tree. ``seed_tree`` is the small, realistic
ACME tree used by the end-to-end test; ``add_oversized_artifacts`` extends it
with deliberately large artefacts so the byte caps are genuinely exercised.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: Canonical ticker used by every test.
SYMBOL = "ACME"
CIK = "0000000001"

#: Accessions that exist in the seeded tree.
ACCN_10K = "0000000001-24-000001"
ACCN_10Q = "0000000001-24-000002"
#: Extra accessions that only ``add_oversized_artifacts`` creates.
BIG_TOC_ACCN = "0000000001-24-000099"
HUGE_SECTION_ACCN = "0000000001-24-000098"

#: First anchor in ``filing_sample.htm``.
ANCHOR = "item-7"


def _copy(name: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURES / name, destination)
    return destination


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def seed_tree(db_root: Path, theses_root: Path) -> dict[str, object]:
    """Create the small, realistic ACME tree used by the E2E test."""
    json_data = db_root / "debug" / "jsonData" / "acme"
    _copy("companyFacts_0000000001.json", json_data / "companyFacts_0000000001.json")
    _copy("submissions_0000000001.json", json_data / "submissions_0000000001.json")

    merged = db_root / "debug" / "merged" / "us" / "acme" / "annual" / "filings"
    _copy(
        "merged_sample.tables.filtered.md",
        merged
        / (
            "acme_10-K_2023-12-31_0000000001-24-000001_"
            "acme-20231231.tables.filtered.md"
        ),
    )

    leadership = db_root / "leadership-debug" / "acme"
    _copy(
        "def14a_filtered_tables.md",
        leadership / "000000000124000003_acme_def14a_htm_filtered_tables.md",
    )
    _copy(
        "def14a_raw_tables.md",
        leadership / "000000000124000003_acme_def14a_htm_raw_tables.md",
    )
    _copy(
        "def14a_aggregate_filtered_tables.md",
        leadership / "aggregate_filtered_tables.md",
    )
    _copy("leadership_person_view.json", leadership / "aggregate_person_view.json")
    _copy(
        "leadership_unique_persons.json",
        leadership / "aggregate_unique_persons.json",
    )
    _copy(
        "leadership_scores_report.json",
        leadership / "aggregate_scores_report.json",
    )
    gfp = leadership / "gfp"
    _copy("leadership_merged_board.json", gfp / "merged_board.json")
    _copy("leadership_merged_compensation.json", gfp / "merged_compensation.json")

    _copy("insider_summary.json", db_root / "insider" / "acme" / "summary.json")

    filing = db_root / "filing" / "us" / "ACME"
    _copy(
        "filing_sample.htm",
        filing / "10-K" / "2023-12-31_0000000001-24-000001_acme-20231231.htm",
    )
    _copy(
        "filing_sample.htm",
        filing / "10-Q" / "000000000124000005_acme-20240331.htm",
    )

    vault = theses_root / "ACME"
    _copy("thesis.md", vault / "thesis.md")
    _copy("thesis_attachment.md", vault / "attachments" / "meeting-notes.md")
    _copy(
        "thesis_annotations.json",
        vault / ".thesis" / "annotations" / "report.pdf.json",
    )

    return {
        "db": db_root,
        "theses": theses_root,
        "symbol": SYMBOL,
        "accn": ACCN_10K,
        "anchor": ANCHOR,
    }


# ---------------------------------------------------------------------------
# oversized artefacts (cap and paging tests)
# ---------------------------------------------------------------------------
def add_oversized_artifacts(db_root: Path, theses_root: Path) -> None:
    """Add artefacts large enough to force every response cap to truncate."""
    _add_wide_facts(db_root)
    _add_many_filings(db_root)
    _add_large_filings(db_root)
    _add_large_tables(db_root)
    _add_many_people(db_root)
    _add_many_insider_transactions(db_root)
    _add_many_symbols(db_root)
    _add_large_thesis(theses_root)
    _add_many_annotations(theses_root)


def _add_wide_facts(db_root: Path) -> None:
    path = db_root / "debug" / "jsonData" / "acme" / "companyFacts_0000000001.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for body in (payload.get("facts") or {}).get("us-gaap", {}).values():
        units = body.get("units") or {}
        for unit, entries in units.items():
            if not entries:
                continue
            units[unit] = [
                {
                    "start": f"{year}-01-01",
                    "end": f"{year}-12-31",
                    "val": 1000 + year - 2000,
                    "accn": f"0000000001-{year % 100:02d}-000001",
                    "fy": year,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": f"{year + 1}-02-15",
                }
                for year in range(2000, 2026)
            ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def _add_many_filings(db_root: Path, count: int = 160) -> None:
    path = db_root / "debug" / "jsonData" / "acme" / "submissions_0000000001.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    recent = payload["filings"]["recent"]
    for index in range(count):
        recent["accessionNumber"].append(f"0000000001-24-{1000 + index:06d}")
        recent["filingDate"].append(f"2024-{index % 12 + 1:02d}-15")
        recent["reportDate"].append(f"2023-{index % 12 + 1:02d}-28")
        recent["form"].append("10-K" if index % 2 else "10-Q")
        recent["primaryDocument"].append(f"acme-{1000 + index:06d}.htm")
    path.write_text(json.dumps(payload), encoding="utf-8")


def _add_large_filings(db_root: Path) -> None:
    filing = db_root / "filing" / "us" / "ACME" / "10-K"

    entries = "".join(
        (
            f'<div id="cap-{index}"></div>'
            f"<div>Item {index}. Capital Allocation Heading {index}</div>"
            f"<p>Paragraph {index} of the synthetic filing.</p>"
        )
        for index in range(300)
    )
    _write(
        filing / "2023-12-31_0000000001-24-000099_acme-20231299.htm",
        f"<html><body>{entries}</body></html>",
    )

    huge = " ".join(f"word{index}" for index in range(6000))
    _write(
        filing / "2023-12-31_0000000001-24-000098_acme-20231298.htm",
        (
            "<html><body><h2 id=\"huge\">Item 7. Management Discussion</h2>"
            f"<p>{huge}</p></body></html>"
        ),
    )


def _add_large_tables(db_root: Path, tables: int = 200) -> None:
    parts = ["# acme-20241231 — Tables", ""]
    for index in range(tables):
        parts.extend(
            [
                f"## Table {index}",
                "| Item | Fiscal 2024 | Fiscal 2023 |",
                "| --- | --- | --- |",
                f"| Revenue | {1000 + index} | {900 + index} |",
                "",
            ]
        )
    _write(
        db_root
        / "debug"
        / "merged"
        / "us"
        / "acme"
        / "annual"
        / "filings"
        / (
            "acme_10-K_2024-12-31_0000000001-24-000098_"
            "acme-20241231.tables.filtered.md"
        ),
        "\n".join(parts),
    )


def _add_many_people(db_root: Path, count: int = 80) -> None:
    leadership = db_root / "leadership-debug" / "acme"
    view = {}
    for index in range(count):
        key = f"person_{index:03d}"
        view[key] = {
            "person_key": key,
            "display_name": f"Person {index:03d}",
            "titles": ["Director"],
            "table_count": 1,
            "tables": [
                {
                    "table_index": index,
                    "table_id": index,
                    "heading": "Director Compensation",
                    "row_count": 1,
                    "rows": [
                        {
                            "Name": f"Person {index:03d}",
                            "Director Since": "2020",
                            "Independent": "yes",
                            "Committee": "Audit",
                        }
                    ],
                }
            ],
        }
    _write(leadership / "aggregate_person_view.json", json.dumps(view))
    _write(leadership / "aggregate_unique_persons.json", "[]")

    board = {
        "symbol": SYMBOL,
        "years": ["FY2024"],
        "merged_rows": [
            {
                "name": f"Director {index:03d}",
                "FY2024_role": "Director",
                "FY2024_age": str(40 + index % 30),
                "FY2024_director_since": "2015",
                "FY2024_independent": "yes",
                "FY2024_committees": "Audit",
            }
            for index in range(120)
        ],
    }
    _write(leadership / "gfp" / "merged_board.json", json.dumps(board))


def _add_many_insider_transactions(db_root: Path, count: int = 300) -> None:
    path = db_root / "insider" / "acme" / "summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["transactions"] = [
        {
            "date": f"2024-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
            "owner": f"Owner {index:03d}",
            "type": "Sale" if index % 2 else "Purchase",
            "shares": 100 + index,
            "price": 10.5,
            "value": (100 + index) * 10.5,
        }
        for index in range(count)
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def _add_many_symbols(db_root: Path, count: int = 80) -> None:
    for index in range(count):
        symbol = f"ZZ{index:04d}"
        name = f"{symbol} " + "Long Company Name " * 8
        _write(
            db_root
            / "debug"
            / "jsonData"
            / symbol
            / f"submissions_{CIK}.json",
            json.dumps({"cik": CIK, "name": name}),
        )


def _add_large_thesis(theses_root: Path) -> None:
    body = "\n\n".join(
        f"Paragraph {index}: the thesis body is intentionally long."
        for index in range(1200)
    )
    _write(
        theses_root / "ACME" / "thesis.md",
        f"---\nticker: {SYMBOL}\nconviction: 4\n---\n\n{body}\n",
    )


def _add_many_annotations(theses_root: Path, count: int = 200) -> None:
    items = [
        {
            "type": "highlight" if index % 2 else "note",
            "page": index,
            "text": f"Annotation {index}",
            "detail": "synthetic detail " * 3,
        }
        for index in range(count)
    ]
    _write(
        theses_root / "ACME" / ".thesis" / "annotations" / "big.json",
        json.dumps({"mtime": 1714600000, "annotations": items}),
    )
