# netsmoke — Claude Code context

## What this project is

SmokePing-inspired latency monitor. A Python/FastAPI backend collects fping data into SQLite, renders smoke-band graphs with matplotlib, and serves them as PNGs. A React/Vite frontend displays those images with a drag-to-zoom interaction.

---

## Tracking work

For anything ticket-sized or larger (a bug fix, a feature, a refactor, an investigation), create a GitHub Issue rather than adding to a local TODO file. Use `gh issue create --repo wlonkly/netsmoke` from the CLI.

---

## Dev workflow

```bash
just dev               # start both services (hot-reload)
just stop              # stop both
just status            # check PIDs
just test              # run backend test suite
just test-frontend     # run frontend test suite
just import-smokeping data_dir targets_file  # import SmokePing RRD data
```

Backend: http://localhost:8000 — Frontend: http://localhost:5173

Vite proxies `/api` and `/health` to `:8000` in dev (see `vite.config.js`). In production, `frontend/dist/` is served as a static site alongside the API.

### SmokePing importer

One-time migration tool lives in `importer/` (package `smokeping_import`). It reads SmokePing RRD files via `rrdtool dump` and bulk-inserts into `ping_samples`, then calls `backfill_rollups` to pre-compute `ping_rollups` so the 1mo/1y graphs work immediately.

```bash
just import-smokeping /path/to/smokeping/data /path/to/Targets
```

All recipes (`dev`, `run`, `import-smokeping`) use the same DB path: `netsmoke.db` at the project root. Do not call the importer CLI directly from outside the project root — the `just` recipes handle the `--db` paths correctly.

---

## Architecture: things that aren't obvious

### Graphs are server-rendered PNGs, not JS charts

The backend renders matplotlib figures to PNG bytes and serves them as `image/png`. The frontend just puts them in `<img>` tags. There is no charting library on the frontend.

Consequence: interactive features (zoom, time selection) need a transparent overlay div over the image to capture mouse events, not event listeners on chart elements.

### Zoom interaction is a transparent div mapped to timestamps

`GraphView.jsx` and `ZoomView.jsx` place a `.graph-drag-overlay` absolutely over each image. On drag-end, pixel X is mapped linearly to Unix timestamps:

```js
const ts = startTs + (x / containerWidth) * (endTs - startTs)
```

Matplotlib's Y-axis label area means the left ~10% of the image doesn't correspond to chart time — the mapping is intentionally approximate. The datetime inputs in ZoomView let users correct this.

### No React Router — zoom is pure state

Navigation between the 4-panel view and the zoom view is a single `zoomState: { target, startTs, endTs } | null` in `App.jsx`. When non-null, `<ZoomView>` renders instead of `<GraphView>`. Clicking a sidebar target calls `setZoomState(null)` to reset.

### Target paths are used as both DB keys and URL segments

A target like `{ folder: "CDNs", name: "Cloudflare" }` gets the path `"CDNs/Cloudflare"`. This string is:
- The `target` column value in `ping_samples`
- The URL path segment in `/api/graph/CDNs/Cloudflare`
- The `path` field returned by `/api/targets`

FastAPI's `{target_path:path}` route parameter captures slashes, so nested paths work. `encodePath()` in `api.js` encodes each segment individually while preserving `/` separators.

### `RANGE_SECONDS` is duplicated intentionally

The backend has it in `graph.py` for rendering. The frontend has a copy in `GraphView.jsx` to compute `startTs`/`endTs` for each panel's drag overlay at render time. Keep them in sync if you add ranges.

### `matplotlib.use("Agg")` must appear before pyplot import

It's at the top of `graph.py`. If you add any new file that imports matplotlib, do the same before importing `pyplot`. The backend is a server process with no display — without `Agg`, matplotlib will try to open a GUI window and crash.

### Graph x-axis ticks are driven by duration, not a range name

`_locator_and_format(duration_s)` in `graph.py` picks the tick density based on the actual window length in seconds. `render_graph()` no longer takes a `time_range` string — it takes `start_ts`/`end_ts` ints and computes `duration_s = end_ts - start_ts`. If you call `render_graph()` directly in tests, pass `start_ts`/`end_ts` instead of `time_range`.

---

## Key invariants to preserve

