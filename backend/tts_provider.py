from __future__ import annotations

import asyncio
import os
import xml.sax.saxutils as saxutils
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional until dependencies are installed
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if load_dotenv:
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env")

VOICE_NAME = "ja-JP-NanamiNeural"
CN_VOICE_NAME = "zh-CN-XiaoxiaoNeural"
DEFAULT_PROSODY_RATE = -0.30


def _xml_encode(text: str) -> str:
    """Escape XML special chars then encode non-ASCII as numeric character references.

    The Azure Speech SDK C++ layer uses the Windows filesystem encoding when it
    receives a Python str on Windows.  Converting every non-ASCII codepoint to an
    XML numeric reference (&#N;) keeps the entire SSML string pure ASCII and avoids
    any encoding-dependent data loss.
    """
    escaped = saxutils.escape(text)
    return "".join(c if ord(c) < 128 else f"&#{ord(c)};" for c in escaped)


def _speechsdk():
    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError as exc:
        raise RuntimeError("缺少 azure-cognitiveservices-speech 依赖，请先安装 backend/requirements.txt") from exc
    return speechsdk


def _speech_config(voice_name: str):
    speechsdk = _speechsdk()
    speech_key = os.getenv("AZURE_SPEECH_KEY", "")
    speech_region = os.getenv("AZURE_SPEECH_REGION", "eastus")
    if not speech_key:
        raise RuntimeError("缺少 AZURE_SPEECH_KEY")

    config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
    config.speech_synthesis_voice_name = voice_name
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio24Khz96KBitRateMonoMp3
    )
    return speechsdk, config


def _generate_word_sync(word: str) -> bytes:
    speechsdk, config = _speech_config(VOICE_NAME)
    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ja-JP">'
        f'<voice name="{VOICE_NAME}">'
        f'<prosody rate="{DEFAULT_PROSODY_RATE:+.0%}">{_xml_encode(word)}</prosody>'
        "</voice></speak>"
    )
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    result = synthesizer.speak_ssml_async(ssml).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        details = result.cancellation_details
        raise RuntimeError(f"Azure TTS 失败: {details.error_details}")
    return result.audio_data


def _generate_cn_sync(text: str) -> bytes:
    speechsdk, config = _speech_config(CN_VOICE_NAME)
    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">'
        f'<voice name="{CN_VOICE_NAME}">'
        f'<prosody rate="-10%">{_xml_encode(text)}</prosody>'
        "</voice></speak>"
    )
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
    result = synthesizer.speak_ssml_async(ssml).get()
    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        details = result.cancellation_details
        raise RuntimeError(f"Azure Chinese TTS 失败: {details.error_details}")
    return result.audio_data


async def generate_word_speech(word: str) -> bytes:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _generate_word_sync, word)


async def generate_cn_speech(text: str) -> bytes:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _generate_cn_sync, text)
