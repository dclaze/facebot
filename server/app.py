"""One local ghost. Run with FACEBOT_TOKEN and python -m server.app.

Development transport defaults to loopback. LAN use requires explicit TLS
certificate/key arguments; never send the pairing token or visitor audio over
an unencrypted LAN socket. No raw media/transcript logging is configured.
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
from pipecat.services.whisper.stt import WhisperSTTServiceMLX
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport, FastAPIWebsocketParams
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import SpeechTimeoutUserTurnStopStrategy
from server.protocol import FaceSerializer
from server.tts import SpeechEngine, LocalTTS
from server.guard import ReplyGuard
from server.persona import instructions, bounded_context
from server.scene import SceneState
from server.timing import StageTiming
from server.interaction import InteractionState, VisitorControl, ProactiveTurn
from pipecat.processors.frame_processor import FrameProcessor

class FrameTrace(FrameProcessor):
    def __init__(self, scene=None, timing=None, **kwargs):
        super().__init__(**kwargs)
        self.timing = timing
        self.scene = scene
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
            if stage: self.timing.mark(stage)
        if type(frame).__name__ == "LLMContextFrame" and self.name == "before_llm":
            source = frame.context.get_messages()
            if self.scene and self.encounter_generation != self.scene.encounter.generation:
                # Preserve only the new triggering utterance, not another group's history.
                source = source[-1:] if source and source[-1].get('role') == 'user' and not getattr(frame, 'scene_event', None) else []
                self.encounter_generation = self.scene.encounter.generation
            messages = bounded_context(source, os.environ.get("FACEBOT_NAME", "Boo"))
            if self.scene:
                messages.insert(1, {'role': 'system', 'content': self.scene.context()})
            if getattr(frame, 'scene_event', None):
                messages.append({'role': 'system', 'content':
                    'EVENT: stable_visual_arrival. This is a camera event, not visitor speech. '
                    'Initiate one brief, witty welcome to the visible audience at the Halloween table. '
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
    instructions(os.environ.get("FACEBOT_NAME", "Boo"))
    engine = engine or SpeechEngine(voice=os.environ.get("FACEBOT_VOICE", "af_heart"), speed=float(os.environ.get("FACEBOT_SPEECH_RATE", "1.12")))
    occupied = asyncio.Lock()
    timing = StageTiming()
    @asynccontextmanager
    async def lifespan(app):
        # Startup warm-up is synthetic and not a visitor-latency measurement.
        await engine.render('One piece, darling. My haunting budget is tiny.')
        yield
        engine.executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.get('/health')
    async def health():
        return {'status':'ready', 'occupied':occupied.locked(), 'protocol':1}

    @app.get('/diagnostics')
    async def diagnostics(authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, 'Bearer ' + token):
            raise HTTPException(status_code=403)
        return timing.report()

    @app.websocket('/voice')
    async def voice(ws: WebSocket):
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
            interaction = InteractionState(scene)
            codec = FaceSerializer(on_scene=scene.update)
            transport = FastAPIWebsocketTransport(ws, FastAPIWebsocketParams(
                audio_in_enabled=True, audio_out_enabled=True,
                audio_in_sample_rate=16000, audio_out_sample_rate=24000,
                serializer=codec, allowed_origins=[]))
            context = LLMContext([{'role':'system','content':instructions(os.environ.get('FACEBOT_NAME', 'Boo'))}])
            pair = LLMContextAggregatorPair(context, user_params=LLMUserAggregatorParams(
                vad_analyzer=SileroVADAnalyzer(params=VADParams(start_secs=.1, stop_secs=.25)),
                user_turn_strategies=UserTurnStrategies(stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=.25)])))
            stt = WhisperSTTServiceMLX(settings=WhisperSTTServiceMLX.Settings(
                model='mlx-community/whisper-tiny.en-mlx'))
            llm = OLLamaLLMService(base_url='http://127.0.0.1:11434/v1', settings=OLLamaLLMService.Settings(
                model=os.environ.get('FACEBOT_LLM','qwen2.5:1.5b'),
                max_completion_tokens=64, temperature=.7,
                extra={'extra_body':{'think':False}}))
            pipeline = Pipeline([transport.input(), stt, FrameTrace(name="after_stt", timing=timing), VisitorControl(interaction), pair.user(), ProactiveTurn(interaction, context), FrameTrace(name="before_llm", scene=scene, timing=timing), llm, FrameTrace(name="after_llm", timing=timing), ReplyGuard(is_silenced=lambda: scene.encounter.silenced),
                                 LocalTTS(engine, timing=timing), FrameTrace(name="after_tts", timing=timing), transport.output(), pair.assistant()])
            task = PipelineTask(pipeline, params=PipelineParams(), enable_rtvi=False)
            @transport.event_handler('on_client_disconnected')
            async def disconnected(transport, websocket):
                await task.cancel()
            try:
                await PipelineRunner(handle_sigint=False).run(task)
            except Exception:
                # Framework exceptions can contain text; keep runtime log content-free.
                logger.warning('Voice session failed; connection closed')
                await ws.close(code=1011)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--cert')
    parser.add_argument('--key')
    args = parser.parse_args()
    if args.host not in ('127.0.0.1','::1','localhost') and not (args.cert and args.key):
        parser.error('LAN listening requires --cert and --key')
    # Disable library debug logs which include transcriptions and model messages.
    logger.remove()
    logger.add(sys.stderr, level='WARNING')
    import uvicorn
    uvicorn.run(create_app(os.environ.get('FACEBOT_TOKEN','')), host=args.host, port=args.port,
                ssl_certfile=args.cert, ssl_keyfile=args.key, access_log=False, ws_max_size=4096,
                ws_max_queue=8)

if __name__ == '__main__':
    main()
