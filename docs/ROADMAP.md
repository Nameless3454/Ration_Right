# RationAI — Future Roadmap

Phase 16 ends feature development. The items below are **future work** —
none are implemented, and none are required for the current demo.

## Phase 17+

1. **Verified government data sources** — connect and verify official PDS
   APIs (the Phase 7 connector is ready; requires live credentials), with
   freshness monitoring and source-failure recovery.
2. **Broader geographic coverage** — multi-state rollouts, real map
   visualization, standardized district/FPS hierarchies.
3. **Stronger forecasting** — seasonal models, longer-history demand
   forecasting, and confidence-calibrated projections (currently the
   deterministic forecast requires a minimum history and otherwise reports
   INSUFFICIENT_DATA).
4. **Mobile / offline operations** — native field app, offline caching,
   low-bandwidth sync for field officers.
5. **Advanced optimization** — allocation/replenishment optimization,
   route planning, cost-aware recommendations.
6. **Deeper integrations** — email/SMS/push alerting (configurable only),
   ERP/SCM connectors, single sign-on and role-based access control.
7. **Production infrastructure** — PostgreSQL, containerized deployment,
   distributed rate limiting, structured observability (metrics/tracing).
