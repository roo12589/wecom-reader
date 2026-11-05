# 企业微信聊天记录 Web 界面重构 Spec

## Why

当前 `python -m wecom_reader.web --db-dir ...\Cache` 可以完成解密并展示网页，但界面与查询层存在明显缺陷：会话最多 500 条、聊天记录分页会漏消息、消息时间缺少年份且顺序错乱、图片等非文本消息只显示内部 ID、单聊/部分群聊/外部会话直接显示会话 ID。需要把 Web 端重构为接近主流 IM（企业微信）的可用界面，并同步修正数据查询与消息解析逻辑。

## What Changes

- **BREAKING（仅 Web 展示层）**：重写 Web UI 的布局、样式与交互，从单文件内嵌模板改为模板 + 静态资源。
- 会话列表：完整分页加载全部会话，按最后消息时间倒序；解析单聊、群聊、微信/文档、应用、系统及外部会话的可读名称；合并重复的数字会话。
- 聊天记录：统一跨表查询并真正分页到全部消息；按时间正序展示（最新在底部），提供“加载更早消息”；按日期分隔并显示年份。
- 消息解析：按企业微信 protobuf 内容结构解析文本、图片、文件、视频、语音、链接、应用卡片、会议、通话、引用、表情、系统消息等，不再把内部 ID 当作正文。
- 媒体：从本地 `Cache/Image|File|Video|Voice` 与 `file.db` 建立索引，通过受控接口展示图片/视频、下载文件；找不到本地文件时展示带文件名/大小的占位卡片。
- 会话内与全局搜索、会话类型筛选、消息类型筛选、日期筛选，并支持从搜索结果定位到具体消息。
- 头像：优先使用 `avatar_store_v3.db` 与 `Avator` 本地缓存，缺失时使用姓名首字母占位。
- 保留启动命令与 CLI 行为；新增依赖 `flask` 到项目依赖声明。

## Impact

- 影响能力：会话列表、会话名称解析、聊天记录分页、消息内容解析、媒体展示、搜索/筛选、Web UI。
- 影响代码：
  - `wecom_reader/web.py`（HTTP 入口与 API）
  - `wecom_reader/templates/index.html`、`wecom_reader/static/app.js`、`wecom_reader/static/style.css`（新增，承载新 UI）
  - `wecom_reader/reader.py`（对外接口与缓存）
  - `wecom_reader/db/session.py`（名称解析、去重、分页）
  - `wecom_reader/db/message.py`（统一分页、结构化消息、搜索）
  - `wecom_reader/db/contact.py`（自身账号识别、头像映射）
  - `wecom_reader/db/proto.py`、`wecom_reader/db/media.py`（新增：protobuf 解析与本地媒体索引）
  - `pyproject.toml`（补充 Flask 依赖）
- 不变：数据库解密逻辑、密钥提取流程、CLI 子命令语义、`--db-dir` 参数形式。

## ADDED Requirements

### Requirement: 会话名称解析

系统 SHALL 为每个会话提供可读展示名称，禁止在会话列表和聊天标题中直接展示裸会话 ID。

#### Scenario: 单聊名称
- **WHEN** 会话 ID 为 `S:<A>_<B>` 且两个成员存在于 `user.db`
- **THEN** 名称显示为对方姓名（排除当前登录账号），不显示 `S:...` 原文

#### Scenario: 群聊名称
- **WHEN** `conversation_table.name` 或 `roomname_remark` 非空
- **THEN** 优先显示该名称；若均为空
- **THEN** 使用成员姓名组合（如“张三、李四等 5 人”）或“群聊 · N 人”，不显示 `R:...` 原文

#### Scenario: 应用/系统/微信/文档会话
- **WHEN** 会话前缀为 `O:`、`Y:`、`M:` 或特殊 ID（`FILEASSIST`、`APPROVAL`、`ANNOUNCE`、`SERVICE_NOTIFICATION`、`MAIL`、`WORK_JOURNAL`、`HIDDEN_APP_CONVERGE`）
- **THEN** 分别显示应用名/系统名/微信或文档标题/固定中文名称；`M:` 会话从 `type_content` 或 `tencent_doc_list.db` 解析文档标题

#### Scenario: 重复与外部会话
- **WHEN** 存在无前缀数字会话，且存在对应 `R:<id>` 会话
- **THEN** 合并为一条会话并使用 `R:` 会话的名称与消息
- **WHEN** 无前缀数字会话既无 `R:` 对应、也未命中联系人
- **THEN** 显示“外部会话”并保留在列表中，不隐藏、不显示裸 ID

### Requirement: 会话列表分页与筛选

系统 SHALL 提供可加载全部会话的分页接口与界面，会话按最后消息时间倒序排列。

#### Scenario: 超过 500 个会话
- **WHEN** 数据库中存在 1000+ 个会话
- **THEN** 会话列表支持滚动/按钮继续加载，直到全部加载完毕，且不会重复或遗漏

