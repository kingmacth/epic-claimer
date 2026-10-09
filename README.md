# Epic 周免游戏 自动领取

每周自动登录 Epic、发现当周免费游戏、自动过 hCaptcha、自动完成 0 元下单。
全流程无需人工干预，领完把结果发到你邮箱。

> 本仓库只含**部署方案与本地补丁**，不含上游源码。首次使用请先运行 `setup.cmd`（Windows 双击）
> 或 `./setup.sh`（Linux / macOS），它会 clone 上游仓库并自动打好补丁。

---

## 一、原理与组成

| 组成 | 说明 |
| --- | --- |
| 领取引擎 | 开源项目 `Ronchy2000/epic-freebies-helper`（GPL-3.0），脱胎于 `QIN2DIM/epic-awesome-gamer` |
| 运行方式 | 本机 Docker 容器，从 `repo/` 源码 + 本目录的 `Dockerfile` 本地构建 |
| 浏览器 | **Camoufox**（C++ 层改过的反指纹 Firefox），1.29 GB 内核已成功安装并启用 |
| 验证码 | 用视觉大模型（GLM-4.6V）自动识别并破解 hCaptcha，支持点选/拖拽/多选 |
| 定时 | 容器内置 APScheduler，**周四 23:30 → 周五 03:30 每小时跑一次**，外加每天 12:00 兜底 |
| 登录态 | 浏览器 profile 持久化在 `volumes/`，一次登录后长期复用 |
| 出境网络 | 可选挂本机代理（容器内写 `host.docker.internal:<端口>`），Epic 访问可从 50-60 秒降到 1 秒内 |
| 通知 | 读取容器日志，通过智能体邮箱把结果发到你邮箱 |

时间说明：Epic 周免是**每周四 11:00 美东时间**刷新，折合北京时间约 **周四 23:00 ~ 周五 0 点**。
所以定时窗口从周四 23:30 开始，正好卡住刷新点。

### 浏览器后端说明

上游镜像 `ghcr.io/ronchy2000/epic-freebies-helper` 是**私有仓库**（GHCR 匿名拉取直接
`denied`），外部拿不到，所以本方案改为**本地构建**。

上游使用 **Camoufox**（反指纹 Firefox）。它的内核约 1.2 GB，需从 GitHub Release 下载。
**实测可以下动并安装成功**（约 11.5 MB/s），`.env` 里 `BROWSER_BACKEND=auto`，运行时日志确认：

```
Browser backend active | backend=camoufox
```

`Dockerfile` 里的 `uv run camoufox fetch` 做成了**失败不阻断构建**：即使某次内核下载失败，
`app/services/browser_context.py` 也会自动降级到 Playwright 自带的 Firefox，并在日志里打印：

```
Browser backend degraded | from=camoufox | to=playwright-firefox
```

任务不会因此中断。也就是说这套构建对网络波动是容错的。

### 网络与代理说明

`.env` 里有一条 `BROWSER_PROXY`，需要走本机代理时的填法示例：

```
BROWSER_PROXY=http://host.docker.internal:7890
```

（`7890` 换成你代理软件实际的监听端口；留空即为直连。）

三个要点：

1. **只对浏览器生效**。IMAP 取码（163）和 GLM API 都不走代理——不会因为挂代理而读不到邮箱。
2. **必须写 `host.docker.internal`**，不能写 `127.0.0.1`。容器里的 `127.0.0.1` 指向容器自己，
   而你的代理跑在宿主机上。
3. **代理有没有开是判断依据**。如果哪天你把代理软件关了，容器会连不上 Epic 而失败——
   这种情况把 `BROWSER_PROXY=` 留空（改成直连）即可，直连模式同样验证过可以跑通，
   只是每次登录慢一些（约 4 分钟 vs 1 分钟）。

实测对比（容器内访问 `store.epicgames.com`）：

