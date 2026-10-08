# 本地补丁

这里是对上游 [Ronchy2000/epic-freebies-helper](https://github.com/Ronchy2000/epic-freebies-helper)
的修改，由 `setup.sh`（Windows 上 `setup.cmd`）在拉取上游源码之后自动应用。

**基准提交**：`d90190bf3f9f87e9da71c50c81f155c4586bdb33`

| 补丁 | 涉及的变更 |
| --- | --- |
| `0001-email-otp-mfa.patch` | 新增 `app/services/epic_email_otp_service.py`、`tools/test_email_otp.py`；修改 `app/services/epic_totp_service.py` |
| `0002-cn-network-fixes.patch` | 修改 `app/services/epic_authorization_service.py`、`app/services/browser_context.py` |

## 0001 —— 邮箱验证码 2FA

上游只支持「验证器 App」（pyotp 本地算码）。这个补丁增加一条路径：连 IMAP 读 Epic 的验证码邮件，
抽出 6 位码填进登录页。

- `epic_email_otp_service.py`（新增）：IMAP 连接（143 + STARTTLS）、解析邮件、抽取验证码、轮询等待。
- `epic_totp_service.py`：`totp_login_enabled()` 改为「有 TOTP 密钥 **或** 有 IMAP 配置」即启用；
  `_current_totp_code()` 在没有 TOTP 密钥时改走邮箱取码。原有的填码、重试、切换验证方式等逻辑**未改动**。
- `tools/test_email_otp.py`（新增）：容器内自测脚本，先单独验证取码链路是否通。

两处针对特定服务端的处理，不是可选项：

- **143 + STARTTLS**：部分网络出口封了 993，143 正常。
- **登录后补发 IMAP `ID` 命令**：必须先把 `ID` 注册进 `imaplib.Commands`，否则 imaplib 直接抛
  `KeyError`，命令根本发不出去。不发 ID 时网易系邮箱会拒绝 `SELECT`：
  `NO [EXAMINE Unsafe Login. ...]`。
- **邮件头用 `make_header(decode_header(...))` 解码**：否则 MIME 编码的发件人/标题会变成空串，
  导致匹配不到目标邮件。

## 0002 —— 国内网络适配

- **登录元素超时**：上游把「点击登录按钮」「等待密码框出现」硬编码为 `timeout=10000`，
  网络较慢时必然超时。改为读环境变量 `EPIC_ELEMENT_TIMEOUT_MS`。
- **排除 uBlock 插件**：camoufox 默认下载 uBlock Origin，下载失败会留下空目录，
  下次启动抛 `InvalidAddonPath` 且不在降级白名单内，导致任务崩溃。
  改为 `exclude_addons=[DefaultAddons.UBO]`。
- **商店会话 SSO 交换**：登录 API 成功不等于商店会话就绪——`store.epicgames.com` 的 cookie
  需要走一次 `/id/api/redirect` 交换才会种下。默认直接跳商店页会读到 `isloggedin=false`。
  改为先做一次 SSO 交换再重读，并放宽该步骤超时。

## 手动应用

```bash
# 在仓库根目录
git -C repo apply --3way patches/0001-email-otp-mfa.patch
git -C repo apply --3way patches/0002-cn-network-fixes.patch
```

若上游已更新导致某条补丁无法应用，可先尝试：

```bash
git -C repo apply --3way patches/xxx.patch    # 三方合并，容错更好
```

仍失败则需要对照本文件的说明手动改。
