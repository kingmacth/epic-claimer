# -*- coding: utf-8 -*-
"""用桩函数直接驱动真实代码，验证 _verify_weekly_claims 的控制流。"""
import asyncio
import sys
import types

sys.path.insert(0, "/app/app")
from services.epic_games_service import EpicAgent  # noqa: E402


class FakePage:
    async def wait_for_timeout(self, ms):
        return None


def P(title, ns):
    return types.SimpleNamespace(title=title, url="https://x/" + title, namespace=ns)


def build(library, *, retry_converges):
    agent = EpicAgent(FakePage())
    calls = []

    async def refresh():
        return set(library)

    async def collect(promos):
        calls.append([p.title for p in promos])
        if retry_converges:
            library.update(p.namespace for p in promos)

    agent.refresh_order_namespaces = refresh
    agent.epic_games.collect_weekly_games = collect
    return agent, calls


async def main():
    a, b = P("Out of Sight", "a" * 32), P("TerraScape", "b" * 32)
    ok = True

    # 1) 两款都已在库：不补领
    agent, calls = build({a.namespace, b.namespace}, retry_converges=True)
    await agent._verify_weekly_claims([a, b])
    print(f"[1] 全部入库 -> calls={calls}")
    ok &= calls == []

    # 2) 缺一款：自动补领后收敛
    agent, calls = build({a.namespace}, retry_converges=True)
    await agent._verify_weekly_claims([a, b], max_attempts=3)
    print(f"[2] 缺 TerraScape -> 补领 calls={calls}")
    ok &= calls == [["TerraScape"]]

    # 3) 始终缺一款：应抛错且错误信息列出缺项
    agent, calls = build({a.namespace}, retry_converges=False)
    try:
        await agent._verify_weekly_claims([a, b], max_attempts=2)
        print("[3] FAIL: 未抛错")
        ok = False
    except RuntimeError as err:
        msg = str(err)
        print(f"[3] 始终缺项 -> 抛错: {msg[:70]}")
        ok &= "TerraScape" in msg

    # 4) 空清单：直接返回，不查订单历史
    agent, calls = build(set(), retry_converges=True)
    await agent._verify_weekly_claims([])
    print(f"[4] 空清单 -> calls={calls}")
    ok &= calls == []

    print("RESULT:", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
