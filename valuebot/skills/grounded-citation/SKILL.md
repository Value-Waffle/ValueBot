---
name: grounded-citation
description: Mandatory citation protocol for valuebot — turn tool-issued citations into [n] markers, open sources through citation_view or citation_resolve, render the references footer, and drop any claim that has no tool-issued citation.
---

# Grounded citation protocol

Every factual or numeric claim must be traceable to tool output in this
conversation. Tools return a `citations[]` array. If a claim has no citation,
it does not appear in the answer.

Each citation in the tool response's `citations[]` array carries an `artifact`
block and a `citation_id`. **A citation is an identifier, not a link.** The
`references` array contains only `{n, label, source}` metadata for the model to
use when composing the footer; it does not carry a token. The footer is plain
text and carries **no url**: a citation never has one, so there is nothing to
print.

## Marker protocol

- Cite inline with `[n]`, numbered from 1 per answer, in order of first use.
- Reuse the same number for the same `key`.
- Place the marker immediately after the supported claim, before the period.
- Never place a marker on a sentence the source does not support.

## Opening a citation — `citation_resolve`

When `citation.artifact.status == "cached"`, open the source with
`citation_resolve` before writing the claim:

```
citation_resolve(citation_id="<the citation_id token>", offset=0, limit_chars=8000)
```

- Match the desired entry by its label in `references`, then pass either the
  full matching `citation` object from `citations[]` or that citation's
  `citation_id`. The token addresses cached evidence with no URL at all, so it
  works locally, in Docker and remotely.
- Passing the whole `citation` object is supported; passing its `citation_id`
  is also supported.
- Page with `offset` / `next_offset` until you have the passage you need.
- The response returns `chunk`, `format`, `kind`, `total_chars` and (for
  spreadsheets) `path` and `preview`.
- **Quote the returned chunk inline** as the evidence for the claim. The
  cached fact belongs in the answer, not behind a link.
- Never paraphrase a number you have not read in the resolved chunk.

When `citation.artifact.status == "not_cached"`, the raw material is not on
disk yet. Run the domain tool that builds it (`report_section`, `facts_query`,
`facts_export`, `ratio_compute`, `thesis_read`). State plainly that the source
is not cached; do not invent content.

## Inline evidence — `citation_view` (the evidence channel)

`citation_view` renders one cached artifact as an inline HTML panel. It is the
**only** evidence channel: it needs no browser-to-plugin network path, so it
works in every deployment. Because a citation never carries a url, opening a
source always means this tool or `citation_resolve`.

```
citation_view(citation={...}, offset=0, limit_chars=8000)
```

or:

```
citation_view(citation_id="<the citation_id token>", offset=0, limit_chars=8000)
```

Match the desired entry by its label in `references`, then pass either the
full matching `citation` object from `citations[]` or that citation's
`citation_id`.

**When to call it — all three must hold:**

1. the user asked to see the source, or the whole answer rests on one quoted
   passage, and
2. the entry has a `citation_id`, and
3. you have not already called it for that same `citation_id` in this answer.

**Hard limits — these prevent a loop:**

- **At most one `citation_view` call per citation, and at most three per
  answer.** Never call it for every footer entry.
- **Never call it twice for the same `citation_id`**, even if the panel looks
  incomplete. Page with `offset` only up to two times.
- **A miss is final.** If it returns `artifact_not_cached` or
  `citation_unresolvable`, do not retry and do not call it again: cite the
  entry as plain text and say the source is not cached.

The result carries a short text summary plus an embedded HTML resource. The
client renders it and tells you where to place its marker. Place the marker
once, on its own line, after the claim it supports. The model never receives or
writes a URL for this path.

Use `citation_resolve` when you only need text to quote; it is the text-quoting
tool, while `citation_view` is how a source is shown.

## Source types

| `source` | Meaning | `artifact.kind` | Identity fields |
|:---|:---|:---|:---|
| `sec-xbrl` | One XBRL fact | `facts-json`, `facts-txt`, `facts-xlsx` | accession, form, filed, period |
| `sec-statement` | Normalized statement period | `facts-json` | accession, form, filed, period |
| `sec-report` | Filing section or table (sec-parser) | `semantic-section`, `semantic-table`, `semantic-index`, `raw-html` | accession, form, filed, section |
| `derived-analysis` | Ratio, growth metric or DCF result | `derived-inputs` | `derived_from[]` |
| `thesis` | Local thesis vault | `vault-doc` | symbol, file |