#### Scenario: 会话搜索与类型筛选
- **WHEN** 用户输入关键词或选择“全部/单聊/群聊/应用/系统/外部”筛选
- **THEN** 返回匹配的可读名称、最后消息预览或成员的会话；结果仍按时间倒序分页

#### Scenario: 会话摘要
- **WHEN** 会话有最后一条消息
- **THEN** 列表项展示该消息的文本摘要（图片显示 `[图片]`、文件显示文件名、语音显示 `[语音]` 等），以及相对时间

### Requirement: 聊天记录时间线

系统 SHALL 以时间正序渲染聊天记录（最早在上、最新在下），并在日期分隔中显示完整年份。

#### Scenario: 跨年/跨日展示
- **WHEN** 消息时间跨越不同日期或年份
- **THEN** 插入日期分隔条，格式包含年份（如“2024年8月15日 星期四”）
- **THEN** 每条消息显示 `HH:mm`，悬浮提示显示完整 `YYYY-MM-DD HH:mm:ss`

#### Scenario: 首次打开会话
- **WHEN** 用户选择会话
- **THEN** 自动定位到最新消息（底部）；上滑到顶部时自动加载更早消息

#### Scenario: 已加载全部
- **WHEN** 所有消息已加载
- **THEN** 显示“已加载全部 N 条消息”，不再出现“加载更多”

### Requirement: 聊天记录完整分页

系统 SHALL 对 `message_table`、`message_small_table`、`kf_message_tableV1` 做统一排序与分页，确保“加载更多”能覆盖该会话全部消息。

#### Scenario: 大量消息
- **WHEN** 单个会话消息数超过一页（50 条）
- **THEN** 每次加载更早一页时返回不同消息，`has_more` 准确；连续加载后消息总数等于该会话真实消息数
- **THEN** 分页键稳定为 `send_time DESC, sequence DESC, message_id DESC`，不因跨表合并产生重复/漏项

### Requirement: 消息类型结构化渲染

系统 SHALL 将消息内容解析为结构化类型，并按主流 IM 形态渲染；任何情况下不得将内部文件 ID/会话 ID 作为消息正文。

#### Scenario: 图片
- **WHEN** 收到图片消息（如 `content_type` 4/48）
- **THEN** 展示缩略图，点击可放大；本地缓存缺失时展示“图片 · 文件名/大小”占位卡

#### Scenario: 文件
- **WHEN** 收到文件消息（如 `content_type` 15/48/123）
- **THEN** 展示文件图标、文件名、大小与下载按钮；本地文件存在时可直接下载

#### Scenario: 语音
- **WHEN** 收到语音消息
- **THEN** 展示语音卡片；存在语音转文字记录时显示转写文本；本地音频存在时可播放

#### Scenario: 视频
- **WHEN** 收到视频消息（`content_type` 17）
- **THEN** 展示视频卡片；本地缓存存在时可在页面播放

#### Scenario: 链接 / 应用卡片 / 会议 / 通话
- **WHEN** 收到链接（13）、图文/应用消息（35/38/145/573/520/581）、会议（1011/581）、通话（40）
- **THEN** 分别展示标题、描述、域名/时间/地点/时长等卡片信息，链接可新窗口打开

#### Scenario: 引用与表情
- **WHEN** 消息包含引用（如 123/570/48）或自定义表情（29）
- **THEN** 引用展示“发送人：被引用文本”，回复内容独立展示；表情显示“[表情]”

#### Scenario: 系统与未知类型
- **WHEN** 消息为系统通知（如 1002/1022/1052/1043）或未支持类型
- **THEN** 系统消息居中灰色展示可读文本；未知类型显示“暂不支持的消息类型（N）”或已解析摘要，不显示原始 ID

#### Scenario: 发送方
- **WHEN** 消息由当前账号发送
- **THEN** 气泡右侧绿色显示且不显示自己的头像/姓名；群聊中他人消息显示头像与姓名，单聊中他人消息只显示头像

### Requirement: 本地媒体安全服务

系统 SHALL 通过受控接口提供本地媒体访问，并防止路径穿越。

#### Scenario: 媒体索引
- **WHEN** 启动或刷新后首次访问媒体
- **THEN** 建立 `Cache/Image`、`Cache/File`、`Cache/Video`、`Cache/Voice` 文件名索引，并根据 `file.db file_table4` 的 `message_id` 解析文件

#### Scenario: 不存在的媒体
- **WHEN** 消息对应文件未缓存在本地
- **THEN** 接口返回 404 与结构化原因，前端展示占位卡片而不是空白或 ID

#### Scenario: 非法请求
- **WHEN** 请求包含 `..`、绝对路径或非索引文件
- **THEN** 拒绝访问，不返回任意磁盘文件

### Requirement: 头像展示

系统 SHALL 优先使用本地头像资源，缺失时生成可辨识占位头像。

