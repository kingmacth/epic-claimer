# -*- coding: utf-8 -*-
"""测量 GLM-4.6V 在「默认」与「thinking=disabled」下的单次请求耗时。

只读取环境变量中的 GLM_API_KEY，不打印密钥。
"""
import base64
import io
import os
import time

import httpx

BASE = os.environ.get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
KEY = os.environ["GLM_API_KEY"]
MODEL = os.environ.get("GLM_MODEL", "glm-4.6v")

# 构造一张 500x400 的测试图（纯色，避免外部依赖）
def make_image_b64() -> str:
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (500, 400), (240, 240, 240))
        d = ImageDraw.Draw(img)
        d.rectangle([50, 50, 200, 200], fill=(200, 60, 60))
        d.ellipse([250, 120, 400, 270], fill=(60, 120, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        # 1x1 png 兜底
        return (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
            "IQAAAABJRU5ErkJggg=="
        )


def call(image_b64: str, thinking: str | None) -> tuple[float, str]:
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                    {"type": "text", "text": "Describe the shapes and their approximate pixel coordinates as JSON."},
                ],
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }
    if thinking is not None:
        payload["thinking"] = {"type": thinking}
    headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    t0 = time.monotonic()
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=20.0)) as c:
        r = c.post(f"{BASE}/chat/completions", headers=headers, json=payload)
    dt = time.monotonic() - t0
    if r.is_error:
        return dt, f"HTTP {r.status_code}: {r.text[:200]}"
    data = r.json()
    txt = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    if isinstance(txt, list):
        txt = " ".join(p.get("text", "") for p in txt if isinstance(p, dict))
    return dt, (txt or "")[:160].replace("\n", " ")


def main() -> int:
    img = make_image_b64()
    for label, thinking in (("default", None), ("disabled", "disabled")):
        try:
            dt, txt = call(img, thinking)
            print(f"[{label:8}] {dt:6.2f}s | {txt}")
        except Exception as e:
            print(f"[{label:8}] ERROR: {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
