from navigation.route_optimizer import RouteOptimizer


def test_alternatives_are_bounded_and_fast(monkeypatch):
    optimizer = RouteOptimizer.__new__(RouteOptimizer)
    calls = []

    def fake_optimize(self, *args, **kwargs):
        preference = kwargs.get("preference") or args[4]
        calls.append(preference)
        return {"preference": preference, "coordinates": [(0.0, 0.0), (1.0, 1.0)]}

    monkeypatch.setattr(RouteOptimizer, "optimize", fake_optimize)

    results = optimizer.alternatives(0.0, 0.0, 1.0, 1.0, excluded="recommended", max_results=1)

    assert len(results) == 1
    assert results[0]["preference"] == "shortest"
    assert calls == ["shortest"]
