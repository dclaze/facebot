"""One local character. Run with FACEBOT_TOKEN and python -m server.app.

Development transport defaults to loopback. LAN use requires explicit TLS
certificate/key arguments; never send the pairing token or visitor audio over
an unencrypted LAN socket. Private local recording requires explicit owner configuration.
"""
import argparse
import asyncio
import hmac
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, Header, HTTPException
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair, LLMUserAggregatorParams
from pipecat.services.ollama.llm import OLLamaLLMService
from server.transcription import LocalSTT
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport, FastAPIWebsocketParams
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import SpeechTimeoutUserTurnStopStrategy
from server.protocol import FaceSerializer
from server.tts import SpeechEngine, LocalTTS
from server.guard import ReplyGuard
from server.persona import instructions, bounded_context
from server.scene import SceneState
from server.timing import StageTiming
from server.recording import InteractionRecorder, RecordingTap
from server.hearing import HearingRepair
from server.prepared_conversation import PreparedConversation
from server.kiosk_playback import KioskPlayback
from server.playback_probe import PlaybackProbes, SCENARIOS
from server.kiosk_control import MuteLatch
from server import settings, skill_store
from server.profiles import active
from server.context_budget import ContextBudget, BudgetedContext
from server.interaction import InteractionState, VisitorControl, ProactiveTurn
from server.vision import VisionState, ImageLabeler
from server.visual_reactions import VisualReaction
from server.scripted_quips import QuipDirector, load_quips
from server.sound_effects import SoundBank, SoundEffectRequest, SoundEffectPlayback
from server.robin_skit import RobinSkitRequest
from server.robin_performance import RobinPerformance as RobinSkit, RobinPerformancePlayback as RobinSkitPlayback, add_media_route
from server.robin_intent import RobinIntentReply
from server.sound_performance import SoundPerformance, AutomaticSoundDirector, load_performance
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import LLMContextFrame

class FrameTrace(FrameProcessor):
    def __init__(self, scene=None, timing=None, vision=None, **kwargs):
        super().__init__(**kwargs)
        self.timing = timing
        self.scene = scene
        self.vision = vision
        self.encounter_generation = scene.encounter.generation if scene else 0

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if self.timing:
            kind = type(frame).__name__
            stages = {
                'after_stt': {'VADUserStartedSpeakingFrame':'vad_start', 'VADUserStoppedSpeakingFrame':'vad_stop', 'TranscriptionFrame':'stt_done'},
                'before_llm': {'LLMContextFrame':'llm_start'},
                'after_llm': {'LLMTextFrame':'llm_first_text', 'LLMFullResponseEndFrame':'llm_done'},
                'after_tts': {'TTSAudioRawFrame':'first_pcm'},
            }
            stage = stages.get(self.name, {}).get(kind)
            if stage and not getattr(frame,'sound_effect',False): self.timing.mark(stage)
        if type(frame).__name__ == "LLMContextFrame" and self.name == "before_llm":
            source = frame.context.get_messages()
            if self.scene and self.encounter_generation != self.scene.encounter.generation:
                # Preserve only the new triggering utterance, not another group's history.
                source = source[-1:] if source and source[-1].get('role') == 'user' and not getattr(frame, 'scene_event', None) else []
                self.encounter_generation = self.scene.encounter.generation
            messages = bounded_context(source, settings.read()['character_name'])
            if self.scene:
                messages.insert(1, {'role': 'system', 'content': self.scene.context()})
            if self.vision and self.vision.context():
                messages.insert(2, {'role': 'system', 'content': self.vision.context()})
            if getattr(frame, 'scene_event', None):
                messages.append({'role': 'system', 'content':
                    'EVENT: stable_visual_arrival. This is a camera event, not visitor speech. '
                    + active()['arrival_instruction'] + ' '
                    'Do not imply recognition, identify costumes or invent actions. '
                    'Do not require a name or repeat an introduction. Keep it under 15 words.'})
            frame.context.set_messages(messages)
        if os.environ.get("FACEBOT_TRACE_FRAMES") == "1" and type(frame).__name__ not in ("InputAudioRawFrame", "OutputAudioRawFrame", "TTSAudioRawFrame"):
            logger.warning("{} {}", self.name, type(frame).__name__)
        await self.push_frame(frame, direction)




