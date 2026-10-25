#!/usr/bin/env python3
"""Synthetic network replay of generated speech; not acoustic/device acceptance."""
import argparse
import asyncio
import json
import pathlib
import struct
import sys
import time
import numpy as np
from scipy.signal import resample_poly
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from server.tts import SpeechEngine

async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--text', default='May I have some candy?')
    args = parser.parse_args()
    token = pathlib.Path('.local/pairing-token').read_text()
    url = 'ws://127.0.0.1:8765/voice'
    try:
        async with connect(url):
            raise AssertionError('Unauthenticated connection accepted')
    except InvalidStatus as e:
        assert e.response.status_code == 403
    engine = SpeechEngine()
    pcm = await engine.render(args.text)
    engine.executor.shutdown()
    source = np.frombuffer(pcm, dtype='<i2').astype(np.float32)
    input_pcm = resample_poly(source, 2, 3).clip(-32768,32767).astype('<i2').tobytes()
    async with connect(url, additional_headers={'Authorization':'Bearer '+token}, max_size=65536) as ws:
        # Speech and trailing silence are replayed at real-time cadence.
        end_at = None
        async def feed():
            nonlocal end_at
            for payload in (bytes(16000), input_pcm, bytes(16000*2*12)):
                for offset in range(0,len(payload),640):
                    await ws.send(payload[offset:offset+640])
                    await asyncio.sleep(.02)
                if payload is input_pcm:end_at=time.monotonic()
        task = asyncio.create_task(feed())
        received = 0
        first = None
        try:
            async with asyncio.timeout(45):
                async for message in ws:
                    if isinstance(message,bytes):
                        assert len(message)>8 and (len(message)-8)%2==0
                        received += len(message)-8
                        if first is None:
                            first=time.monotonic()
                            await ws.send(json.dumps({'type':'interrupt'}))
                    elif json.loads(message).get('type')=='interrupt' and first:
                        print(json.dumps({'evidence':'synthetic network speech replay',
                            'audio_bytes_before_interrupt_ack':received,
                            'reply_after_input_end_ms':(first-end_at)*1000 if end_at else None,
                            'interrupt_roundtrip_ms':(time.monotonic()-first)*1000}))
                        break
                else:raise AssertionError('Connection ended before audio and interrupt')
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)

asyncio.run(main())
