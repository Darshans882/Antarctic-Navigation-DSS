from assistant.assistant_service import pick_tools
from assistant.knowledge import build_knowledge_context, matching_glossary
from assistant.prompts import build_fallback, looks_like_definition, looks_like_howto


def test_greeting_introduces_raga():
    assert build_fallback("Hi", []).startswith("Hi, I'm Raga.")


def test_which_question_is_not_treated_as_a_greeting():
    answer = build_fallback("Which model is available?", [])

    assert "Hi, I'm Raga." not in answer
    assert "I don't have a number for that one" in answer


def test_alert_question_explains_current_alert():
    answer = build_fallback(
        "Why did this alert appear?",
        [{
            "name": "current_alerts",
            "data": [{
                "title": "Nearest Iceberg Alert",
                "message": "HIGH: DEMO-B001 detected 12 km from the route.",
                "type": "iceberg",
                "severity": "high",
                "recommended_action": "Monitor iceberg movement.",
                "distance_km": 12.0,
            }],
        }],
    )

    assert "Nearest Iceberg Alert" in answer
    assert "DEMO-B001" in answer
    assert "Monitor iceberg movement." in answer


def test_alert_question_without_details_does_not_make_up_a_reason():
    answer = build_fallback("Why did this alert appear?", [])

    assert "can't see the alert details" in answer


# --------------------------------------------------------------------------
# Dashboard how-to questions
# --------------------------------------------------------------------------
def test_how_to_questions_are_routed_to_the_guide():
    assert looks_like_howto("How do I plan a route?")
    assert looks_like_howto("how do i use the dashboard")
    assert looks_like_howto("walk me through the iceberg page")
    assert looks_like_howto("what does the horizon dropdown do")
    assert looks_like_howto("where do I find the alerts")


def test_data_questions_are_not_mistaken_for_how_to():
    assert not looks_like_howto("What is the current sea-ice concentration?")
    assert not looks_like_howto("How many icebergs are tracked?")
    assert not looks_like_howto("Which iceberg is closest to the vessel?")
    assert not looks_like_howto("What is the estimated keel depth?")


def test_how_to_answer_never_asks_for_a_number():
    answer = build_fallback("How do I plan a route?", [], page="planner")

    assert "Start Journey" in answer
    assert "Advance 2 Hours" in answer
    assert "Recalculate Route" in answer


def test_how_to_answer_uses_the_current_page_when_the_question_is_vague():
    answer = build_fallback("How does this page work?", [], page="alerts")

    assert "Mark All as Read" in answer
    assert "severity" in answer.lower()


def test_terminology_question_is_answered_from_the_glossary():
    answer = build_fallback("What is sea ice concentration?", [])

    assert "fraction" in answer.lower() or "covered by ice" in answer.lower()


def test_fallback_never_addresses_the_user_as_captain():
    answers = [
        build_fallback("What is the 48 hour sea-ice forecast?", [{
            "name": "sea_ice_forecast",
            "status": "ok",
            "demo": False,
            "data": {
                "horizon_hours": 48, "model": "persistence", "mean_concentration": 0.42,
                "max_concentration": 0.91, "coverage_pct": 88.0,
                "model_used_real": False, "skill_note": "Baseline only.",
            },
        }]),
        build_fallback("Why was this route selected?", [{
            "name": "route_details",
            "status": "ok",
            "demo": False,
            "data": {
                "route_id": "abc", "vessel_id": "polar_explorer", "preference": "recommended",
                "recommended": {
                    "distance_km": 812.0, "distance_nm": 438.0, "travel_time_hours": 67.0,
                    "fuel_tons": 210.5, "risk_level": "low", "risk_score": 0.2, "warnings": [],
                },
                "alternatives": [],
            },
        }]),
    ]

    for answer in answers:
        assert "Captain" not in answer
    assert "42.0%" in answers[0]


# --------------------------------------------------------------------------
# Knowledge retrieval
# --------------------------------------------------------------------------
def test_knowledge_context_always_includes_the_orientation():
    context = build_knowledge_context("What is the total mass of Antarctica?", None)

    assert "Cryosphere Routing Optimization" in context


