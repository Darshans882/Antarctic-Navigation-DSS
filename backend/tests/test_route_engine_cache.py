from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np

from services.route_engine import build_route_engine


class FakeGrid:
    def __init__(self):
        self.nlat = 1
        self.nlon = 1
        self.lats = np.array([0.0])
        self.lons = np.array([0.0])
        self.land_mask = np.zeros((1, 1), dtype=bool)
        self.lat_min = -90.0
        self.lat_max = 90.0
        self.lon_min = -180.0
        self.lon_max = 180.0
        self.resolution = 1.0

    def contains(self, lat, lon):
        return True

    def set_land_mask(self, mask):
        self.land_mask = np.asarray(mask, dtype=bool)


class FakeRiskEngine:
    def __init__(self, grid, config):
        self.grid = grid
        self.config = config
        self.blocked_mask = np.zeros((1, 1), dtype=bool)
        self.notes = []

    def add_sea_ice(self, lat, lon, concentration):
        return None

    def add_icebergs(self, icebergs):
        return None

    def add_weather_severity(self, weather):
        return None

    def set_vessel_constraints(self, vessel):
        return None

    def apply_iceberg_hard_block(self):
        return None

    def apply_sea_ice_hazard_blocks(self):
        return None

    def compute_total(self):
        return None

    def hazard_config(self):
        return {}

    def explanation(self):
        return ""


def test_build_route_engine_reuses_cache(monkeypatch):
    calls = {"snapshot": 0}

    def fake_snapshot(ts, config):
        calls["snapshot"] += 1
        return {
            "_classification": "real",
            "_sea_ice": {"lat": np.array([0.0]), "lon": np.array([0.0]), "concentration": np.array([0.0])},
            "_icebergs": {"classification": "real", "icebergs": [], "trained_used": False, "model": "persistence"},
            "_weather": np.zeros((1, 1), dtype=float),
            "_weather_ok": False,
        }

    monkeypatch.setattr("services.route_engine._load_source_snapshot", fake_snapshot)
    monkeypatch.setattr("services.route_engine.AntarcticGrid.from_config", lambda config: FakeGrid())
    monkeypatch.setattr(
        "services.route_engine.RiskConfig.from_dict",
        lambda config: SimpleNamespace(risk_weights={}, max_risk_ratio=0.95),
    )
    monkeypatch.setattr("services.route_engine.RiskEngine", FakeRiskEngine)
    monkeypatch.setattr(
        "services.route_engine.load_land_mask",
        lambda grid, path: (np.zeros((1, 1), dtype=bool), {"format": "test", "land_cells": 0}),
    )
    monkeypatch.setattr("services.route_engine._ENGINE_CACHE", {})

    vessel = {"vessel_id": "demo", "cruise_speed_knots": 12}
    ts = datetime.now(timezone.utc)
    config = {"forecast_horizon_hours": 24}

    build_route_engine(vessel, ts, config)
    build_route_engine(vessel, ts, config)

    assert calls["snapshot"] == 1
