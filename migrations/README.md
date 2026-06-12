# Scrum app migrations

Numbered SQL or Python files. The platform loader runs each unrun
migration once and tracks application state in `public.app_migrations`
(scope `app_id='scrum'`).

Files run in lexical filename order. `001_initial.sql` first.

- `001_initial.sql` — creates the `app_scrum` schema + the `scrum_items` table
  and its indexes.
- `002+` — additive schema changes as the app evolves.

## Rules (per `specs/APP_PACKAGES.md`)

- SQL runs with `search_path = app_scrum, public` so unqualified table names
  refer to this app's schema, but `public.*` (memories, links, users,
  notifications) is still readable.
- No cross-schema foreign keys. References to other apps' entities
  (`source_entity_id` points at Goals tasks/projects) are by string only,
  not by FK — the link edge is recorded in `public` via `data_layer.links`.
- Migrations are idempotent — `CREATE TABLE IF NOT EXISTS`,
  `ADD COLUMN IF NOT EXISTS`, `ALTER TABLE ADD CONSTRAINT` wrapped in `DO`
  blocks catching `duplicate_object` / `invalid_table_definition` /
  `duplicate_table`.
- Every migration body is wrapped in an explicit `BEGIN; ... COMMIT;` block
  so `SET LOCAL search_path` actually scopes to the migration.
- Migrations never delete user data without an explicit destructive flag.