#### Scenario: 会话头像
- **WHEN** `avatar_store_v3.db` 中 `conversation_avatar_table` 存在该会话头像
- **THEN** 通过头像接口返回图片并展示

#### Scenario: 用户头像
- **WHEN** `user_table.avator_url` 的 MD5 命中 `Avator/<年-月>/<md5>.*`
- **THEN** 展示本地用户头像；否则使用姓名首字母/末两字占位

### Requirement: 搜索与定位

系统 SHALL 支持会话内搜索与全局消息搜索，并可从搜索结果定位到消息。

#### Scenario: 会话内搜索
- **WHEN** 用户在会话内输入关键词并选择消息类型/日期范围
- **THEN** 返回该会话中包含关键词的文本、文件名、卡片标题等消息，高亮关键词

#### Scenario: 全局搜索
- **WHEN** 用户在侧栏搜索消息
- **THEN** 返回跨会话结果（会话名、发送人、时间、摘要），点击后打开对应会话并定位/高亮该消息

#### Scenario: 无结果
- **WHEN** 搜索无匹配
- **THEN** 展示空状态与搜索条件，不清空当前会话

### Requirement: 企业微信风格界面

系统 SHALL 提供接近企业微信桌面端的布局与视觉，并在常见分辨率下可用。

#### Scenario: 桌面布局
- **WHEN** 窗口宽度 ≥ 1024px
- **THEN** 左侧为会话栏（搜索、筛选、会话列表），右侧为聊天区（标题栏、工具栏、消息区），视觉采用浅灰画布、白色卡片、蓝色强调色与绿色发送气泡

#### Scenario: 窄屏
- **WHEN** 窗口宽度 < 900px
- **THEN** 会话栏可收起/展开，聊天内容不被遮挡，消息与媒体自适应宽度

#### Scenario: 状态反馈
- **WHEN** 数据加载中、为空、失败或刷新中
- **THEN** 分别显示骨架/加载提示、空状态、可重试错误、刷新进度

### Requirement: 刷新与容错

系统 SHALL 在“刷新数据”后重建会话/消息/媒体/头像缓存，并保证单条坏数据不影响页面整体。

#### Scenario: 刷新
- **WHEN** 用户点击刷新并重新解密成功
- **THEN** 会话列表、当前会话消息、搜索与媒体索引均反映新数据

#### Scenario: 异常数据
- **WHEN** 某条消息内容无法解析或某数据库缺少表
- **THEN** 该消息降级为可读提示，接口仍返回其他消息，不抛出 500

## MODIFIED Requirements

### Requirement: 会话列表查询

`list_sessions` 从“直接返回 `conversation_table` 原始行并按 `limit/offset` 截断”改为：读取全部会话、解析可读名称、合并数字别名与重复项、附带最后消息摘要与类型，再在内存中按 `last_message_time DESC` 分页。返回 `total`、`has_more` 与 `sessions`。

### Requirement: 聊天记录查询

`get_messages` 从“逐表独立 `LIMIT/OFFSET` 后合并再截断”改为：跨表 `UNION ALL` 后统一按 `send_time DESC, sequence DESC, message_id DESC` 排序分页，返回 `total`、`has_more`，并附带结构化 `kind`、`text`、`quote`、`media` 等字段。

### Requirement: 消息内容解析

`_parse_content` 的“UTF-8 后正则抽取字符串”启发式改为企业微信 protobuf wire 解析 + 类型专用字段映射；仅对未知类型保留通用字符串提取作为兜底，且兜底结果需过滤纯 ID/长数字串。

### Requirement: Web UI

原单文件内嵌 HTML/JS 页面改为 Flask 模板 + 独立 CSS/JS 静态资源；保留 `/`、`/api/sessions`、`/api/messages`、`/api/search`、`/api/refresh` 路径兼容，同时扩展分页、媒体、头像、会话详情接口。

### Requirement: 启动方式

`python -m wecom_reader.web --db-dir "C:\Users\Administrator\Documents\airchina\1688849876550208_1970325081491960\Cache"` 仍可直接启动；`--db-dir` 指向 `Cache` 或 `Data` 时均能自动定位媒体目录；新增可选 `--media-dir`、`--self-id`、`--port`、`--host`。

## REMOVED Requirements

### Requirement: 会话 500 条硬上限

**Reason**：会话列表请求固定 `limit=500`，超过部分永远不可见。
**Migration**：改为服务端分页 + 前端滚动加载，默认每页 50 条。

### Requirement: 正则抽取消息正文

**Reason**：会把图片/文件 ID、二进制片段误当正文，也会破坏引用与卡片语义。
**Migration**：使用结构化 protobuf 解析，按消息类型渲染。

### Requirement: 裸 ID 作为名称/正文兜底

**Reason**：单聊、群聊、外部会话显示 `S:...`/`R:...`/数字 ID 不可读。
**Migration**：名称解析与“外部会话/未知类型”友好占位；原始 ID 仅在详情弹层中可复制查看。
