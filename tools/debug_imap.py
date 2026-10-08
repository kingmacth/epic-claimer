# -*- coding: utf-8 -*-
"""验证修复方案：把 ID 注册进 imaplib 命令表后再发送，看能否解除 163 的 Unsafe Login。"""
import imaplib
import os
import ssl

HOST = os.getenv("EPIC_IMAP_HOST", "imap.163.com")
PORT = int(os.getenv("EPIC_IMAP_PORT", "143"))
USER = os.getenv("EPIC_IMAP_USER", "")
PWD = os.getenv("EPIC_IMAP_PASS", "")

# ★ 关键：imaplib 的命令表里没有 ID，不注册就会 KeyError。
imaplib.Commands["ID"] = ("NONAUTH", "AUTH", "SELECTED")

ID_ARGS = (
    '("name" "epic-claimer" "version" "1.0" "vendor" "workbuddy" '
    '"support-email" "noreply@localhost")'
)


def connect() -> imaplib.IMAP4:
    conn = imaplib.IMAP4(HOST, PORT)
    conn.starttls(ssl_context=ssl.create_default_context())
    conn.login(USER, PWD)
    return conn


print("=== 方案 A：登录后先发 ID，再 SELECT ===")
conn = connect()
try:
    typ, dat = conn._simple_command("ID", ID_ARGS)
    print("ID ->", typ, dat)
    print("untagged keys:", list(conn.untagged_responses.keys()))
except Exception as err:
    print("ID 异常:", type(err).__name__, err)

typ, dat = conn.select("INBOX", readonly=True)
print("SELECT ->", typ, dat)
if typ == "OK":
    typ, dat = conn.uid("SEARCH", None, "(SINCE 01-Sep-2026)")
    print("SEARCH ->", typ, "命中", len(dat[0].split()) if dat and dat[0] else 0, "封")
    typ, dat = conn.list()
    print("LIST ->", typ)
    for item in (dat or [])[:12]:
        print("   ", item)

    # 试一次真实取信
    typ, data = conn.uid("SEARCH", None, "(SINCE 01-Sep-2026)")
    uids = data[0].split() if (typ == "OK" and data and data[0]) else []
    if uids:
        uid = uids[-1]
        typ, fetched = conn.uid("FETCH", uid, "(RFC822.SIZE BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        print(f"FETCH 最新一封 -> {typ}")
        raw = next((i[1] for i in fetched if isinstance(i, tuple) and len(i) > 1), b"")
        print(raw.decode("utf-8", "replace")[:400])

print("\n=== 方案 B：用 xatom('ID') ===")
conn2 = connect()
try:
    typ, dat = conn2.xatom("ID", ID_ARGS)
    print("xatom ->", typ, dat)
except Exception as err:
    print("xatom 异常:", type(err).__name__, err)
typ, dat = conn2.select("INBOX", readonly=True)
print("SELECT ->", typ, dat)