def create_app(token, engine=None):
    if len(token) < 24:
        raise ValueError('FACEBOT_TOKEN must contain at least 24 characters')
    if os.environ.get('FACEBOT_LLM', 'qwen2.5:1.5b') not in ('qwen2.5:1.5b', 'qwen3.5:9b', 'qwen3:1.7b'):
        raise ValueError('Choose an evaluated local model; cloud model routing is disabled')
    instructions(settings.read()["character_name"])
    if engine is None:
        backend = os.environ.get('FACEBOT_TTS', 'kokoro')
        if backend == 'qwen3':
            from server.expressive_tts import ExpressiveSpeechEngine
            engine = ExpressiveSpeechEngine(voice=os.environ.get('FACEBOT_EXPRESSIVE_VOICE', 'Aiden'),
                speed=float(os.environ.get('FACEBOT_SPEECH_RATE', '1.18')), live_settings=True)
        elif backend == 'kokoro':
            engine = SpeechEngine(voice=os.environ.get("FACEBOT_VOICE", active()["character_profile"]["voice"]), speed=float(os.environ.get("FACEBOT_SPEECH_RATE", "1.18")), live_settings=True)
        else:
            raise ValueError('Choose local TTS: kokoro or qwen3')
    occupied = asyncio.Lock()
    current_interaction = None
    current_task = None
    current_quips = None
    recorder = InteractionRecorder.configured()
    timing = StageTiming()
    probes = PlaybackProbes()
    mute = MuteLatch()
    sound_bank = SoundBank()
    robin_skit = RobinSkit()
    sound_performance_config = load_performance(active()['id'], sound_bank)
    if os.environ.get("FACEBOT_LLM", "qwen2.5:1.5b") != "qwen2.5:1.5b":
        raise ValueError("Install and verify the selected model tokenizer before changing the runtime model")
    context_budget = ContextBudget()
    quip_pack = load_quips(active()['id'])
    quips = QuipDirector(quip_pack) if quip_pack else None
    vision = VisionState()
    labeler = ImageLabeler(vision)
    vision_occupied = asyncio.Lock()
    @asynccontextmanager
    async def lifespan(app):
        # Startup warm-up is synthetic and not a visitor-latency measurement.
        await engine.render(active()['arrival'][0])
        yield
        recorder.close()
        await labeler.close()
        engine.executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
    add_media_route(app, robin_skit, token)
    from server.owner_quips import OwnerQuips, add_routes as add_quip_routes
    add_quip_routes(app, token, lambda: current_quips)

    @app.get('/health')
    async def health():
        return {'status':'ready', 'occupied':occupied.locked(), 'protocol':1, 'kiosk_mode':os.environ.get('FACEBOT_KIOSK_MODE') == '1', 'profile':active()['id'], 'scripted_quips':quips.report() if quips else {'enabled':False}, 'robin_skit':robin_skit.report(),
                'tts':{'backend':'qwen3' if getattr(engine, 'supports_emotion', False) else 'kokoro', 'model':engine.model_name, 'voice':engine.voice,
                       'emotion_controls':getattr(engine, 'supports_emotion', False)},
                'sound_effects':{'types':len(sound_bank.effects),'clips':len(sound_bank.pcm), 'automatic':sound_performance_config is not None, 'routing_version':2}}

    @app.get('/runtime-settings')
    async def runtime_settings(authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, 'Bearer ' + token):
            raise HTTPException(status_code=403)
        from fastapi.responses import JSONResponse
        rate = engine.last_synthesized_rate
        return JSONResponse({**settings.presentation(),
                             'last_synthesized_rate': rate if type(rate) in (int, float) else None},
                            headers={'Cache-Control': 'no-store'})

    @app.get('/diagnostics')
    async def diagnostics(authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, 'Bearer ' + token):
            raise HTTPException(status_code=403)
        report = timing.report()
        report['playback_probes'] = probes.report()
        report['mute'] = {'enabled': mute.value, 'persistence_error': mute.error}
        report['recording'] = recorder.report()
        report['transcription'] = current_interaction.stt.report() if current_interaction else None
        report['scripted_quips'] = quips.report() if quips else {'enabled': False}
        report['sound_effects'] = current_interaction.sound_performance.report() if current_interaction else None
        report['voice_state'] = ({
            'silenced': current_interaction.scene.encounter.silenced,
            'user_speaking': current_interaction.user_speaking,
            'bot_speaking': current_interaction.bot_speaking,
            'response_pending': current_interaction.response_pending,
            'performance_video_enabled': getattr(current_interaction,'performance_video_enabled',False),
        } if current_interaction else None)
        return report

    @app.post('/owner/rehearse/{scenario}')
    async def rehearse(scenario: str, authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, 'Bearer ' + token):
            raise HTTPException(status_code=403)
        if scenario not in SCENARIOS:
            raise HTTPException(status_code=404, detail='Unknown rehearsal')
        if not current_task or not current_interaction:
            raise HTTPException(status_code=409, detail='No connected face')
        if not getattr(current_interaction, 'playback_probes_enabled', False):
            raise HTTPException(status_code=409, detail='Update the tablet for native playback receipts')
        if (current_interaction.scene.encounter.silenced or current_interaction.user_speaking
                or current_interaction.bot_speaking or current_interaction.response_pending):
            raise HTTPException(status_code=409, detail='Wait for an unmuted idle face')
        try:
            identifier = probes.begin(scenario)
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error))
        from pipecat.frames.frames import OutputTransportMessageFrame
        await current_task.queue_frame(OutputTransportMessageFrame(message={'type':'playback_probe','id':identifier}))
        await current_task.queue_frame(LLMContextFrame(LLMContext([{'role':'user','content':SCENARIOS[scenario]}])))
        return {'id': identifier, 'status':'queued', 'evidence':'synthetic scenario; not microphone recognition or audible latency'}

    @app.post('/owner/stop')
    async def owner_stop(authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, 'Bearer ' + token):
            raise HTTPException(status_code=403)
        effective = mute.set_muted(True)
        if current_interaction and current_task:
            from pipecat.frames.frames import InterruptionFrame, OutputTransportMessageFrame
            current_interaction.scene.encounter.silenced = effective
            current_interaction.control_epoch += 1
            current_interaction.response_pending = False
            await current_task.queue_frame(InterruptionFrame())
            await current_task.queue_frame(OutputTransportMessageFrame(message={
                'type': 'kiosk_state', 'muted': effective}))
        probes.cancel()
        return {'status':'muted'}

    @app.post('/owner/resume')
    async def owner_resume(authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, 'Bearer ' + token):
            raise HTTPException(status_code=403)
        effective = mute.set_muted(False)
        if current_interaction:
            current_interaction.scene.encounter.silenced = effective
            if current_task:
                from pipecat.frames.frames import OutputTransportMessageFrame
                await current_task.queue_frame(OutputTransportMessageFrame(message={
                    'type': 'kiosk_state', 'muted': effective}))
        if effective:
            raise HTTPException(status_code=503, detail='Mute settings could not be saved; staying muted')
        return {'status':'unmuted' if current_interaction else 'disconnected'}

    @app.post('/skills/robin-williams/preview')
    async def preview_robin(utterance: str = 'Is Robin Williams there?', authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, 'Bearer ' + token):
            raise HTTPException(status_code=403)
        if not current_task or not current_interaction:
            raise HTTPException(status_code=409, detail='No connected face')
        if (current_interaction.scene.encounter.silenced or current_interaction.user_speaking
                or current_interaction.bot_speaking or current_interaction.response_pending):
            raise HTTPException(status_code=409, detail='Wait for an unmuted idle face')
        if not isinstance(utterance,str) or not 1 <= len(utterance.strip()) <= 180:
            raise HTTPException(status_code=422, detail='Preview utterance must be 1-180 characters')
        if not robin_skit.pcm:
            raise HTTPException(status_code=409, detail='Performance unavailable')
        recorder.event('owner_performance_preview')
        await current_task.queue_frame(LLMContextFrame(LLMContext([{'role':'user','content':utterance}])))
        return {'status':'queued','evidence':'synthetic owner preview, not microphone recognition'}

    @app.websocket('/voice')
    async def voice(ws: WebSocket):
        nonlocal current_interaction, current_task, current_quips
        supplied = ws.headers.get('authorization', '')
        if not hmac.compare_digest(supplied, 'Bearer ' + token):
            await ws.close(code=1008)
            return
        if occupied.locked():
            await ws.close(code=1013)
            return
        async with occupied:
            await ws.accept()
            scene = SceneState()
            scene.encounter.silenced = mute.value
            interaction = InteractionState(scene)
            performance = SoundPerformance(sound_bank, interaction, sound_performance_config,
                                           pack_enabled=lambda: skill_store.enabled('sound-effects'))
            interaction.sound_performance = performance
            current_interaction = interaction
            codec = FaceSerializer(on_scene=scene.update, recorder=recorder, probes=probes)
            transport = FastAPIWebsocketTransport(ws, FastAPIWebsocketParams(
                audio_in_enabled=True, audio_out_enabled=True,
                audio_in_sample_rate=16000, audio_out_sample_rate=24000,
                serializer=codec, allowed_origins=[]))
            context = LLMContext([{'role':'system','content':instructions(settings.read()['character_name'])}])
            pair = LLMContextAggregatorPair(context, user_params=LLMUserAggregatorParams(
                vad_analyzer=SileroVADAnalyzer(params=VADParams(start_secs=.1, stop_secs=.45)),
                user_turn_strategies=UserTurnStrategies(stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=.25)])))
            stt = LocalSTT(recorder=recorder, settings=LocalSTT.Settings(
                model='mlx-community/whisper-tiny.en-mlx'))
            interaction.stt = stt
            llm = OLLamaLLMService(base_url='http://127.0.0.1:11434/v1', settings=OLLamaLLMService.Settings(
                model=os.environ.get('FACEBOT_LLM','qwen2.5:1.5b'),
                max_completion_tokens=64, temperature=.7,
                extra={'extra_body':{'think':False}}))
            robin_request = RobinSkitRequest(robin_skit, interaction, mark=timing.mark, name_provider=lambda: settings.read()['character_name'], performance=performance, enabled=lambda: skill_store.enabled('robin-williams'))
            video_enabled = bool({'performance_video_v1','performance-video-v1'} & {x.strip() for x in ws.headers.get('x-facebot-capabilities','').split(',')})
            interaction.performance_video_enabled = video_enabled
            interaction.playback_probes_enabled = 'playback-probe-v1' in ws.headers.get('x-facebot-capabilities','').split(',')
            current_quips = OwnerQuips(interaction, mark=timing.mark)
            pipeline = Pipeline([transport.input(), stt, RecordingTap(recorder, "input"), FrameTrace(name="after_stt", timing=timing), VisitorControl(interaction, on_mute=mute.set_muted), pair.user(), ProactiveTurn(interaction, context, vision=vision, quips=quips), robin_request, SoundEffectRequest(sound_bank, interaction, mark=timing.mark, name_provider=lambda: settings.read()['character_name'], performance=performance, enabled=lambda: skill_store.enabled('sound-effects')), VisualReaction(interaction, mark=timing.mark), HearingRepair(name=active()['character_profile']['defaults']['character_name'], mark=timing.mark, name_provider=lambda: settings.read()['character_name']), PreparedConversation(interaction, mark=timing.mark, name_provider=lambda: settings.read()['character_name'], enabled=skill_store.enabled), FrameTrace(name="before_llm", scene=scene, timing=timing, vision=vision), BudgetedContext(context_budget, timing), llm, FrameTrace(name="after_llm", timing=timing), RobinIntentReply(robin_request), ReplyGuard(is_silenced=lambda: scene.encounter.silenced, record=recorder.event),
                                 AutomaticSoundDirector(performance), RecordingTap(recorder, "reply"), current_quips, LocalTTS(engine, timing=timing), KioskPlayback(interaction, mark=timing.mark), RobinSkitPlayback(robin_skit, interaction, mark=timing.mark, video_enabled=video_enabled), SoundEffectPlayback(sound_bank, interaction, mark=timing.mark, performance=performance), FrameTrace(name="after_tts", timing=timing), transport.output(), pair.assistant()])
            # Visitor encounters can be separated by long quiet periods.
            # Socket disconnect/app lifecycle still cancels this worker.
            task = PipelineTask(pipeline, params=PipelineParams(), enable_rtvi=False,
                                idle_timeout_secs=None)
            current_task = task
            @transport.event_handler('on_client_disconnected')
            async def disconnected(transport, websocket):
                await task.cancel()
            try:
                await PipelineRunner(handle_sigint=False).run(task)
            except Exception:
                # Framework exceptions can contain text; keep runtime log content-free.
                recorder.event('voice_session_failed')
                logger.warning('Voice session failed; connection closed')
                await ws.close(code=1011)
            finally:
                probes.cancel()
                current_interaction = None
                current_task = None
                current_quips = None
    @app.get('/vision/diagnostics')
    async def vision_diagnostics(authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, 'Bearer ' + token):
            raise HTTPException(status_code=403)
        return vision.report()

    @app.websocket('/vision')
    async def visual_stream(ws: WebSocket):
        if not hmac.compare_digest(ws.headers.get('authorization', ''), 'Bearer ' + token):
            await ws.close(code=1008)
            return
        if vision_occupied.locked():
            await ws.close(code=1013)
            return
        async with vision_occupied:
            await ws.accept()
            try:
                while True:
                    packet = await ws.receive_bytes()
                    if not 5 <= len(packet) <= 256004:
                        await ws.close(code=1009)
                        return
                    age_ms = int.from_bytes(packet[:4], 'big')
                    try:
                        await labeler.label(packet[4:], age_ms)
                    except Exception as error:
                        # Class only: never retain image/model output or exception text.
                        vision.errors += 1
                        vision.last_error_kind = type(error).__name__
                    await ws.send_json(vision.report())
            except Exception:
                pass  # Connection closure must never tear down the voice pipeline.
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--cert')
    parser.add_argument('--key')
    parser.add_argument('--allow-private-lan', action='store_true',
                        help='Opt in to unencrypted pairing/audio on a trusted private IPv4 LAN only')
    args = parser.parse_args()
    from server.network import validate_bind
    try:
        validate_bind(args.host, args.cert, args.key, args.allow_private_lan)
    except ValueError as error:
        parser.error(str(error))
    # Disable library debug logs which include transcriptions and model messages.
    logger.remove()
    logger.add(sys.stderr, level='WARNING')
    import uvicorn
    uvicorn.run(create_app(os.environ.get('FACEBOT_TOKEN','')), host=args.host, port=args.port,
                ssl_certfile=args.cert, ssl_keyfile=args.key, access_log=False, ws_max_size=256004,
                ws_max_queue=8, ws_ping_interval=5, ws_ping_timeout=5)

if __name__ == '__main__':
    main()
