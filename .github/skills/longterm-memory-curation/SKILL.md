---
name: longterm-memory-curation
description: 'Maintain and curate the Hippo long-term memory store. Use when: running memory maintenance, reviewing the maintenance checklist, promoting thoughts, adjusting confidence, pruning stale connections, merging tags, archiving inactive items, grooming the knowledge DB.'
user-invocable: false
disable-model-invocation: false
---

# Long-Term Memory (Hippo) — Curation

## When to Use
- **Session start** — run the maintenance checklist and address top priorities
- **After storing new knowledge** — discover connections to existing items
- **Weekly maintenance** — prune stale connections, review low-confidence items, tag hygiene
- **Monthly deep curation** — archive inactive items, clean up superseded knowledge, check storage health
- **When knowledge is invalidated** — supersede old items instead of deleting them

## What It Does
Memory is not write-once. This skill covers maintenance: promoting thoughts, discovering connections, calibrating confidence, pruning staleness, and archiving inactive items — the actions that keep the store lean and trustworthy. Every maintenance action writes a `memory_event` row, so the history is auditable. Maintenance is agent-initiated, not automatic: any dev agent inspects the checklist and decides what to act on.

## Procedure

### Daily: Session Start
1. **Run the checklist** — call `get_maintenance_checklist()`. It returns counts for: `unpromoted_thoughts`, `stale_connections`, `low_confidence_items`, `unused_tags`, `inactive_items`.
2. **Review unpromoted thoughts** — call `list_unpromoted_thoughts()` (newest first). For each thought, decide: promote with `promote_thought(thought_id, category, confidence, tags)`, merge into an existing item with `update_knowledge(...)`, or discard.
3. **Review recent knowledge** — check items created in the last 24h. Adjust confidence if miscategorized.

### Weekly: Connection & Confidence Maintenance
1. **Prune stale connections** — call `prune_stale_connections(knowledge_id=None)`. Removes edges marked stale or touching inactive endpoints.
2. **Review low-confidence items** — call `get_stale_items(max_confidence=0.4)`. For each: verify and upgrade to `0.7+`, or downgrade if stored too optimistically. Use `update_knowledge(knowledge_id, confidence=...)`.
3. **Tag hygiene** — remove unused tags (linked to no knowledge). Merge near-duplicates with `merge_tags(tag_id_to_keep, tag_id_to_merge)`.
4. **Review weak connections** — call `get_weak_connections(min_strength=0.2, never_validated_only=True)`. Strengthen, validate, or prune each.

### Monthly: Deep Curation
1. **Archive inactive items** — call `get_stale_items(days_since_access=90)`. Review each: archive with `archive_inactive_items(before_date="YYYY-MM-DD")` or reactivate if still relevant.
2. **Clean up superseded items** — for each superseded item, verify the replacement is valid.
3. **Check storage health** — call `get_storage_stats()`. Evaluate compression if `db_file_size_mb` > 250 MB.

### On-Demand: Connection Discovery
1. **After storing new knowledge** — search for items with overlapping tags (`retrieve_knowledge` / `search_by_tags`) and create `related_to` edges.
2. **When you find contradictory information** — create a `contradicts` edge and resolve the tension explicitly.
3. **Create typed edges** — use `connect_knowledge(source_id, target_id, relation_type, strength=0.5, notes="")`. Supported types: `related_to`, `contradicts`, `supports`, `extends`, `example_of`, `superseded_by`. Edges are idempotent on the `(source, target, relation_type)` key.

### On-Demand: Superseding Invalid Knowledge
1. **Store the new, correct knowledge item.**
2. **Create a `superseded_by` edge** — `connect_knowledge(old_id, new_id, "superseded_by", strength=0.9)`.
3. **Optionally lower the old item's confidence** and add a note. Use `get_superseded_by(id)` to find valid replacements.

### On-Demand: Validating Connections
- Call `validate_connection(connection_id)` when a connection proves useful. It bumps `validation_count` and clears `is_stale`.

## Audit Trail
Every maintenance action (promote, connect, validate, prune, forget, mark_useful) appends a `memory_events` row. Trace knowledge changes with `get_memory_events(event_type=...)`. Nothing is deleted without a trace.

## References
- [Maintenance Cadence](./references/maintenance-cadence.md) — daily/weekly/monthly schedule and connection relation types
- [Storage Health](./references/storage-health.md) — `get_storage_stats()` metrics reference
