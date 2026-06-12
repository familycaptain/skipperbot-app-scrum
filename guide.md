# Scrum Guide

The Scrum app is the daily standup for a household that runs like a software
team. Every morning the platform's Goals/PM daily-update runner writes each
person a personalized set of **scrum items** — what they finished, what they're
focused on, what's blocking them, plus findings and schedule reminders. The user
answers those items, either in the Scrum app or by replying to their PM
check-in in chat. Your job is to capture those replies and act on them.

## Tools

### `get_pending_scrum_items(user_id)`

List a user's **unanswered** scrum items for today. Call this when:

- A user replies to their PM daily check-in and you need to know which items are
  still open so you can match their reply to the right one.
- A user asks "what's on my standup?", "what are my scrum items?", "what did the
  PM ask me today?".

`user_id` is the canonical lowercase username (e.g. `alice`). Returns each
pending item with its type, title, optional detail/project, and its `si-...` ID.

### `respond_to_scrum_item(item_id, response_text, task_action="")`

Record the user's reply to one scrum item. Match each part of a multi-part reply
to its item and call this once per item — you can call it several times in a
single turn.

`item_id` is the `si-...` ID from `get_pending_scrum_items`. `response_text` is
the user's reply for that item. It's idempotent: if the item already has a
response it is left untouched.

Set `task_action` to roll the linked task forward based on what the user says:

| `task_action`      | When                                         | Effect              |
|--------------------|----------------------------------------------|---------------------|
| `mark_done`        | They say they finished it                     | linked task → done        |
| `mark_in_progress` | They say they're working on it                | linked task → in_progress |
| `mark_blocked`     | They say they're stuck / blocked              | linked task → blocked     |
| `""` (empty)       | Just record the reply, no status change       | (no task change)          |

A scrum item only has a linked task when it was generated from a goal/task
(`source_entity_id` is set) — for freeform findings or schedule items there is
nothing to update, so leave `task_action` empty.

## Typical flow

1. User replies to their morning standup: "finished the auth refactor, still
   working on the dashboard, blocked on the API key."
2. Call `get_pending_scrum_items("alice")` to see today's open items.
3. For each matched item, call `respond_to_scrum_item(...)`:
   - auth refactor item → `task_action="mark_done"`
   - dashboard focus item → `task_action="mark_in_progress"`
   - API key blocker → `task_action="mark_blocked"`
4. Confirm back what you recorded and which tasks moved.

Only record what the user actually said — don't invent answers for items they
didn't address.
