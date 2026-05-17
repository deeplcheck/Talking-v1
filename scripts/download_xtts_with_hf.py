import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download


TARGET = Path.home() / "AppData" / "Local" / "tts" / "tts_models--multilingual--multi-dataset--xtts_v2"
TARGET.mkdir(parents=True, exist_ok=True)

files = [
    "config.json",
    "vocab.json",
    "hash.md5",
    "speakers_xtts.pth",
    "model.pth",
]

tos = TARGET / "tos_agreed.txt"
if not tos.exists():
    tos.write_text("I have read, understood and agreed to the Terms and Conditions.", encoding="utf-8")

for name in files:
    print(f"downloading {name}", flush=True)
    local_path = hf_hub_download(
        repo_id="coqui/XTTS-v2",
        filename=name,
        repo_type="model",
    )
    src = Path(local_path)
    dst = TARGET / name
    if src != dst:
        shutil.copy2(src, dst)
    print(f"ready {name} -> {dst}", flush=True)

print("all files ready", flush=True)
