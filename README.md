# wecom-reader

企业微信（WeCom）本地聊天记录读取工具。从客户端进程内存提取密钥，解密本地 SQLite 数据库，提供 CLI / Python 库 / Web UI 三种访问方式。

## 原理

企业微信使用 wxSQLite3 AES-128-CBC 加密本地数据库：

- 密钥长度：16 字节（128 bit）
- 密钥数量：**一个全局密钥**解密所有数据库（比个人微信简单得多）
- 加密方式：每页独立派生 key/IV，无 HMAC，无 PBKDF2
- 密钥提取：通过 Windows API 读取客户端进程内存

## 安装

```bash
pip install pycryptodomex click flask
```

## 使用

### CLI

```bash
# 提取密钥 + 解密所有数据库（需要管理员权限，客户端运行中）
python -m wecom_reader.cli init --db-dir "E:\WXWork\<account_id>\Data"
# --db-dir / --decrypted-dir 既可以放在子命令后，也可以放在子命令前：
python -m wecom_reader.cli --db-dir "E:\WXWork\<account_id>\Data" init

# 私有化部署版本进程名通常不是 WXWork.exe（例如 airchina.exe），
# 工具会自动识别；识别失败时再显式指定：
python -m wecom_reader.cli init --process-name airchina.exe \
    --db-dir "C:\Users\<user>\Documents\airchina\<account_id>\Data"

# 查看状态
python -m wecom_reader.cli status

# 列出会话
python -m wecom_reader.cli sessions --limit 20

# 查看消息
python -m wecom_reader.cli messages R:12345 --limit 50

# 搜索消息
python -m wecom_reader.cli search "关键词"

# 查看联系人
python -m wecom_reader.cli contacts --keyword "张三"
```

### 私有化部署版本（进程名不是 WXWork.exe）

私有化版本会重命名客户端可执行文件，进程名不再是 `WXWork.exe`。本工具**自动识别**：
先从 `--db-dir` 的路径推断厂商目录名（`...\Documents\airchina\<account>\Data` → `airchina.exe`），
再与当前运行进程比对；找不到匹配时退回 `WXWork.exe`。

```bash
# 一般无需指定，自动识别即可：
python -m wecom_reader.cli init --db-dir "C:\Users\<user>\Documents\airchina\<account_id>\Data"

# 也可用环境变量指定：
set WXWORK_PROCESS_NAME=airchina.exe
```

> **注意**：同一台机器上可能并存基于飞书的产品（如 `AirChina5.0.exe`）。
> 它与基于企业微信的 `airchina.exe` 是两套独立程序，数据库互不通用；
> 自动识别时会排除这类同名不同源的进程，请勿混用它们的 `--db-dir`。

### 中文输出编码

CLI 默认以 **UTF-8** 向标准输出写 JSON（不受 Windows 控制台 GBK 代码页影响），
重定向或管道传给其它工具时中文不会乱码。若要沿用控制台原生编码：

```bash
set WECOM_READER_ENCODING=native
```

### Python 库

```python
from wecom_reader import WeComReader

reader = WeComReader(db_dir="E:/WXWork/<account_id>/Data")
reader.init()  # 提取密钥 + 解密

sessions = reader.list_sessions(limit=10)
msgs = reader.get_messages("R:12345", limit=50)
results = reader.search_messages("关键词")
contacts = reader.contacts(keyword="张三")
```

### Web UI

```bash
python -m wecom_reader.web --db-dir "C:\Users\<user>\Documents\airchina\<account_id>\Cache"
# 浏览器打开 http://127.0.0.1:8765
```

界面能力：

- 会话列表滚动分页加载（每页 50 条，可继续加载全部，不受 500 条限制）
- 会话内搜索 / 全局消息搜索，结果高亮并可跳转定位
- 消息类型筛选（文本、图片、文件、视频、语音、链接、引用、转发、会议卡片）与日期区间筛选
- 消息时间线带年份的日期分隔条，聊天窗口上滑自动加载更早消息
- 图片灯箱预览（点击打开，Esc 关闭）、文件消息显示文件名/大小/下载按钮
- 头像与媒体接口、一键刷新数据

常用参数：

| 参数 | 说明 |
|------|------|
| `--db-dir` | 必填。企微数据目录，可指向 `Cache` 或 `Data` |
| `--decrypted-dir` | 解密输出目录，默认 `wxwork_decrypted` |
| `--media-dir` | 媒体缓存目录，可选；留空自动定位 `Image/File/Video/Voice` |
| `--self-id` | 当前账号 ID，可选；留空自动识别 |
| `--port` | 监听端口，默认 `8765` |
| `--host` | 绑定地址，默认 `127.0.0.1` |

> 需要“刷新”重新解密最新数据时，`--db-dir` 请指向 `Data` 目录（媒体会自动定位到同级 `Cache`）；
> 指向 `Cache` 时仍可正常浏览，刷新只会重建已有解密数据的索引。

## 数据库结构

| 数据库 | 内容 | 大小 |
|--------|------|------|
| message.db | 聊天消息（130万+条） | ~770MB |
| session.db | 会话列表（5800+个） | ~22MB |
| user.db | 联系人/用户信息 | ~8MB |
| file.db | 文件传输记录 | ~158MB |
| calendar_r7.db | 日程信息 | ~2.5MB |
| crm.db | CRM 数据 | ~424KB |

## 会话 ID 格式

| 前缀 | 类型 |
|------|------|
| `R:<数字>` | 群聊 |
| `S:<数字>_<数字>` | 单聊 |
| `M:<数字>` | 微信联系人 |
| `O:<数字>` | 应用/公众号 |
| `Y:<数字>` | 系统会话 |

## 依赖

- Python >= 3.10
- pycryptodomex >= 3.20（AES 解密）
- click >= 8.0（CLI 框架）
- flask >= 3.0（Web UI，可选）

## 致谢

- [wechat-decrypt](https://github.com/ylytdeng/wechat-decrypt) — 企微解密参考实现
- [CipherTalk (密语)](https://github.com/ILoveBingLu/miyu) — WCDB 架构参考

## 免责声明

本工具仅供个人数据备份和学习研究使用。请遵守企业微信服务条款和当地法律法规。
