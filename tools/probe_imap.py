# -*- coding: utf-8 -*-
"""探针：验证 163 IMAP（143 + STARTTLS）在「发/不发 ID 命令」两种情况下的登录响应。

用假账号即可：重点看服务端返回的是 "Unsafe Login"（说明必须发 ID）
还是 "authentication failed / 用户名或密码错误"（说明 ID 已被接受，协议链路 OK）。
不涉及任何真实凭据。
"""
import imaplib
import ssl
import sys

HOST = "imap.163.com"
PORT = 143

ID_ARGS = '("name" "epic-claimer" "version" "1.0" "vendor" "workbuddy")'


def probe(send_id: bool) -> None:
    label = "先发 ID 再登录" if send_id else "不发 ID 直接登录"
    print(f"== {label} ==")
    try:
        conn = imaplib.IMAP4(HOST, PORT)
        conn.starttls(ssl_context=ssl.create_default_context())
        print("   STARTTLS  OK")
    except Exception as err:
        print(f"   连接/STARTTLS 失败: {type(err).__name__}: {err}")
        return

    if send_id:
        try:
            typ, dat = conn._simple_command("ID", ID_ARGS)
            print(f"   ID 命令: {typ} {dat}")
            conn._untagged_response(typ, dat, "ID")
        except Exception as err:
            print(f"   ID 命令异常: {type(err).__name__}: {err}")

    try:
        conn.login("probe_probe_probe@163.com", "wrong-password-probe")
        print("   login 意外成功（不应发生）")
    except Exception as err:
        print(f"   login 结果: {type(err).__name__}: {err}")

    with_quiet(conn.logout)


def with_quiet(fn) -> None:
    try:
        fn()
    except Exception:
        pass


if __name__ == "__main__":
    probe(False)
    print()
    probe(True)
    sys.exit(0)
