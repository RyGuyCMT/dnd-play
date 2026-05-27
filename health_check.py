#!/usr/bin/env python3
"""Health check — combined smoke test runner.

Covers all major features end-to-end:
  smoke_test.py   — REST campaign lifecycle (create, character, session, messages)
  smoke_registry  — Registry-driven loading (seeds → registry → /load → WS manager)
  WebSocket connect test — real WS connections as DM and character + round-trip message

Run with:
  python health_check.py          [all tests]
  python health_check.py --ws    [WebSocket test only]
  python health_check.py --rest  [REST tests only]
"""
import sys, os, argparse, subprocess

DATA = '/tmp/dnd-play-health'
os.environ['DATA_PATH'] = DATA
os.environ['SECRET_KEY'] = 'health-check-secret'

def clean():
    import shutil
    try:
        shutil.rmtree(DATA)
    except FileNotFoundError:
        pass

def run_script(name, path):
    """Run a Python script; return (exit_code, output)."""
    result = subprocess.run(
        [sys.executable, path],
        capture_output=True, text=True,
        cwd='/home/hermesadmin/dnd-play',
        env={**os.environ, 'PYTHONPATH': 'src'},
    )
    out = result.stdout + result.stderr
    ok = result.returncode == 0
    status = '✓ PASS' if ok else '✗ FAIL'
    print(f'  [{status}] {name}')
    if not ok:
        print(out)
    return ok


# ── WebSocket test (real server + websockets client) ────────────────────────────

