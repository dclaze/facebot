# Skill: Laughing contest

Status: **preview only; awaiting Doug's approval**. Not loaded by the runtime.
Owner: Laughing contest demo chat; deployment remains with the app owner.

1. During an engaged conversation, offer once: “Want to try a laughing contest?”
   Wait for assent; silence is not assent.
2. Say “You go first.” Yield the floor until the participant's laugh ends.
3. Hide the normal face for 0.18s immediately before the prepared theatrical
   cackle. Show amber wolf-like eyes from the first audio sample through the
   entire recording, including its echo tail. Restore the normal face only
   when the clip ends. Doug approved the V2 laugh and requested this V3 timing.
4. Restore the ordinary face and finish silently. Doug requested removing “Okay, you win” in v4. End without automatic repetition.

The demo participant is synthesized, not Doug's daughter. “You go first” is
the character's line in this interpretation.

## Playback contract for eventual integration

Use prepared local audio, no volume boost, strobe or looping. Stop, mute,
interruption, departure, timeout or playback failure cancels audio and the visual
override and restores the face. Muting stays in force. Uncertain laughter
detection must not trigger the scare; never overlap a participant's speech.
Production requires explicit game state and audio-playhead cues in both native
clients; a prompt alone cannot implement synchronization or cancellation.

## Rehearsal

Run `.venv/bin/python scripts/laughing-contest-demo.py`. Outputs live under
`.local/laughing-contest/`: MP4, soundtrack, two laugh variants, frame previews,
and a JSON timeline/verification receipt. The renderer never connects to the
live server, microphone or tablet. This is a locally rendered rehearsal, not a
physical device recording or a live laughter-recognition test.

Speech: installed local Kokoro af_heart; simulated participant: af_sky.
V2 scary laugh: NinjaSharkStudios' CC0 Evil Laugh_1.wav, sourced from Freesound
at Doug's request for a MUCH scarier, deeper performance. Main treatment is
-4.98 semitones, bass reinforcement and short echo. See
content/laughing-contest/CREDITS.md and source.json for source/license/checksum.
V1 used AntumDeluge's witch cackle and is preserved privately for comparison.
No paid service. Face geometry
adapts the existing asymmetric face; forest and eyes are new vector geometry.
Rendering uses Pillow, NumPy, SciPy and imageio-ffmpeg (development only).
Install imageio-ffmpeg under .local/laughing-contest-tools if absent.

Await Doug's approval of sound, intensity and pacing before runtime integration.
The app owner then verifies actual detection, synchronization and cancellation
on both platforms. Approval of this demo does not itself prove those behaviors.
