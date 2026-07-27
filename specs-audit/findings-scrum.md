# Findings — scrum

Survey only; nothing fixed. Corpus 0 → 47 records (written from scratch — the repo had no C/F/S
records). Items marked **VERIFIED** were confirmed independently by the PM.

## VERIFIED — the app's headline feature is dead code

**`routes.py:106` — `import data_layer.goals as dl_goals` names a module that does not exist.** The
platform's `data_layer/` contains 25 modules and `goals.py` is not among them (goals live in
`apps/goals/data.py` and `store.py`). That import sits inside the outer `try:` at line 103, so it raises
`ModuleNotFoundError` on **every** reply made from the Scrum app UI, is swallowed by
`except Exception as e: logger.error("Failed to dispatch scrum chat: %s", e)`, and the entire block after
it — Definition-of-Done lookup, the `[SCRUM ACTION REQUIRED …]` prompt, `process_chat`, the
progress/response WebSocket events — never runs.

Consequences:
- Replying in the app saves the response and **nothing else ever happens**: no task marked
  done/in-progress/blocked, no due date set, no note recorded. `help.md` ("Answering can also nudge the
  underlying task forward") and `README.md` ("the response is saved and also pushed through the chat
  pipeline so the LLM can act on it") both promise behaviour that cannot occur.
- The UI shows "Sending to Skipper..." while nothing is sent, and the API still returns `{"ok": true}`.
- The whole Definition-of-Done closure rule (~40 lines of prompt) is unreachable, and it is the only place
  that logic exists. Two specs (`scrum.answering.definition-of-done`,
  `scrum.answering.reply-in-the-app-reaches-skipper`) are written to the evident intent and **currently
  describe behaviour that does not happen.**

Expected: import `apps.goals.data` (which has `load_entity`) — though the app contract forbids
`apps.<other>.*` and would want this read via `query_entities`.

## The absence coupling, confirmed against the platform

`apps/goals/pm_runner.py::check_and_run_pm` returns immediately when `import apps.scrum.data` fails, and
`apps/scrum/` is gitignored as an external app — so on a stock platform the 7 AM standup never runs. The
guard is deliberate and commented, but it silently disables more than the standup:

- **`_append_focus_nags` is called only from inside `check_and_run_pm`, after the scrum guard.** So
  `apps/prioritize`'s daily focus nudge never fires without this app — while `PrioritizeApp.jsx` still
  renders a "Nag on / Nag off" toggle and per-member `focus_nag_enabled` state, and
  `apps/prioritize/help.md` still describes the nudge. **A user can toggle a setting that has no effect on
  any install lacking an optional third-party app.** Expected: the focus nag should run from its own
  scheduled hook.
- **`PM_QUIET_MODE` is honoured only inside `_deliver_pm_messages`**, likewise reachable only past the
  scrum guard. Turning quiet mode on or off is a no-op without this app — a setting that exists, is
  settable, and means nothing.
- `run_pm_check` (the lighter between-standups check-in) has the same guard, so overdue `pending_action`
  review is also scrum-gated.

Note the internal inconsistency: `_persist_scrum_items` and `_get_yesterday_commitments` each carry their
*own* graceful `ImportError` fallback commented "the standup still runs and DMs still go out — they just
aren't persisted". That is now false, because the outer guard means neither is ever reached. **Two layers
of defensive code disagree about what happens when scrum is absent.**

## App-contract violations (`specs/APP_PACKAGES.md`, binding per `CLAUDE.md`)

- **No memory digestion anywhere.** `data.py` performs four mutations and never calls
  `app_platform.memory.digest_record`. The contract says an app that skips this "is invisible to chat
  recall" — so no standup question or answer is ever recallable in conversation.
- **Isolation broken in four places.** The contract permits only `app_platform.*` and this package.
  `tools.py` imports `apps.goals.store.update_item` and `data_layer.skipper_state`; `data.py` imports
  `data_layer.links.ensure_edge`; `routes.py` imports `chat`, `agent`, `data_layer.goals`. Only the
  `data_layer.links` one is annotated as intentional.
- **Naive time everywhere.** The contract mandates `app_platform.time`. `data.py::get_scrum_items`,
  `routes.py::api_create_scrum_item` and `tools.py::get_pending_scrum_items` all use `date.today()`, which
  resolves in server-local/UTC — so "today's standup" flips at the wrong midnight for a household outside
  the server's zone. `apps/goals/pm_runner.py` correctly uses `datetime.now(get_timezone())` to decide the
  run hour but then writes `report_date=date.today()`, so **the two disagree near midnight.**
- **Raw Tailwind colour scales throughout `ui/ScrumApp.jsx`.** The contract says semantic design-system
  classes only and that "raw Tailwind color scales fail the build"; the file is built almost entirely from
  `bg-slate-800`, `text-indigo-400`, `bg-emerald-500/10` etc. Either the app cannot build against a current
  platform, or the stated build rule is not enforced. Worth resolving which.
- **`CLAUDE.md` says "Tests live in `tests/` and ship with the app: `python -m pytest tests/`". There is no
  `tests/` directory and no test file anywhere in the repo** — which is why all 41 specs carry `tests: []`.

## Correctness bugs

**VERIFIED — `ui/ScrumApp.jsx:114` — `isOwnItem = !person || person === userId`.** When the person picker
is on "All Users" (`person === ""`), `!person` is true, so `isOwnItem` is true for **every** item and the
Reply button (line 178) appears on **other people's** unanswered items — posting a response on their behalf
with `user_id: userId`, so the chat side would act as the wrong person. Expected:
`isOwnItem = (item.person === userId)`.

- **Day-range off-by-one.** `data.py::get_scrum_items` computes
  `cutoff = date.today() - timedelta(days=days)` then filters `report_date >= cutoff`. With the UI's
  "Today" option (`days=1`) this returns **today and yesterday**; "3 days" returns four. Every label in the
  day picker is off by one.
- **`data.py::respond_to_item` is described as atomic but cannot report what it did.** The
  `UPDATE … WHERE id = %s AND response IS NULL` is conditional, but the function then re-`SELECT`s and
  returns the row unconditionally, so a caller cannot distinguish "I recorded your answer" from "someone
  already answered". `tools.py` papers over it with a separate pre-`SELECT` (a TOCTOU race);
  `routes.py` does not check at all — it returns `{"ok": true, "item": …}` with the *old* response and,
  absent the import bug, would still fire a chat turn carrying the *new* text. Expected: `RETURNING`.
- **`routes.py` hardcodes `"alice"` as the fallback identity, twice** —
  `person=req.person.strip().lower() or "alice"` and `user_id = req.user_id.strip().lower() or "alice"`. A
  specific household member's name is baked in as the default owner for any unattributed request on every
  install.
- **No authentication or authorization on any route.** All three endpoints take the acting identity from
  the request body and never verify it against a session. Anyone reaching `/api/apps/scrum` can file items
  as anyone, answer anyone's items, and read every member's standup history via `GET /` with no `person`.
- **`tools.py::respond_to_scrum_item` reaches into the data layer's re-exports** —
  `_dl.fetch_one_in_schema(_dl.SCHEMA, "SELECT id, response FROM scrum_items WHERE id = %s", …)` — raw SQL
  in the tool layer, working only because `data.py` happens to import that helper into its namespace.
- **`_persist_scrum_items`'s idempotency guard is household-wide, not per-person**
  (`items_exist_for_date(today)` with no `person`). If any one person's items land, a later run covering a
  newly-added person is skipped for that day. `data.py::items_exist_for_date` supports the per-person form;
  the caller does not use it.

## Dead / unreachable surfaces

- **Two of the five item types are never produced.** `finding` and `schedule` are accepted by the route,
  rendered by `TYPE_META`, badged by `SEVERITY_BADGE`, iconed in `tools.py`, and documented in `SPEC.md`
  with example titles — but `_persist_scrum_items` only ever emits `done`, `focus` and `blocked` ("Rule-based
  scan + LLM evaluation removed (Phase 2.6)"). The "Other" section of the UI is unreachable in practice and
  `severity` is a column nothing populates.
- **`detail`, `source_entity_type`, `severity` and `project_name` cannot be set through the REST API.**
  `api_create_scrum_item` accepts only `item_type`, `title`, `person`, `response`, so a freeform item can
  never carry detail, a link or a severity — beside a data layer that supports all of them.
- **`ScrumCreateRequest.item_type`'s comment says `done | focus | blocked` while the validation below
  accepts five values.**
- **`manifest.yaml` declares `platform_deps: [goals, notifications]`, but this app never touches
  notifications** — delivery is entirely `apps/goals/pm_runner.py::_deliver_pm_messages`. The declared
  dependency describes something the *platform* does on this app's behalf. (The loader parses
  `platform_deps` and nothing ever reads it, for any app.)
- **`_deliver_pm_messages` defines `def save_notification(...): return None  # superseded`, then calls it
  in a `try/except` and logs failures** — a dead call with a dead error handler.
- **No delete or edit path exists** for a scrum item — no route, no tool, no data-layer function. Specced
  as intent (`scrum.household.a-standup-is-a-record`) because it is defensible, but flagged in case it is
  an omission: a mis-filed item cannot be removed short of SQL.

## Consciousness / logging

- **`api_respond_to_scrum_item` injects a machine-authored instruction block into the log as the user's
  own words.** It calls `process_chat(user_id=user_id, user_message=item_context, …)` where `item_context`
  is the ~15-line `[SCRUM ACTION REQUIRED — … TASK CLOSURE RULE …]` prompt with the user's actual reply
  appended. `chat.py` then writes
  `shadow_log_event(kind="message", who_from=user_id, content=user_message, …)` — so the web console, meant
  to be the complete and faithful record of both sides, would record **the entire internal prompt as
  something the person typed.** Currently masked by the import bug; it goes live the moment that is fixed.
  Expected: pass the reply as the content and the scrum framing as `app_context`.
- That call passes `domain` implicitly as `"chat"`, though `specs/CONSCIOUSNESS.md` lists `scrum` as a
  first-class domain — so a scrum-originated turn is indistinguishable from ordinary chat in the log.
- `routes.py` also pushes `chat_progress`/`chat_response` events directly via `manager.send_to_user` **in
  addition to** whatever `process_chat` emits — a second path to the same screen alongside the one writer.
  Worth checking for a duplicated reply once the block executes.

## `specs/SPEC.md` accuracy

Left in place as prose (matching the notifications exemplar) but it should not be treated as current. It
states as fact that the respond endpoint "saves a response AND push[es] it through the chat pipeline" (it
cannot — see the import bug); that `finding` and `schedule` items come from "PM findings (rule + LLM)" and
"Schedule summary" (both removed from the PM runner); and documents `severity` as populated for findings
(nothing populates it). Its example titles are drawn from one specific household's data.
