"""Tests for project-aware behaviour: live state, actions, and documentation.

These cover the three things that make the assistant project-aware rather than
a FAQ: it reads the state the browser actually sent, it proposes only validated
actions against that state, and it answers questions about the project itself
from the repository's own documentation.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from main import app
from schemas.models import AssistantChatRequest, DashboardState

client = TestClient(app)


def _dashboard(**overrides) -> dict:
    """A realistic 'user is on the Navigation Dashboard mid-voyage' payload."""
    data = {
        "page": "planner",
        "sea_ice_horizon": 48,
        "selected_iceberg_id": "DEMO-B001",
        "unread_alert_count": 2,
        "alert_context": [
            {
                "title": "Growler ahead",
                "message": "Small growler detected near the route",
                "type": "growler",
                "severity": "warning",
                "read": False,
            }
        ],
        "navigation": {
            "journey_mode": "sailing",
            "live_lat": "-57.2",
            "live_lon": "-62.4",
            "port_id": "Punta Arenas",
            "center_id": "Rothera Station",
            "vessel_id": "V1",
            "selected_route": {
                "id": "r1",
                "label": "Main Route",
                "risk_level": "moderate",
                "distance_nm": 420.0,
                "is_recommended": True,
            },
            "routes_available": [
                {
                    "id": "r1",
                    "label": "Main Route",
                    "risk_level": "moderate",
                    "distance_nm": 420.0,
                    "is_recommended": True,
                }
            ],
            "journey": {
                "journey_id": "J1",
                "status": "active",
                "origin": "Punta Arenas",
                "destination": "Rothera Station",
                "vessel_lat": -57.2,
                "vessel_lon": -62.4,
                "progress_percent": 31.5,
            },
        },
        "vessel": {
            "vessel_id": "V1",
            "name": "MV Akademik",
            "lat": -57.2,
            "lon": -62.4,
            "speed_known": False,
        },
    }
    data.update(overrides)
    return data


def ask(question: str, dashboard: dict | None = None, **extra) -> dict:
    payload = {"question": question, "history": [], "horizon_hours": 24}
    if dashboard is not None:
        payload["dashboard"] = dashboard
    payload.update(extra)
    response = client.post("/api/assistant/chat", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def action_types(body: dict) -> list[str]:
    return [a["type"] for a in body.get("actions", [])]


# ----------------------------------------------------------------------
# Current application state
# ----------------------------------------------------------------------
class TestCurrentState:
    def test_reports_the_page_the_user_is_on(self):
        body = ask("Which page am I on?", _dashboard())
        assert "Navigation Dashboard" in body["answer"]

    def test_reports_the_horizon_on_screen(self):
        body = ask("What is the current horizon?", _dashboard(page="sea-ice"))
        assert "48h" in body["answer"]

    def test_reports_the_selected_iceberg(self):
        body = ask("Which iceberg is selected?", _dashboard())
        assert "DEMO-B001" in body["answer"]

    def test_reports_the_selected_route(self):
        body = ask("Which route is currently selected?", _dashboard())
        assert "Main Route" in body["answer"]

    def test_reports_journey_status(self):
        body = ask("What is my journey status?", _dashboard())
        assert "active" in body["answer"]

    def test_reports_vessel_position(self):
        body = ask("What is my current position?", _dashboard())
        assert "-57.2" in body["answer"]

    def test_reports_alert_count(self):
        body = ask("How many unread alerts are there?", _dashboard())
        assert "2" in body["answer"]

    def test_says_when_no_voyage_has_started(self):
        dashboard = _dashboard()
        dashboard["navigation"]["journey"] = None
        body = ask("What is my journey status?", dashboard)
        assert "no voyage" in body["answer"].lower()

    def test_does_not_invent_a_speed(self):
        """The app reports speed as unknown; the assistant must not guess it."""
        body = ask("How fast is my vessel moving?", _dashboard())
        assert "knot" not in body["answer"].lower()


# ----------------------------------------------------------------------
# Actions
# ----------------------------------------------------------------------
class TestActions:
    def test_navigates_to_a_page(self):
        body = ask("Go to the alerts page", _dashboard())
        assert action_types(body) == ["navigate"]
        assert body["actions"][0]["params"] == {"page": "alerts"}

    def test_changes_the_forecast_horizon(self):
        body = ask("Change the horizon to 72 hours", _dashboard())
        assert action_types(body) == ["set_horizon"]
        assert body["actions"][0]["params"] == {"hours": 72}

    def test_showing_a_forecast_also_opens_the_page(self):
        """Setting a horizon the user cannot see would be a silent no-op."""
        body = ask("Show me the 72 hour forecast", _dashboard())
        assert action_types(body) == ["navigate", "set_horizon"]

    def test_selects_an_iceberg(self):
        body = ask("Select iceberg DEMO-B001", _dashboard())
        assert action_types(body) == ["select_iceberg"]
        assert body["actions"][0]["params"] == {"iceberg_id": "DEMO-B001"}

    def test_selects_a_route(self):
        body = ask("Select the recommended route", _dashboard())
        assert action_types(body) == ["select_route"]
        assert body["actions"][0]["params"]["is_recommended"] is True

    def test_marks_alerts_read(self):
        body = ask("Mark all alerts as read", _dashboard())
        assert action_types(body) == ["mark_alerts_read"]

    def test_consequential_actions_require_confirmation(self):
        body = ask("Recalculate the route", _dashboard())
        action = body["actions"][0]
        assert action["type"] == "recalculate_route"
        assert action["needs_confirmation"] is True
        assert "current position" in action["confirmation_prompt"]

    def test_rejects_a_horizon_the_page_does_not_offer(self):
        body = ask("Set forecast to 96 hours", _dashboard())
        assert body["actions"] == []
        assert "96h isn't one of the horizons" in body["answer"]

    def test_rejects_starting_a_voyage_that_is_already_running(self):
        body = ask("Start the voyage", _dashboard())
        assert body["actions"] == []
        assert "already running" in body["answer"]

    def test_rejects_advancing_with_no_voyage(self):
        dashboard = _dashboard()
        dashboard["navigation"]["journey"] = None
        body = ask("Advance 2 hours", dashboard)
        assert body["actions"] == []
        assert "no voyage running" in body["answer"].lower()

    def test_no_action_for_a_plain_question(self):
        """Asking about a route must never start one."""
        body = ask("Why is this route risky?", _dashboard())
        assert body["actions"] == []


class TestHonestRefusals:
    def test_pause_journey_is_supported(self):
        body = ask("Pause the journey", _dashboard())
        assert action_types(body) == ["pause_journey"]

    def test_export_is_refused(self):
        body = ask("Save the route as a file", _dashboard())
        assert body["actions"] == []
        assert "no save, export or delete" in body["answer"]


# ----------------------------------------------------------------------
# Confirmation
# ----------------------------------------------------------------------
class TestConfirmation:
    def test_confirming_returns_an_executable_action(self):
        body = ask("Recalculate the route", _dashboard(),
                   confirm_action_id="recalculate_route:0")
        assert action_types(body) == ["recalculate_route"]
        assert body["actions"][0]["needs_confirmation"] is False

    def test_cancelling_changes_nothing(self):
        body = ask("Recalculate the route", _dashboard(),
                   denied_action_ids=["recalculate_route:0"])
        assert body["actions"] == []
        assert "cancelled" in body["answer"].lower()

    def test_a_forged_action_id_is_refused(self):
        """A client cannot name an action that was never proposed."""
        body = ask("Recalculate the route", _dashboard(),
                   confirm_action_id="start_journey:0")
        assert body["actions"] == []

    def test_confirmation_is_bound_to_the_original_question(self):
        """An id from one question cannot be confirmed against another."""
        body = ask("Go to the alerts page", _dashboard(),
                   confirm_action_id="recalculate_route:0")
        assert body["actions"] == []

    def test_confirmation_is_revalidated_against_current_state(self):
        """State that changed since the proposal invalidates it."""
        dashboard = _dashboard()
        dashboard["navigation"]["journey"] = None
        body = ask("Recalculate the route", dashboard,
                   confirm_action_id="recalculate_route:0")
        assert body["actions"] == []


class TestActionResult:
    def test_reports_success_only_after_the_browser_confirms(self):
        response = client.post("/api/assistant/action-result", json={
            "action_id": "recalculate_route:0",
            "type": "Recalculate the route",
            "success": True,
            "message": "Recalculate the route",
        })
        assert response.status_code == 200
        assert "Done" in response.json()["answer"]

    def test_reports_failure_honestly(self):
        response = client.post("/api/assistant/action-result", json={
            "action_id": "recalculate_route:0",
            "type": "Recalculate the route",
            "success": False,
            "message": "no viable route from that position",
        })
        assert response.status_code == 200
        answer = response.json()["answer"]
        assert "didn't complete" in answer
        assert "no viable route" in answer


# ----------------------------------------------------------------------
# Project documentation
# ----------------------------------------------------------------------
class TestDocumentation:
    def test_answers_from_project_documentation(self):
        body = ask("Explain the complete architecture of this project")
        assert body["actions"] == []
        assert any("docs/" in s or "README" in s for s in body["knowledge_used"])

    def test_names_real_project_documents(self):
        body = ask("What datasets does this project use?")
        assert any("datasets.md" in s for s in body["knowledge_used"])

    def test_architecture_answer_mentions_the_real_stack(self):
        body = ask("What is this project?")
        lowered = body["answer"].lower()
        assert "react" in lowered or "fastapi" in lowered

    def test_greetings_do_not_run_tools_or_pull_documentation(self):
        body = ask("hi")
        assert body["knowledge_used"] == []
        assert body["sources"] == []
        assert "Raga" in body["answer"]


# ----------------------------------------------------------------------
# Natural conversation about the project
# ----------------------------------------------------------------------
class TestConversationalBriefing:
    """The project briefing has to read like a person, not a search result."""

    def test_does_not_dump_raw_markdown_or_a_disclaimer(self):
        body = ask("What is this project?")
        answer = body["answer"]
        # The old behaviour pasted "[docs: file - Section]" blocks and told the
        # user no language model was configured.
        assert "[docs:" not in answer
        assert "no language model" not in answer.lower()
        assert "verbatim" not in answer.lower()

    def test_overview_covers_the_whole_system(self):
        answer = ask("What is this project?")["answer"].lower()
        for expected in ("sea ice", "iceberg", "route", "fastapi", "react"):
            assert expected in answer, f"overview never mentions {expected!r}"

    def test_asks_for_everything_gets_the_overview(self):
        body = ask("Tell me everything about this project")
        assert "sea ice" in body["answer"].lower()
        assert body["actions"] == []

    @pytest.mark.parametrize(
        "question, expected",
        [
            ("What datasets does it use?", "copernicus"),
            ("How do the models work?", "convlstm"),
            ("How does the route engine score risk?", "riskengine"),
            ("What are the honest limitations?", "synthetic"),
            ("How do I run it?", "run.ps1"),
            ("What is the api surface?", "openapi"),
            ("How is the frontend built?", "vite"),
        ],
    )
    def test_each_area_answers_from_that_area(self, question, expected):
        assert expected in ask(question)["answer"].lower()

    def test_followup_goes_deeper_instead_of_repeating(self):
        first = ask("What is this project?")["answer"]
        history = [
            {"role": "user", "content": "What is this project?"},
            {"role": "assistant", "content": first},
        ]
        deeper = ask("tell me more", _dashboard(), history=history)["answer"]
        assert deeper != first
        assert "backend/main.py" in deeper

    def test_followup_naming_a_new_topic_switches_topic(self):
        history = [
            {"role": "user", "content": "How does the route engine score risk?"},
            {"role": "assistant", "content": "..."},
        ]
        body = ask("and the models?", _dashboard(), history=history)
        # "and the models?" names a subject, so it is a switch, not a request
        # for more of the same thing.
        assert "convlstm" in body["answer"].lower()

    def test_bare_followup_without_history_still_answers(self):
        body = ask("tell me more")
        assert body["answer"].strip()

    def test_real_question_is_not_mistaken_for_a_followup(self):
        # "how does ...?" is a genuine question, not a bare "how?".
        assert "riskengine" in ask("How does the route engine score risk?")[
            "answer"
        ].lower()

    def test_agreement_does_not_restart_the_conversation(self):
        body = ask("yes")
        # Re-introducing myself in reply to "yes" reads like losing the thread.
        assert "I'm Raga" not in body["answer"]

    def test_thanks_is_acknowledged_briefly(self):
        assert "any time" in ask("thanks")["answer"].lower()

    def test_no_control_characters_leak_into_answers(self):
        # Windows paths like .\run.ps1 must survive as text, not as \r / \n.
        for question in ("How do I run it?", "What is this project?"):
            answer = ask(question)["answer"]
            assert not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", answer)

    def test_answers_are_plain_prose_not_sections(self):
        answer = ask("What is this project?")["answer"]
        assert "```" not in answer
        assert not answer.lstrip().startswith("#")

    def test_docs_questions_carry_sources_and_stay_action_free(self):
        body = ask("What is this project?")
        assert body["actions"] == []
        assert any("docs/" in s or "README" in s for s in body["knowledge_used"])


# ----------------------------------------------------------------------
# Context building
# ----------------------------------------------------------------------
class TestProjectContext:
    def test_page_horizon_beats_the_request_default(self):
        ctx = _context(_dashboard(page="sea-ice", sea_ice_horizon=72))
        assert ctx.effective_horizon == 72

    def test_journey_position_wins_over_the_planner_position(self):
        ctx = _context(_dashboard())
        lat, lon = ctx.vessel_position
        assert (lat, lon) == (-57.2, -62.4)

    def test_no_position_reports_none_rather_than_guessing(self):
        dashboard = _dashboard()
        dashboard["navigation"]["live_lat"] = None
        dashboard["navigation"]["live_lon"] = None
        dashboard["navigation"]["journey"] = None
        dashboard["vessel"] = {"vessel_id": "V1", "name": "MV Akademik", "speed_known": False}
        assert _context(dashboard).vessel_position == (None, None)

    def test_speed_is_never_rendered_when_unknown(self):
        """A speed the app calls unknown must not survive into the prompt."""
        dashboard = _dashboard()
        dashboard["vessel"]["speed_knots"] = 12.5
        rendered = _context(dashboard).as_dict()["vessel"]
        assert rendered.get("speed_knots") is None

    def test_alerts_are_carried_through(self):
        assert len(_context(_dashboard()).alerts) == 1


def _context(dashboard: dict):
    from assistant.project_context import ProjectContext

    return ProjectContext.from_request(
        AssistantChatRequest(question="x", dashboard=DashboardState(**dashboard))
    )
