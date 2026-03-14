# TODO

- [ ] Add collector status at the bottom of the sidebar
- [ ] Add license file and credit SmokePing (derivative work, not a cleanroom implementation)
- [ ] Update URL when zooming and unzooming so that users can link others to what they're seeing by copying the current URL
- [ ] Sample data generation for a demo site, with "targets" that have different properties (like low latency, or high variation/smoke, or maybe one that has occasional degradation alternating with good performance -- all optimized for humans to see what the data looks like and for visual testing, rather than for automated code tests)
- [ ] Drag-to-zoom always queries raw `ping_samples` regardless of window size — `render_graph_for_window` has no rollup path. For large zoom windows (e.g. a 2-week selection on a 1mo panel) this could be slow. Fix: auto-select `bucket_size` in `render_graph_for_window` based on `end_ts - start_ts` (e.g. >7d → "day", >6h → "hour") rather than only routing through rollups via `render_graph_for_target`.
---

## Adopted from netsmoke-claude-superpowers

The following three enhancements were recommended after a comparative code review of three netsmoke implementations. They improve storage efficiency, type safety, and user experience.

### 1. Rollup Aggregation Strategy

**Why**: The current implementation stores only raw ping samples. With 20 pings every 60 seconds, one target generates ~730,000 rows per year. For long time ranges (1mo, 1y), this means querying millions of rows to render a graph. The rollup strategy pre-aggregates data into hourly and daily buckets, making long-range graphs efficient while preserving full granularity for short-range graphs.

**How it works**:
- Short time ranges (3h, 2d) continue to use raw samples from `ping_samples`
- Long time ranges (1mo, 1y) use pre-aggregated data from a new `ping_rollups` table
- Rollups are computed incrementally after each probe round (not batch-processed)

#### 1.1 Database Schema Changes

Add a new table to `backend/netsmoke/db.py`:

```sql
CREATE TABLE IF NOT EXISTS ping_rollups (
    id           INTEGER PRIMARY KEY,
    target       TEXT NOT NULL,
    bucket_start INTEGER NOT NULL,      -- Unix timestamp of bucket start
    bucket_size  TEXT NOT NULL,         -- "hour" or "day"
    sorted_rtts  TEXT NOT NULL,         -- JSON array of RTT values, pre-sorted
    loss_count   INTEGER NOT NULL,      -- Number of lost packets in bucket
    total_count  INTEGER NOT NULL,      -- Total packets in bucket
    UNIQUE (target, bucket_start, bucket_size)
);

CREATE INDEX IF NOT EXISTS idx_ping_rollups_target_bucket
    ON ping_rollups (target, bucket_start, bucket_size);
```

#### 1.2 Rollup Update Function

Add to `db.py` a function that recomputes the rollup for a bucket after each probe:

```python
async def update_rollup(
    db: aiosqlite.Connection,
    target: str,
    probe_timestamp: int,
    bucket_size: str,  # "hour" or "day"
    pings: int,
) -> None:
    """Recompute and upsert rollup for the bucket containing probe_timestamp."""
    if bucket_size == "hour":
        duration = 3600
    elif bucket_size == "day":
        duration = 86400
    else:
        raise ValueError(f"Unknown bucket_size: {bucket_size!r}")

    bucket_start = (probe_timestamp // duration) * duration
    bucket_end = bucket_start + duration

    # Query all samples in this bucket
    rows = await query_samples(db, target, bucket_start, bucket_end - 1)

    all_rtts = [r[2] for r in rows]  # r[2] is rtt_ms
    total_count = len(all_rtts)
    loss_count = sum(1 for r in all_rtts if r is None)
    non_null = sorted(r for r in all_rtts if r is not None)
    count = len(non_null)

    if count < 2:
        sorted_rtts_json = "[]"
    elif count >= pings:
        # Sub-sample to exactly `pings` values at evenly-spaced positions
        # This preserves the distribution while bounding storage
        n = pings
        indices = [round(i * (count - 1) / (n - 1)) for i in range(n)]
        sampled = [non_null[idx] for idx in indices]
        sorted_rtts_json = json.dumps(sampled)
    else:
        sorted_rtts_json = json.dumps(non_null)

    await db.execute(
        """
        INSERT INTO ping_rollups
        (target, bucket_start, bucket_size, sorted_rtts, loss_count, total_count)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (target, bucket_start, bucket_size) DO UPDATE SET
            sorted_rtts = excluded.sorted_rtts,
            loss_count = excluded.loss_count,
            total_count = excluded.total_count
        """,
        (target, bucket_start, bucket_size, sorted_rtts_json, loss_count, total_count),
    )
    await db.commit()
```

