#!/usr/bin/env python3
"""Render authored kiosk rehearsals from real pack lines and accepted cackle.

Offline synthetic visitors only. This does not assert physical device behavior.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('rig', ROOT / 'scripts/laughing-contest-demo.py')
rig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rig)
from server.kiosk_experiences import load_pack
from server.kiosk_playback import load_cackle
from server.tts import SpeechEngine


def render(output):
    output.mkdir(parents=True, exist_ok=True)
    pack = load_pack()['replies']
    scenes = {
        'candy-welcome': [('visitor', 'Trick or treat!'), ('bot', pack['greeting'][0][0]),
                          ('visitor', 'Can I take two candies?'), ('bot', 'ONE ONLY, PLEASE!')],
        'ghost-joke': [('visitor', 'Tell me a joke.'), ('bot', pack['joke'][0][0])],
        'tiny-scare': [('visitor', 'Can you scare me?'), ('bot', pack['scare'][0][0])],
        'laugh-challenge': [('visitor', 'Laughing game!'), ('bot', pack['game_start'][0][0]),
                            ('visitor', 'Ha ha ha!'), ('visitor', 'Your turn.'), ('cackle', '')],
    }
    engine = SpeechEngine()
    receipts = []
    try:
        for name, lines in scenes.items():
            folder = output / name
            folder.mkdir(parents=True, exist_ok=True)
            parts = [rig.np.zeros(round(.4 * rig.SR))]
            cursor, cues = .4, []
            for index, (actor, text) in enumerate(lines):
                if actor == 'cackle':
                    data = rig.np.frombuffer(load_cackle(), '<i2').astype(float)/32768
                    key = 'deep-cackle'
                else:
                    engine.voice = 'af_heart' if actor == 'bot' else 'am_adam'
                    data = rig.np.frombuffer(engine.synthesize(text), '<i2').astype(float)/32768
                    key = 'line-' + str(index)
                cues.append({'key': key, 'start': cursor, 'end': cursor + len(data)/rig.SR,
                             'caption': text, 'speaker': 'Casper' if actor != 'visitor' else 'Visitor - simulated'})
                parts.extend([data, rig.np.zeros(round(.65 * rig.SR))])
                cursor += len(data)/rig.SR + .65
            parts.append(rig.np.zeros(round(.5 * rig.SR)))
            audio = rig.np.concatenate(parts)
            rig.write_wav(folder / 'soundtrack.wav', audio)
            if not any(c['key'] == 'deep-cackle' for c in cues):
                cues.append({'key': 'deep-cackle', 'start': -10, 'end': -10, 'caption': '', 'speaker': ''})
            movie = folder / 'preview.mp4'
            fps = 15
            command = [rig.imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-v', 'error', '-f', 'rawvideo',
                       '-pix_fmt', 'rgb24', '-s', f'{rig.W}x{rig.H}', '-r', str(fps), '-i', 'pipe:0',
                       '-i', str(folder / 'soundtrack.wav'), '-c:v', 'libx264', '-preset', 'fast',
                       '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k',
                       '-movflags', '+faststart', '-shortest', str(movie)]
            process = subprocess.Popen(command, stdin=subprocess.PIPE)
            try:
                for frame in range(math.ceil(len(audio)/rig.SR*fps)):
                    process.stdin.write(rig.render(frame/fps, audio, cues,
                        title=name.upper().replace('-', ' ') + ' / KIOSK REHEARSAL').tobytes())
                process.stdin.close()
                if process.wait():
                    raise RuntimeError('Encoding failed')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            subprocess.run([rig.imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-i', str(movie),
                            '-f', 'null', '-'], check=True)
            selections = [('reply', next(c['start'] + .5 for c in cues if c['speaker'] == 'Casper')),
                          ('restored', len(audio)/rig.SR - .2)]
            if name == 'laugh-challenge':
                cackle = next(c for c in cues if c['key'] == 'deep-cackle')
                selections += [('eyes', cackle['start'] + 1), ('eyes-tail', cackle['end'] - .15)]
            for label, at in selections:
                subprocess.run([rig.imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-v', 'error', '-i', str(movie), '-ss', str(at), '-frames:v', '1', str(folder / (label + '-encoded.png'))], check=True)
            receipt = {'scene': name, 'evidence': 'offline synthetic rehearsal; not physical acceptance',
                       'duration_seconds': len(audio)/rig.SR, 'full_decode': True,
                       'timeline': cues, 'sha256': hashlib.sha256(movie.read_bytes()).hexdigest(),
                       'peak_dbfs': float(20*rig.np.log10(max(abs(rig.read_wav(folder/'soundtrack.wav')))))}
            (folder/'verification.json').write_text(json.dumps(receipt, indent=2)+'\n')
            receipts.append(receipt)
            print(name + ': ' + str(movie), flush=True)
    finally:
        engine.executor.shutdown()
    (output/'verification.json').write_text(json.dumps(receipts, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    render(parser.parse_args().output)
