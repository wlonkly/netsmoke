# TODO

- [ ] Add collector status at the bottom of the sidebar
- [ ] Add license file and credit SmokePing (derivative work, not a cleanroom implementation)
- [ ] Update URL when zooming and unzooming so that users can link others to what they're seeing by copying the current URL
- [ ] Sample data generation for a demo site, with "targets" that have different properties (like low latency, or high variation/smoke, or maybe one that has occasional degradation alternating with good performance -- all optimized for humans to see what the data looks like and for visual testing, rather than for automated code tests)
- [ ] Drag-to-zoom always queries raw `ping_samples` regardless of window size — `render_graph_for_window` has no rollup path. For large zoom windows (e.g. a 2-week selection on a 1mo panel) this could be slow. Fix: auto-select `bucket_size` in `render_graph_for_window` based on `end_ts - start_ts` (e.g. >7d → "day", >6h → "hour") rather than only routing through rollups via `render_graph_for_target`.
- [ ] Confirm color for packet loss works and add a legend to each graph
---

## Adopted from netsmoke-claude-superpowers

The following enhancements were recommended after a comparative code review of three netsmoke implementations.

### 1. Strict Config Validation at Startup

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

### 3. TypeScript Conversion for Frontend ✓ DONE (PR #8)

All `.jsx`/`.js` source and test files converted to `.tsx`/`.ts` with strict TypeScript. `tsconfig.json` added with `strict`, `noUnusedLocals`, `noUnusedParameters`. Shared types live in `src/types.ts`. 34/34 tests pass, `tsc --noEmit` clean.