def test_knowledge_context_pulls_in_the_relevant_page():
    context = build_knowledge_context("how do I use the journey controls", "planner")

    assert "Journey Controls" in context
    assert "Advance 2 Hours" in context


def test_knowledge_context_includes_plain_language_definitions():
    context = build_knowledge_context("what is a growler", None)

    assert "growler" in context.lower()


def test_knowledge_context_tells_the_model_where_the_user_is():
    context = build_knowledge_context("why did this happen", "icebergs")

    assert "where the user is right now" in context
    assert "icebergs" in context


def test_glossary_lookup_finds_mentioned_terms():
    hits = dict(matching_glossary("how thick is multi-year ice and what is the keel"))

    assert "multi-year ice" in hits
    assert "keel" in hits


# --------------------------------------------------------------------------
# Definition questions
# --------------------------------------------------------------------------
def test_definition_questions_are_recognised():
    assert looks_like_definition("What is a growler?")
    assert looks_like_definition("what is multi-year ice")
    assert looks_like_definition("define keel depth")


def test_data_questions_are_not_treated_as_definitions():
    assert not looks_like_definition("What is the current sea-ice concentration?")
    assert not looks_like_definition("How thick is the ice right now?")
    assert not looks_like_definition("How do I use the horizon dropdown?")


def test_definition_wins_over_irrelevant_tool_data():
    answer = build_fallback("What is a growler?", [{
        "name": "sea_ice_forecast",
        "status": "ok",
        "demo": False,
        "data": {
            "horizon_hours": 24, "model": "persistence", "mean_concentration": 0.42,
            "max_concentration": 0.91, "coverage_pct": 88.0,
            "model_used_real": False, "skill_note": "Baseline only.",
        },
    }])

    assert "growler" in answer.lower()
    assert "42.0%" not in answer


# --------------------------------------------------------------------------
# Tool routing
# --------------------------------------------------------------------------
def _tool_names(question: str) -> list[str]:
    return [name for name, _ in pick_tools(question, 24)]


def test_specific_ice_questions_pick_the_specific_tool():
    assert _tool_names("What is the estimated keel depth?") == ["sea_ice_keel_depth"]
    assert _tool_names("How thick is the ice?") == ["sea_ice_thickness"]
    assert _tool_names("What are the types of ice?") == ["sea_ice_classification"]
    assert "sea_ice_current" in _tool_names("What is the current sea-ice concentration?")
    assert "sea_ice_forecast" in _tool_names("What is the 48 hour sea-ice forecast?")


def test_iceberg_questions_pick_the_iceberg_tools():
    assert _tool_names("Where is DEMO-B001 drifting?") == ["iceberg_trajectory", "iceberg_detail"]
    assert _tool_names("How far apart are DEMO-B001 and DEMO-B002?") == ["iceberg_distance"]
    assert "closest_iceberg" in _tool_names("Which iceberg is closest to the vessel?")
    assert "iceberg_list" in _tool_names("How many icebergs are tracked?")


def test_route_questions_pick_the_route_tools():
    assert "route_details" in _tool_names("Why was this route selected?")
    assert "fuel_estimate" in _tool_names("How much fuel would I burn?")


def test_model_questions_pick_the_model_tools():
    assert "model_convergence" in _tool_names("How accurate is the model?")
    assert "model_metrics" in _tool_names("What is the MAE of the forecast?")


def test_place_questions_pick_the_reference_table():
    assert "fleet_reference" in _tool_names("Which port should I leave from?")


def test_broad_questions_get_a_full_situation_picture():
    names = _tool_names("Give me a situation summary")

    assert "sea_ice_forecast" in names
    assert "sea_ice_risk" in names
    assert "route_details" in names
    assert "iceberg_list" in names


def test_alert_questions_leave_the_answer_to_the_alert_records():
    # The dashboard already sends the alert details, so a sea-ice forecast
    # dump would bury the actual answer.
    assert _tool_names("Why did this alert appear?") == []
    assert _tool_names("What is the highest severity alert?") == []


def test_alert_summary_questions_still_get_the_wider_picture():
    names = _tool_names("Give me a summary of the alerts and how bad the ice is")

    assert "sea_ice_forecast" in names
    assert "iceberg_list" in names