| 模式 | 耗时 |
| --- | --- |
| 直连 | 50~60 秒，首次尝试常超时 |
| 走代理 | **0.9 秒** |

---

## 二、文件说明

```
epic-claimer/
├─ setup.sh / setup.cmd  ★ 首次使用先跑这个：clone 上游 + 打补丁 + 生成 .env
├─ Dockerfile            ★ 本方案自己的构建文件（基础镜像版本对齐、Camoufox 容错、GeoIP 库补装）
├─ docker-compose.yaml   容器编排（已修正官方模板对 GLM 用户的模型名冲突）
├─ .env                  ★ 你的账号与密钥，需要你填（不要外传、不要提交 git）
├─ .env.example          配置模板
├─ start.cmd             双击启动
├─ stop.cmd              双击停止
├─ logs.cmd              双击看实时日志
├─ patches/              ★ 本地补丁（对上游源码的修改，见第七节）
├─ tools/                诊断与自测脚本（宿主机侧，见第七节）
├─ volumes/              运行数据：日志、截图、浏览器 profile（自动生成，不入库）
└─ repo/                 上游源码副本（由 setup 脚本生成，不入库）
   └─ tools/test_email_otp.py   ★ 邮箱取码自测脚本（在容器内运行）

**为什么 `repo/` 不入库**：它整份都是上游作者的代码（GPL-3.0），重复托管没有意义，
也会让仓库膨胀到上百 MB。本仓库只保留**自己的部署层**与**对上游的最小改动**
（`patches/`），`setup` 脚本负责把两者拼装起来。
```

---

## 三、使用步骤

### 1. 启动 Docker Desktop

开始菜单搜 **Docker Desktop** 打开，等右下角鲸鱼图标不再转动
（在终端执行 `docker ps` 不报错即表示已就绪）。

> 注意：`docker --version` 能出结果**不代表引擎已启动**——那只是个命令行客户端。

### 2. 填写 `.env`

用记事本打开本目录的 `.env`，至少要填这四项：

| 配置项 | 填什么 |
| --- | --- |
| `EPIC_EMAIL` | Epic 账号邮箱 |
| `EPIC_PASSWORD` | Epic 账号密码 |
| `GLM_API_KEY` | 智谱 API Key，从 https://open.bigmodel.cn 获取 |
| 2FA 相关 | 见第四节，二选一（验证器 App 或邮箱取码） |

> 密码里如果包含 `$` `\` `#` 或反引号，请用单引号包起来，例如 `EPIC_PASSWORD='abc$def'`。

### 3. 构建并启动

双击 `start.cmd`，或在本目录执行：

```
docker compose up -d --build
```

首次构建约 5~10 分钟（要拉 Playwright 基础镜像 + 下载 Camoufox 内核，视网速）。
容器**启动后会立刻跑一次**领取任务，之后转入定时模式。

### 4. 看结果

双击 `logs.cmd`，或执行 `docker compose logs -f --tail=200`。

一次完整运行，**走代理约 1~2 分钟**（实测 74 秒），直连约 4~10 分钟（首次尝试常超时重试）。
期间不要中断。

日志里出现这些字样即为成功：

```
Login success
Right account validation success
Epic store session verification success
Authentication completed
Starting free games collection process
All week-free games are already in the library   ← 或 "Successfully claimed ..."
Free games collection completed
```

---

## 四、两步验证（2FA）配置

Epic 登录会要第二因子。脚本能自动完成**两种**来源，任配其一即可。

### 方式 A：验证器 App（最稳，推荐）

1. 登录 epicgames.com → 账号 → **密码与安全** → **两步验证**。
2. 在「**验证器应用 / Authenticator App**」旁点 **设置**，用手机验证器 App 扫码。
3. 在二维码页面点「**无法扫码 / Can't scan**」，把给出的 **Base32 密钥**
   （形如 `JBSWY3DPEHPK3PXP`）抄下来。
