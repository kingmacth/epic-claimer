# -*- coding: utf-8 -*-
"""分析 Epic 邮件纯文本里所有数字序列及其上下文。"""
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

_, fetched = conn.uid("FETCH", uid, "(RFC822)")
raw = next(it[1] for it in fetched if isinstance(it, tuple) and len(it) > 1)
msg = email.message_from_bytes(raw)

# 原始 HTML
html = None
for part in msg.walk():
    if part.get_content_type() == "text/html":
        html = part.get_payload(decode=True).decode("utf-8", errors="replace")

print("=" * 70)
print("原始 HTML 中所有数字序列（长度 1-8）及上下文")
print("=" * 70)
for m in re.finditer(r"\d{1,8}", html):
    s, e = m.start(), m.end()
    ctx_before = html[max(s - 45, 0) : s].replace("\n", "\\n")
    ctx_after = html[e : e + 25].replace("\n", "\\n")
    print(f"  [{m.group()}] ...{ctx_before[-45:]} <<HERE>> {ctx_after}...")

print()
print("=" * 70)
print("纯文本中所有数字序列及上下文")
print("=" * 70)
plain = svc._message_text(msg)
for m in re.finditer(r"\d+", plain):
    s, e = m.start(), m.end()
    before = plain[max(s - 40, 0) : s].replace("\n", "\\n")
    after = plain[e : e + 20].replace("\n", "\\n")
    print(f"  [{m.group()}] ...{before} <<HERE>> {after}...")

conn.logout()
