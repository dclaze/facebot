"""Owner-device settings UI. No pairing secrets or visitor recordings."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
import uvicorn
from server import settings, coaching
from server.profiles import active

ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    c = coaching.read()
    result = {**settings.read(), 'rules': c['rules'], 'revision': c['revision'], 'profile': active()['id'],
              'defaults': {**active()['character_profile']['defaults'], 'rules': []}}
    result['etag'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


def create_admin(host='192.168.4.32', port=8766, allowed_clients=()):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    allowed = {host, '127.0.0.1', '::1'}
    for address in allowed_clients:
        ip = ipaddress.ip_address(address)
        if not ip.is_private or ip.is_unspecified or ip.is_multicast:
            raise ValueError('Owner devices must use an explicit private IP address')
        allowed.add(str(ip))
    origins = {f'http://{host}:{port}', f'http://localhost:{port}', f'http://127.0.0.1:{port}'}

    @app.middleware('http')
    async def owner_only(request, call_next):
        from fastapi.responses import JSONResponse
        if not request.client or request.client.host not in allowed:
            return JSONResponse({'detail': 'This device is not enabled for Facebot settings. Ask the owner to allow its current network address.'}, status_code=403)
        if request.headers.get('host') not in {f'{x}:{port}' for x in (host, 'localhost', '127.0.0.1')}:
            return JSONResponse({'detail': 'Invalid host'}, status_code=403)
        if request.method not in ('GET', 'HEAD') and request.headers.get('origin') not in origins:
            return JSONResponse({'detail': 'Same-origin edits required'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
        return response

    @app.get('/')
    async def index():
        return FileResponse(ROOT/'web/settings.html')

    @app.get('/api/settings')
    async def get_settings():
        return snapshot()

    @app.get('/packs')
    async def packs():
        return FileResponse(ROOT/'web/packs.html')

    @app.get('/store')
    async def store_page():
        return FileResponse(ROOT/'web/store.html')

    @app.get('/api/store')
    async def store_catalog():
        from server.skill_store import snapshot
        return snapshot()

    @app.put('/api/store/{pack_id}')
    async def store_update(pack_id: str, request: Request):
        from server.skill_store import update
        body = await request.body()
        if len(body) > 1024:
            raise HTTPException(413)
        try:
            return update(pack_id, json.loads(body))
        except LookupError as error:
            raise HTTPException(404, str(error))
        except RuntimeError as error:
            raise HTTPException(409, str(error))
        except (ValueError, TypeError) as error:
            raise HTTPException(400, str(error))
        except OSError:
            raise HTTPException(503, 'Could not save skills. Existing settings remain in place.')

    @app.get('/quips')
    async def quips_page():
        return FileResponse(ROOT/'web/quips.html')

    async def voice_command(route, method='POST', payload=None):
        try:
            token = (ROOT/'.local/pairing-token').read_text().strip()
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                response = await client.request(method, f'http://{host}:8765/'+route,
                    headers={'Authorization':'Bearer '+token}, json=payload)
            if response.status_code >= 400:
                detail = response.json().get('detail', 'Voice command failed')
                raise HTTPException(response.status_code, detail)
            return response.json()
        except (OSError, httpx.HTTPError, ValueError):
            raise HTTPException(503, 'Voice server unavailable; command was not confirmed. Do not assume it played.')

    @app.post('/api/quips')
    async def send_quip(request: Request):
        from server.owner_quips import validate_quip
        if len(await request.body()) > 2048:
            raise HTTPException(413)
        try:
            payload = validate_quip(await request.json())
        except (ValueError, TypeError, KeyError):
            raise HTTPException(400, 'Use plain child-safe text, up to 32 words and 240 characters')
        return await voice_command('owner/quips', payload=payload)

    @app.get('/api/quips/{identifier}')
    async def get_quip(identifier: str):
        from uuid import UUID
        try:
            if str(UUID(identifier)) != identifier: raise ValueError()
        except ValueError:
            raise HTTPException(400)
        return await voice_command('owner/quips/'+identifier, method='GET')

    @app.post('/api/scenarios/robin-williams/send')
    async def send_robin():
        return await voice_command('skills/robin-williams/preview')

    @app.get('/api/catalog')
    async def catalog():
        from server.catalog import snapshot as catalog_snapshot
        return catalog_snapshot()

    @app.get('/api/sounds/{sound_id}')
    async def sound(sound_id: str):
        from server.catalog import sound_path
        path = sound_path(sound_id)
        if path is None: raise HTTPException(404)
        return FileResponse(path, media_type='audio/wav')


    @app.get('/api/experiences')
    async def experiences():
        from server.experiences import snapshot, report
        return {'experiences': snapshot(), 'workshop': report()}

    @app.get('/api/experiences/{skill_id}/media/{kind}')
    async def experience_media(skill_id: str, kind: str, revision: str | None = None):
        from server.experiences import entries, asset_path, MIME, revision_key
        item = next((x for x in entries() if x['id'] == skill_id and active()['id'] in x.get('event_ids', [])), None)
        if item and revision is not None and revision != revision_key(item):
            raise HTTPException(409, 'This preview changed. Reload the catalog.')
        path = asset_path(item, kind) if item else None
        if path is None: raise HTTPException(404, 'Preview unavailable')
        return FileResponse(path, media_type=MIME[path.suffix.lstrip('.')])

    @app.post('/api/experiences/{skill_id}/review')
    async def experience_review(skill_id: str, request: Request):
        from server.experiences import review
        raw = await request.body()
        if len(raw) > 4096: raise HTTPException(413)
        try:
            return review(skill_id, json.loads(raw))
        except LookupError as e: raise HTTPException(404, str(e))
        except RuntimeError as e: raise HTTPException(409, str(e))
        except (ValueError, TypeError, KeyError) as e: raise HTTPException(400, str(e))
        except OSError: raise HTTPException(503, 'Could not save feedback. Please retry.')

    @app.put('/api/settings')
    async def put_settings(request: Request):
        raw = await request.body()
        if len(raw) > 4096: raise HTTPException(413)
        try:
            value = json.loads(raw)
            if not isinstance(value, dict) or set(value) != {'speech_rate', 'character_name', 'color_scheme', 'rules', 'etag'}: raise ValueError('Invalid settings fields')
            if value['etag'] != snapshot()['etag']: raise HTTPException(409, 'Settings changed elsewhere. Reload before saving.')
            rate = settings.validate({k: value[k] for k in settings.DEFAULTS})
            rules = coaching.validate(value['rules'])
            previous = settings.read()
            settings.save(rate)
            try:
                if rules != coaching.read()['rules']:
                    coaching.save(rules)
            except OSError:
                settings.save(previous)
                raise HTTPException(503, 'Could not save character direction. Settings were restored; retry saving.')
            return snapshot()
        except (ValueError, TypeError, KeyError) as e:
            raise HTTPException(400, str(e))

    @app.get('/api/status')
    async def status():
        result = {'vision': {'fresh': False}, 'voice': {'status': 'unavailable'}}
        try:
            token = (ROOT/'.local/pairing-token').read_text().strip()
        except OSError:
            token = ''
        async with httpx.AsyncClient(timeout=1, trust_env=False) as client:
            for field, route in [('voice','health'), ('vision','vision/diagnostics'), ('runtime','runtime-settings')]:
                try:
                    response = await client.get(f'http://{host}:8765/'+route, headers={'Authorization':'Bearer '+token})
                    response.raise_for_status(); result[field] = response.json()
                except (httpx.HTTPError, ValueError): pass
        usage = ROOT/'.local/codex-usage.json'
        try:
            result['usage'] = json.loads(usage.read_text())
        except (OSError, ValueError):
            pass
        return result
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--allow-client', action='append', default=[],
                        help='Allow one owner device private IP; repeat for additional devices')
    args = parser.parse_args()
    uvicorn.run(create_admin(args.host,args.port,args.allow_client), host=args.host, port=args.port,
                access_log=False, proxy_headers=False)