4. 填进 `.env` 的 `EPIC_TOTP_SECRET=`。

原理：脚本用 pyotp 在本地算 6 位码，不依赖任何网络，永不失效。

> 如果账号同时开着邮箱 2FA，请把**验证器 App 设为主方式**
> （在方法右侧三点菜单里选「Make my primary 2FA method」），
> 这样 Epic 会直接显示验证器输入框，脚本能自动填入。

### 方式 B：邮箱验证码（本方案已加补丁支持）

即当前的情况：Epic 把 6 位码发到**账号邮箱**。脚本会连 IMAP 读这封邮件，
自动抽出验证码填进登录页。这里有**三条本机实测出的硬约束**：

1. **Gmail 完全不可达**。本机网络下 `imap.gmail.com`、`googleapis.com` 全部超时。
   Epic 账号邮箱是 Gmail，所以**必须在 Gmail 里设置自动转发**到国内邮箱
   （163 / 126 / QQ 均可）。
2. **必须用 143 端口**。实测容器出口把 **993 端口封了**（163/126/QQ 的 993 全部超时），
   而 143 正常。所以 `.env` 里保持 `EPIC_IMAP_PORT=143`，走 STARTTLS（传输仍是加密的）。
3. **`EPIC_IMAP_PASS` 填「授权码」**，不是邮箱登录密码。

#### 第 1 步：Gmail 设置自动转发

1. Gmail → 设置（齿轮）→ **查看所有设置** → **转发和 POP/IMAP** → **添加转发地址**，
   填你的 163 邮箱。
2. Gmail 会往 163 发一封确认邮件 → 登录 163 打开它并点确认链接。
3. 回到 Gmail → **过滤器和已封锁的地址** → **新建过滤器**：
   发件人填 `epicgames.com`，操作勾选「**转发给**」你的 163 地址 → 创建过滤器。

#### 第 2 步：163 开启 IMAP 并取得授权码

1. 登录 mail.163.com → **设置** → **POP3/SMTP/IMAP**。
2. 开启「**IMAP/SMTP 服务**」，按提示完成手机验证。
3. 新增或查看「**授权密码**」——那串字符就是 `EPIC_IMAP_PASS`。

#### 第 3 步：填 `.env`

| 配置项 | 填什么 |
| --- | --- |
| `EPIC_IMAP_HOST` | `imap.163.com` |
| `EPIC_IMAP_PORT` | `143`（**别改成 993**，本机网络下不通） |
| `EPIC_IMAP_USER` | 你的 163 邮箱全称 |
| `EPIC_IMAP_PASS` | 上一步拿到的授权密码 |

其余 `EPIC_OTP_*` 项保持默认即可（等码时长、发件人关键字、邮件时间窗）。

#### 第 4 步：先单独自测（强烈建议）

```
docker compose run --rm --no-deps claimer \
  /app/.venv/bin/python /app/tools/test_email_otp.py
```

它会打印最近邮件列表、标出 Epic 的邮件、并报告能否抽出验证码。
**这一步通过了再去跑完整登录**，能省掉大量来回排查。

---

## 五、通知

运行结束后，结果会以邮件形式发到你邮箱，内容包含：
本周免费游戏清单、本次新领取、此前已拥有、未确认成功项、失败原因。

实现方式：一个每天 9:30 触发的定时任务，读取 `volumes/logs/runtime.log` 里最近一次运行的段落，
整理成中文摘要后用智能体邮箱发出。**带去重**——同一轮运行只通知一次，不会重复打扰。
如果检测到容器没在运行，会先 `docker compose up -d` 把它拉起来（会立即补跑一次）。

---

## 六、必须注意

1. **两步验证**：见第四节。支持「验证器 App」和「邮箱验证码」两种；
   **短信验证码不支持**——如果账号只开了短信 2FA，请改用前两种，或先关掉再跑。
