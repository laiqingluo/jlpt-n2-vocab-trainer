from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from tts_provider import generate_cn_speech, generate_word_speech


BACKEND_DIR = Path(__file__).resolve().parent
CACHE_DIR = BACKEND_DIR / "cache"
WORD_CACHE_DIR = CACHE_DIR / "word"
CN_CACHE_DIR = CACHE_DIR / "cn"
WORD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
CN_CACHE_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()


class AudioRequest(BaseModel):
    word: str


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


@router.post("/api/word_audio")
async def word_audio_endpoint(req: AudioRequest):
    word = req.word.strip()
    if not word:
        raise HTTPException(422, "word 不能为空")

    cache_path = WORD_CACHE_DIR / f"{_md5(word)}.mp3"
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return FileResponse(cache_path, media_type="audio/mpeg")

    try:
        audio_bytes = await generate_word_speech(word)
    except Exception as exc:
        raise HTTPException(502, f"词语 TTS 失败: {exc}") from exc
    if not audio_bytes:
        raise HTTPException(502, "词语 TTS 返回空音频")

    cache_path.write_bytes(audio_bytes)
    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/api/cn_audio")
async def cn_audio_endpoint(req: AudioRequest):
    text = req.word.strip()
    if not text:
        raise HTTPException(422, "text 不能为空")

    cache_path = CN_CACHE_DIR / f"{_md5('cn:' + text)}.mp3"
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return FileResponse(cache_path, media_type="audio/mpeg")

    try:
        audio_bytes = await generate_cn_speech(text)
    except Exception as exc:
        raise HTTPException(502, f"中文 TTS 失败: {exc}") from exc
    if not audio_bytes:
        raise HTTPException(502, "中文 TTS 返回空音频")

    cache_path.write_bytes(audio_bytes)
    return Response(content=audio_bytes, media_type="audio/mpeg")
