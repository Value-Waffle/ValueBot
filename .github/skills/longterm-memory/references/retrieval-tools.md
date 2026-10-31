# Retrieval Tools

All tools are called from `hippo.agents`.

| Tool | Purpose |
|---|---|
| `retrieve_knowledge(query, category, tags, match_all_tags=True, limit=10, offset=0)` | Two-stage pipeline: tag filter → FTS5 fallback. The main search. |
| `explore(query, category, tags, limit=5)` | Discover **untested** knowledge (`usefulness == 0`), newest first. |
| `get_knowledge_by_id(id)` | Fetch one item (increments access counters). |
| `get_knowledge_by_id_batch(ids)` | Bulk fetch without touching access counters. |
| `search_by_tags(tags, match_all=True, limit=50)` | AND/OR tag search (active items only). |
| `get_recent(limit=10, category="")` | Most recently created/updated active items. |
| `get_frequently_useful(limit=10, category="")` | Highest-usefulness active items. |
