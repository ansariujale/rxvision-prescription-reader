import json

import httpx

from app.core.ratelimit import auth_bucket
from tests.conftest import jpeg_bytes, register

API = "/api/v1"


async def upload(client, crop=None):
    files = {"image": ("rx.jpg", jpeg_bytes(), "image/jpeg")}
    data = {"crop": json.dumps(crop)} if crop else None
    return await client.post(f"{API}/scans", files=files, data=data)


async def done_scan(client) -> dict:
    r = await upload(client)
    assert r.status_code == 202, r.text
    # The ASGI transport runs background tasks before returning, so it is done.
    scan = (await client.get(f"{API}/scans/{r.json()['id']}")).json()
    assert scan["status"] == "done", scan
    return scan


# -- system & auth ---------------------------------------------------------

async def test_health_and_providers(client):
    health = (await client.get(f"{API}/health")).json()
    assert health["database"] == "ok" and health["catalogue"] == 80
    providers = (await client.get(f"{API}/providers")).json()
    assert providers["active"] == "mock"


async def test_register_login_logout_me(client):
    r = await register(client)
    assert r.json()["email"] == "asha@example.com"
    assert "rx_session" in r.cookies
    assert r.headers["set-cookie"].lower().count("httponly") == 1

    assert (await client.get(f"{API}/auth/me")).status_code == 200
    await client.post(f"{API}/auth/logout")
    client.cookies.clear()
    me = await client.get(f"{API}/auth/me")
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "unauthorized"

    bad = await client.post(f"{API}/auth/login", json={"email": "asha@example.com", "password": "nope nope"})
    assert bad.status_code == 401
    good = await client.post(f"{API}/auth/login", json={"email": "ASHA@example.com", "password": "correct horse"})
    assert good.status_code == 200


async def test_duplicate_email_and_validation(client):
    await register(client)
    dup = await client.post(f"{API}/auth/register", json={"email": "asha@example.com", "password": "12345678", "name": "B"})
    assert dup.status_code == 409
    short = await client.post(f"{API}/auth/register", json={"email": "b@example.com", "password": "123", "name": "B"})
    assert short.status_code == 422
    assert short.json()["error"]["code"] == "validation_error"


async def test_bearer_token_also_works(client):
    r = await register(client)
    token = r.cookies["rx_session"]
    client.cookies.clear()
    me = await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200