Key details:
- `bucket_start` is floor-aligned to the bucket boundary (e.g., 14:00:00 for hour, 00:00:00 for day)
- Sub-sampling uses evenly-spaced indices: `[0, k, 2k, ..., count-1]` to preserve distribution percentiles
- `ON CONFLICT ... DO UPDATE` makes the operation idempotent and handles bucket recomputation as new probes arrive
- The JSON array is pre-sorted so the graph renderer doesn't need to sort

#### 1.3 Query Rollups Function

Add to `db.py`:

```python
async def query_rollups(
    db: aiosqlite.Connection,
    target: str,
    start: int,
    end: int,
    bucket_size: str,
) -> list[dict]:
    """Return rollup rows as dicts, ordered by bucket_start."""
    async with db.execute(
        """
        SELECT bucket_start, sorted_rtts, loss_count, total_count
        FROM ping_rollups
        WHERE target = ? AND bucket_start >= ? AND bucket_start <= ? AND bucket_size = ?
        ORDER BY bucket_start
        """,
        (target, start, end, bucket_size),
    ) as cursor:
        rows = await cursor.fetchall()

    return [
        {
            "bucket_start": r[0],
            "sorted_rtts": json.loads(r[1]),
            "loss_count": r[2],
            "total_count": r[3],
        }
        for r in rows
    ]
```

#### 1.4 Collector Integration

In `collector.py`, after calling `insert_samples()`, also update both rollups:

```python
await insert_samples(db, target_path, timestamp, rtts)
await update_rollup(db, target_path, timestamp, "hour", config.ping_count)
await update_rollup(db, target_path, timestamp, "day", config.ping_count)
```

This ensures rollups are always current. The recomputation is cheap because it only touches one bucket's worth of samples.

#### 1.5 Graph Rendering Changes

In `graph.py`, modify `render_graph_for_target` and `render_graph_for_window` to use rollups for long ranges:

```python
# Map time ranges to bucket sizes (None = use raw samples)
RANGE_BUCKET_SIZE = {
    "3h": None,
    "2d": None,
    "1mo": "hour",
    "1y": "day",
}
```

When rendering:
1. If `bucket_size is None`: use existing `query_samples()` logic
2. If `bucket_size is not None`: use `query_rollups()` and pass the pre-sorted RTTs directly to the smoke band calculation

The rollup dict already has `sorted_rtts`, `loss_count`, and `total_count`, which is exactly what the graph renderer needs. The data format should be adapted so `render_graph()` can accept either raw samples or rollup data.

#### 1.6 Migration for Existing Data

For users with existing data, provide a one-time backfill:

```python
async def backfill_rollups(db: aiosqlite.Connection, pings: int) -> None:
    """One-time backfill of rollups from existing ping_samples."""
    # Get all targets
    async with db.execute("SELECT DISTINCT target FROM ping_samples") as cursor:
        targets = [r[0] for r in await cursor.fetchall()]

    for target in targets:
        # Get time range
        async with db.execute(
            "SELECT MIN(time), MAX(time) FROM ping_samples WHERE target = ?",
            (target,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] is None:
                continue
            min_time, max_time = row

        # Backfill hourly rollups
        for bucket_size, duration in [("hour", 3600), ("day", 86400)]:
            bucket_start = (min_time // duration) * duration
            while bucket_start <= max_time:
                await update_rollup(db, target, bucket_start, bucket_size, pings)
                bucket_start += duration
```

Add a CLI flag or startup check to run this migration once.

---

### 2. Strict Config Validation at Startup

**Why**: The current config loader silently accepts invalid configurations that could cause runtime errors or confusing behavior. Strict validation at startup catches problems early with clear error messages.

#### 2.1 Validations to Add

In `config.py`, add these checks in `load_config()`:

1. **Duplicate target names** (across all folders):
   ```python
   seen_names: set[str] = set()
   # During parsing, check:
   if target.name in seen_names:
       sys.exit(f"ERROR: Duplicate target name: {target.name!r}")
   seen_names.add(target.name)
   ```

2. **Invalid characters in target names** (slashes break URL routing):
   ```python
   if "/" in name:
       sys.exit(f"ERROR: Target name contains '/': {name!r}")
   ```

3. **Settings bounds**:
   ```python
   if ping_interval < 10:
       sys.exit(f"ERROR: settings.ping_interval must be >= 10 (got {ping_interval})")
   if ping_count < 2:
       sys.exit(f"ERROR: settings.ping_count must be >= 2 (got {ping_count})")
   ```

4. **Config file errors** (wrap file loading):
   ```python
   try:
       with open(path) as f:
           data = yaml.safe_load(f)
   except FileNotFoundError:
       sys.exit(f"ERROR: Config file not found: {path}")
   except yaml.YAMLError as e:
       sys.exit(f"ERROR: Invalid YAML in config file: {e}")
   ```

#### 2.2 Import sys

