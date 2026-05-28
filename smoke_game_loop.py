#!/usr/bin/env python3
"""GameLoop API smoke test — uses TestClient like other smoke tests."""
import os
from pathlib import Path

# Must set env BEFORE importing app
DATA_PATH = Path(__file__).parent / "data"
os.environ["DATA_PATH"] = str(DATA_PATH)
os.environ["SECRET_KEY"] = "test-secret-key-for-game-loop-smoke-test"

import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from starlette.testclient import TestClient

from main import app


def run():
    client = TestClient(app)

    # ── 1. Create campaign ───────────────────────────────────────────────────
    resp = client.post("/campaigns", json={"title": "GL Smoke Test"})
    assert resp.status_code == 200, f"create campaign: {resp.status_code} {resp.text}"
    d = resp.json()
    cid = d["id"]
    dm = d["dm_token"]
    print(f"✓ Campaign: {cid}")

    # ── 2. Start session ──────────────────────────────────────────────────────
    # Basic Auth: username = dm_token (from campaign), password = ""
    resp = client.post(
        f"/campaigns/{cid}/sessions/start",
        params={"role": "dm", "campaign_id": cid},
        headers={"Authorization": f"Bearer {dm}"},
    )
    assert resp.status_code == 200, f"start session: {resp.status_code} {resp.text}"
    sess = resp.json()["session_number"]
    print(f"✓ Session: {sess}")

    # ── 3. Default state is EXPLORATION ──────────────────────────────────────
    resp = client.get(
        f"/campaigns/{cid}/sessions/{sess}/game-loop",
        params={"campaign_id": cid, "role": "dm"},
        headers={"Authorization": f"Bearer {dm}"},
    )
    assert resp.status_code == 200, f"get game-loop: {resp.status_code} {resp.text}"
    d = resp.json()
    assert d["state_type"] == "EXPLORATION"
    assert d["infinite"] is True
    assert d["initiative_required"] is None
    assert d["broadcast_scope"] == "ALL"
    print(f"✓ Default: {d['state_type']}  infinite={d['infinite']}  broadcast={d['broadcast_scope']}")

    # ── 4. Enter COMBAT ────────────────────────────────────────────────────────
    resp = client.post(
        f"/campaigns/{cid}/sessions/{sess}/game-loop",
        params={"campaign_id": cid, "role": "dm"},
        headers={"Authorization": f"Bearer {dm}"},
        json={"state_type": "COMBAT", "initiative_order": ["Grog", "Goblin"], "surprise": "npc"},
    )
    assert resp.status_code == 200, f"enter combat: {resp.status_code} {resp.text}"
    d = resp.json()
    assert d["state_type"] == "COMBAT"
    assert d["initiative_order"] == ["Grog", "Goblin"]
    assert d["surprise"] == "npc"
    assert d["parent_state_type"] == "EXPLORATION"
    print(f"✓ COMBAT: surprise={d['surprise']}  initiative={d['initiative_order']}")

    # ── 5. COMBAT cascades all properties ───────────────────────────────────
    resp = client.get(
        f"/campaigns/{cid}/sessions/{sess}/game-loop",
        params={"campaign_id": cid, "role": "dm"},
        headers={"Authorization": f"Bearer {dm}"},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d["state_type"] == "COMBAT"
    assert d["initiative_required"] is True
    assert d["broadcast_scope"] == "ACTIVE"
    assert len(d["allowed_actions"]) == 9
    assert d["parent_state_type"] == "EXPLORATION"
    print(f"✓ Cascade: initiative={d['initiative_required']}  broadcast={d['broadcast_scope']}  {len(d['allowed_actions'])} actions")

    # ── 6. Advance round ─────────────────────────────────────────────────────
    resp = client.post(
        f"/campaigns/{cid}/sessions/{sess}/game-loop/advance-round",
        params={"campaign_id": cid, "role": "dm"},
        headers={"Authorization": f"Bearer {dm}"},
    )
    assert resp.status_code == 200, f"advance round: {resp.status_code} {resp.text}"
    d = resp.json()
    assert d["round"] == 1
    print(f"✓ Round advanced: {d['round']}")

    # ── 7. Return to parent (EXPLORATION) ─────────────────────────────────────
    resp = client.post(
        f"/campaigns/{cid}/sessions/{sess}/game-loop",
        params={"campaign_id": cid, "role": "dm"},
        headers={"Authorization": f"Bearer {dm}"},
        json={"state_type": "RETURN"},
    )
    assert resp.status_code == 200, f"return: {resp.status_code} {resp.text}"
    d = resp.json()
    assert d["state_type"] == "EXPLORATION"
    print(f"✓ Return: {d['state_type']}")

    # ── 8. EXPLORATION properties restored ──────────────────────────────────
    resp = client.get(
        f"/campaigns/{cid}/sessions/{sess}/game-loop",
        params={"campaign_id": cid, "role": "dm"},
        headers={"Authorization": f"Bearer {dm}"},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d["state_type"] == "EXPLORATION"
    assert d["broadcast_scope"] == "ALL"
    assert d["initiative_required"] is None
    print(f"✓ RESTORED: {d['state_type']}  broadcast={d['broadcast_scope']}  infinite={d['infinite']}")

    # ── 9. COMBAT mode=mass sequence ──────────────────────────────────────────
    resp = client.post(
        f"/campaigns/{cid}/sessions/{sess}/game-loop",
        params={"campaign_id": cid, "role": "dm"},
        headers={"Authorization": f"Bearer {dm}"},
        json={"state_type": "COMBAT", "mode": "mass"},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d["state_type"] == "COMBAT"
    resp = client.get(f"/campaigns/{cid}/sessions/{sess}/game-loop", params={"campaign_id": cid, "role": "dm"}, headers={"Authorization": f"Bearer {dm}"})
    d = resp.json()
    assert d["sequence"] == ["ROLL_INITIATIVE", "MORALE_CHECK", "ARMY_ROUND"]
    print(f"✓ COMBAT(mass): sequence={d['sequence']}")

    # ── 10. DOWNTIME ─────────────────────────────────────────────────────────
    resp = client.post(
        f"/campaigns/{cid}/sessions/{sess}/game-loop",
        params={"campaign_id": cid, "role": "dm"},
        headers={"Authorization": f"Bearer {dm}"},
        json={"state_type": "DOWNTIME"},
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d["state_type"] == "DOWNTIME"
    print(f"✓ DOWNTIME: {d['state_type']}")

    print()
    print("ALL GAME LOOP TESTS PASSED!")


if __name__ == "__main__":
    run()
