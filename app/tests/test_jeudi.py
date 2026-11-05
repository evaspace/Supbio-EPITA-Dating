import os
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient
from PIL import Image

os.environ["DROP_FORCE_OPEN"] = "true"
import backend.jeudi as J
from backend.main import create_app
from tests.test_api import enroll

THU_EVENING = datetime(2026, 11, 5, 18, 0)  # 19:00 in Paris


@pytest.fixture()
def pair(monkeypatch):
    clock = {"t": THU_EVENING}
    monkeypatch.setattr(J, "now", lambda: clock["t"])
    with TemporaryDirectory() as tmp:
        app = create_app(f"sqlite:///{Path(tmp) / 'j.db'}", dev_otp=True)
        with TestClient(app, headers={"X-Campus-Request": "1"}) as a, TestClient(app, headers={"X-Campus-Request": "1"}) as b:
            ua = enroll(a, "a@epita.fr", "EPITA", "Alice", gender="Femme")
            ub = enroll(b, "b@esme.fr", "ESME", "Bob", gender="Homme")
            a.post("/api/swipes", json={"target_id": ub["id"], "action": "like"})
            m = b.post("/api/swipes", json={"target_id": ua["id"], "action": "like"}).json()["match_id"]
            yield a, b, m, clock


def test_drop_window_is_thursday_evening_in_paris():
    wed = J.drop_window(datetime(2026, 11, 4, 12, 0))
    assert not wed["open"] and wed["opens_at"] == datetime(2026, 11, 5, 17, 0)
    assert J.drop_window(datetime(2026, 11, 5, 18, 0))["open"]
    after = J.drop_window(datetime(2026, 11, 5, 21, 30))
    assert not after["open"] and after["opens_at"] == datetime(2026, 11, 12, 17, 0)


def book(a, b, m):
    offer = a.get("/api/drop").json()["offers"][0]
    r = a.post("/api/bookings", json={"match_id": m, "offer_id": offer["id"]})
    assert r.status_code == 200, r.text
    bid = r.json()["id"]
    assert b.post(f"/api/bookings/{bid}/accept").status_code == 200
    return bid, datetime.fromisoformat(offer["starts_at"].rstrip("Z")), offer


def test_full_meeting_flow_scores_both_people(pair):
    a, b, m, clock = pair
    bid, start, offer = book(a, b, m)
    assert a.post("/api/bookings", json={"match_id": m, "offer_id": offer["id"]}).status_code == 409  # one slot per match
    assert a.post(f"/api/bookings/{bid}/checkin").status_code == 409  # too early
    clock["t"] = start - timedelta(minutes=50)
    assert a.post(f"/api/bookings/{bid}/checkin").status_code == 200
    assert b.post(f"/api/bookings/{bid}/checkin").status_code == 200
    clock["t"] = start - timedelta(minutes=2)
    assert a.post(f"/api/bookings/{bid}/validate", json={"code": "nope"}).status_code == 422
    code = {"cafet": "CAFE", "babyfoot": "BABY", "run": "RUN7", "tp": "TPLY"}[offer["venue_id"]]
    assert a.post(f"/api/bookings/{bid}/validate", json={"code": code}).status_code == 200
    assert b.post(f"/api/bookings/{bid}/validate", json={"code": code.lower()}).status_code == 200
    clock["t"] = start + timedelta(minutes=31)
    res = a.get("/api/bookings").json()
    assert res["bookings"][0]["status"] == "done" and res["me"]["meetings"] == 1 and res["me"]["reliability"] == 100
    assert a.post(f"/api/bookings/{bid}/feedback", json={"again": True}).json()["my_again"] is True


def test_missing_checkin_cancels_cleanly_without_strike(pair):
    a, b, m, clock = pair
    bid, start, _ = book(a, b, m)
    clock["t"] = start - timedelta(minutes=50)
    a.post(f"/api/bookings/{bid}/checkin")
    clock["t"] = start - timedelta(minutes=20)
    res = a.get("/api/bookings").json()
    assert res["bookings"][0]["status"] == "cancelled" and res["me"]["lapins"] == 0