Add `import sys` to config.py.

#### 2.3 Update Tests

Add test cases for each validation:
- `test_config_duplicate_target_name_exits()`
- `test_config_slash_in_name_exits()`
- `test_config_ping_interval_too_low_exits()`
- `test_config_ping_count_too_low_exits()`

Use `pytest.raises(SystemExit)` or mock `sys.exit` to capture the calls.

---

### 3. TypeScript Conversion for Frontend

**Why**: TypeScript provides compile-time type checking, which catches errors before runtime and makes the codebase easier to refactor. This is especially valuable for agent-maintained code where the agent can rely on the type system to validate changes.

#### 3.1 Setup

1. Add TypeScript dependencies:
   ```bash
   cd frontend
   npm install -D typescript @types/react @types/react-dom
   ```

2. Create `tsconfig.json`:
   ```json
   {
     "compilerOptions": {
       "target": "ES2020",
       "useDefineForClassFields": true,
       "lib": ["ES2020", "DOM", "DOM.Iterable"],
       "module": "ESNext",
       "skipLibCheck": true,
       "moduleResolution": "bundler",
       "allowImportingTsExtensions": true,
       "resolveJsonModule": true,
       "isolatedModules": true,
       "noEmit": true,
       "jsx": "react-jsx",
       "strict": true,
       "noUnusedLocals": true,
       "noUnusedParameters": true,
       "noFallthroughCasesInSwitch": true
     },
     "include": ["src"],
     "references": [{ "path": "./tsconfig.node.json" }]
   }
   ```

3. Update `vite.config.js` to `vite.config.ts` (Vite supports TypeScript natively).

#### 3.2 File Conversions

Rename files from `.jsx` to `.tsx` and `.js` to `.ts`:
- `src/App.jsx` → `src/App.tsx`
- `src/api.js` → `src/api.ts`
- `src/components/GraphView.jsx` → `src/components/GraphView.tsx`
- `src/components/ZoomView.jsx` → `src/components/ZoomView.tsx`
- `src/components/Sidebar.jsx` → `src/components/Sidebar.tsx`

#### 3.3 Type Definitions

Create `src/types.ts` with shared types:

```typescript
export interface TargetNode {
  type: "target"
  name: string
  host: string
  path: string
}

export interface FolderNode {
  type: "folder"
  name: string
  path: string
  children: TreeNode[]
}

export type TreeNode = TargetNode | FolderNode

export interface Stats {
  median_ms: number | null
  loss_pct: number | null
  sample_count: number
}

export interface ZoomState {
  target: string
  startTs: number
  endTs: number
}

export type TimeRange = "3h" | "2d" | "1mo" | "1y"
```

#### 3.4 api.ts Types

```typescript
const BASE = ""

export function encodePath(p: string): string {
  return p.split("/").map(encodeURIComponent).join("/")
}

export function graphUrl(targetPath: string, range: TimeRange = "3h"): string {
  return `${BASE}/api/graph/${encodePath(targetPath)}?range=${range}`
}

export function graphUrlWindow(targetPath: string, startTs: number, endTs: number): string {
  return `${BASE}/api/graph/${encodePath(targetPath)}?start=${startTs}&end=${endTs}`
}

export async function fetchTargets(): Promise<TreeNode[]> {
  const res = await fetch(`${BASE}/api/targets`)
  if (!res.ok) throw new Error(`fetchTargets failed: ${res.status}`)
  return res.json()
}

export async function fetchStats(targetPath: string, window?: number): Promise<Stats> {
  const params = window ? `?window=${window}` : ""
  const res = await fetch(`${BASE}/api/targets/${encodePath(targetPath)}/stats${params}`)
  if (!res.ok) throw new Error(`fetchStats failed: ${res.status}`)
  return res.json()
}
```

#### 3.5 Component Props

Add prop types to each component:

```typescript
// Sidebar.tsx
interface SidebarProps {
  tree: TreeNode[]
  activeTarget: string | null
  onSelectTarget: (path: string) => void
}

// GraphView.tsx
interface GraphViewProps {
  targetPath: string
  onZoom: (state: ZoomState) => void
}

// ZoomView.tsx
interface ZoomViewProps {
  target: string
  startTs: number
  endTs: number
  onBack: () => void
  onZoom: (state: ZoomState) => void
}
```

#### 3.6 Test File Updates

Rename test files to `.test.tsx` / `.test.ts` and update imports. Vitest supports TypeScript natively with the existing setup.

#### 3.7 Incremental Migration

This can be done incrementally:
1. First add TypeScript config and rename `api.js` → `api.ts`
2. Then convert components one at a time
3. Run `npm run build` after each change to catch type errors

The Vite build will fail if there are type errors when `noEmit: true` is set, which enforces correctness.

