"""Chat endpoint for the AI assistant.

Security notes:
* The frontend only sends the question, optional session history, and a
  description of the state its own page is currently showing.
* LLM credentials are read inside the process (``config.Settings``) and are
  never part of any response or CORS-exposed header.
* Actions the assistant proposes are validated server-side against that state
  and returned as data. The browser performs them; the backend never claims to
  have changed anything in the application.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from assistant.assistant_service import assistant_service
from schemas.models import (
    AssistantActionResultRequest,
    AssistantChatRequest,
    AssistantChatResponse,
)

logger = logging.getLogger("dss.assistant")

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", response_model=AssistantChatResponse)
async def chat(req: AssistantChatRequest) -> AssistantChatResponse:
    """POST /api/assistant/chat

    Returns an answer grounded in the DSS backend plus the sources that were
    used, the LLM status, the demo flag, any warnings, and any validated
    actions for the browser to carry out.

    A follow-up turn with ``confirm_action_id`` or ``denied_action_ids``
    settles a previously proposed action. The action is re-derived from the
    original question and re-validated, so the server keeps no pending state
    that a client could tamper with.
    """
    if not req.question.strip():
        raise HTTPException(status_code=422, detail="question must not be empty")

    try:
        out = await assistant_service.answer(req)
    except Exception as exc:  # noqa: BLE001 - never leak internals
        logger.exception("Assistant chat failed")
        raise HTTPException(status_code=503, detail=f"Assistant unavailable: {exc}") from exc

    return AssistantChatResponse(**out)


@router.post("/action-result", response_model=AssistantChatResponse)
async def action_result(req: AssistantActionResultRequest) -> AssistantChatResponse:
    """POST /api/assistant/action-result

    The browser reports what actually happened when it ran a proposed action, so
    the conversation stays truthful: the assistant only says it worked if the
    application says so.
    """
    llm = {"provider": "none", "model": None, "configured": False}
    # ``message`` carries the browser's own wording: a human label on success,
    # an error description on failure. Only report what it actually sent.
    detail = req.message.strip()
    if req.success:
        clean_detail = detail.rstrip(".")
        answer = f"✓ Done - {clean_detail}."
    else:
        answer = f"✗ {req.type} didn't complete: {detail or 'no result was reported'}."
    return AssistantChatResponse(
        answer=answer,
        sources=[],
        llm=llm,
        demo_mode=False,
        warnings=[],
        actions=[],
        knowledge_used=[],
    )