2. **GLM Key 会过期，这是最可能失效的一环**。智谱免费令牌有效期通常只有 1~2 个月，
   过期后 hCaptcha 解不了，日志里会出现：
   `GLM auth issue | http_status=401 | 令牌已过期或验证不正确`。
   届时去 https://open.bigmodel.cn 重新生成一个 Key，更新 `.env` 的 `GLM_API_KEY` 即可。
   可以先用这条命令验证新 Key（不会泄露 Key 本身）：
   ```
   docker compose run --rm --no-deps --entrypoint sh claimer -c \
     'curl -s -o /dev/null -w "%{http_code}\n" -X POST https://open.bigmodel.cn/api/paas/v4/chat/completions \
      -H "Authorization: Bearer $GLM_API_KEY" -H "Content-Type: application/json" \
      -d "{\"model\":\"glm-4.6v\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}]}"'
   ```
   返回 `200` 即正常，`401` 就是过期了。
3. **代理开着才能走代理**。见第一节「网络与代理说明」。代理软件没开时容器会连不上 Epic，
   把 `BROWSER_PROXY=` 留空改成直连即可（同样能跑通，只是慢）。
4. **不要频繁重启容器**：Epic 有 24 小时领取限流，每次重启都会立刻跑一轮，容易白白消耗额度。
5. **密码是明文存在 `.env` 里的**。这是全自动方案绕不开的代价——脚本必须能自己登录。
   请勿把 `.env` 传到网盘、仓库或任何云端。
6. **电脑要开着**：本地 Docker 方案在关机时不会运行。好消息是容器设了 `restart: unless-stopped`，
   开机后 Docker Desktop 一启动容器就会自动恢复并**立即补跑一次**，所以漏掉的那周通常能自动补上。
   建议在 Docker Desktop 设置里勾选 **Start Docker Desktop when you sign in**，省得每次手动开。
7. **邮件通知依赖 WorkBuddy 在运行**。通知任务由 WorkBuddy 的定时器驱动（每天 9:30），
   如果那时 WorkBuddy 没开，那天的通知会跳过——但**领取动作本身不依赖它**，容器会照常跑。
8. **风控风险**：自动化领取理论上可能触发 Epic 风控，实际被封案例极少但非零。风险自行评估。
9. **首次可能遇到的坑**：
   - 若日志出现 `privacy-policy correction`，说明账号需要先确认隐私政策 →
     用你自己的浏览器登录一次 Epic 完成确认，再重跑。
   - 若出现 `Device not supported`，通常是该商品仅限 Windows → 脚本会自动点 Continue，一般不影响。
   - 若出现 `sessionInvalidated=true`，是 Epic 因 IP 变化吊销了旧会话，脚本会自动清 cookie 重登，
     属正常自愈，不用管。

---

## 七、本地补丁说明（重要）

本项目对上游 `repo/` 打了若干**最小补丁**，都是上游的硬伤或国内网络环境的必要适配。
这些补丁同时导出在 `patches/` 目录，由 `setup` 脚本自动应用。
**如果以后更新上游代码，这些地方可能被覆盖或产生冲突，需要重新检查**：

### 补丁 1：登录元素等待超时可配置
`app/services/epic_authorization_service.py`

上游把「点击登录按钮」和「等待密码框出现」两处硬编码为 `timeout=10000`（10 秒）。
国内网络访问 Epic 页面偏慢，10 秒经常不够，登录必然失败。
已改为读取环境变量 `EPIC_ELEMENT_TIMEOUT_MS`，本目录 `.env` 里设为 `60000`。

### 补丁 2：排除 uBlock Origin 插件
`app/services/browser_context.py`

camoufox 启动时默认下载 uBlock Origin 插件，但 `addons.mozilla.org` 在部分网络下返回 451，
下载失败会留下一个**空目录**；下次启动时 camoufox 会因为 `manifest.json` 缺失抛
`InvalidAddonPath`，而这个异常不在项目自己的降级白名单里，会导致整个任务崩溃。
已在启动参数中加 `exclude_addons=[DefaultAddons.UBO]` 彻底绕开。

