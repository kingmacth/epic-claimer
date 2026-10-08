# -*- coding: utf-8 -*-
"""用真实的 Epic 验证码邮件回归测试修复后的抽码逻辑。"""
import email
import imaplib
import os
import re
import ssl
import sys

sys.path.insert(0, "/app/app")
from services import epic_email_otp_service as svc  # noqa: E402

HOST = os.environ.get("EPIC_IMAP_HOST", "imap.163.com")
PORT = int(os.environ.get("EPIC_IMAP_PORT", "143"))
USER = os.environ.get("EPIC_IMAP_USER", "")
PASS = os.environ.get("EPIC_IMAP_PASS", "")

ctx = ssl.create_default_context()
conn = imaplib.IMAP4(HOST, PORT)
conn.starttls(ssl_context=ctx)
conn.login(USER, PASS)
svc._send_imap_id(conn)
conn.select("INBOX", readonly=True)

_, data = conn.uid("SEARCH", None, "ALL")
uid = None
for cand in reversed(data[0].split()):
    _, f = conn.uid("FETCH", cand, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
    blob = next((it[1] for it in f if isinstance(it, tuple) and len(it) > 1), b"")
    if b"epicgames" in blob.lower():
        uid = cand
        break

if uid is None:
    print("没找到 Epic 邮件，无法回归测试")
    sys.exit(1)

_, fetched = conn.uid("FETCH", uid, "(RFC822)")
raw = next(it[1] for it in fetched if isinstance(it, tuple) and len(it) > 1)
msg = email.message_from_bytes(raw)

plain = svc._message_text(msg)
print("=" * 70)
print(f"清洗后纯文本长度: {len(plain)}  (清洗前约 20083)")
print("=" * 70)

print()
print("---- 清洗后纯文本里的所有 6 位数字 ----")
all6 = [m.group(1) for m in svc._CODE_RE.finditer(plain)]
print(f"候选: {sorted(set(all6))}  (共 {len(all6)} 处)")
print(f"→ {'唯一，可直接兜底命中' if len(set(all6)) == 1 else '不唯一'}")

print()
print("---- 独立成行的 6 位数字 ----")
standalone = {m.group(1) for m in re.finditer(r"(?m)^[ \t\u00a0]*(\d{6})[ \t\u00a0]*$", plain)}
print(f"候选: {sorted(standalone)}")

print()
print("=" * 70)
print("抽码逻辑最终结果")
print("=" * 70)
code = svc._find_code(plain)
if code:
    print(f"✅ 抽到验证码: {code[0]}{'*' * (len(code) - 1)}   (长度 {len(code)})")
else:
    print("❌ 仍未抽到")

print()
print("---- 验证码附近的纯文本上下文 ----")
for m in svc._CODE_RE.finditer(plain):
    s = m.start()
    ctx_txt = plain[max(s - 120, 0) : s + 120].replace("\n", "\\n")
    print(f"  ...{ctx_txt}...")
    break

print()
print("---- 'code' 相关提示词在纯文本中的位置 ----")
for m in svc._HINT_RE.finditer(plain):
    print(f"  [{m.group()}] @ {m.start()}: ...{plain[m.start():m.start()+70].replace(chr(10), ' ')}...")
    if m.start() > 2000:
        break

conn.logout()
