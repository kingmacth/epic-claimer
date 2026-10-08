# -*- coding: utf-8 -*-
"""复现取码模块 _poll_once 的每一步，定位为什么找不到 Epic 邮件。"""
import email
import email.utils
import imaplib
import os
import re
import ssl
import sys
import time

sys.path.insert(0, "/app/app")

from services import epic_email_otp_service as svc  # noqa: E402

HOST = os.environ.get("EPIC_IMAP_HOST", "imap.163.com")
PORT = int(os.environ.get("EPIC_IMAP_PORT", "143"))
USER = os.environ.get("EPIC_IMAP_USER", "")
PASS = os.environ.get("EPIC_IMAP_PASS", "")
FOLDER = os.environ.get("EPIC_IMAP_FOLDER", "INBOX")
SENDER_HINT = os.environ.get("EPIC_OTP_SENDER_HINT", "epicgames").lower()
LOOKBACK = int(os.environ.get("EPIC_OTP_LOOKBACK_SECONDS", "600"))

print("=" * 70)
print("配置")
print("=" * 70)
print(f"HOST={HOST}  PORT={PORT}  FOLDER={FOLDER}")
print(f"USER={USER}  SENDER_HINT={SENDER_HINT}  LOOKBACK={LOOKBACK}")
print(f"容器 TZ = {time.strftime('%Z %z')}  当前本地时间 = {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"当前 UTC 时间 = {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}")

threshold = time.time() - LOOKBACK
print(f"threshold(epoch)={threshold:.0f} → 本地 {time.strftime('%H:%M:%S', time.localtime(threshold))}")

print()
print("=" * 70)
print("连接 IMAP")
print("=" * 70)
ctx = ssl.create_default_context()
if PORT == 993:
    conn = imaplib.IMAP4_SSL(HOST, PORT, ssl_context=ctx)
else:
    conn = imaplib.IMAP4(HOST, PORT)
    conn.starttls(ssl_context=ctx)
print("登录 ->", conn.login(USER, PASS))
svc._send_imap_id(conn)
print("SELECT ->", conn.select(FOLDER, readonly=True))

since = time.strftime("%d-%b-%Y", time.gmtime(threshold - 86400))
print(f"SEARCH SINCE {since}")
typ, data = conn.uid("SEARCH", None, f"(SINCE {since})")
print("SEARCH ->", typ, "数量:", len(data[0].split()) if data and data[0] else 0)

uids = data[0].split()[-30:] if data and data[0] else []
print(f"检查最近 {len(uids)} 封（从最新往回）")
print()

print("=" * 70)
print("逐封检查")
print("=" * 70)
for i, uid in enumerate(reversed(uids), 1):
    typ, fetched = conn.uid("FETCH", uid, "(RFC822)")
    if typ != "OK" or not fetched:
        print(f"[{i}] uid={uid!r} FETCH 失败")
        continue
    raw = next((it[1] for it in fetched if isinstance(it, tuple) and len(it) > 1), None)
    if not raw:
        print(f"[{i}] uid={uid!r} 无 RFC822 内容")
        continue

    msg = email.message_from_bytes(raw)
    sender_raw = msg.get("From") or ""
    sender = sender_raw.lower()
    date_raw = msg.get("Date")
    subject = svc._decode_header_value(msg.get("Subject"))

    hit_sender = SENDER_HINT in sender
    # 时间解析
    recv_err = ""
    received = time.time()
    try:
        parsed = email.utils.parsedate_to_datetime(date_raw)
        received = parsed.timestamp()
        recv_desc = f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(received))} (tz={parsed.tzinfo})"
    except Exception as e:  # noqa: BLE001
        recv_err = f"{type(e).__name__}: {e}"
        recv_desc = f"解析失败→用当前时间 {time.strftime('%H:%M:%S')}"

    passed_time = received >= threshold

    flag = "★" if hit_sender else " "
    print(f"[{i}]{flag} uid={uid!r}")
    print(f"     From    : {sender_raw}")
    print(f"     Subject : {subject[:70]}")
    print(f"     Date原始 : {date_raw}")
    print(f"     Date解析 : {recv_desc} {('  ERR: ' + recv_err) if recv_err else ''}")
    print(f"     判定     : 发件人匹配={hit_sender}  时间通过={passed_time} (received={received:.0f} vs threshold={threshold:.0f}, 差={received - threshold:+.0f}s)")

    if hit_sender:
        text = svc._message_text(msg)
        code = svc._find_code(text)
        print(f"     正文长度 : {len(text)}")
        print(f"     抽码结果 : {code if code else '** 未抽到 **'}")
        if not code:
            print("     ---- 正文前 800 字 ----")
            print(text[:800])
            print("     ---- 正文结束 ----")

    if hit_sender and passed_time:
        print("     >>> 该邮件应被采用 <<<")
    print()

conn.logout()
print("完成")
