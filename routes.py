"""Scrum — REST API router. Mounted by the platform at /api/apps/scrum.

Paths here are RELATIVE to that mount point:
    GET  /                       → list scrum items
    POST /                       → create a freeform scrum item
    POST /{item_id}/respond      → record a response (+ push through chat)

Ported from the platform's agent.py scrum endpoints. The respond endpoint also
fans the response out through the chat pipeline so the LLM can act on it; that
push is imported lazily and guarded so a failure never breaks the HTTP response.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter
from pydantic import BaseModel

from apps.scrum import data as _dl


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def api_get_scrum_items(
    person: str | None = None,
    date: str | None = None,
    days: int = 7,
    item_type: str | None = None,
):
    from datetime import date as _date_type
    report_date = None
    if date:
        try:
            report_date = _date_type.fromisoformat(date)
        except ValueError:
            return {"error": "Invalid date format, use YYYY-MM-DD"}
    items = await asyncio.to_thread(
        _dl.get_scrum_items,
        person=person, report_date=report_date,
        days=min(days, 90), item_type=item_type,
    )
    return {"items": items, "count": len(items)}


class ScrumCreateRequest(BaseModel):
    item_type: str          # done | focus | blocked
    title: str
    person: str
    response: str = ""      # optional — if provided, marks as already answered


@router.post("/")
async def api_create_scrum_item(req: ScrumCreateRequest):
    """Create a freeform scrum item (user adds something not in the predefined list)."""
    from datetime import date as _date_type
    if req.item_type not in ("done", "focus", "blocked", "finding", "schedule"):
        return {"error": "item_type must be one of: done, focus, blocked, finding, schedule"}
    if not req.title.strip():
        return {"error": "title is required"}
    item = await asyncio.to_thread(
        _dl.save_scrum_item,
        report_date=_date_type.today(),
        person=req.person.strip().lower() or "alice",
        item_type=req.item_type,
        title=req.title.strip(),
    )
    # If a response was provided, mark it as answered immediately
    if req.response.strip():
        item = await asyncio.to_thread(
            _dl.respond_to_item, item["id"], req.response.strip()
        )
    return {"ok": True, "item": item}


class ScrumRespondRequest(BaseModel):
    response_text: str
    user_id: str = ""


@router.post("/{item_id}/respond")
async def api_respond_to_scrum_item(item_id: str, req: ScrumRespondRequest):
    """Save a response to a scrum item AND send it through the chat pipeline."""
    if not req.response_text.strip():
        return {"error": "response_text is required"}

    # 1. Save response to DB
    result = await asyncio.to_thread(
        _dl.respond_to_item, item_id, req.response_text.strip()
    )
    if not result:
        return {"error": f"Scrum item '{item_id}' not found"}

    # 2. Send through the chat pipeline so the LLM can take actions.
    #    Everything below is best-effort — a failure here must not break the
    #    HTTP response (the response is already saved). The chat pipeline +
    #    connection manager are platform infra, imported lazily and guarded.
    try:
        from chat import process_chat
        from agent import manager
        import data_layer.goals as dl_goals

        user_id = req.user_id.strip().lower() or "alice"
        source_entity_id = result.get("source_entity_id", "")
        source_entity_type = result.get("source_entity_type", "")
        item_type = result.get("item_type", "?")
        item_title = result.get("title", "?")
        user_text = req.response_text.strip()

        # Load Definition of Done for the source entity (if it's a task/project)
        dod_text = ""
        if source_entity_id:
            try:
                _entity = await asyncio.to_thread(dl_goals.load_entity, source_entity_id)
                if _entity:
                    dod_text = _entity.get("definition_of_done", "") or ""
            except Exception:
                pass

        if dod_text.strip():
            dod_section = (
                f"\nDefinition of Done for this task: \"{dod_text.strip()}\"\n"
                f"TASK CLOSURE RULE (DoD present): Compare the user's response to the Definition of Done above. "
                f"If their response indicates they have completed what the DoD describes — even without "
                f"explicitly saying 'done' — mark the task as done. Use intent matching: if the DoD says "
                f"'sprite is drawn' and the user says 'the sprite has been drawn', that meets the DoD.\n"
            )
        else:
            dod_section = (
                f"\nThis task has NO Definition of Done.\n"
                f"TASK CLOSURE RULE (no DoD): Do NOT mark the task as done unless the user EXPLICITLY "
                f"says the task is done, finished, complete, or closed. A progress update alone (e.g. "
                f"'I worked on X') is NOT enough to close a task when there is no DoD. Only close it "
                f"when the user clearly states it is done.\n"
            )

        item_context = (
            f"[SCRUM ACTION REQUIRED — The user replied to a daily scrum {item_type} item.\n"
            f"Item: {item_title}\n"
            f"Source entity: {source_entity_type} {source_entity_id}\n"
            f"{dod_section}"
            f"The response has ALREADY been saved to the scrum item — do NOT call respond_to_scrum_item.\n"
            f"Instead, ACT on what the user said. Examples:\n"
            f"- If they say a task is done/complete (or meets the DoD) → call update_task to set status='done'\n"
            f"- If they give a due date → call update_task to set the due_date\n"
            f"- If they say it's blocked → call update_task to set status='blocked'\n"
            f"- If they say to defer it → call update_task to set status='deferred'\n"
            f"- If they provide a status update → record it as a note on the entity\n"
            f"Do NOT just acknowledge — take the appropriate goal/task action.]\n"
            f"User's reply: {user_text}"
        )

        # Fire-and-forget: send to chat as if the user typed it
        async def _process():
            try:
                async def _send_progress(text: str):
                    await manager.send_to_user(user_id, {
                        "type": "chat_progress",
                        "content": text,
                    })

                async def _send_event(event: dict):
                    await manager.send_to_user(user_id, event)

                reply = await process_chat(
                    user_id=user_id,
                    user_message=item_context,
                    channel="web",
                    send_progress=_send_progress,
                    send_event=_send_event,
                )
                if reply:
                    await manager.send_to_user(user_id, {
                        "type": "chat_response",
                        "response": reply,
                        "user_id": user_id,
                    })
            except Exception as e:
                logger.error("Scrum chat processing failed: %s", e, exc_info=True)

        asyncio.create_task(_process())
    except Exception as e:
        logger.error("Failed to dispatch scrum chat: %s", e)

    return {"ok": True, "item": result}
