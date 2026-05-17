import logging
import os
import re
import subprocess
import wave
import uuid
import audioop
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

import imageio_ffmpeg
import torch
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from database import (
    create_access_token,
    create_user,
    decode_access_token,
    get_generated_file,
    init_db,
    authenticate_user,
    record_generated_file,
    JWT_ALGORITHM,
    JWT_SECRET,
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = BASE_DIR / "output"
REFERENCE_DIR = BASE_DIR / "reference_voices"

MAX_TEXT_LENGTH = 500
MAX_UPLOAD_SIZE = 8 * 1024 * 1024
REFERENCE_SAMPLE_RATE = 24000
REFERENCE_MAX_SECONDS = 12
REFERENCE_SEGMENT_SECONDS = 6
REFERENCE_MAX_SEGMENTS = 3
REFERENCE_WINDOW_SECONDS = 0.5
VOICE_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
MEDIA_TOKEN_EXPIRE_MINUTES = 60
ALLOWED_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("VOICE_TOOL_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
OUTPUT_FILENAME_RE = re.compile(r"^[a-f0-9]{32}\.(mp3|wav)$")
PRESET_VOICES = {
    "dashu": {"label": "大叔", "filename": "dashu.wav"},
    "shounv": {"label": "少女", "filename": "shounv.wav"},
}
CUSTOM_VOICE_ID = "my_voice"

logger = logging.getLogger("voice-tool")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Private Voice Tool", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=bool(ALLOWED_CORS_ORIGINS),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

tts_model = None
tts_lock = Lock()
generation_lock = Lock()


class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    voice_id: str = Field(min_length=1, max_length=128)
    language: str = Field(default="zh-cn", min_length=2, max_length=16)
    style: str = Field(default="natural", min_length=1, max_length=32)


SPEAKING_STYLES = {
    "natural": {
        "label": "自然口播",
        "temperature": 0.72,
        "top_p": 0.85,
        "top_k": 50,
        "repetition_penalty": 5.0,
        "length_penalty": 1.0,
        "speed": 0.95,
    },
    "steady": {
        "label": "稳重慢讲",
        "temperature": 0.62,
        "top_p": 0.8,
        "top_k": 45,
        "repetition_penalty": 5.5,
        "length_penalty": 1.0,
        "speed": 0.9,
    },
    "energetic": {
        "label": "轻快口播",
        "temperature": 0.82,
        "top_p": 0.9,
        "top_k": 60,
        "repetition_penalty": 4.8,
        "length_penalty": 1.0,
        "speed": 1.02,
    },
    "clone": {
        "label": "音色优先",
        "temperature": 0.65,
        "top_p": 0.85,
        "top_k": 40,
        "repetition_penalty": 10.0,
        "length_penalty": 1.0,
        "speed": 0.95,
    },
}
SENTENCE_PUNCTUATION_RE = re.compile(r"[，。！？；：、,.!?;:]")
CHINESE_BREAK_WORDS = (
    "但是",
    "所以",
    "然后",
    "因为",
    "如果",
    "其实",
    "另外",
    "接下来",
    "同时",
    "不过",
    "而且",
    "比如",
    "最后",
)


def ensure_directories() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)


def prepare_spoken_text(raw_text: str) -> str:
    text = raw_text.strip()
    if not text:
        return ""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    lines = [line.strip(" -—\t") for line in text.split("\n") if line.strip()]
    text = "。".join(line.rstrip("。.!！？?") for line in lines)
    text = text.replace("...", "。").replace("……", "。")

    if SENTENCE_PUNCTUATION_RE.search(text):
        return text if text[-1] in "。.!！？?" else f"{text}。"

    for word in CHINESE_BREAK_WORDS:
        text = text.replace(word, f"，{word}")
    text = text.strip("，")

    chunks = []
    current = ""
    for char in text:
        current += char
        if len(current) >= 18 and char not in "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ":
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)

    if len(chunks) <= 1:
        return text if text[-1] in "。.!！？?" else f"{text}。"

    spoken_parts = []
    for index, chunk in enumerate(chunks):
        punct = "。" if index == len(chunks) - 1 or index % 2 == 1 else "，"
        spoken_parts.append(f"{chunk}{punct}")
    return "".join(spoken_parts)


def get_speaking_style(style_id: str) -> Dict[str, object]:
    return SPEAKING_STYLES.get(style_id, SPEAKING_STYLES["natural"])


def get_tts():
    global tts_model
    with tts_lock:
        if tts_model is None:
            logger.info("Loading XTTS v2 model...")
            from TTS.api import TTS

            device = "cuda" if torch.cuda.is_available() else "cpu"
            tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
            logger.info("XTTS loaded on %s", device)
    return tts_model