Resolve evidence by `citation_id` or the `artifact` block. Never invent an
accession, form, filing date, section ID or URL.

## No URLs — ever

A citation never carries a url. The server does not mint one and the footer
contains none, so there is no link to print or markdown-format.

- **Never invent or print a URL for a citation; there is no link to print.**
  Not a SEC link, not a localhost link, not `#`, a relative path or an empty
  target, and nothing remembered from another conversation.
- **`original_url` is provenance metadata only**, never the citation link, and
  is never printed as one.
- Evidence is opened by `citation_id` with `citation_view` (inline panel) or
  `citation_resolve` (text to quote).
- **A fact citation has no outbound fallback.** The value came from cached
  companyfacts rows; quote them. Do not redirect the reader to sec.gov.
- If `meta.citation_coverage.dropped > 0`, the response contains facts the tool
  could not attribute: say so plainly and do not present those values.

## Artifact kinds

| `kind` | What `citation_resolve` returns |
|:---|:---|
| `semantic-section` | Filing section text, character-paged |
| `semantic-table` | One table rendered as a GFM grid |
| `semantic-index` | Section/note index for the filing (id, kind, title, size) |
| `raw-html` | Slice of the original filing HTML |
| `facts-json` | Raw XBRL concepts in SEC companyfacts shape |
| `facts-txt` | Raw XBRL concepts as tab-separated rows |
| `facts-xlsx` | Path to the exported workbook plus a text preview |
| `derived-inputs` | Inputs, assumptions, formula and quality behind a metric |
| `vault-doc` | Markdown from the local thesis vault |

## Derived values

A ratio or DCF value is not evidence by itself. Cite the underlying facts that
the tool returned in `inputs[]` or `assumptions[]`. For a `derived-analysis`
citation, open it with `citation_resolve` to inspect the inputs and formula
before presenting the number. If a metric has quality `unavailable`,
`not_meaningful`, `gap` or `partial`, do not present a number; state the
quality and reason.

## References footer

The tool response's `references` array is machine-readable metadata for the
model. Never reproduce the raw array. Never print a `citation_id`, a `ui://`
URI, a base64 token, or an artifact file path. Render only a readable markdown
list of attribution lines:

```markdown
---
**References**
1. MSFT 10-K FY2026, Item 7, table 8 — parsed filing table (cached).
2. MSFT stockholders' equity FY2025–FY2026 — cached XBRL rows.
```

Rules:

- **Exactly one footer per response.** Merge the `references` of every tool
  response the answer draws on into that single footer, then **renumber
  continuously from 1** in order of first use. Deduplicate entries that share
  the same evidence; keep one number for one piece of evidence.
- The footer's numbering must match the inline `[n]` markers.
- **The footer is plain text: no link, no url, no markdown link syntax.** A
  `citation_id`, `ui://` URI, base64 token, and artifact file path must never
  appear in the footer or answer text.
- Never invent an entry.

## Rejection rule — drop, never soften

If a claim has no tool-issued citation, drop it. Do not hedge with "roughly",
"approximately", "around" or "reportedly". Do not replace the number with a
qualitative statement. Prefer fewer grounded claims over a complete-looking
answer.

## Stop rule — never loop

A citation workflow is bounded. Obey these without exception:

- **One attempt per citation.** If `citation_resolve` or `citation_view`
  returns `artifact_not_cached`, `citation_unresolvable` or the same content
  you already received, stop. Do not retry the same call.
- **Two pages maximum** per artifact, then write the answer with what you have.
- **Three inline panels maximum** per answer, and never the same `citation_id`
  twice.
- **Never re-call a domain tool because a value came back `null`,
  `"uncited"` or `truncated: true`.** That is the server reporting a gap, not
  an invitation to retry. State the gap.
- If two consecutive tool calls return the same payload, stop calling tools
  and answer with the evidence you already hold.

## Banned behaviour

- Never invent citations, URLs, accessions, form types, filing dates or
  section names.
- Never print a `citation_id`, a `ui://` URI, a base64 token, or an artifact
  file path in the answer text.
- **Never invent or print a URL for a citation; there is no link to print.**
- Never use `[text](#)`, an empty link or a relative path as a citation target.
- Never claim a citation is clickable, and never reference a citation url or
  the artifact viewer in an answer.
- Never present an XLSX path that `facts_export` did not return.
- Never cite a tool you did not call in this conversation.
- Never present model memory, prior chats or web snippets as SEC evidence.
- Never compare a DCF value to market price in v1; the plugin has no price data.