### 补丁 3（构建层）：基础镜像版本对齐
`Dockerfile`

上游 Dockerfile 用 `mcr.microsoft.com/playwright:v1.52.0-noble`，但 `uv.lock` 已锁定
playwright 1.53.0，运行时报 `Executable doesn't exist at /ms-playwright/firefox-1488/...`。
已改为 `v1.53.0-noble`。另外把 `uv run camoufox fetch` 做成失败不阻断构建。

### 补丁 4：邮箱验证码取码能力
`app/services/epic_email_otp_service.py`（新增文件）+ `app/services/epic_totp_service.py`

上游只支持验证器 App（pyotp）。新增模块连 IMAP 读 Epic 验证码邮件、抽出 6 位码；
`epic_totp_service.py` 里：
- `totp_login_enabled()` 改为「TOTP 密钥 **或** IMAP 配置任一存在即可」；
- `_current_totp_code()` 在无 TOTP 密钥时改走邮箱取码。

原有的「找验证码输入框、填码、提交、失败重试、自动切换验证方式」等逻辑**全部复用，未改动**。

另注意取码模块里针对本机环境/服务端的三处必要处理：
- **`143 + STARTTLS`**：实测容器出口把 993 封了（163/126/QQ 的 993 全部超时）。
- **登录后补发 IMAP `ID` 命令**：必须先把它注册进 `imaplib.Commands`，否则 imaplib 会直接抛
  `KeyError`，命令根本发不出去。不发 ID 的后果是 `SELECT` 被服务端拒绝：
  `NO [EXAMINE Unsafe Login. Please contact kefu@188.com for help]`。
- **邮件头用 `make_header(decode_header(...))` 解码**：否则 MIME 编码的发件人/标题会变成空串，
  导致匹配不到 Epic 的邮件。

### 补丁 5：诊断/自测脚本
| 脚本 | 用途 |
| --- | --- |
| `repo/tools/test_email_otp.py` | 容器内运行：验证 IMAP 连通性、列出最近邮件、标出 Epic 邮件、报告能否抽码 |
| `tools/probe_imap.py` | IMAP 协议探针（用假账号验证登录链路，不需要真实凭据） |
| `tools/debug_imap.py` | 打印 IMAP 原始响应，排查 `SELECT` 被拒之类的问题 |
| `tools/dump_mail.py` | 打印指定发件人的邮件正文与其中链接（如「转发确认信」） |
| `tools/test_extract.py` | 验证码抽取逻辑离线单测（覆盖 7 种正文格式） |
| `tools/test_real_mail.py` | **用真实收到的 Epic 邮件**回归验证抽码逻辑（推荐改完抽码代码后跑） |
| `tools/debug_poll.py` | 逐封打印邮件的时间/发件人/匹配判定，定位"为什么没取到码" |
| `tools/analyze_code.py` | 打印邮件里所有数字序列及其上下文，分析验证码在正文中的形态 |

### 补丁 6：商店会话 SSO 交换
`app/services/epic_authorization_service.py`

**现象**：登录 API 成功（`Login success`）、账号页校验也过了，但商店页 `egs-navigation`
仍报 `isloggedin=false`，任务失败。截图确认商店页右上角确实显示「Sign in」。

**原因**：Epic 的登录态是分域种的。`www.epicgames.com` 域的会话已经有了（所以账号页正常），
但 `store.epicgames.com` 的会话需要走一次 **SSO 交换端点**
（`/id/api/redirect?redirectUrl=...`）才会种下 cookie。上游直接跳商店页，跳过了这一步。

**修法**：`_ensure_store_session_ready()` 读到 `isloggedin=false` 时不再立即判死，
而是先走一次 SSO 交换 → 回商店页重读；仍失败则 reload 再重读；两次都不行才抛错。
同时把该函数的超时从 45 秒放宽到 90 秒。实测 SSO 一次即成功。