def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录或令牌无效")
    token = authorization.split(" ", 1)[1].strip()
    user = decode_access_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或令牌无效")
    return user


def get_user_voice_dir(user_id: int) -> Path:
    path = REFERENCE_DIR / f"user_{user_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_custom_voice_path(user_id: int) -> Optional[Path]:
    user_dir = get_user_voice_dir(user_id)
    preferred = user_dir / f"{CUSTOM_VOICE_ID}.wav"
    if preferred.exists():
        return preferred

    for ext in VOICE_EXTENSIONS:
        candidate = user_dir / f"{CUSTOM_VOICE_ID}{ext}"
        if candidate.exists():
            return candidate
    return None


def get_custom_voice_paths(user_id: int) -> List[Path]:
    user_dir = get_user_voice_dir(user_id)
    main_voice = user_dir / f"{CUSTOM_VOICE_ID}.wav"
    if main_voice.exists():
        parts = sorted(user_dir.glob(f"{CUSTOM_VOICE_ID}_part*.wav"))
        return [main_voice, *parts]

    legacy_voice = get_custom_voice_path(user_id)
    return [legacy_voice] if legacy_voice else []


def build_media_token(user_id: int, filename: str) -> str:
    payload = {
        "sub": str(user_id),
        "file": filename,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=MEDIA_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_media_token(token: str, filename: str) -> Dict:
    if not OUTPUT_FILENAME_RE.fullmatch(filename):
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="媒体令牌无效") from exc

    token_filename = payload.get("file")
    user_id = payload.get("sub")
    if token_filename != filename or not user_id:
        raise HTTPException(status_code=401, detail="媒体令牌无效")

    record = get_generated_file(filename)
    if not record or str(record["user_id"]) != str(user_id):
        raise HTTPException(status_code=404, detail="文件不存在或无权访问")
    return record


def resolve_voice_path(user: Dict, voice_id: str):
    if voice_id == CUSTOM_VOICE_ID:
        custom_voices = get_custom_voice_paths(user["id"])
        if not custom_voices:
            raise HTTPException(status_code=400, detail="请先上传“我的声音”参考音频")
        return [str(path) for path in custom_voices]

    preset = PRESET_VOICES.get(voice_id)
    if not preset:
        raise HTTPException(status_code=400, detail="无效的音色选项")

    path = REFERENCE_DIR / preset["filename"]
    if not path.exists():
        raise HTTPException(status_code=400, detail="预设音色尚未准备完成")
    return path


def ensure_output_filename(filename: str) -> Path:
    if not OUTPUT_FILENAME_RE.fullmatch(filename):
        raise HTTPException(status_code=404, detail="文件不存在")
    return OUTPUT_DIR / filename


def list_voices(user: Dict) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = [
        {
            "id": CUSTOM_VOICE_ID,
            "name": "我的声音",
            "type": "custom",
            "available": get_custom_voice_path(user["id"]) is not None,
        }
    ]
    for voice_id, preset in PRESET_VOICES.items():
        items.append(
            {
                "id": voice_id,
                "name": preset["label"],
                "type": "preset",
                "available": (REFERENCE_DIR / preset["filename"]).exists(),
            }
        )
    return items