- `render_graph_for_target` must remain a thin wrapper over `render_graph_for_window` — no duplicate rendering logic between the two entry points
- `set_state(config, db)` in `api.py` is the test injection point — it must stay; it's called by every API test fixture
- `asyncio_mode = "auto"` in `pyproject.toml` means pytest-asyncio auto-applies to async test functions; don't add `@pytest.mark.asyncio` unless it's missing somewhere already
- DB fixtures use `tmp_path` — tests must never open or write to `netsmoke.db` (the live database)
- The `_k` query param on graph image URLs is a cache-bust key; it's not sent to the backend and not validated there

---

## Adding a new API endpoint

1. Add the route in the `create_app()` function in `api.py`
2. Add a corresponding test in `tests/test_api.py` using the existing `client` fixture
3. If it needs a new graph function, add it to `graph.py` and test it in `tests/test_graph.py`

Do not add routes outside `create_app()` — the lifespan and middleware are only attached inside that function.

## Adding a new time range

- Add to `RANGE_SECONDS` in `backend/netsmoke/graph.py`
- Add to the `pattern=` regex in the `range` Query param in `api.py`
- Add to `RANGES` array in `frontend/src/components/GraphView.jsx`
- Add the same seconds value to `RANGE_SECONDS` in `GraphView.jsx`

---

## DB schema

```sql
CREATE TABLE ping_samples (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    time        INTEGER NOT NULL,   -- Unix timestamp (seconds)
    target      TEXT NOT NULL,      -- e.g. "CDNs/Cloudflare"
    sample_num  INTEGER NOT NULL,   -- 1..N (one row per ping per measurement)
    rtt_ms      REAL                -- NULL = packet loss
);

CREATE TABLE ping_rollups (
    id           INTEGER PRIMARY KEY,
    target       TEXT NOT NULL,
    bucket_start INTEGER NOT NULL,  -- Unix timestamp, aligned to bucket boundary
    bucket_size  TEXT NOT NULL,     -- "hour" (3600s) or "day" (86400s)
    sorted_rtts  TEXT NOT NULL,     -- JSON array, pre-sorted ascending, non-null only
    loss_count   INTEGER NOT NULL,
    total_count  INTEGER NOT NULL,
    UNIQUE (target, bucket_start, bucket_size)
);
```

`ping_samples` indexed on `(target, time)`. `ping_rollups` indexed on `(target, bucket_start, bucket_size)`. WAL mode + `synchronous=NORMAL` for write performance.

---

## Rollup strategy

The 1mo and 1y graphs would be too slow to render from raw `ping_samples`. Instead, pre-aggregated rows in `ping_rollups` are used for those ranges:

| Time range | Bucket size | Data source |
|-----------|-------------|-------------|
| 3h, 2d    | —           | `ping_samples` (raw) |
| 1mo       | `"hour"`    | `ping_rollups` |
| 1y        | `"day"`     | `ping_rollups` |

This mapping lives in `RANGE_BUCKET_SIZE` in `graph.py`. `render_graph_for_target` reads it and passes `bucket_size` to `render_graph_for_window`, which dispatches to either `query_samples` + `build_rtt_matrix` (raw path) or `query_rollups` + `build_rollup_rtt_matrix` (rollup path).

### What a rollup row holds

- `sorted_rtts`: JSON array of received RTTs, pre-sorted ascending, sub-sampled to at most `ping_count` values using evenly-spaced indices
- `loss_count` / `total_count`: used to compute loss percentage; loss values are not included in `sorted_rtts`
- `bucket_start` is always boundary-aligned: `(timestamp // duration) * duration`

### Rollup maintenance

**During ongoing collection** (`collector.py`): after every probe, `update_rollup()` is called twice — once for the hour bucket, once for the day bucket. It queries the full bucket from `ping_samples`, recomputes the aggregates, and upserts via `ON CONFLICT DO UPDATE`. This means every rollup row always reflects all samples in its bucket.

**After historical import** (`importer/`): `backfill_rollups()` batch-computes all hour and day buckets for all targets and upserts them in one pass. This is what makes 1mo/1y graphs usable immediately after a SmokePing migration.

Raw `ping_samples` are never deleted by the rollup system. The 365-day `prune_old_data()` is the only thing that removes raw rows; rollup rows are not pruned.

