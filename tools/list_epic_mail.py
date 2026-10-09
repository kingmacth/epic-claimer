# -*- coding: utf-8 -*-
"""列出 Epic 邮箱最近的邮件（日期/发件人/标题），用于核对「领取确认邮件」有几封。

自包含：直接读同目录上级的 .env，不依赖容器内代码。只打印标题，不打印口令。
"""
import email
import imaplib
import re
import ssl
import sys
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / ".env"
IMAP_SEND_ID = '("name" "epic-claimer" "version" "1.0" "vendor" "workbuddy")'


def load_env() -> dict:
    out = {}
    if not ENV.is_file():
        return out
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def dec(v) -> str:
    if not v:
        return ""
    try:
        return str(make_header(decode_header(v)))
    except Exception:
        return str(v)


def send_id(conn) -> None:
    if not hasattr(imaplib, "Commands"):
        imaplib.Commands = {}
    if "ID" not in imaplib.Commands:
        imaplib.Commands["ID"] = ("AUTH", "SELECTED")
    try:
        typ, dat = conn._simple_command("ID", IMAP_SEND_ID)
        conn._untagged_response(typ, dat, "ID")
    except Exception as err:
        print(f"[warn] ID 命令失败（可忽略）: {err!r}")


def main() -> int:
    env = load_env()
    host = env.get("EPIC_IMAP_HOST") or "imap.163.com"
    port = int(env.get("EPIC_IMAP_PORT") or 143)
    user = env.get("EPIC_IMAP_USER") or ""
    pwd = env.get("EPIC_IMAP_PASS") or ""
    folder = env.get("EPIC_IMAP_FOLDER") or "INBOX"
    print(f"host={host} port={port} folder={folder} user_set={bool(user)} pass_set={bool(pwd)}")
    if not user or not pwd:
        print("[error] .env 里没有 EPIC_IMAP_USER / EPIC_IMAP_PASS")
        return 1

    if port == 993:
        conn = imaplib.IMAP4_SSL(host, port, timeout=40)
    else:
        conn = imaplib.IMAP4(host, port, timeout=40)
        conn.starttls(ssl_context=ssl.create_default_context())
    conn.login(user, pwd)
    # 163 要求登录后立刻发 ID，否则 SELECT 会返回 "EXAMINE Unsafe Login"
    send_id(conn)
    typ, data = conn.select(folder, readonly=True)
    print(f"SELECT -> {typ} {data}")

    typ, data = conn.uid("SEARCH", None, "SINCE", "06-Oct-2026")
    uids = data[0].split() if typ == "OK" and data and data[0] else []
    print(f"命中 {len(uids)} 封（2026-10-06 起），展示最近 40 封：\n")
    print(f"{'时间':16} | {'发件人':34} | 标题")
    print("-" * 118)

    for u in uids[-40:]:
        typ, fetched = conn.uid("FETCH", u, "(BODY.PEEK[HEADER.FIELDS (DATE FROM SUBJECT)])")
        blob = next((it[1] for it in fetched if isinstance(it, tuple) and len(it) > 1), b"")
        if not blob:
            continue
        msg = email.message_from_bytes(blob)
        subj = dec(msg.get("Subject"))
        frm = dec(parseaddr(msg.get("From"))[1] or msg.get("From"))
        try:
            dt = parsedate_to_datetime(msg.get("Date")).strftime("%m-%d %H:%M")
        except Exception:
            dt = dec(msg.get("Date"))[:16]
        print(f"{dt:16} | {frm[:34]:34} | {subj[:76]}")

    conn.logout()
    return 0


def dump_receipts() -> int:
    """打印所有「回执/订单」类邮件的纯文本正文，用于确认实际入库的游戏。"""
    env = load_env()
    host = env.get("EPIC_IMAP_HOST") or "imap.163.com"
    port = int(env.get("EPIC_IMAP_PORT") or 143)
    user = env.get("EPIC_IMAP_USER") or ""
    pwd = env.get("EPIC_IMAP_PASS") or ""
    folder = env.get("EPIC_IMAP_FOLDER") or "INBOX"
    keywords = ("receipt", "order", "purchase", "confirmed")

    conn = imaplib.IMAP4(host, port, timeout=40)
    conn.starttls(ssl_context=ssl.create_default_context())
    conn.login(user, pwd)
    send_id(conn)
    conn.select(folder, readonly=True)
    typ, data = conn.uid("SEARCH", None, "SINCE", "01-Oct-2026")
    uids = data[0].split() if typ == "OK" and data and data[0] else []

    for u in uids:
        typ, fetched = conn.uid("FETCH", u, "(RFC822)")
        raw = next((it[1] for it in fetched if isinstance(it, tuple) and len(it) > 1), b"")
        if not raw:
            continue
        msg = email.message_from_bytes(raw)
        subj = dec(msg.get("Subject"))
        if not any(k in subj.lower() for k in keywords):
            continue
        try:
            dt = parsedate_to_datetime(msg.get("Date")).strftime("%Y-%m-%d %H:%M %z")
        except Exception:
            dt = dec(msg.get("Date"))
        print("=" * 100)
        print(f"[{dt}] {subj}")
        print("=" * 100)
        picked = ""
        for part in msg.walk():
            if part.get_content_type() not in ("text/html", "text/plain"):
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            if part.get_content_type() == "text/html":
                text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
                text = re.sub(r"<br\s*/?>|</(p|div|tr|td|h\d)>", "\n", text, flags=re.I)
                text = re.sub(r"<[^>]+>", " ", text)
                text = (
                    text.replace("&nbsp;", " ")
                    .replace("&amp;", "&")
                    .replace("&#39;", "'")
                    .replace("&quot;", '"')
                )
            lines = [ln.strip() for ln in text.splitlines()]
            lines = [ln for ln in lines if ln]
            body = "\n".join(lines)
            if len(body) > len(picked):
                picked = body
        print(picked[:2500])
        print()

    conn.logout()
    return 0


if __name__ == "__main__":
    if "--body" in sys.argv:
        sys.exit(dump_receipts())
    sys.exit(main())
