import asyncio

from main import lifespan


def test_startup_does_not_eagerly_seed_or_warm_routes(monkeypatch):
    calls = []

    def fake_init_db():
        calls.append("db")

    monkeypatch.setattr("main.init_db", fake_init_db)

    async def _run():
        async with lifespan(None):
            pass

    asyncio.run(_run())

    assert calls == ["db"]
