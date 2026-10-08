# -*- coding: utf-8 -*-
"""dump Epic 验证码邮件的完整正文，分析验证码在 HTML 里的组织方式。"""
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
typ, data = conn.uid("SEARCH", None, "ALL")
all_uids = data[0].split()
print("全部 UID 数:", len(all_uids))

uid = None
for cand in reversed(all_uids):
    _, f = conn.uid("FETCH", cand, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
    blob = next((it[1] for it in f if isinstance(it, tuple) and len(it) > 1), b"")
    if b"epicgames" in blob.lower():
        uid = cand
        break
if uid is None:
    print("没找到 Epic 邮件")
    sys.exit(0)
print("Epic 邮件 UID:", uid)
typ, fetched = conn.uid("FETCH", uid, "(RFC822)")
raw = next(it[1] for it in fetched if isinstance(it, tuple) and len(it) > 1)
msg = email.message_from_bytes(raw)

print("=" * 70)
print("邮件结构")
print("=" * 70)
for part in msg.walk():
    print(f"  type={part.get_content_type():30} charset={part.get_content_charset()} "
          f"encoding={part.get('Content-Transfer-Encoding')}")

print()
print("=" * 70)
print("各 text 部分的原始 payload（前 3000 字符）")
print("=" * 70)
for part in msg.walk():
    if part.get_content_type() not in ("text/plain", "text/html"):
        continue
    payload = part.get_payload(decode=True)
    if not payload:
        continue
    charset = part.get_content_charset() or "utf-8"
    text = payload.decode(charset, errors="replace")
    print(f"---- {part.get_content_type()} ({len(text)} 字符) ----")
    # 找出所有数字串，帮助定位验证码样式
    nums = re.findall(r"\d[\d\s\u00a0\u200b]{4,}\d|\d{4,}", text)
    print("  含数字的片段:", nums[:20])

    # 定位验证码区域
    for kw in ("Security Code", "security code"):
        idx = text.find(kw)
        if idx >= 0:
            print(f"  ==== '{kw}' 附近原文（{idx} ~ {idx + 2200}）====")
            print(text[idx : idx + 2200])
            print("  ==== 结束 ====")
            break
    print()

print("=" * 70)
print("现有解析结果")
print("=" * 70)
plain = svc._message_text(msg)
print("纯文本长度:", len(plain))
print("纯文本前 1500 字:")
print(plain[:1500])
print()
print("_find_code 结果:", svc._find_code(plain))

conn.logout()
