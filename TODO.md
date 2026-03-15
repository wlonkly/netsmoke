# TODO

Items are tracked as GitHub Issues: https://github.com/wlonkly/netsmoke/issues

Previously listed here:
- Collector status in sidebar → #9
- License file and SmokePing attribution → #10
- Update URL on zoom/unzoom → #11
- Sample data generator for demo site → #12
- Drag-to-zoom rollup path (performance) → #13
- Packet loss color and per-graph legend → #14
- Strict config validation at startup → #15

---

## Adopted from netsmoke-claude-superpowers

### TypeScript Conversion for Frontend ✓ DONE (PR #8)

All `.jsx`/`.js` source and test files converted to `.tsx`/`.ts` with strict TypeScript. `tsconfig.json` added with `strict`, `noUnusedLocals`, `noUnusedParameters`. Shared types live in `src/types.ts`. 34/34 tests pass, `tsc --noEmit` clean.
