#!/usr/bin/env bash
# 首次使用：拉取上游源码 + 应用本地补丁 + 生成 .env
# 用法：./setup.sh        （需要已安装 git）
set -euo pipefail
cd "$(dirname "$0")"

UPSTREAM="${UPSTREAM:-https://github.com/Ronchy2000/epic-freebies-helper.git}"
# 补丁适配的上游提交。换上游版本时改这里，并重新校验 patches/ 是否仍能应用。
BASE_COMMIT="${BASE_COMMIT:-d90190bf3f9f87e9da71c50c81f155c4586bdb33}"

echo "==> 上游仓库：$UPSTREAM"
echo "==> 基准提交：${BASE_COMMIT:0:7}"

# 判定 repo/ 是否真的就绪：光有 .git 不算（下载失败会留下空壳仓库）
if [ -d repo/.git ] && [ -n "$(git -C repo ls-files 2>/dev/null | head -1)" ]; then
  echo "==> repo/ 已存在，跳过下载（需要干净重建请先删除 repo/ 再运行）"
else
  rm -rf repo
  mkdir -p repo
  git -C repo init -q
  git -C repo remote add origin "$UPSTREAM"
  echo "==> 下载上游源码（只取单个提交）"
  ok=0
  for i in 1 2 3; do
    if git -C repo -c core.autocrlf=false fetch -q --depth 1 origin "$BASE_COMMIT" 2>/dev/null; then
      ok=1
      break
    fi
    echo "    第 $i 次下载失败，5 秒后重试..."
    sleep 5
  done
  if [ "$ok" != 1 ]; then
    rm -rf repo
    echo
    echo "[错误] 下载上游源码失败（已重试 3 次）。"
    echo "  若本机访问 GitHub 不稳定，先给 git 配个代理再重试："
    echo "      git config --global http.proxy http://127.0.0.1:7890   # 端口换成你自己的"
    echo "  用完可以取消："
    echo "      git config --global --unset http.proxy"
    exit 1
  fi
  # 强制 LF，保证补丁在任何平台都能一致应用
  git -C repo -c core.autocrlf=false checkout -q FETCH_HEAD
fi

echo "==> 应用本地补丁"
shopt -s nullglob
found=0
for p in patches/*.patch; do
  found=1
  printf '    - %-32s ' "$(basename "$p")"
  # 在 repo/ 内执行、用相对路径回指补丁：
  # 既避开 git -C 切换工作目录的陷阱，也避开 MSYS 与 Windows 路径格式的差异
  if out=$(cd repo && git apply --3way "../$p" 2>&1); then
    echo "OK"
  else
    echo "失败"
    [ -n "$out" ] && printf '%s\n' "$out" | sed 's/^/      /'
    echo
    echo "[错误] 补丁应用失败：$p"
    echo "常见原因：上游代码已更新，补丁上下文不再匹配。"
    echo "处理办法：改 BASE_COMMIT 为新的提交，或手动检查该补丁。"
    exit 1
  fi
done
[ "$found" = 1 ] || echo "    （patches/ 下没有补丁文件）"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> 已生成 .env（请填写账号与密钥）"
else
  echo "==> .env 已存在，保持不动"
fi

cat <<'EOF'

完成。下一步：
  1. 编辑 .env，至少填好 EPIC_EMAIL、EPIC_PASSWORD、GLM_API_KEY
  2. 运行 docker compose up -d --build
EOF
