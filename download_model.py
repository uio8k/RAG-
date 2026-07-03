"""通过 requests 手动下载模型文件到 HuggingFace 缓存目录"""
import requests
import os
import json
from pathlib import Path

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MIRROR = "https://hf-mirror.com"

# 模型文件列表
FILES = [
    "config.json",
    "tokenizer_config.json",
    "vocab.txt",
    "modules.json",
    "sentence_bert_config.json",
    "tokenizer.json",
    "special_tokens_map.json",
    "1_Pooling/config.json",
    "0_Transformer/config.json",
    "0_Transformer/model.safetensors",
]


def download_model():
    # 1. 获取最新的 commit hash
    print("[1/3] 获取最新版本信息...")
    r = requests.get(f"{MIRROR}/{MODEL_ID}/resolve/main/config.json", timeout=30)
    r.raise_for_status()
    print("  ✓ 镜像连通正常")

    # 通过 API 获取 refs
    r2 = requests.get(f"{MIRROR}/api/models/{MODEL_ID}", timeout=30)
    if r2.status_code == 200:
        sha = r2.json().get("sha", "main")
    else:
        sha = "main"
    print(f"  commit: {sha[:12]}...")

    # 2. 确定缓存路径
    safe_name = f"models--{MODEL_ID.replace('/', '--')}"
    cache_base = Path.home() / ".cache" / "huggingface" / "hub" / safe_name
    snapshots_dir = cache_base / "snapshots" / sha
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    # 创建 refs 文件
    refs_dir = cache_base / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (refs_dir / "main").write_text(sha)

    print(f"\n[2/3] 下载 {len(FILES)} 个文件到:\n  {snapshots_dir}")

    # 3. 下载所有文件
    for fname in FILES:
        url = f"{MIRROR}/{MODEL_ID}/resolve/main/{fname}"
        dest = snapshots_dir / fname
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            dest.write_bytes(r.content)
            size_kb = len(r.content) / 1024
            print(f"  ✓ {fname} ({size_kb:.0f} KB)")
        except Exception as e:
            print(f"  ✗ {fname}: {e}")

    # 4. 验证
    print(f"\n[3/3] 验证下载...")
    model_file = snapshots_dir / "0_Transformer" / "model.safetensors"
    if model_file.exists():
        size_mb = model_file.stat().st_size / (1024 * 1024)
        print(f"  ✓ model.safetensors: {size_mb:.1f} MB")
        print(f"\n✅ 模型下载完成！重启项目即可使用。")
    else:
        print("  ✗ model.safetensors 未找到，请检查网络")
        return False

    return True


if __name__ == "__main__":
    download_model()