后补：还有一种更隐蔽的情况——`//egs-navigation` 一直**超时读不到**（既不是 true 也不是 false）。
旧逻辑只在读到 `false` 时才走 SSO 交换，这条路会直接跳过交换、仅凭账号域（订单历史）探测
就宣布"会话就绪"，结果 store 域 cookie 从未种下，采集阶段报
`context cookies is not available`。现已改为：**只要商店会话没有被确认为 `true`，
就补一次 SSO 交换**；采集阶段的商店会话判定同样加了"先换会话再重试"的兜底，
不再把首次读到的 `isloggedin=false` 直接判死。

### 补丁 7：邮箱取码抽不到码（关键 bug）
`app/services/epic_email_otp_service.py`

**现象**：邮件明明在邮箱里（发件人、时间都匹配），轮询 180 秒却报"未找到验证码邮件"。

**原因有两个，叠加导致**：
1. **CSS 色值污染**。Epic 的验证码邮件是 31 KB 纯 HTML，里面含大量 6 位颜色值
   （`#595959`、`#999999`、`#333336`、`#000001`…）。纯文本化之后它们混进"数字池"，
   导致"全文唯一的 6 位数字"这条兜底判断**永远不成立**（候选不唯一）。
2. **提示词句式不匹配**。Epic 实际写的是「Enter this **6-digit code** to verify...」，
   而提示词表里只有 `security code` / `verification code`，匹配不到验证码所在区域。

**修法**：
- 转纯文本**之前**先清掉 `<style>` / `<script>` 块、HTML 注释、所有内联 `style="..."` 属性，
  再额外剥离 `#RRGGBB` 形式的色值 —— 清洗后正文从 20083 字符降到 4221，6 位数字候选只剩验证码本身。
- 提示词表补充 `digit code`、`code to verify`、`verify your`。
- 新增一条判定：**独立成行的 6 位数字**（验证码通常单独占一行）。

已用真实收到的 Epic 邮件回归验证通过。

### 补丁 8（构建层）：补装 GeoIP 城市库
`Dockerfile`

**现象**：一启用 `BROWSER_PROXY`，容器立刻崩溃循环：
`maxminddb.errors.InvalidDatabaseError: Error opening database file (.../camoufox/GeoLite2-City.mmdb)`。

**原因**：camoufox 需要 GeoLite2 城市库，用来**按代理出口 IP 生成一致的地理指纹**。
此前构建时 `camoufox fetch` 的 geoip 步骤下载失败，留下了一个**无效的 .mmdb 文件**；
直连时用不到所以一直没暴露，挂代理后一读就崩。

