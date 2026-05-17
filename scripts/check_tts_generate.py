from pathlib import Path

import torch
from TTS.api import TTS


BASE_DIR = Path(__file__).resolve().parents[1]
voice_path = BASE_DIR / "reference_voices" / "dashu.wav"
output_path = BASE_DIR / "output" / "diag-test.wav"

print("cuda_available", torch.cuda.is_available(), flush=True)
print("device_name", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu", flush=True)
print("loading_model", flush=True)
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda" if torch.cuda.is_available() else "cpu")
print("model_loaded", flush=True)
tts.tts_to_file(
    text="你好，这是一次诊断生成测试。",
    speaker_wav=str(voice_path),
    language="zh-cn",
    file_path=str(output_path),
)
print("generated", output_path, flush=True)
