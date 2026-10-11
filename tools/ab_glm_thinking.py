# -*- coding: utf-8 -*-
"""离线 A/B：glm-4.6v 在同一道已保存的点选题上，思考开 vs 关的精度与耗时。

只用已保存的截图，不触碰 Epic。密钥从环境变量读取，不打印。
"""
import base64
import json
import os
import time

import httpx

BASE = os.environ.get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
KEY = os.environ["GLM_API_KEY"]
MODEL = os.environ.get("GLM_MODEL", "glm-4.6v")

CH_DIR = (
    "/app/app/volumes/hcaptcha/.challenge/image_label_area_select/"
    "Please click on the elements that are identical/20261011/20261011100350548087"
)
CHALLENGE = f"{CH_DIR}/20261011100350548087_0_challenge_view.png"
HELPER = f"{CH_DIR}/20261011100350548087_0_spatial_helper.png"

SYSTEM_PROMPT = """**Rule for 'Find the Different Object' Tasks:**

*   **Constraint:** Do **NOT** consider size differences caused by perspective (near/far).
*   **Focus:** Identify difference based **only** on object outline, shape, and core structural features.

**Core Principles for Visual Analysis:**

*   **Processing Order:** Always analyze **Global Context** before **Local Details**.
*   **Perspective:** Maintain awareness of the overall scene ("look outside the immediate focus") when interpreting specific elements.
*   **Validation:** Ensure local interpretations are consistent with the global context to avoid settling for potentially incorrect "local optima".
*   **Method:** Employ a calm, systematic, top-down (Global-to-Local) analysis workflow.

**Workflow:**
1. Identify challenge prompt about the Challenge Image
2. Think about what the challenge requires identification goals, and where are they in the picture
3. Based on the plane rectangular coordinate system, reasoning about the absolute position of the "answer object" in the coordinate system

Finally, solve the challenge, locate the object, output the coordinates of the correct answer as json."""

AUX = (
    "Please click on the elements that are identical\n\n"
    "Every returned point must be inside the visible challenge bounds "
    "x=390..890, y=99..569."
)

BOUNDS = (390.0, 99.0, 890.0, 569.0)


def b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def call(image_b64s: list[str], thinking: str | None) -> tuple[float, str]:
    content = [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b}"}}
        for b in image_b64s
    ]
    content.append({"type": "text", "text": AUX})
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "response_format": {"type": "json_object"},
    }
    if thinking is not None:
        payload["thinking"] = {"type": thinking}
    headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    t0 = time.monotonic()
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=20.0)) as c:
        r = c.post(f"{BASE}/chat/completions", headers=headers, json=payload)
    dt = time.monotonic() - t0
    if r.is_error:
        return dt, f"HTTP {r.status_code}: {r.text[:150]}"
    data = r.json()
    msg = (data.get("choices") or [{}])[0].get("message", {})
    txt = msg.get("content") or ""
    if isinstance(txt, list):
        txt = " ".join(p.get("text", "") for p in txt if isinstance(p, dict))
    return dt, txt.strip()


def parse_points(txt: str) -> list[tuple[float, float]]:
    try:
        data = json.loads(txt)
    except Exception:
        return []
    ans = data.get("answer") if isinstance(data, dict) else None
    if ans is None:
        ans = data.get("points") if isinstance(data, dict) else None
    pts = []
    for item in ans or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            pts.append((float(item[0]), float(item[1])))
        elif isinstance(item, dict):
            try:
                pts.append((float(item["x"]), float(item["y"])))
            except Exception:
                pass
    return pts


def judge(pts: list[tuple[float, float]]) -> str:
    if not pts:
        return "NO_POINTS"
    inside = [p for p in pts if BOUNDS[0] <= p[0] <= BOUNDS[2] and BOUNDS[1] <= p[1] <= BOUNDS[3]]
    return f"{len(inside)}/{len(pts)} in-bounds"


def main() -> int:
    imgs = [b64(CHALLENGE), b64(HELPER)]
    for thinking in ("disabled", "enabled"):
        for i in range(3):
            try:
                dt, txt = call(imgs, thinking)
                pts = parse_points(txt)
                print(f"[{thinking:8} #{i+1}] {dt:6.2f}s | {judge(pts)} | {pts}")
            except Exception as e:
                print(f"[{thinking:8} #{i+1}] ERROR {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