**修法**：镜像构建时补下载 [P3TERX/GeoLite.mmdb](https://github.com/P3TERX/GeoLite.mmdb)
的最新 `GeoLite2-City.mmdb`（约 48 MB，用 `releases/latest/download` 会自动跳转最新版），
并用 `maxminddb.open_database()` 当场校验。构建内下载耗时约 106 秒。

### 补丁 9：领取结果以「订单历史」为准复核（关键修复）
`app/services/epic_games_service.py`

**现象**：日志明明打印 `🎉 Instant checkout confirmed claim state`，Epic 邮箱里却没有该游戏的
领取回执 —— 也就是说**看起来领到了，实际没有下单**。本期 TerraScape 就是这样被漏掉的：
日志报成功，但既无订单也无回执（对比同期 Out of Sight 有正式回执）。

**原因**：上游判断"是否领取成功"靠的是页面 UI 标记（商品页购买按钮变成 `IN LIBRARY`、
结算区出现确认文案）。当结算 iframe（`structural-checkout-frame`）没有正常收尾时，
这些标记会**误报成功**。

**修法**：新增 `_verify_weekly_claims()`，在领取动作跑完之后**回到 Epic 订单历史**
（`/account/v2/payment/ajaxGetOrderHistory`，与"此前已拥有"判定同一数据源，即服务端真实数据）
逐款复核：

- 先打印「本期免费游戏共 N 款待领取：…」，把"这一期要领几个"说清楚，不再含糊；
- 未入库的自动补领，最多 3 轮，每轮之间等待并**重新**拉取订单历史；
- 全部确认入库才打印 `🎉 全部 N 款免费游戏已确认入库：…`；
- 3 轮后仍有缺漏才抛错，交给调度器（12:00 兜底 + 周四夜间多轮）继续重试。

同时 `collect_epic_games()` 不再因为 UI 层的"未确认"就直接失败，而是转交订单历史复核决定。

### 补丁 10：即时运行失败不再拖垮容器
`app/deploy.py`

**现象**：容器内跑完一次领取后进程退出、Docker 立刻重启，又触发一次即时运行；如果失败是
持续性的（例如结算阶段 hCaptcha 解不开），就变成**崩溃-重启循环**，反复登录/领取，
既浪费 Epic 的 24 小时限流额度，也给账号带来风控风险。

**原因**：`deploy()` 先跑一次即时任务、再启动调度器；即时任务抛错时异常一路冒到
`asyncio.run` 顶层，进程退出。而 compose 里配的是 `restart: unless-stopped`。

**修法**：把即时运行包进 `try/except`，失败只记日志，**调度器照常启动**，
由计划任务负责重试。

### 附：领取回执核对工具
`tools/claim_receipts.py`

```
docker exec epic-freebies-helper uv run tools/claim_receipts.py --hours 72
```

读取 Epic 的「Your Epic Games Receipt」邮件，列出最近 N 小时**实际入库**的游戏。
回执邮件是"确实下单"的权威凭证，因此它被用作对账与通知的依据
（每日 9:30 的邮件通知会附带这一段）。

### 重建镜像后如何让补丁生效
```
docker compose up -d --build
```
只有 `repo/` 内文件或 `Dockerfile` 变化时才会重新构建，其余情况走缓存，通常十几秒完成。

**注意**：镜像构建要从 GitHub 下载 camoufox 内核（约 1.29 GB）和 GeoLite2 城市库。
如果本机直连 GitHub 不通，构建会在下载步骤失败（日志里是 `Connection refused`）。
此时给构建挂上本地代理即可（下面的端口换成你自己的）：

```
docker build \
  --build-arg HTTP_PROXY=http://host.docker.internal:10080 \
  --build-arg HTTPS_PROXY=http://host.docker.internal:10080 \
  --build-arg NO_PROXY=localhost,127.0.0.1,::1 \
  --add-host host.docker.internal:host-gateway \
  -t epic-freebies-helper:local -f Dockerfile .

docker compose up -d --no-build
```

---

## 八、维护与升级

```bash
# 更新上游源码后重建（注意先检查第七节的本地补丁是否被覆盖）
cd repo && git pull && cd ..
docker compose up -d --build

# 从头重建 repo/（补丁应用失败、或想换上游版本时）
rm -rf repo && ./setup.sh        # Windows 上双击 setup.cmd
docker compose up -d --build

# 完全重置（会清掉登录态，需重新登录）
docker compose down
rm -rf volumes
```

---

## 九、来源与许可

- 领取引擎：[Ronchy2000/epic-freebies-helper](https://github.com/Ronchy2000/epic-freebies-helper)
  （GPL-3.0，脱胎于 [QIN2DIM/epic-awesome-gamer](https://github.com/QIN2DIM/epic-awesome-gamer)）
- 本仓库内容：Docker 构建与编排、国内网络适配补丁、邮箱验证码取码模块、诊断脚本。
  与上游保持同一许可（GPL-3.0）。
- 仅供个人学习与自用。自动化操作可能不符合平台服务条款，使用风险自负。
