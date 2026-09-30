"""Assistant service: intent detection, tool dispatch, LLM call.

When an LLM provider/credentials are configured (env vars), the question plus
the real backend context and the curated dashboard/domain knowledge is sent to
the provider and the answer is returned. When no provider is configured,
``prompts.build_fallback`` produces a conversational answer from the same tool
data and the same knowledge base. Either way the frontend and the API get:
answer, sources, llm status, demo flag, warnings.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.request
import urllib.error
from typing import Any

from assistant import actions as action_registry
from assistant import briefing
from assistant import docs_index, knowledge, prompts
from assistant.project_context import ProjectContext
from assistant.tools import TOOLS, datasets_status, extracted_iceberg_ids
from config import settings

logger = logging.getLogger("dss.assistant")

TIMEOUT_S = 45
MAX_TOKENS = 900
#: Session history kept in the prompt, to bound its size.
MAX_HISTORY = 14

DEFAULT_ROUTE = {
    "start_lat": -65.0,
    "start_lon": 140.0,
    "dest_lat": -77.8469,
    "dest_lon": 166.6687,
    "vessel_id": settings.DEFAULT_VESSEL_ID,
    "preference": "recommended",
}

# Keyword groups used to route a question to the right tools. Keeping them
# here (rather than inline) makes it obvious what the assistant can answer.
_SEA_ICE_WORDS = (
    "sea ice", "sea-ice", "sea_ice", "concentration", "pack ice", "ice field", "ice cover",
)
_ICE_WORDS = ("ice", "icy", "frozen")
_ICE_TYPE_WORDS = ("ice type", "types of ice", "fyi", "myi", "first-year", "first year",
                   "multi-year", "multi year", "young ice", "old ice", "classification of ice")
_THICKNESS_WORDS = ("thick", "thickness", "how thick", "draft of ice")
_KEEL_WORDS = ("keel", "clearance", "underwater", "under water", "under the ice", "below the ice",
               "sub-ice", "sub ice", "ship can pass", "can the ship")
_MELT_WORDS = ("melt", "melting", "melt zone", "melt pond", "thaw", "freezing")
_CHANGE_WORDS = ("changing", "change", "getting icier", "getting clearer", "trending",
                 "more or less ice", "compared to")
_TREND_WORDS = ("trend", "long term", "long-term", "over time", "anomaly", "history",
                "historical", "baseline", "climate", "climatology", "recent years")
_RISK_WORDS = ("risk", "dangerous", "hazard", "how safe", "is it safe", "threat", "hazardous")
_ALERT_WORDS = ("alert", "notification", "warning message")
_MODEL_WORDS = ("model", "accuracy", "accurate", "how good", "mae", "rmse", "convlstm", "lstm",
                "random forest", "persistence", "convergence", "metric", "validation", "skill")
_FLEET_WORDS = ("vessel", "ship", "fleet", "icebreaker", "ice-breaker", "port", "harbour",
                "harbor", "station", "research center", "research centre", "ice class",
                "which ship", "hobart", "ushuaia", "mcmurdo", "departure port", "destination")
_ROUTE_WORDS = ("route", "routing", "path", "waypoint", "voyage", "itinerary", "plan a route")
_FUEL_WORDS = ("fuel", "burn", "consumption", "bunker", "diesel")
_MOVEMENT_WORDS = ("where will", "move", "moving", "drift", "drifting", "trajectory", "heading",
                   "going to", "predicted position", "end up", "track", "travelling", "traveling")
_DISTANCE_WORDS = ("distance", "how far", "apart", "separation", "between")
_COUNT_WORDS = ("how many", "count", "number of", "list of", "list all")
_CLOSE_WORDS = ("closest", "nearest", "closest to", "nearest to", "next one")
_ALERT_WORDS = ("alert", "notification", "warning message", "raised", "flagged")
_SUMMARY_WORDS = ("summary", "overview", "brief me", "situation", "what's happening",
                  "whats happening", "status", "how bad", "report")

#: Questions about how the project itself is built. These are answered from the
#: repository's own documentation rather than from live data.
_DOCS_WORDS = (
    "architecture", "architect", "how is this built", "how does this project work",
    "codebase", "code base", "project structure", "tech stack", "technology stack",
    "what framework", "what language", "backend", "front end", "frontend",
    "data flow", "pipeline", "endpoint", "endpoints", "api design", "repository",
    "source code", "modules", "folder structure", "directories", "database",
    "model training", "trained", "training", "features", "feature engineering",
    "datasets", "dataset", "limitations", "disclaimer", "production ready",
    "deployment", "deploy", "docker", "readme", "documentation", "docs",
    "how does the system", "what is this project", "tell me about this project",
    "how do you", "who are you", "what are you", "what can you do",
)

#: Questions about the user's own current situation, answered from the browser
#: state the frontend already sent rather than from a fresh backend read.
_SOCIAL_RE = re.compile(
    r"^\s*(hi|hey|hello|yo|thanks|thank you|thx|cheers|appreciate it|ok|okay|cool|"
    r"nice|great|perfect|awesome|good|bye|goodbye|yes|yep|yeah|no|nope|sure|alright|"
    r"right|got it|makes sense|understood|understood thanks|how are you|whats up|"
    r"what's up|good morning|good evening)\b[\s!.?]*$",
    re.IGNORECASE,
)

#: Bare agreement is a reply to something I just said, not a question. Answering
#: "yes" with a fresh introduction reads like I lost the thread.
_ACK_RE = re.compile(
    r"^\s*(ok|okay|cool|nice|great|perfect|awesome|good|yes|yep|yeah|no|nope|"
    r"sure|alright|right|got it|makes sense|understood)\b[\s!.?]*$",
    re.IGNORECASE,
)

_GREETING_RE = re.compile(
    r"^\s*(hi|hey|hello|yo|good morning|good evening|good afternoon)\b[\s!.?]*$",
    re.IGNORECASE,
)

_THANKS_RE = re.compile(
    r"^\s*(thanks|thank you|thx|cheers|appreciate it)\b[\s!.?]*$", re.IGNORECASE
)

_SELF_STATE_WORDS = (
    "am i on", "which page", "what page", "current page", "where am i",
    "what am i looking at", "right now in the app", "current horizon",
    "what horizon", "which horizon", "which iceberg", "current iceberg",
    "selected iceberg", "my vessel", "my journey", "current journey",
    "is the journey", "journey status", "selected route", "which route",
    "my position", "current position", "unread alert", "how many alerts",
)


class AssistantError(Exception):
    """Raised when the assistant cannot produce any answer at all."""


def resolve_provider() -> dict:
    """Return (provider, model) according to config/env; never the API key."""
    cfg = settings.ASSISTANT_PROVIDER.strip().lower()
    model_override = (settings.ASSISTANT_MODEL or "").strip() or None

    if cfg == "none":
        return {"provider": "none", "model": None, "configured": False}
    if cfg in ("openai", "anthropic", "ollama"):
        provider = cfg
        model = model_override
        if provider == "openai":
            if not settings.OPENAI_API_KEY:
                return {"provider": "none", "model": None, "configured": False, "reason": f"{cfg} requested but OPENAI_API_KEY missing"}
            model = model or settings.OPENAI_MODEL
        elif provider == "anthropic":
            if not settings.ANTHROPIC_API_KEY:
                return {"provider": "none", "model": None, "configured": False, "reason": f"{cfg} requested but ANTHROPIC_API_KEY missing"}
            model = model or settings.ANTHROPIC_MODEL
        else:  # ollama
            model = model or settings.OLLAMA_MODEL
        return {"provider": provider, "model": model, "configured": True}

    # auto: only providers with actual credentials are auto-picked.
    # Ollama has no key, so it needs ASSISTANT_PROVIDER=ollama explicitly.
    if settings.OPENAI_API_KEY:
        return {"provider": "openai", "model": model_override or settings.OPENAI_MODEL, "configured": True}
    if settings.ANTHROPIC_API_KEY:
        return {"provider": "anthropic", "model": model_override or settings.ANTHROPIC_MODEL, "configured": True}
    return {"provider": "none", "model": None, "configured": False}


# --------------------------------------------------------------------------
# LLM clients (stdlib only, credentials in-process)
# --------------------------------------------------------------------------
def _post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        **({} if headers is None else headers),
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 - configured by the operator
        return json.loads(resp.read().decode("utf-8"))


def _chat_openai(model: str, messages: list[dict]) -> str:
    base = (settings.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
    data = _post_json(
        f"{base}/chat/completions",
        {
            "model": model,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": MAX_TOKENS,
        },
        {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
    )
    return data["choices"][0]["message"]["content"]


def _chat_anthropic(model: str, system: str, history: list[dict]) -> str:
    msgs = [
        {"role": m["role"], "content": m["content"]}
        for m in history
        if m["role"] in ("user", "assistant")
    ]
    data = _post_json(
        "https://api.anthropic.com/v1/messages",
        {
            "model": model,
            "system": system,
            "messages": msgs,
            "max_tokens": MAX_TOKENS,
        },
        {
            "x-api-key": settings.ANTHROPIC_API_KEY or "",
            "anthropic-version": "2023-06-01",
        },
    )
    return "".join(block.get("text", "") for block in data.get("content", []))


def _chat_ollama(model: str, messages: list[dict]) -> str:
    base = (settings.OLLAMA_BASE_URL or "http://localhost:11434").rstrip("/")
    data = _post_json(
        f"{base}/api/chat",
        {"model": model, "messages": messages, "stream": False},
    )
    return data.get("message", {}).get("content", "")


def run_llm(provider: str, model: str, messages: list[dict]) -> str:
    """Call the configured provider. Raises AssistantError on failure."""
    try:
        if provider == "openai":
            return _chat_openai(model, messages)
        if provider == "anthropic":
            system = messages[0]["content"]
            return _chat_anthropic(model, system, messages[1:])
        if provider == "ollama":
            return _chat_ollama(model, messages)
    except (urllib.error.URLError, KeyError, IndexError, OSError, json.JSONDecodeError) as exc:
        raise AssistantError(f"LLM provider {provider} ({model}) error: {exc}") from exc
    raise AssistantError(f"Unknown LLM provider: {provider}")


# --------------------------------------------------------------------------
# Intent detection -> which tools to run
# --------------------------------------------------------------------------
def _has(question: str, words) -> bool:
    return any(word in question for word in words)


def _route_kwargs(dashboard: Any) -> dict:
    kwargs = dict(DEFAULT_ROUTE)
    if dashboard:
        data = dashboard.model_dump() if hasattr(dashboard, "model_dump") else dashboard
        for key in ("start_lat", "start_lon", "dest_lat", "dest_lon", "vessel_id", "preference"):
            value = data.get(key)
            if value is not None:
                kwargs[key] = value
    return kwargs


def _add(tools: list[tuple[str, dict]], name: str, **kwargs) -> None:
    """Queue a tool once - the first queueing wins so callers can prioritise."""
    if all(existing != name for existing, _ in tools):
        tools.append((name, kwargs))


def looks_like_docs_question(question: str, history: list[dict] | None = None) -> bool:
    """True for questions about the project itself rather than its data.

    The keyword list catches the common phrasings; ``briefing`` adds a request
    for the whole system in one go ("explain everything") and a short follow-up
    ("tell me more") that only means something against the previous turn.
    """
    q = (question or "").lower()
    if any(word in q for word in _DOCS_WORDS):
        return True
    return briefing.looks_like_project_question(question, history)


def pick_tools(question: str, horizon: int, dashboard: Any = None) -> list[tuple[str, dict]]:
    """Map a question onto the backend tools that can answer it.

    Deliberately keyword-driven: it is fast, deterministic, cheap to reason
    about, and the LLM still gets the final say on how to phrase the answer.
    """
    q = (question or "").lower()
    tools: list[tuple[str, dict]] = []
    ids = extracted_iceberg_ids(question)

    sea_ice = _has(q, _SEA_ICE_WORDS)
    any_ice = sea_ice or (bool(re.search(r"\b(?:ice|icy|frozen)\b", q)) and "iceberg" not in q and "berg" not in q)

    # --- sea ice ---------------------------------------------------------
    if (
        sea_ice
        or any_ice
        or _has(q, _THICKNESS_WORDS)
        or _has(q, _KEEL_WORDS)
        or _has(q, _MELT_WORDS)
    ):
        wants_now = _has(q, ("actual", "current", "observed", "right now", "now", "today", "latest"))
        wants_forecast = _has(q, ("forecast", "predict", "expect", "will", "going to", "next",
                                  "outlook", "valid", "projected"))

        # Intimate sea-ice analytics, most specific first.
        if _has(q, _KEEL_WORDS):
            _add(tools, "sea_ice_keel_depth")
        if _has(q, _THICKNESS_WORDS):
            _add(tools, "sea_ice_thickness")
        if _has(q, _ICE_TYPE_WORDS) or ("ice" in q and "type" in q):
            _add(tools, "sea_ice_classification")
        if _has(q, ("melt pond", "meltpond", "pond")):
            _add(tools, "sea_ice_melt_pond")
        if _has(q, ("melt zone", "melt", "melting", "thaw")):
            _add(tools, "sea_ice_melt_zones", horizon_hours=horizon)
        if _has(q, _TREND_WORDS):
            _add(tools, "sea_ice_climate_trend")
        if _has(q, _RISK_WORDS) and (sea_ice or "ice" in q):
            _add(tools, "sea_ice_risk", horizon_hours=horizon)
        if _has(q, _CHANGE_WORDS) and (sea_ice or "ice" in q):
            _add(tools, "sea_ice_change", horizon_hours=horizon)

        if wants_now or "difference" in q or ("observed" in q and "forecast" in q):
            _add(tools, "sea_ice_current")
        if wants_forecast or not tools:
            _add(tools, "sea_ice_forecast", horizon_hours=horizon)
        if "difference" in q or "compared" in q or "versus" in q or "vs" in q:
            _add(tools, "sea_ice_forecast", horizon_hours=horizon)
            _add(tools, "sea_ice_change", horizon_hours=horizon)
        if not tools:
            _add(tools, "sea_ice_forecast", horizon_hours=horizon)

    # --- icebergs --------------------------------------------------------
    if ids:
        a, b = ids[0], (ids[1] if len(ids) > 1 else None)
        if _has(q, _DISTANCE_WORDS) and b:
            _add(tools, "iceberg_distance", iceberg_a=a, iceberg_b=b)
        elif _has(q, ("size", "large", "length", "wide", "how big", "detail")):
            _add(tools, "iceberg_detail", iceberg_id=a)
        else:
            _add(tools, "iceberg_trajectory", iceberg_id=a, horizon_hours=horizon)

    if "iceberg" in q or "berg" in q or _has(q, _MOVEMENT_WORDS):
        if _has(q, _DISTANCE_WORDS) and len(ids) >= 2:
            pass  # already handled above
        elif _has(q, _COUNT_WORDS):
            _add(tools, "iceberg_list")
        elif _has(q, _CLOSE_WORDS):
            wps = None
            if dashboard:
                data = dashboard.model_dump() if hasattr(dashboard, "model_dump") else (dashboard if isinstance(dashboard, dict) else {})
                nav = data.get("navigation") or {}
                sel_route = nav.get("selected_route") or {}
                wps = sel_route.get("waypoints") or sel_route.get("coordinates")
            _add(tools, "closest_iceberg", route_waypoints=wps)
        elif _has(q, _MOVEMENT_WORDS) or "drift" in q:
            target_id = ids[0] if ids else (getattr(dashboard, "selected_iceberg_id", None) or "A23A")
            _add(tools, "iceberg_trajectory",
                 iceberg_id=target_id, horizon_hours=horizon)
        elif not ids:
            _add(tools, "iceberg_list")
        if ids and "detail" not in tools:
            _add(tools, "iceberg_detail", iceberg_id=ids[0])

    # --- routes, fuel, risk ---------------------------------------------
    if _has(q, _ROUTE_WORDS) or _has(q, _FUEL_WORDS) or (_has(q, _RISK_WORDS) and not sea_ice):
        kwargs = _route_kwargs(dashboard)
        _add(tools, "route_details", **kwargs)
        if _has(q, _FUEL_WORDS):
            _add(tools, "fuel_estimate", **kwargs)

    # --- models and data quality ----------------------------------------
    if _has(q, _MODEL_WORDS):
        _add(tools, "model_convergence")
        _add(tools, "model_metrics", pipeline="sea_ice" if ("sea" in q or "ice" in q) else None)

    # --- fleet / places --------------------------------------------------
    if _has(q, _FLEET_WORDS):
        _add(tools, "fleet_reference")

    # --- broad situational questions ------------------------------------
    # An alert question is answered from the alert records the dashboard
    # already sent, so don't bury that explanation in a full data dump.
    if not tools and _has(q, _ALERT_WORDS) and not _has(q, _SUMMARY_WORDS):
        return tools

    if not tools or _has(q, _SUMMARY_WORDS):
        _add(tools, "sea_ice_forecast", horizon_hours=horizon)
        _add(tools, "sea_ice_risk", horizon_hours=horizon)
        _add(tools, "route_details", **_route_kwargs(dashboard))
        _add(tools, "iceberg_list")
        _add(tools, "fleet_reference")

    return tools


class AssistantService:
    """Assistant: answer(question, history, page, dashboard) -> response dict."""

    def llm_status(self) -> dict:
        return {k: v for k, v in resolve_provider().items() if k != "reason"}

    async def _answer_without_data(
        self,
        question: str,
        history: list[dict] | None,
        page: str | None,
        provider_info: dict,
        is_howto: bool,
    ) -> dict:
        """Answer an app-usage or terminology question from knowledge alone.

        No tools run here, so the answer is always about how the product works
        or what a word means, and never mixes in numbers the user didn't ask for.
        """
        provider = provider_info["provider"]
        knowledge_ctx = knowledge.build_knowledge_context(question, page)
        local = (
            knowledge.answer_dashboard_question(question, page)
            if is_howto
            else knowledge.answer_glossary_question(question)
        )

        if provider == "none":
            return {
                "answer": local,
                "sources": [],
                "llm": {"provider": "none", "model": None, "configured": False},
                "demo_mode": False,
                "warnings": [],
                "actions": [],
                "knowledge_used": [],
            }

        ask = (
            "The user is asking how the product works, not for live data."
            if is_howto
            else "The user is asking what a term means, not for live data."
        )
        messages = [
            {"role": "system", "content": prompts.SYSTEM_PROMPT},
            *prompts.build_history_prefix(history),
            {"role": "user", "content": (
                f"{ask}\n\n"
                f"{knowledge_ctx}\n\n"
                f"Question: {question}\n\n"
                "Answer from the knowledge above. Name the exact buttons, panels and labels they "
                "will see. Do not invent numbers."
            )},
        ]
        try:
            text = await asyncio.to_thread(
                run_llm, provider, provider_info["model"], messages
            )
            answer = (text or "").strip() or local
            warnings: list[str] = []
        except AssistantError as exc:
            logger.warning("LLM call failed, falling back to template: %s", exc)
            answer = local
            warnings = [f"LLM call failed ({exc}); answered from templates instead."]

        return {
            "answer": answer,
            "sources": [],
            "llm": {"provider": provider, "model": provider_info["model"], "configured": True},
            "demo_mode": False,
            "warnings": warnings,
            "actions": [],
            "knowledge_used": [],
        }

    async def _answer_from_docs(
        self,
        question: str,
        history: list[dict] | None,
        ctx: ProjectContext,
        provider_info: dict,
    ) -> dict:
        """Answer a question about the project from its own documentation.

        The retrieved sections still ground the answer and the source chips
        still say where it came from, but the offline path now *speaks*
        instead of pasting markdown: ``assistant.briefing`` holds a
        conversational briefing per topic, written from these same documents.
        """
        provider = provider_info["provider"]
        docs_block, used = docs_index.render(question)
        knowledge_ctx = knowledge.build_knowledge_context(question, ctx.page)
        conversation = briefing.build_answer(question, history)

        if not docs_block:
            # Nothing indexed matched. Say so instead of inventing a design.
            local = (
                "I couldn't find anything on that in the project documentation. "
                f"I've indexed {len(docs_index.available_sources())} documents - "
                + ", ".join(docs_index.available_sources())
                + ". I can take you through the architecture, the data and where it "
                  "comes from, the models, the route engine, the voyage simulation, "
                  "the API, or the honest limitations. Which of those did you mean?"
            )
            return {
                "answer": local,
                "sources": [],
                "llm": {"provider": "none", "model": None, "configured": False},
                "demo_mode": False,
                "warnings": [],
                "actions": [],
                "knowledge_used": [],
            }

        if provider == "none":
            return {
                "answer": conversation,
                "sources": [{"name": s, "demo": False, "note": "Project documentation",
                             "status": "ok"} for s in dict.fromkeys(used)],
                "llm": {"provider": "none", "model": None, "configured": False},
                "demo_mode": False,
                "warnings": [],
                "actions": [],
                "knowledge_used": list(dict.fromkeys(used)),
            }

        messages = [
            {"role": "system", "content": prompts.SYSTEM_PROMPT},
            *prompts.build_history_prefix(history),
            {"role": "user", "content": (
                "The user is asking how THIS project is built or what it contains. "
                "Answer only from the documentation retrieved below and from the "
                "product knowledge. Name real files, folders, modules and endpoints. "
                "If the documentation does not cover something, say so.\n\n"
                f"{docs_block}\n\n"
                f"{knowledge_ctx}\n\n"
                f"Question: {question}"
            )},
        ]
        try:
            text = await asyncio.to_thread(run_llm, provider, provider_info["model"], messages)
            answer = (text or "").strip() or conversation
            warnings: list[str] = []
        except AssistantError as exc:
            logger.warning("LLM call failed, falling back to conversation: %s", exc)
            answer = conversation
            warnings = [f"LLM call failed ({exc}); answered from the project "
                        f"documentation instead."]

        return {
            "answer": answer,
            "sources": [{"name": s, "demo": False, "note": "Project documentation",
                         "status": "ok"} for s in dict.fromkeys(used)],
            "llm": {"provider": provider, "model": provider_info["model"], "configured": True},
            "demo_mode": False,
            "warnings": warnings,
            "actions": [],
            "knowledge_used": list(dict.fromkeys(used)),
        }

    # ------------------------------------------------------------------
    def _answer_state(self, question: str, ctx: ProjectContext) -> str:
        """Answer "what am I looking at / where am I" from the live snapshot.

        Only values actually present in the context are stated. Anything missing
        is reported as unknown rather than filled in.
        """
        from assistant.actions import PAGES

        q = question.lower()
        lines: list[str] = []
        page_name = PAGES.get(ctx.page or "", ctx.page)
        if page_name:
            lines.append(f"You're on the {page_name} page.")

        lat, lon = ctx.vessel_position
        journey = ctx.journey
        selected = ctx.navigation.get("selected_route") or {}

        if any(w in q for w in ("horizon", "forecast")):
            lines.append(f"The forecast horizon in effect is {ctx.effective_horizon}h.")
        if "iceberg" in q:
            if ctx.selected_iceberg_id:
                lines.append(f"Iceberg {ctx.selected_iceberg_id} is selected.")
            else:
                lines.append("No iceberg is selected right now.")
        if "route" in q and selected.get("label"):
            lines.append(f"The selected route is {selected['label']}.")
        if any(w in q for w in ("journey", "voyage", "simulation")):
            if not journey:
                lines.append("No voyage has been started yet.")
            else:
                status = journey.get("status", "unknown")
                where = " → ".join(
                    str(x) for x in (journey.get("origin"), journey.get("destination")) if x
                )
                lines.append(f"Voyage status: {status}." + (f" Route: {where}." if where else ""))
        if "position" in q or "where am i" in q or "vessel" in q:
            v_name = ctx.vessel.get("name") or "Polar Explorer"
            v_type = ctx.vessel.get("type") or "Research Vessel"
            v_ice = ctx.vessel.get("ice_class") or "PC5"
            if lat is not None and lon is not None:
                if journey and journey.get("status") == "active":
                    lines.append(
                        f"Vessel {v_name} ({v_type}, Ice Class {v_ice}) is underway at "
                        f"Lat {lat:.4f}°, Lon {lon:.4f}° on voyage {journey.get('origin')} → {journey.get('destination')}."
                    )
                else:
                    lines.append(
                        f"Vessel {v_name} ({v_type}, Ice Class {v_ice}) is currently located at "
                        f"Lat {lat:.4f}°, Lon {lon:.4f}°."
                    )
            else:
                lines.append(f"Vessel {v_name} ({v_type}, Ice Class {v_ice}) is active.")
        if "alert" in q:
            unread = ctx.unread_alert_count
            total = len(ctx.alerts)
            count = unread if unread is not None else total
            if total == 0:
                lines.append("There are currently 0 active hazard alerts in the system.")
            else:
                lines.append(f"There are {count} alert(s) in the log"
                             + (f" ({total} total)." if unread is not None and unread != total
                                else "."))
        if "vessel" in q and ctx.vessel.get("name") and "position" not in q and "where" not in q:
            lines.append(f"Selected vessel: {ctx.vessel['name']} ({ctx.vessel.get('ice_class', 'PC5')}).")
        if not lines:
            lines.append("I don't have any of that loaded in the current session state.")
        return " ".join(lines)

    # ------------------------------------------------------------------
    def _resolve_confirmation(
        self,
        request: Any,
        ctx: ProjectContext,
        provider_info: dict,
    ) -> dict:
        """Turn a Confirm/Cancel click into a single executable action.

        The action is *re-derived* from the original question and re-validated
        against the state the browser has now, rather than trusted from the
        client. The server keeps no pending-action state, so a confirm cannot be
        replayed, forged or applied to a different question.
        """
        llm = {"provider": provider_info["provider"],
               "model": provider_info["model"],
               "configured": provider_info["provider"] != "none"}
        question = request.question
        request_found = action_registry.resolve_actions(question, ctx)
        by_id = {a["id"]: a for a in request_found.actions}

        if request.confirm_action_id:
            action = by_id.get(request.confirm_action_id)
            if action is None:
                return {
                    "answer": (
                        "That action is no longer available - the application state "
                        "changed since I proposed it. "
                        + (" ".join(request_found.rejections)
                           if request_found.rejections else "Please ask me again.")
                    ),
                    "sources": [], "llm": llm, "demo_mode": False,
                    "warnings": [], "actions": [],
                    "knowledge_used": [],
                }
            # needs_confirmation is cleared: the user has now confirmed.
            action = {**action, "needs_confirmation": False}
            return {
                "answer": f"Confirmed - {action['label']}.",
                "sources": [], "llm": llm, "demo_mode": False,
                "warnings": [], "actions": [action],
                "knowledge_used": [],
            }

        if request.denied_action_ids:
            return {
                "answer": "Cancelled - I haven't changed anything.",
                "sources": [], "llm": llm, "demo_mode": False,
                "warnings": [], "actions": [],
                "knowledge_used": [],
            }

        return {
            "answer": "Nothing to confirm.",
            "sources": [], "llm": llm, "demo_mode": False,
            "warnings": [], "actions": [], "knowledge_used": [],
        }

    # ------------------------------------------------------------------
    async def answer(
        self,
        request: Any,
    ) -> dict:
        """Answer one chat turn.

        ``request`` is an ``AssistantChatRequest``. The order of the branches
        matters: confirmations are settled first, then questions about the
        project itself, then product-usage/terminology, and only then questions
        that need live data.
        """
        question = request.question.strip()
        ctx = ProjectContext.from_request(request)
        provider_info = resolve_provider()
        provider = provider_info["provider"]
        history = [m.model_dump() for m in request.history[-MAX_HISTORY:]] \
            if getattr(request, "history", None) else []
        horizon = ctx.effective_horizon

        # 1. A Confirm/Cancel click on something the assistant just proposed.
        if request.confirm_action_id or request.denied_action_ids:
            return self._resolve_confirmation(request, ctx, provider_info)

        # 2. A greeting or "thanks" is a social turn. Answer it and stop -
        #    running the whole tool battery for "hi" wastes seconds and then
        #    dumps numbers nobody asked for.
        # 2. A greeting or "thanks" is a social turn. Answer it and stop -
        #    running the whole tool battery for "hi" wastes seconds and then
        #    dumps numbers nobody asked for.
        if _SOCIAL_RE.match(question):
            from assistant.actions import PAGES

            page = PAGES.get(ctx.page or "")
            where = f" You're on the {page} page." if page else ""
            if _THANKS_RE.match(question):
                text = (
                    "Any time. Ask me about any panel, term or number whenever you "
                    "need it."
                )
            elif _ACK_RE.match(question):
                # Agreement is a reply to something I already said. Re-introducing
                # myself here would read like I lost the thread, so pick the
                # conversation back up instead.
                text = (
                    "Good - where do you want to go next? I can read you the live "
                    "numbers, explain how any of it is calculated, take you through "
                    "how the system is built, or open a page and run an action."
                )
            else:
                text = (
                    f"Hi, I'm Raga - I work inside this thing, so I can tell you "
                    f"what's on screen right now, explain any panel or term, walk "
                    f"you through the voyage, or talk you through how the whole "
                    f"system is built.{where}\n\n"
                    f"Try asking what this project is, how the route engine scores "
                    f"risk, how accurate the models are, or what the sea-ice "
                    f"forecast looks like for the next 48 hours. I can also open "
                    f"pages and run actions for you."
                )
            return {
                "answer": text,
                "sources": [], "demo_mode": False, "warnings": [],
                "llm": {"provider": "none", "model": None, "configured": False},
                "actions": [], "knowledge_used": [],
            }

        # 3. Something this application genuinely cannot do ("pause the
        #    voyage"). Answer that plainly - running data tools and burying the
        #    refusal under a forecast would be both useless and dishonest.
        refusal = action_registry.unsupported_answer(question)
        if refusal:
            return {
                "answer": refusal,
                "sources": [], "demo_mode": False, "warnings": [],
                "llm": {"provider": "none", "model": None, "configured": False},
                "actions": [], "knowledge_used": [],
            }

        # 4. "What is this project?" / "how does the route engine work?" -
        #    answered from the repository's own documentation.
        #
        #    This sits *before* the state and action branches, so it has to
        #    stand aside for them: "advance 2 hours" and "which page am I on?"
        #    both contain words a project briefing would recognise, and
        #    answering either with documentation instead of doing the thing
        #    (or reporting the state) would be wrong.
        is_live_query = any(k in question.lower() for k in (
            "three available routes", "three routes", "3 routes", "available routes",
            "why is this route recommended", "why this route",
            "which iceberg is nearest", "nearest iceberg", "closest iceberg",
            "what alerts are currently active", "active alerts",
            "current sea-ice", "current sea ice", "sea-ice concentration", "sea ice concentration",
            "selected iceberg trajectory", "iceberg trajectory", "trajectory",
        ))
        action_intent = action_registry.resolve_actions(question, ctx)
        asks_for_action = action_intent is not None and action_intent.recognised
        asks_about_state = (
            not asks_for_action
            and not is_live_query
            and any(w in question.lower() for w in _SELF_STATE_WORDS)
            and not any(k in question.lower() for k in ("nearest", "closest", "near to", "close to", "distance"))
        )
        if (
            looks_like_docs_question(question, history)
            and not asks_about_state
            and not asks_for_action
            and not is_live_query
        ):
            return await self._answer_from_docs(question, history, ctx, provider_info)

        # 5. "How do I plan a route?" and "what is a growler?" need no data.
        is_howto = prompts.looks_like_howto(question) and not is_live_query
        is_definition = prompts.looks_like_definition(question) and not is_live_query
        if is_howto or is_definition:
            out = await self._answer_without_data(
                question, history, ctx.page, provider_info, is_howto
            )
            out.setdefault("actions", [])
            out.setdefault("knowledge_used", [])
            return out

        # 6. The user asked about their own current situation.
        if asks_about_state:
            return {
                "answer": self._answer_state(question, ctx),
                "sources": [], "demo_mode": False, "warnings": [],
                "llm": {"provider": "none", "model": None, "configured": False},
                "actions": [], "knowledge_used": [],
            }

        # 7. An action request that turns out to be impossible right now. Say
        #    why, and do not answer it with an unrelated data dump.
        if (
            action_intent is not None
            and action_intent.recognised
            and not action_intent.actions
        ):
            return {
                "answer": " ".join(action_intent.rejections) or (
                    "I can't do that with the application in its current state."
                ),
                "sources": [], "demo_mode": False, "warnings": [],
                "llm": {"provider": "none", "model": None, "configured": False},
                "actions": [], "knowledge_used": [],
            }

        # 7. Live data. Tools are blocking (pandas / netCDF / SQLAlchemy), so
        #    run them in worker threads to keep the event loop free.
        selected = pick_tools(question, horizon, request.dashboard)
        tool_results = await asyncio.gather(
            *(asyncio.to_thread(TOOLS[name], **kwargs) for name, kwargs in selected)
        )
        tool_results = [r for r in tool_results if r is not None]

        if any(term in question.lower() for term in ("alert", "notification")):
            tool_results.append({
                "name": "current_alerts",
                "status": "ok",
                "note": "Alert details currently displayed in the dashboard.",
                "data": ctx.alerts,
            })
        if not any(r.get("name") == "datasets_status" for r in tool_results):
            tool_results.append(await asyncio.to_thread(datasets_status))

        # Record what is real and what is synthetic, so the answer and the
        # prompt both carry the same honesty labels.
        for result in tool_results:
            if result.get("demo"):
                ctx.note_demo(result["name"])

        context_report = prompts.build_context_report(tool_results)
        sources = [
            {
                "name": r["name"],
                "demo": bool(r.get("demo")),
                "note": r.get("note"),
                "status": r.get("status", "ok"),
            }
            for r in tool_results
        ]

        demo_any = any(r.get("demo") for r in tool_results if r.get("status") == "ok")
        real_any = any((not r.get("demo")) for r in tool_results if r.get("status") == "ok")
        warnings: list[str] = []

        # 8. Actions the user asked for, validated against the live state.
        if action_intent and action_intent.actions:
            return await self._answer_with_actions(
                question, action_intent.actions, action_intent.rejections, history, ctx,
                context_report, provider_info, sources, demo_any, real_any,
            )

        if provider == "none":
            answer = prompts.build_fallback(question, tool_results, ctx.page)
            llm = {"provider": "none", "model": None, "configured": False}
        else:
            messages = [
                {"role": "system", "content": prompts.SYSTEM_PROMPT},
                *prompts.build_history_prefix(history),
                {"role": "user", "content": prompts.build_user_prompt(
                    question, context_report, ctx.page
                )},
            ]
            try:
                text = await asyncio.to_thread(
                    run_llm, provider, provider_info["model"], messages
                )
                answer = (text or "").strip() or prompts.build_fallback(
                    question, tool_results, ctx.page
                )
                llm = {"provider": provider, "model": provider_info["model"], "configured": True}
            except AssistantError as exc:
                logger.warning("LLM call failed, falling back to template: %s", exc)
                answer = prompts.build_fallback(question, tool_results, ctx.page)
                llm = {"provider": provider, "model": provider_info["model"], "configured": True}
                warnings.append(f"LLM call failed ({exc}); answered from templates instead.")

        answer = self._append_rejections(
            answer, action_intent.rejections if action_intent else []
        )
        self._add_data_warnings(warnings, demo_any, real_any)

        return {
            "answer": answer,
            "sources": sources,
            "llm": llm,
            "demo_mode": demo_any,
            "warnings": warnings,
            "actions": [],
            "knowledge_used": [r["name"] for r in tool_results],
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _append_rejections(answer: str, rejections: list[str]) -> str:
        if not rejections:
            return answer
        return answer.rstrip() + "\n\n" + " ".join(rejections)

    @staticmethod
    def _add_data_warnings(warnings: list[str], demo_any: bool, real_any: bool) -> None:
        if demo_any and not real_any:
            warnings.append(
                "All data behind this answer is synthetic demo data. It carries no "
                "information about real-world conditions and must not be used for "
                "actual navigation decisions."
            )
        if real_any:
            warnings.append(
                "Predictions are model estimates; no route is guaranteed safe."
            )

    # ------------------------------------------------------------------
    async def _answer_with_actions(
        self,
        question: str,
        actions: list[dict[str, Any]],
        rejections: list[str],
        history: list[dict] | None,
        ctx: ProjectContext,
        context_report: str,
        provider_info: dict,
        sources: list[dict],
        demo_any: bool,
        real_any: bool,
    ) -> dict:
        """Propose validated actions for the browser to carry out.

        The assistant never performs them itself; it returns them as data and
        the frontend runs the matching existing control.
        """
        provider = provider_info["provider"]
        lines = []
        for action in actions:
            if action.get("needs_confirmation"):
                lines.append(action.get("confirmation_prompt", action["label"]))
            else:
                lines.append(f"{action['label']}.")
        local = " ".join(lines)
        if rejections:
            local = local + " " + " ".join(rejections)

        if provider == "none":
            return {
                "answer": local,
                "sources": sources,
                "llm": {"provider": "none", "model": None, "configured": False},
                "demo_mode": demo_any,
                "warnings": [],
                "actions": actions,
                "knowledge_used": [],
            }

        messages = [
            {"role": "system", "content": prompts.SYSTEM_PROMPT},
            *prompts.build_history_prefix(history),
            {"role": "user", "content": (
                "The user asked the assistant to perform an action in the running "
                "application. The actions below have already been validated against "
                "the live state. Briefly say what you are about to do and, for each "
                "action that needs confirmation, ask the user to confirm. Do not "
                "claim the action has already happened.\n\n"
                f"Proposed actions: {json.dumps(actions, indent=2, default=str)}\n\n"
                f"{context_report}\n\n"
                f"Question: {question}"
            )},
        ]
        warnings: list[str] = []
        try:
            text = await asyncio.to_thread(run_llm, provider, provider_info["model"], messages)
            answer = (text or "").strip() or local
        except AssistantError as exc:
            logger.warning("LLM call failed, falling back to template: %s", exc)
            answer = local
            warnings = [f"LLM call failed ({exc}); described the action directly instead."]

        self._add_data_warnings(warnings, demo_any, real_any)
        return {
            "answer": answer,
            "sources": sources,
            "llm": {"provider": provider, "model": provider_info["model"], "configured": True},
            "demo_mode": demo_any,
            "warnings": warnings,
            "actions": actions,
            "knowledge_used": [],
        }


assistant_service = AssistantService()
