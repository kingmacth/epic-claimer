# -*- coding: utf-8 -*-
"""打印指定发件人的邮件正文与其中的链接，用于排查「转发确认」这类需要点链接的邮件。

用法：
    --from forwarding-noreply      按发件人子串过滤（默认取最新一封）
    --limit 3                      最多打印几封
"""
from __future__ import annotations

import argparse
import email
import email.utils
import imaplib
import os
import re
import ssl
import sys
import time
from contextlib import suppress

HOST = os.getenv("EPIC_IMAP_HOST", "imap.163.com")
PORT = int(os.getenv("EPIC_IMAP_PORT", "143"))
USER = os.getenv("EPIC_IMAP_USER", "")
PWD = os.getenv("EPIC_IMAP_PASS", "")
FOLDER = os.getenv("EPIC_IMAP_FOLDER", "INBOX")

imaplib.Commands["ID"] = ("NONAUTH", "AUTH", "SELECTED")
ID_ARGS = (
    '("name" "epic-claimer" "version" "1.0" "vendor" "workbuddy" '
    '"support-email" "noreply@localhost")'
)

URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+")
HTML_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")


def decode(value: str | None) -> str:
    if not value:
        return ""
    with suppress(Exception):
        from email.header import make_header, decode_header

        return str(make_header(decode_header(value)))
    return value


def bodies(message: email.message.Message) -> tuple[str, str]:
    plain: list[str] = []
    html_parts: list[str] = []

    for part in message.walk() if message.is_multipart() else [message]:
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        with suppress(Exception):
            text = payload.decode(charset, errors="replace")
            (plain if ctype == "text/plain" else html_parts).append(text)

    return "\n".join(plain), "\n".join(html_parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="sender", default="", help="发件人子串过滤")
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()

    conn = imaplib.IMAP4(HOST, PORT)
    conn.starttls(ssl_context=ssl.create_default_context())
    conn.login(USER, PWD)
    typ, _ = conn._simple_command("ID", ID_ARGS)
    with suppress(Exception):
        conn._untagged_response(typ, None, "ID")
    conn.select(FOLDER, readonly=True)

    since = time.strftime("%d-%b-%Y", time.gmtime(time.time() - 30 * 86400))
    typ, data = conn.uid("SEARCH", None, f"(SINCE {since})")
    uids = data[0].split() if (typ == "OK" and data and data[0]) else []

    printed = 0
    for uid in reversed(uids):
        typ, fetched = conn.uid("FETCH", uid, "(RFC822)")
        if typ != "OK" or not fetched:
            continue
        raw = next((i[1] for i in fetched if isinstance(i, tuple) and len(i) > 1), None)
        if not raw:
            continue
        message = email.message_from_bytes(raw)
        sender = decode(message.get("From"))
        if args.sender and args.sender.lower() not in sender.lower():
            continue

        received = time.time()
        with suppress(Exception):
            received = email.utils.parsedate_to_datetime(message.get("Date")).timestamp()

        print("=" * 74)
        print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(received))}")
        print(f"发件人: {sender}")
        print(f"标题: {decode(message.get('Subject'))}")
        print("=" * 74)

        plain, html = bodies(message)
        if plain.strip():
            print("--- 纯文本正文 ---")
            print(plain.strip()[:3000])
        if html.strip():
            text = HTML_TAG_RE.sub(" ", html)
            text = re.sub(r"\s{2,}", " ", text)
            print("--- HTML 转文本 ---")
            print(text.strip()[:3000])

        links: list[str] = []
        for url in URL_RE.findall(html) + URL_RE.findall(plain):
            if url not in links:
                links.append(url)
        for url in HTML_HREF_RE.findall(html):
            if url not in links:
                links.append(url)
        if links:
            print("--- 邮件中的链接 ---")
            for url in links[:25]:
                print("  " + url)

        printed += 1
        if printed >= args.limit:
            break

    with suppress(Exception):
        conn.logout()

    if not printed:
        print("没有匹配的邮件。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
