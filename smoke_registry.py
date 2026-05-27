#!/usr/bin/env python3
"""Smoke test: registry-driven campaign lifecycle.

Tests the complete flow:
  1. Write seed files to disk (simulating Session Zero output):
     - campaigns/<id>/campaign.json
     - campaigns/<id>/world_state.json
     - campaigns/<id>/characters/<name>.json  (per character)
  2. Write a registry file (Session Zero finalizes → produces this)
  3. GET /registries              → lists available campaigns
  4. GET /registries/{id}/load   → loads into WS manager
  5. WS connect                  → succeeds now campaign is loaded

No campaign is loaded on startup — DM must explicitly select via /load.
"""
import sys, os
os.environ['DATA_PATH'] = '/tmp/dnd-registry-test'
os.environ['SECRET_KEY'] = 'test-secret'
sys.path.insert(0, 'src')

import hashlib, hmac, json, pathlib

from main import app
from fastapi.testclient import TestClient
from persistence.base import LocalStorageAdapter, RegistryService
from models.registry import CampaignRegistry, CharacterPointer
from models.campaign import Campaign
from models.character import Character


DATA = '/tmp/dnd-registry-test'
adapter = LocalStorageAdapter(data_path=DATA)
svc = RegistryService(adapter)

# ── Setup: build a campaign + registry on disk (simulating Session Zero output) ──

campaign_id = 'test-reg-campaign'

# Relative paths as the registry stores them
campaign_rel = f'campaigns/{campaign_id}/campaign.json'
world_rel    = f'campaigns/{campaign_id}/world_state.json'

campaign_dir = pathlib.Path(DATA) / 'campaigns' / campaign_id
campaign_dir.mkdir(parents=True, exist_ok=True)

# Add two characters
characters = [
    {'name': 'Grog',  'player_id': 'player1', 'character_class': 'Barbarian', 'race': 'Half-Orc'},
    {'name': 'Elora', 'player_id': 'player1', 'character_class': 'Wizard',    'race': 'Elf'},
]

# Generate DM token hash (plaintext returned; hash stored)
dm_token_plain = 'dm-secret-token'
key = f"test-secret:{campaign_id}:dm"
dm_token_hash = hmac.new(key.encode(), dm_token_plain.encode(), hashlib.sha256).hexdigest()[:64]

# Build campaign dict (what Campaign.as_dict would produce)
campaign_dict = {
    'id': campaign_id,
    'title': 'Curse of the Crimson Throne',
    'elevator_pitch': 'Dark forces converge on a city on the brink of revolution.',
    'tone': 'Gothic noir',
    'pacing': 'Pulsing — events accelerate as the conspiracy unfolds.',
    'dm_token': dm_token_hash,
    'characters': {},
    'current_session': None,
    'sessions': {},
    'status': 'ACTIVE',
    'created_at': '2026-01-01T00:00:00',
    'updated_at': '2026-01-01T00:00:00',
}

# Write character sheets + populate campaign.characters
for cd in characters:
    char_file = campaign_dir / 'characters' / f"{cd['name'].lower()}.json"
    char_file.parent.mkdir(parents=True, exist_ok=True)

    char_token_plain = f'char-token-{cd["name"]}'
    char_token_hash  = hmac.new(
        f"test-secret:{campaign_id}:{cd['name']}".encode(),
        char_token_plain.encode(), hashlib.sha256
    ).hexdigest()[:64]

    char_sheet = {
        'name': cd['name'],
        'player_id': cd['player_id'],
        'character_class': cd['character_class'],
        'race': cd['race'],
        'backstory': '',
        'notes': '',
        'character_token': char_token_hash,
        'created_at': '2026-01-01T00:00:00',
    }
    char_file.write_text(json.dumps(char_sheet, indent=2))

    campaign_dict['characters'][cd['name']] = char_sheet

# Write campaign file
(campaign_dir / 'campaign.json').write_text(json.dumps(campaign_dict, indent=2))

# Write world state (empty)
world_file = campaign_dir / 'world_state.json'
world_file.write_text(json.dumps({}, indent=2))

# Write registry
registry = CampaignRegistry.new(
    campaign_id=campaign_id,
    campaign_path=campaign_rel,
    world_state_path=world_rel,
    characters=[
        CharacterPointer(name=cd['name'],
                        path=f'campaigns/{campaign_id}/characters/{cd["name"].lower()}.json')
        for cd in characters
    ],
)
svc.save_registry(registry)

print('Setup complete.')


# ── Test 1: List registries ───────────────────────────────────────────────────

client = TestClient(app)

resp = client.get('/registries')
print('GET /registries:', resp.status_code)
entries = resp.json()
print('  Entries:', entries)
assert resp.status_code == 200
assert any(e['campaign_id'] == campaign_id for e in entries), "Campaign should appear in registry list"
print('  ✓ Registry list shows our campaign')


# ── Test 2: Load from registry ────────────────────────────────────────────────

resp = client.get(f'/registries/{campaign_id}/load')
print('GET /registries/{id}/load:', resp.status_code)
data = resp.json()
print('  Campaign title:', data['campaign']['title'])
print('  Characters:', data['campaign']['character_names'])
assert resp.status_code == 200
assert data['campaign']['title'] == 'Curse of the Crimson Throne'
assert 'Grog' in data['campaign']['character_names']
assert 'Elora' in data['campaign']['character_names']
print('  ✓ Campaign loaded from registry')


# ── Test 3: WS manager populated after load ───────────────────────────────────

from websocket import ws_manager

state = ws_manager.get_campaign('nonexistent-campaign')
print('WS manager check (nonexistent):', state is None, '← should be None')
assert state is None

state = ws_manager.get_campaign(campaign_id)
print('WS manager check (after load):', state is not None, '← should NOT be None')
assert state is not None
print('  ✓ WS manager populated after /load')


# ── Test 4: Registry details ───────────────────────────────────────────────────

resp = client.get(f'/registries/{campaign_id}')
print('GET /registries/{id}:', resp.status_code)
reg = resp.json()
print('  campaign_id:', reg['campaign_id'])
print('  character_count:', len(reg['characters']))
assert resp.status_code == 200
assert reg['campaign_id'] == campaign_id
assert len(reg['characters']) == 2
print('  ✓ Registry details correct')


# ── Test 5: Nonexistent registry → 404 ───────────────────────────────────────

resp = client.get('/registries/does-not-exist')
print('GET /registries/does-not-exist:', resp.status_code, '← should be 404')
assert resp.status_code == 404
print('  ✓ 404 for unknown registry')


# ── Test 6: Load nonexistent registry → 404 ──────────────────────────────────

resp = client.get('/registries/does-not-exist/load')
print('GET /registries/does-not-exist/load:', resp.status_code, '← should be 404')
assert resp.status_code == 404
print('  ✓ 404 for load of unknown registry')


print()
print('ALL REGISTRY TESTS PASSED!')