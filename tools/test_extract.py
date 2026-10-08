# -*- coding: utf-8 -*-
"""校验验证码抽取逻辑：用几种典型邮件正文格式跑一遍，确认能取对。"""
import sys

sys.path.insert(0, "/app/app")

from services.epic_email_otp_service import _find_code  # noqa: E402

CASES = [
    (
        "英文标准句式",
        "Your Epic Games verification code is 123456. This code expires in 10 minutes.",
        "123456",
    ),
    (
        "中文句式",
        "您的 Epic Games 验证码是 654321，10 分钟内有效。",
        "654321",
    ),
    (
        "HTML 标签拆开数字（标签已被去掉，只剩空格）",
        "你的登录验证码\n4 2 3 1 5 6\n请勿泄露",
        "423156",
    ),
    (
        "正文里另有版权年份等干扰数字",
        "Your security code is 987654\n© 2026 Epic Games, Inc. All rights reserved.",
        "987654",
    ),
    (
        "提示词在前、数字在后",
        "登录代码（Login code）：112233",
        "112233",
    ),
    (
        "全文只有一个 6 位数字（无提示词）",
        "Epic Games\n2024\nHello player, here is your number: 445566",
        "445566",
    ),
    (
        "真实订单号噪声（多个 6 位数字，取提示词附近）",
        "Order 300123 delivered. Your verification code is 778899. Ref 400111.",
        "778899",
    ),
]

failed = 0
for label, text, expected in CASES:
    got = _find_code(text)
    ok = got == expected
    if not ok:
        failed += 1
    print(f"[{'通过' if ok else '失败'}] {label}: 期望 {expected} / 实际 {got}")

print()
print(f"结果：{len(CASES) - failed}/{len(CASES)} 通过")
sys.exit(0 if failed == 0 else 1)
