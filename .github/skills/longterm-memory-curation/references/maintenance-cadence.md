# Maintenance Cadence

| Cadence | Trigger | Tasks |
|---|---|---|
| **Daily** | Session start | `get_maintenance_checklist()`; review unpromoted thoughts (promote worthy, discard noise); review new knowledge from the last 24h and adjust confidence if miscategorized. |
| **Weekly** | Dev agent running curation | `prune_stale_connections()`; review items with `confidence < 0.4` (verify, upgrade, or flag); tag hygiene — remove unused tags, suggest merges for near-duplicates. |
| **Monthly** | Dev agent running deep curation | Access audit — items not accessed in 90+ days → review → archive or reactivate; superseded-item cleanup; connection-graph health — weak edges → review or remove; `get_storage_stats()` → check DB size trend → evaluate compression if > 250 MB. |

## Connection Relation Types

| Type | Use When |
|---|---|
| `related_to` | Items share overlapping tags or concepts. |
| `contradicts` | Two items make conflicting claims. Resolve the tension explicitly. |
| `supports` | One item provides evidence for another. |
| `extends` | One item builds on another. |
| `example_of` | One item is a concrete instance of a more general item. |
| `superseded_by` | An old item is replaced by newer, correct knowledge. |

Edges are idempotent on the `(source, target, relation_type)` key.