---

## State injection pattern for tests

Tests never start the lifespan. Instead they call `set_state(config, db)` before creating the `AsyncClient`, which bypasses the env-var + collector startup path:

```python
app = create_app()
set_state(config, db)
async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
    ...
```

This means the collector does not run during tests. If you need to test collector behaviour, do it directly in a separate test — don't go through the API.

---

## Frontend testing

Stack: **Vitest + React Testing Library**, jsdom environment. No Playwright — the frontend is thin wrappers around server-rendered PNGs; all meaningful logic is testable without a browser.

### Running tests

```bash
just test-frontend          # one-shot (use this in CI / after changes)
just test-frontend-watch    # watch mode during development
```

### Mock pattern for API calls

`fetchTargets` and `fetchStats` do real HTTP — always mock them. `graphUrl` and `graphUrlWindow` are pure functions — use their real implementations.

```js
vi.mock('../api.js', async (importActual) => {
  const actual = await importActual()
  return { ...actual, fetchTargets: vi.fn(), fetchStats: vi.fn() }
})
```

In `beforeEach`, reset mocks and set a default resolved value for `fetchStats` to avoid unhandled rejections when GraphView mounts:

```js
beforeEach(() => {
  vi.resetAllMocks()
  fetchStats.mockResolvedValue({ median_ms: 12.3, loss_pct: 0, sample_count: 10 })
})
```

### Drag-to-zoom tests need a mocked `getBoundingClientRect`

jsdom returns `{ width: 0, ... }` from `getBoundingClientRect`. A zero `containerWidth` causes the drag threshold check (`Math.abs(x1 - x0) < 5`) to silently kill the drag. Always mock the overlay before firing mouse events:

```js
const overlay = container.querySelector('.graph-drag-overlay')
overlay.getBoundingClientRect = vi.fn().mockReturnValue({
  left: 0, width: 500, top: 0, right: 500, bottom: 100, height: 100,
})
fireEvent.mouseDown(overlay, { clientX: 100 })
fireEvent.mouseMove(overlay, { clientX: 300 })
fireEvent.mouseUp(overlay)
```

### `GraphPanel` is not exported

`GraphPanel` (inside `GraphView.jsx`) is an internal component. Its drag math is identical to `ZoomView`'s — test drag logic via `ZoomView` directly. For end-to-end zoom state transitions, use the App integration tests (which fire drag events on the `.graph-drag-overlay` rendered by GraphView).

### Async App tests

App calls `fetchTargets` on mount. Use `findBy*` (not `getBy*`) to wait for the async result before making assertions:

```js
await screen.findByText('Google DNS', { selector: '.graph-target-name' })
```

When a state update from a resolved promise would happen after your last assertion (e.g. `fetchStats` settling after a sidebar click), chain an `await findBy*` on something that only appears after that update to flush pending state.

---

## Frontend component responsibilities

| Component | Owns |
|-----------|------|
| `App.jsx` | active target, zoom state, sidebar ↔ main routing |
| `GraphView.jsx` | 4-panel layout, 60s auto-refresh, stats fetch, drag-to-zoom per panel |
| `ZoomView.jsx` | single graph, datetime inputs, zoom-out math, drag-to-further-zoom |
| `Sidebar.jsx` | target tree rendering, folder expand/collapse |
| `api.js` | all fetch/URL construction — nothing else does raw fetch calls |

---

## Things to watch out for

- **Config is loaded once at startup.** Changing `config.yaml` requires a backend restart to take effect.
- **Removed targets keep their DB rows.** Data for a target that's removed from config stays in the database indefinitely (subject to the 365-day pruning).
- **fping must be installed on the host.** The collector will fail silently (or log errors) if fping isn't in PATH.
- **`just dev` uses a single trap for cleanup.** Both processes share a shell; killing one kills both. Don't rely on `just stop` to clean up after an abrupt exit — check `just status` and kill stale PIDs manually if needed.
- **The frontend `now` timestamp is computed at render time**, not at mount. If a user leaves the 4-panel view open for a long time without a page refresh, the `startTs`/`endTs` for each panel will drift from reality (though the 60s auto-refresh re-renders panels with a new `imgKey`, the drag-selection timestamps won't update until the next re-render).