async def test_auth_rate_limit(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    auth_bucket.reset()
    codes = [
        (await client.post(f"{API}/auth/login", json={"email": "x@example.com", "password": "whatever1"})).status_code
        for _ in range(12)
    ]
    auth_bucket.reset()
    assert codes[:10] == [401] * 10 and codes[-1] == 429


# -- scans -----------------------------------------------------------------

async def test_scan_requires_auth(client):
    assert (await upload(client)).status_code == 401


async def test_scan_lifecycle(user_client):
    scan = await done_scan(user_client)
    assert scan["provider"] == "mock"
    assert [i["name"] for i in scan["items"]][:2] == ["Augmentin 625 Duo Tablet", "Pan 40 Tablet"]
    first = scan["items"][0]
    assert first["medicine"]["manufacturer"].startswith("GlaxoSmithKline")
    assert first["status"] == "suggested" and first["source_line"].startswith("1. Tab Augmentin")

    image = await user_client.get(scan["image_url"])
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"

    history = (await user_client.get(f"{API}/scans")).json()
    assert history["total"] == 1 and history["items"][0]["item_count"] == 5
    assert (await user_client.get(f"{API}/scans", params={"q": "becosules"})).json()["total"] == 1
    assert (await user_client.get(f"{API}/scans", params={"q": "insulin"})).json()["total"] == 0

    renamed = await user_client.patch(f"{API}/scans/{scan['id']}", json={"title": "Fever, October"})
    assert renamed.json()["title"] == "Fever, October"

    stats = (await user_client.get(f"{API}/stats")).json()
    assert stats["scans"] == 1 and stats["medicines_found"] == 5

    assert (await user_client.delete(f"{API}/scans/{scan['id']}")).status_code == 204
    assert (await user_client.get(f"{API}/scans/{scan['id']}")).status_code == 404


async def test_crop_is_applied(user_client):
    r = await upload(user_client, crop={"x": 0, "y": 0, "width": 0.5, "height": 0.5})
    scan = (await user_client.get(f"{API}/scans/{r.json()['id']}")).json()
    assert (scan["image_width"], scan["image_height"]) == (400, 300)


async def test_bad_uploads(user_client):
    r = await user_client.post(f"{API}/scans", files={"image": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 415
    r = await upload(user_client, crop={"x": 2})
    assert r.status_code == 422


async def test_users_cannot_see_each_others_scans(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as a, \
            httpx.AsyncClient(transport=transport, base_url="http://test") as b:
        await register(a, "a@example.com")
        await register(b, "b@example.com")
        scan = await done_scan(a)
        for method, path in [
            ("GET", f"/scans/{scan['id']}"),
            ("GET", f"/scans/{scan['id']}/image"),
            ("DELETE", f"/scans/{scan['id']}"),
            ("PATCH", f"/scans/{scan['id']}/items/{scan['items'][0]['id']}"),
        ]:
            r = await b.request(method, f"{API}{path}", json={} if method == "PATCH" else None)
            assert r.status_code == 404, (method, path, r.status_code)
        assert (await b.get(f"{API}/scans")).json()["total"] == 0


# -- items -----------------------------------------------------------------

async def test_edit_confirm_add_delete_items(user_client):
    scan = await done_scan(user_client)
    sid, items = scan["id"], scan["items"]
    base = f"{API}/scans/{sid}/items"

    edited = (await user_client.patch(f"{base}/{items[0]['id']}", json={"duration": "7 days"})).json()
    assert edited["duration"] == "7 days" and edited["status"] == "edited"

    confirmed = (await user_client.patch(f"{base}/{items[1]['id']}", json={"status": "confirmed"})).json()
    assert confirmed["status"] == "confirmed"

    relinked = (await user_client.patch(f"{base}/{items[2]['id']}", json={"medicine_id": 9})).json()
    assert relinked["name"] == "Crocin Advance Tablet" and relinked["confidence"] is None

    added = await user_client.post(base, json={"medicine_id": 17, "frequency": "0-0-1"})
    assert added.status_code == 201
    assert added.json()["name"] == "Montair LC Tablet" and added.json()["status"] == "manual"
    assert added.json()["position"] == 5

    free = await user_client.post(base, json={"name": "Saline gargle", "notes": "warm water"})
    assert free.json()["medicine"] is None

    assert (await user_client.post(base, json={})).status_code == 422
    assert (await user_client.post(base, json={"medicine_id": 99999})).status_code == 422

    assert (await user_client.delete(f"{base}/{items[4]['id']}")).status_code == 204

    after = (await user_client.post(f"{base}/confirm-all")).json()
    statuses = [i["status"] for i in after["items"]]
    assert "suggested" not in statuses and len(after["items"]) == 6


async def test_medicine_search_and_detail(user_client):
    hits = (await user_client.get(f"{API}/medicines/search", params={"q": "allegra"})).json()
    assert hits[0]["name"].startswith("Allegra")
    detail = (await user_client.get(f"{API}/medicines/{hits[0]['id']}")).json()
    assert detail["composition"].startswith("Fexofenadine")
    assert (await user_client.get(f"{API}/medicines/99999")).status_code == 404


async def test_exports(user_client):
    scan = await done_scan(user_client)
    csv_r = await user_client.get(f"{API}/scans/{scan['id']}/export", params={"format": "csv"})
    assert csv_r.status_code == 200
    text = csv_r.content.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("#,medicine,strength")
    assert "Augmentin 625 Duo Tablet" in text

    pdf = await user_client.get(f"{API}/scans/{scan['id']}/export", params={"format": "pdf"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert "attachment" in pdf.headers["content-disposition"]


async def test_failed_scan_and_retry(user_client):
    from app.services.ocr import factory
    from app.services.ocr.base import ProviderError
    from app.services.ocr.mock import MockProvider

    class Broken:
        name = "mock"

        async def read(self, image, mime):
            raise ProviderError("The OCR service is down")

    factory.set_provider(Broken())
    r = await upload(user_client)
    scan = (await user_client.get(f"{API}/scans/{r.json()['id']}")).json()
    assert scan["status"] == "failed" and scan["error"] == "The OCR service is down"
    assert (await user_client.get(f"{API}/scans/{scan['id']}/export")).status_code == 409

    factory.set_provider(MockProvider(delay=0))
    retried = await user_client.post(f"{API}/scans/{scan['id']}/retry")
    assert retried.status_code == 202
    scan = (await user_client.get(f"{API}/scans/{scan['id']}")).json()
    assert scan["status"] == "done" and len(scan["items"]) == 5


# -- routine, medicines, account (v2.1) --------------------------------------

async def test_routine_flow(user_client):
    from datetime import date, timedelta

    scan = await done_scan(user_client)
    sid = scan["id"]
    assert scan["doctor"] == "Dr. A. Mehta" and scan["in_routine"] is False
    today = date.today().isoformat()

    empty = (await user_client.get(f"{API}/routine", params={"day": today})).json()
    assert empty["total"] == 0 and empty["prescriptions"] == 0

    r = await user_client.patch(f"{API}/scans/{sid}", json={"in_routine": True})
    assert r.json()["in_routine"] is True

    plan = (await user_client.get(f"{API}/routine", params={"day": today})).json()
    slots = {s["slot"]: [e["name"] for e in s["entries"]] for s in plan["slots"]}
    # Augmentin 1-0-1, Pan 1-0-0, Ascoril TDS, Becosules 1-0-0; Dolo is SOS.
    assert "Augmentin 625 Duo Tablet" in slots["morning"] and "Augmentin 625 Duo Tablet" in slots["night"]
    assert slots["afternoon"] == ["Ascoril LS Syrup"]
    assert [e["name"] for e in plan["as_needed"]] == ["Dolo 650 Tablet"]
    assert plan["total"] == 7 and plan["taken"] == 0 and len(plan["week"]) == 7

    entry = plan["slots"][0]["entries"][0]
    dose = {"item_id": entry["item_id"], "day": today, "slot": entry["slot"], "taken": True}
    assert (await user_client.put(f"{API}/routine/doses", json=dose)).status_code == 204
    assert (await user_client.put(f"{API}/routine/doses", json=dose)).status_code == 204  # idempotent
    after = (await user_client.get(f"{API}/routine", params={"day": today})).json()
    assert after["taken"] == 1

    dose["taken"] = False
    await user_client.put(f"{API}/routine/doses", json=dose)
    assert (await user_client.get(f"{API}/routine", params={"day": today})).json()["taken"] == 0

    future = {**dose, "taken": True, "day": (date.today() + timedelta(days=5)).isoformat()}
    assert (await user_client.put(f"{API}/routine/doses", json=future)).status_code == 422

    # Moving the start date shifts the course.
    later = (date.today() + timedelta(days=30)).isoformat()
    assert (await user_client.patch(f"{API}/scans/{sid}", json={"prescribed_on": later})).status_code == 422
    old = (date.today() - timedelta(days=60)).isoformat()
    await user_client.patch(f"{API}/scans/{sid}", json={"prescribed_on": old})
    assert (await user_client.get(f"{API}/routine", params={"day": today})).json()["total"] == 0

    only = (await user_client.get(f"{API}/scans", params={"in_routine": "true"})).json()
    assert only["total"] == 1


async def test_dose_on_someone_elses_item_is_404(app):
    from datetime import date

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as a, \
            httpx.AsyncClient(transport=transport, base_url="http://test") as b:
        await register(a, "a@example.com")
        await register(b, "b@example.com")
        scan = await done_scan(a)
        dose = {"item_id": scan["items"][0]["id"], "day": date.today().isoformat(), "slot": "morning", "taken": True}
        assert (await b.put(f"{API}/routine/doses", json=dose)).status_code == 404


async def test_my_medicines_history_and_alternatives(user_client):
    await done_scan(user_client)
    second = await done_scan(user_client)
    await user_client.patch(f"{API}/scans/{second['id']}", json={"in_routine": True})

    mine = (await user_client.get(f"{API}/me/medicines")).json()
    augmentin = next(m for m in mine if m["name"] == "Augmentin 625 Duo Tablet")
    assert augmentin["times"] == 2 and augmentin["active"] is True and len(augmentin["uses"]) == 2
    assert all(m["active"] for m in mine[:5])
    assert len((await user_client.get(f"{API}/me/medicines", params={"q": "pan"})).json()) == 1

    history = (await user_client.get(f"{API}/medicines/1/history")).json()
    assert len(history) == 2 and history[0]["frequency"] == "1-0-1"

    alts = (await user_client.get(f"{API}/medicines/1/alternatives")).json()
    names = {a["name"] for a in alts}
    # Same amoxycillin 500 + clavulanic 125 combination, nothing else.
    assert names == {"Moxikind-CV 625 Tablet", "Clavam 625 Tablet"}

    assert (await user_client.get(f"{API}/medicines/7/alternatives")).json() == []  # Dolo 650 has none


async def test_export_everything(user_client):
    await done_scan(user_client)
    r = await user_client.get(f"{API}/me/export")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["account"]["email"] == "asha@example.com"
    assert len(data["prescriptions"]) == 1 and len(data["prescriptions"][0]["items"]) == 5


async def test_profile_password_and_delete_account(user_client, app):
    from app.services.storage import get_storage

    r = await user_client.patch(f"{API}/auth/me", json={"name": "Asha K"})
    assert r.json()["name"] == "Asha K"

    wrong = await user_client.post(f"{API}/auth/password", json={"current_password": "nope", "new_password": "brand new pass"})
    assert wrong.status_code == 403
    ok = await user_client.post(f"{API}/auth/password", json={"current_password": "correct horse", "new_password": "brand new pass"})
    assert ok.status_code == 204
    relog = await user_client.post(f"{API}/auth/login", json={"email": "asha@example.com", "password": "brand new pass"})
    assert relog.status_code == 200

    scan = await done_scan(user_client)
    storage = get_storage()
    key_count = len(list(storage.root.iterdir()))
    assert key_count == 1

    bad = await user_client.request("DELETE", f"{API}/auth/me", json={"password": "wrong"})
    assert bad.status_code == 403
    gone = await user_client.request("DELETE", f"{API}/auth/me", json={"password": "brand new pass"})
    assert gone.status_code == 204
    assert list(storage.root.iterdir()) == []

    user_client.cookies.clear()
    assert (await user_client.post(f"{API}/auth/login", json={"email": "asha@example.com", "password": "brand new pass"})).status_code == 401
    # Cascade removed the scan too (foreign keys are on in tests, as in Postgres).
    from sqlalchemy import func, select
    from app.db.session import session_factory
    from app.models import Scan, ScanItem
    async with session_factory()() as s:
        assert await s.scalar(select(func.count()).select_from(Scan)) == 0
        assert await s.scalar(select(func.count()).select_from(ScanItem)) == 0