def wav_to_mp3(wav_path: Path, mp3_path: Path) -> None:
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(wav_path),
        "-codec:a",
        "libmp3lame",
        "-qscale:a",
        "2",
        str(mp3_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        logger.warning("ffmpeg conversion failed: %s", completed.stderr)
        raise RuntimeError("MP3 转换失败")


def run_ffmpeg(command: List[str], error_message: str) -> None:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        logger.warning("%s: %s", error_message, completed.stderr)
        raise RuntimeError(error_message)


def find_best_reference_segment(wav_path: Path) -> tuple[float, float]:
    with wave.open(str(wav_path), "rb") as wav_file:
        frame_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        frame_count = wav_file.getnframes()
        duration = frame_count / frame_rate

        if duration <= REFERENCE_MAX_SECONDS:
            return 0.0, duration

        frames_per_window = max(1, int(frame_rate * REFERENCE_WINDOW_SECONDS))
        scores: List[int] = []
        while True:
            frames = wav_file.readframes(frames_per_window)
            if not frames:
                break
            scores.append(audioop.rms(frames, sample_width))

    if not scores:
        return 0.0, min(duration, REFERENCE_MAX_SECONDS)

    window_count = max(1, int(REFERENCE_MAX_SECONDS / REFERENCE_WINDOW_SECONDS))
    max_score = max(scores)
    speech_floor = max(250, int(max_score * 0.18))
    best_index = 0
    best_score = -1.0

    for index in range(0, max(1, len(scores) - window_count + 1)):
        window_scores = scores[index : index + window_count]
        active = [score for score in window_scores if score >= speech_floor]
        active_ratio = len(active) / max(1, len(window_scores))
        total_score = sum(min(score, int(max_score * 0.9)) for score in window_scores)
        weighted_score = total_score * (0.65 + active_ratio)
        if weighted_score > best_score:
            best_score = weighted_score
            best_index = index

    start = best_index * REFERENCE_WINDOW_SECONDS
    end = min(duration, start + REFERENCE_MAX_SECONDS)
    return start, end


def find_best_reference_segments(wav_path: Path) -> List[tuple[float, float]]:
    with wave.open(str(wav_path), "rb") as wav_file:
        frame_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        frame_count = wav_file.getnframes()
        duration = frame_count / frame_rate
        frames_per_window = max(1, int(frame_rate * REFERENCE_WINDOW_SECONDS))
        scores: List[int] = []
        while True:
            frames = wav_file.readframes(frames_per_window)
            if not frames:
                break
            scores.append(audioop.rms(frames, sample_width))

    if not scores:
        return [(0.0, min(duration, REFERENCE_SEGMENT_SECONDS))]

    if duration <= REFERENCE_SEGMENT_SECONDS:
        return [(0.0, duration)]

    window_count = max(1, int(REFERENCE_SEGMENT_SECONDS / REFERENCE_WINDOW_SECONDS))
    max_score = max(scores)
    speech_floor = max(250, int(max_score * 0.18))
    candidates = []

    for index in range(0, max(1, len(scores) - window_count + 1)):
        window_scores = scores[index : index + window_count]
        active = [score for score in window_scores if score >= speech_floor]
        active_ratio = len(active) / max(1, len(window_scores))
        total_score = sum(min(score, int(max_score * 0.9)) for score in window_scores)
        weighted_score = total_score * (0.65 + active_ratio)
        start = index * REFERENCE_WINDOW_SECONDS
        end = min(duration, start + REFERENCE_SEGMENT_SECONDS)
        candidates.append((weighted_score, start, end))

    selected: List[tuple[float, float]] = []
    for _, start, end in sorted(candidates, reverse=True):
        overlaps_too_much = False
        for existing_start, existing_end in selected:
            overlap = max(0.0, min(end, existing_end) - max(start, existing_start))
            if overlap > REFERENCE_SEGMENT_SECONDS * 0.75:
                overlaps_too_much = True
                break
        if overlaps_too_much:
            continue
        selected.append((start, end))
        if len(selected) >= REFERENCE_MAX_SEGMENTS:
            break

    if not selected:
        return [find_best_reference_segment(wav_path)]
    return selected


def convert_reference_to_wav(source_path: Path, wav_path: Path) -> None:
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    full_wav_path = wav_path.with_suffix(".full.wav")
    try:
        run_ffmpeg(
            [
                ffmpeg_path,
                "-y",
                "-i",
                str(source_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(REFERENCE_SAMPLE_RATE),
                "-sample_fmt",
                "s16",
                str(full_wav_path),
            ],
            "参考音频转换失败，请换一段清晰的人声音频",
        )

        segments = find_best_reference_segments(full_wav_path)
        for index, (start, end) in enumerate(segments):
            output_path = wav_path if index == 0 else wav_path.with_name(f"{wav_path.stem}_part{index + 1}.wav")
            run_ffmpeg(
                [
                    ffmpeg_path,
                    "-y",
                    "-i",
                    str(full_wav_path),
                    "-af",
                    f"atrim=start={start:.2f}:end={end:.2f},asetpts=PTS-STARTPTS,loudnorm=I=-20:LRA=7:TP=-2",
                    "-ac",
                    "1",
                    "-ar",
                    str(REFERENCE_SAMPLE_RATE),
                    "-sample_fmt",
                    "s16",
                    str(output_path),
                ],
                "参考音频清理失败，请换一段清晰的人声音频",
            )
            logger.info(
                "Prepared reference segment %s %.2fs-%.2fs from %s",
                index + 1,
                start,
                end,
                source_path,
            )
    finally:
        full_wav_path.unlink(missing_ok=True)


@app.on_event("startup")
def startup() -> None:
    ensure_directories()
    init_db()


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/app")
def app_page():
    return FileResponse(STATIC_DIR / "app.html")


@app.get("/health")
def health():
    return {
        "ok": True,
        "gpu": torch.cuda.is_available(),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
    }


@app.post("/api/register")
def register(payload: AuthRequest):
    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少 3 个字符")

    try:
        user = create_user(username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = create_access_token(user)
    return {"token": token, "user": {"id": user["id"], "username": user["username"]}}


@app.post("/api/login")
def login(payload: AuthRequest):
    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user = authenticate_user(username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user)
    return {"token": token, "user": {"id": user["id"], "username": user["username"]}}


@app.get("/api/me")
def me(user: Dict = Depends(get_current_user)):
    return {"id": user["id"], "username": user["username"]}


@app.get("/api/voices")
def voices(user: Dict = Depends(get_current_user)):
    return {"items": list_voices(user)}


@app.post("/api/upload-reference")
async def upload_reference(
    file: UploadFile = File(...),
    user: Dict = Depends(get_current_user),
):
    filename = file.filename or "my_voice.wav"
    extension = Path(filename).suffix.lower()
    if extension not in VOICE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持常见音频格式")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="音频文件不能超过 8MB")

    target_dir = get_user_voice_dir(user["id"])
    upload_id = uuid.uuid4().hex
    source = target_dir / f"upload_{upload_id}{extension}"
    converted = target_dir / f"upload_{upload_id}.converted.wav"
    original = target_dir / f"original_upload{extension}"
    target = target_dir / f"{CUSTOM_VOICE_ID}.wav"

    try:
        source.write_bytes(content)
        convert_reference_to_wav(source, converted)
        for existing in target_dir.glob("original_upload.*"):
            existing.unlink(missing_ok=True)
        for existing in target_dir.glob(f"{CUSTOM_VOICE_ID}*.wav"):
            existing.unlink(missing_ok=True)
        source.replace(original)
        for index, temp_voice in enumerate([converted, *sorted(target_dir.glob(f"{converted.stem}_part*.wav"))]):
            destination = target if index == 0 else target_dir / f"{CUSTOM_VOICE_ID}_part{index + 1}.wav"
            temp_voice.replace(destination)
    except RuntimeError as exc:
        converted.unlink(missing_ok=True)
        for temp_voice in target_dir.glob(f"{converted.stem}_part*.wav"):
            temp_voice.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        source.unlink(missing_ok=True)

    return {"message": "上传成功", "voice_id": CUSTOM_VOICE_ID}


@app.post("/api/generate")
def generate(payload: SynthesisRequest, user: Dict = Depends(get_current_user)):
    request_id = uuid.uuid4().hex
    wav_path = OUTPUT_DIR / f"{request_id}.wav"
    mp3_path = OUTPUT_DIR / f"{request_id}.mp3"
    text = prepare_spoken_text(payload.text)
    if not text:
        raise HTTPException(status_code=400, detail="请输入要生成的文案")
    style = SPEAKING_STYLES["clone"] if payload.voice_id == CUSTOM_VOICE_ID else get_speaking_style(payload.style)

    try:
        voice_path = resolve_voice_path(user, payload.voice_id)
        speaker_wav = voice_path if isinstance(voice_path, list) else str(voice_path)
        clone_options = (
            {
                "gpt_cond_len": 12,
                "gpt_cond_chunk_len": 4,
                "sound_norm_refs": True,
            }
            if payload.voice_id == CUSTOM_VOICE_ID
            else {}
        )
        tts = get_tts()
        with generation_lock:
            tts.tts_to_file(
                text=text,
                speaker_wav=speaker_wav,
                language=payload.language,
                file_path=str(wav_path),
                split_sentences=True,
                temperature=style["temperature"],
                top_p=style["top_p"],
                top_k=style["top_k"],
                repetition_penalty=style["repetition_penalty"],
                length_penalty=style["length_penalty"],
                speed=style["speed"],
                **clone_options,
            )
        wav_to_mp3(wav_path, mp3_path)
        record_generated_file(user["id"], wav_path.name)
        record_generated_file(user["id"], mp3_path.name)
    except Exception as exc:
        logger.exception("Generation failed")
        raise HTTPException(status_code=500, detail=f"生成失败：{exc}") from exc

    media_token = build_media_token(user["id"], mp3_path.name)
    wav_token = build_media_token(user["id"], wav_path.name)

    return {
        "message": "生成成功",
        "audio_url": f"/api/media/{mp3_path.name}?token={media_token}",
        "download_url": f"/api/download/{mp3_path.name}?token={media_token}",
        "wav_url": f"/api/media/{wav_path.name}?token={wav_token}",
    }


@app.api_route("/api/media/{filename}", methods=["GET", "HEAD"])
def media(filename: str, token: str):
    verify_media_token(token, filename)
    path = ensure_output_filename(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    media_type = "audio/mpeg" if path.suffix.lower() == ".mp3" else "audio/wav"
    return FileResponse(path, media_type=media_type, filename=filename)


@app.api_route("/api/download/{filename}", methods=["GET", "HEAD"])
def download(filename: str, token: str):
    verify_media_token(token, filename)
    path = ensure_output_filename(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    media_type = "audio/mpeg" if path.suffix.lower() == ".mp3" else "audio/wav"
    return FileResponse(path, media_type=media_type, filename=filename)


@app.exception_handler(HTTPException)
async def http_error_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