def test_two_lapins_suspend_booking_for_a_week(pair):
    a, b, m, clock = pair
    for i in range(2):
        clock["t"] = THU_EVENING + timedelta(days=7 * i)
        bid, start, offer = book(a, b, m)
        clock["t"] = start - timedelta(minutes=50)
        a.post(f"/api/bookings/{bid}/checkin"); b.post(f"/api/bookings/{bid}/checkin")
        clock["t"] = start - timedelta(minutes=1)
        code = {"cafet": "CAFE", "babyfoot": "BABY", "run": "RUN7", "tp": "TPLY"}[offer["venue_id"]]
        a.post(f"/api/bookings/{bid}/validate", json={"code": code})  # b never shows up
        clock["t"] = start + timedelta(minutes=40)
        res = b.get("/api/bookings").json()
    assert res["me"]["lapins"] == 2 and res["me"]["banned_until"]
    assert a.get("/api/bookings").json()["me"]["lapins"] == 0
    clock["t"] = THU_EVENING + timedelta(days=14)
    offer = b.get("/api/drop").json()["offers"][0]
    assert b.post("/api/bookings", json={"match_id": m, "offer_id": offer["id"]}).status_code == 403


def test_style_drawing_and_privacy(pair):
    a, b, m, _ = pair
    bad = {"intents": ["dating"], "accent": "#f0f0f0", "ground": "#ffffff"}
    assert a.put("/api/me/style", json=bad).status_code == 422  # contrast
    ok = {"intents": ["dating", "amis"], "accent": "#1d3b2f", "ground": "#e8f0ea", "font": "caveat", "emoji": "x", "hook": "Café ?"}
    assert a.put("/api/me/style", json=ok).status_code == 200
    assert a.put("/api/me/style", json={**ok, "highlights": ["Inconnu"]}).status_code == 422
    png = BytesIO(); Image.new("RGBA", (300, 300), (255, 0, 0, 0)).save(png, "PNG")
    assert a.post("/api/me/drawing", files={"drawing": ("d.png", png.getvalue(), "image/png")}).status_code == 200
    assert b.get(a.get("/api/me/style").json()["drawing"]).status_code == 200
    assert a.post("/api/me/drawing", files={"drawing": ("d.png", b"not an image", "image/png")}).status_code == 422


def test_stats_hide_small_groups(pair):
    a, b, m, _ = pair
    res = a.get("/api/stats").json()
    assert res["ranking"] == [] and res["hidden_groups"] >= 2 and res["threshold"] == 10


def test_password_login_reset_and_lockout(pair):
    a, _, _, _ = pair
    a.post("/api/auth/logout")
    assert a.get("/api/me").status_code == 401
    assert a.post("/api/auth/login", json={"email": "a@epita.fr", "password": "wrong"}).status_code == 401
    assert a.post("/api/auth/login", json={"email": "nobody@epita.fr", "password": "x"}).status_code == 401
    ok = a.post("/api/auth/login", json={"email": "a@epita.fr", "password": "correct horse battery"})
    assert ok.status_code == 200 and a.get("/api/me").json()["email"] == "a@epita.fr"
    a.post("/api/auth/logout")
    code = a.post("/api/auth/request-code", json={"email": "a@epita.fr", "school": "EPITA"}).json()["local_demo_code"]
    assert a.post("/api/auth/reset", json={"email": "a@epita.fr", "school": "EPITA", "code": "000000", "password": "brand new password"}).status_code == 400
    r = a.post("/api/auth/reset", json={"email": "a@epita.fr", "school": "EPITA", "code": code, "password": "brand new password"})
    assert r.status_code == 200
    a.post("/api/auth/logout")
    assert a.post("/api/auth/login", json={"email": "a@epita.fr", "password": "correct horse battery"}).status_code == 401
    assert a.post("/api/auth/login", json={"email": "a@epita.fr", "password": "brand new password"}).status_code == 200
    for _ in range(10):
        last = a.post("/api/auth/login", json={"email": "a@epita.fr", "password": "nope"})
    assert last.status_code == 429
    assert a.post("/api/auth/verify-code", json={"email": "new@epita.fr", "code": "000000", "school": "EPITA", "name": "Zed", "birthday": "2000-01-01", "adult_consent": True}).status_code in (400, 429)
