# 注意：基础镜像版本必须与 repo/uv.lock 里锁定的 playwright 版本一致。
# 上游 Dockerfile 写的是 v1.52.0-noble，但 uv.lock 已升到 playwright 1.53.0，
# 会导致运行时报 "Executable doesn't exist at /ms-playwright/firefox-1488/...".
FROM mcr.microsoft.com/playwright:v1.53.0-noble
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

USER root

WORKDIR /app

SHELL ["/bin/bash", "-c"]

ENV DISPLAY=:99 \
    UV_LINK_MODE=copy

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=repo/uv.lock,target=uv.lock \
    --mount=type=bind,source=repo/pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-cache --all-extras

# Install system packages, including unzip for the manual installation
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
    xvfb \
    tini \
    wget \
    curl \
    unzip && \
    rm -rf /var/lib/apt/lists/*

# Camoufox 浏览器内核需从 GitHub Release 下载（Linux x86_64 约 1.2GB）。
# 上游原注释称"国内不可达会降级"，但实测 Docker 构建网络可达（约 11MB/s）。
RUN uv run camoufox fetch || \
    echo "[warn] camoufox fetch 失败，运行时将自动降级为 playwright-firefox"

# 补装 Camoufox 的 GeoIP 城市库（约 48MB）。启用 BROWSER_PROXY 代理时，
# camoufox 会按代理出口 IP 生成一致的地理指纹，缺了这个库会直接抛
# InvalidDatabaseError 崩溃循环（踩过：camoufox fetch 的 geoip 步骤曾下载失败，
# 留下了无效的 .mmdb 文件）。latest/download 会 302 到最新版本。
RUN SITE=$(/app/.venv/bin/python -c "import pathlib,camoufox; print(pathlib.Path(camoufox.__file__).parent)") && \
    curl -fsSL --retry 3 -o "$SITE/GeoLite2-City.mmdb" \
      "https://github.com/P3TERX/GeoLite.mmdb/releases/latest/download/GeoLite2-City.mmdb" && \
    /app/.venv/bin/python -c "import maxminddb; maxminddb.open_database('$SITE/GeoLite2-City.mmdb').close(); print('GeoIP 校验通过')"

ADD repo /app