def ws_health_check():
    """Start uvicorn server in background, connect via websockets, verify round-trip."""
    import time, json, asyncio

    clean()

    # Start uvicorn in background
    import os as _os
    _env = {**_os.environ, 'PYTHONPATH': 'src'}
    print(f"  [debug] DATA_PATH={_env.get('DATA_PATH')}")
    proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'src.main:app',
         '--host', '127.0.0.1', '--port', '8765'],
        cwd='/home/hermesadmin/dnd-play',
        env=_env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    try:
        # Wait for server to be ready
        for i in range(20):
            time.sleep(0.25)
            if proc.poll() is not None:
                _, stderr = proc.communicate()
                raise RuntimeError(f'Server exited: rc={proc.returncode} stderr={stderr.decode()[:200]}')
            try:
                import urllib.request
                urllib.request.urlopen('http://127.0.0.1:8765/campaigns', timeout=1)
                break
            except Exception as e:
                if i == 0:
                    print(f"  [debug] server not ready yet: {e}")
        else:
            proc.poll()
            if proc.returncode is not None:
                _, stderr = proc.communicate()
                raise RuntimeError(f'Server exited early: {stderr.decode()[:300]}')
            raise RuntimeError('Server failed to start')

        import urllib.request

        # Create campaign via REST (POST creates, returns campaign object)
        req = urllib.request.Request(
            'http://127.0.0.1:8765/campaigns?title=WS+Health+Check',
            data=b'',  # POST body (empty — title is in query string)
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        r = urllib.request.urlopen(req, timeout=5)
        data = json.loads(r.read())
        cid = data['id']
        dm_token = data['dm_token']

        # Register character
        req = urllib.request.Request(
            f'http://127.0.0.1:8765/campaigns/{cid}/characters?role=dm&campaign_id={cid}',
            data=json.dumps({'name': 'Zep', 'player_id': 'player1'}).encode(),
            headers={
                'Authorization': f'Bearer {dm_token}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        r = urllib.request.urlopen(req, timeout=5)
        zep_token = json.loads(r.read())['character_token']

        # Start session
        req = urllib.request.Request(
            f'http://127.0.0.1:8765/campaigns/{cid}/sessions/start?role=dm&campaign_id={cid}',
            headers={'Authorization': f'Bearer {dm_token}'},
            method='POST',
        )
        urllib.request.urlopen(req, timeout=5)

        # Connect Zep to session
        req = urllib.request.Request(
            f'http://127.0.0.1:8765/campaigns/{cid}/sessions/characters/Zep/connect?role=dm&campaign_id={cid}',
            headers={'Authorization': f'Bearer {dm_token}'},
            method='POST',
        )
        urllib.request.urlopen(req, timeout=5)

        # Load into WS manager (requires registry entry — save first, then load)
        req = urllib.request.Request(
            f'http://127.0.0.1:8765/registries/{cid}/save',
            data=b'', headers={'Content-Type': 'application/json'}, method='POST',
        )
        urllib.request.urlopen(req, timeout=5)
        urllib.request.urlopen(f'http://127.0.0.1:8765/registries/{cid}/load', timeout=5)

        # WebSocket connections
        import websockets

        async def run():
            ws_url = 'ws://127.0.0.1:8765/campaigns/{}/ws'.format(cid)

            dm_conn = await websockets.connect(ws_url + f'?token={dm_token}&dm_token={dm_token}')
            char_conn = await websockets.connect(ws_url + f'?token={zep_token}&character_name=Zep')

            # DM sends broadcast
            await dm_conn.send(json.dumps({
                'type': 'message',
                'content': 'All shall know courage.',
                'scope': 'BROADCAST',
                'recipient_names': [],
            }))

            # Character receives broadcast
            msg = await asyncio.wait_for(char_conn.recv(), timeout=5)
            msg = json.loads(msg)
            assert msg['type'] == 'message', f'expected message, got {msg}'
            assert msg['payload']['content'] == 'All shall know courage.'

            # DM sends whisper to Zep only
            await dm_conn.send(json.dumps({
                'type': 'message',
                'content': 'Your secret mission: scout the ruins.',
                'scope': 'SINGLE',
                'recipient_names': ['Zep'],
            }))

            # Only Zep receives whisper
            secret = await asyncio.wait_for(char_conn.recv(), timeout=5)
            secret = json.loads(secret)
            assert secret['payload']['content'] == 'Your secret mission: scout the ruins.'

            # DM pong check
            await dm_conn.send(json.dumps({'type': 'ping'}))
            pong = await asyncio.wait_for(dm_conn.recv(), timeout=5)
            pong = json.loads(pong)
            assert pong['type'] == 'pong'

            await dm_conn.close()
            await char_conn.close()

        asyncio.run(run())

    finally:
        proc.terminate()
        proc.wait(timeout=5)

    clean()
    print('  [✓ PASS] WebSocket connect + round-trip')


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ws', action='store_true', help='WebSocket test only')
    parser.add_argument('--rest', action='store_true', help='REST tests only (smoke_test + smoke_registry)')
    args = parser.parse_args()

    print('═══ dnd-play health check ═══')
    print()

    if args.ws:
        ws_health_check()
        print()
        print('ALL HEALTH CHECKS PASSED!')
        sys.exit(0)

    if args.rest:
        clean()
        ok1 = run_script('smoke_test.py', 'smoke_test.py')
        clean()
        ok2 = run_script('smoke_registry.py', 'smoke_registry.py')
        print()
        if ok1 and ok2:
            print('ALL HEALTH CHECKS PASSED!')
            sys.exit(0)
        else:
            print('SOME TESTS FAILED')
            sys.exit(1)

    # Run all
    print('── REST smoke tests ──')
    clean()
    ok1 = run_script('smoke_test.py', 'smoke_test.py')
    clean()
    ok2 = run_script('smoke_registry.py', 'smoke_registry.py')

    print()
    print('── WebSocket test ──')
    try:
        ws_health_check()
        ok3 = True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'  [✗ FAIL] WebSocket test: {e}')
        ok3 = False

    print()
    all_ok = ok1 and ok2 and ok3
    if all_ok:
        print('ALL HEALTH CHECKS PASSED! ✓')
        sys.exit(0)
    else:
        print('SOME TESTS FAILED ✗')
        sys.exit(1)