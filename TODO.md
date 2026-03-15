# TODO

- [ ] Add collector status at the bottom of the sidebar
- [ ] Add license file and credit SmokePing (derivative work, not a cleanroom implementation)
- [ ] Update URL when zooming and unzooming so that users can link others to what they're seeing by copying the current URL
- [ ] Sample data generation for a demo site, with "targets" that have different properties (like low latency, or high variation/smoke, or maybe one that has occasional degradation alternating with good performance -- all optimized for humans to see what the data looks like and for visual testing, rather than for automated code tests)
- [ ] Drag-to-zoom always queries raw `ping_samples` regardless of window size — `render_graph_for_window` has no rollup path. For large zoom windows (e.g. a 2-week selection on a 1mo panel) this could be slow. Fix: auto-select `bucket_size` in `render_graph_for_window` based on `end_ts - start_ts` (e.g. >7d → "day", >6h → "hour") rather than only routing through rollups via `render_graph_for_target`.
- [ ] Graph range should be set to make the data appear in the middle of the graph at highest, or lower if necessary to display the smoke
- [ ] When a user clicks another target in the UI, there should be a noticeable "update" action and all of the graphs for the new target should appear at the same time, not fetched and displayed one at a time.
- [ ] justfile target to build and upload a docker image to ghcr.io
- [ ] The frontend hits /api/health and gets a 404 error. why?
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

