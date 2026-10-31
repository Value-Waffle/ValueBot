# Storage Health

`get_storage_stats()` reports:

| Metric | Description |
|---|---|
| `total_items` | All items in the database. |
| `active_items` | Items where `is_active = 1`. |
| `total_body_bytes_mb` | Sum of all body content sizes. |
| `db_file_size_mb` | SQLite file size on disk. |
| `wal_file_size_mb` | Write-Ahead Log file size. |
| `stale_connections_count` | Edges marked stale. |
| `unpromoted_thoughts_count` | Thoughts not yet promoted or discarded. |
| `avg_usefulness` | Average usefulness score across active items. |

Track the DB size trend monthly; evaluate compression if `db_file_size_mb` grows past ~250 MB.
