# TODO

- Add explicit collector logging for each probe round, including raw `fping` results, target count, success/failure summary, and persistence outcome.
- Document the Colima/macOS ICMP caveat in `README.md` and consider surfacing it in the UI/dev status later.
- Support hot-reloading or automatic dev-container restarts during development so backend/frontend changes are picked up without manual restarts.
- Evaluate supporting the collector outside Docker for accurate local Mac testing when trustworthy ICMP measurements are needed.

## Next app steps

- Add collector observability: structured logs, richer `/api/collector/status`, last successful run time, last failure, and last persisted round summary.
- Add a recent-measurements API with latest rounds and raw-sample summaries for the frontend.
- Improve frontend usability with auto-refresh, a collector status badge, time-range control, and a recent-measurements panel.
- Harden runtime/config behavior with clearer `fping`/permissions/config errors, duplicate-ID/path validation, and degraded-state reporting.
- Replace metadata-only DB setup with real Alembic migrations for the current tables.
