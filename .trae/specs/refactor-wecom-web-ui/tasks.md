# Tasks

- [x] Task 1: 新增消息解析与媒体基础模块
  - [x] SubTask 1.1: 新建 `wecom_reader/db/proto.py`，实现 protobuf wire 解析（varint/length-delimited/nested），提供 `decode_message(content_type, content, extra_content)`，输出 `kind`、`text`、`quote`、`media`、`card` 等结构化字段
  - [x] SubTask 1.2: 覆盖类型：文本 0/2、图片 4/14/16、文件 15/48/123、视频 17、语音 7、链接 13、图文/应用 35/38/145/520/573/581、通话 40、会议 1011、引用 48/123/570、表情 29、系统 1002/1022/1052/1043、未知类型兜底
  - [x] SubTask 1.3: 新建 `wecom_reader/db/media.py`，读取 `file.db file_table4`，按 `message_id` 汇总文件名/大小/md5/server_id；建立 `Cache/Image|File|Video|Voice` 文件名索引并支持按文件名查找本地路径
  - [x] SubTask 1.4: 校验解析不把 `WN...` 等内部 ID 作为正文；未知类型输出“[暂不支持的消息类型（N）]”而非原始字节
  - [x] SubTask 1.5: 用真实数据抽查：`content_type=4` 的 message 49 得到文件名 `clipbord_1701998054167.png` 且图片命中 `Cache/Image`；`15` 的 message 7 得到 `维护审查表.pdf`；`13` 得到标题与 URL

- [x] Task 2: 会话名称解析、账号识别与头像映射
  - [x] SubTask 2.1: 在 `wecom_reader/db/contact.py` 中实现自动识别当前账号（`conversation_user_table` 中出现次数最多的用户；支持 `--self-id` 覆盖），并复用 `user_table` 构建成员姓名映射
  - [x] SubTask 2.2: 在 `wecom_reader/db/session.py` 中实现名称解析：`S:` 取对方姓名；`R:` 取名称/备注，缺失时取成员姓名组合或“群聊 · N 人”；`M:` 解析文档标题；`O:`/`Y:`/特殊 ID 使用固定中文名或 type_content 标题
  - [x] SubTask 2.3: 合并无前缀数字会话：存在 `R:<id>` 时合并为一条；命中用户 ID 时按单聊显示姓名；其余标记为“外部会话”，不得显示裸 ID
  - [x] SubTask 2.4: 新增会话类型分类（group/single/wechat/app/system/external），并返回 `type_label`
  - [x] SubTask 2.5: 校验真实数据：1001 个原始会话经合并后无重复无遗漏；单聊如 `S:1688849876264269_1688849876550208` 显示“郭睿”；`FILEASSIST` 显示“文件传输助手”

- [x] Task 3: 重构消息查询、筛选、搜索与分页
  - [x] SubTask 3.1: `wecom_reader/db/message.py` 改为跨 `message_table`/`message_small_table`/`kf_message_tableV1` 的 `UNION ALL` 查询，统一 `ORDER BY send_time DESC, sequence DESC, message_id DESC`
  - [x] SubTask 3.2: `get_messages` 返回 `messages`、`total`、`has_more`，确保 offset 翻页无重复/漏项；支持 `types`、`keyword`、`start_time`、`end_time` 过滤
  - [x] SubTask 3.3: 用 `decode_message` 替换 `_parse_content`，消息项附带结构化 `kind`/`text`/`media`/`quote`/`card` 与可检索摘要
  - [x] SubTask 3.4: 重写 `search_messages`，支持会话内/全局、关键词、类型、日期、分页，返回会话 ID/名称、发送人、时间、命中摘要；中文关键词验证（如“预算”）
  - [x] SubTask 3.5: 提供按 `anchor_message_id` 定位的分页接口能力，用于搜索结果跳转并高亮

- [x] Task 4: Reader 层缓存与接口整合
  - [x] SubTask 4.1: `wecom_reader/reader.py` 增加用户映射、会话列表、会话名称、最后消息摘要、媒体索引、头像等懒加载缓存，并在 `init()`/刷新后失效
  - [x] SubTask 4.2: `list_sessions` 返回合并/解析后的完整列表并支持分页、关键词、类型过滤、`total`、`has_more`
  - [x] SubTask 4.3: `get_messages` 自动注入 `self_id`、`sender_name`、会话信息、结构化内容；`self_id` 消息标记为发送方
  - [x] SubTask 4.4: 增加 `session_detail`、`media_path`、`avatar_bytes`、`self_id` 等读取方法，保持既有 CLI 调用兼容
  - [x] SubTask 4.5: 校验 CLI `sessions/messages/search` 仍能运行且输出 JSON

- [x] Task 5: Web API 重构
  - [x] SubTask 5.1: `wecom_reader/web.py` 改为使用 `templates/` 与 `static/`，保留 `/` 页面入口
  - [x] SubTask 5.2: 扩展 `/api/sessions`：`limit`、`offset`、`keyword`、`type`，返回 `total`、`has_more`、`sessions`
  - [x] SubTask 5.3: 扩展 `/api/messages`：`limit`、`offset`、`types`、`keyword`、`start_time`、`end_time`、`anchor_message_id`，返回 `total`、`has_more`、`messages`、`self_id`、`conversation`
  - [x] SubTask 5.4: 扩展 `/api/search`：`q`、`session_id`、`types`、日期、分页
  - [x] SubTask 5.5: 新增 `/api/sessions/<id>/detail`、`/api/media/<message_id>`、`/api/avatar/<conversation_id>`、`/api/avatar/user/<user_id>`
  - [x] SubTask 5.6: 媒体接口只允许返回索引命中的文件，校验 `message_id` 与路径，拒绝穿越；404 返回结构化原因
  - [x] SubTask 5.7: `POST /api/refresh` 重新解密后刷新全部缓存；`--db-dir` 指向 `Cache` 或 `Data` 均自动定位媒体目录；支持 `--media-dir`、`--self-id`
  - [x] SubTask 5.8: 所有接口统一 JSON 编码（bytes/时间安全），异常不返回 500 堆栈

- [x] Task 6: 前端界面重构
  - [x] SubTask 6.1: 新建 `templates/index.html`、`static/style.css`，实现企业微信风格：浅灰画布、白色会话栏、蓝色强调、绿色发送气泡、圆角卡片
  - [x] SubTask 6.2: 会话栏：搜索框、类型筛选标签、头像、名称、最后消息摘要、时间、当前选中态；滚动到底自动加载下一页并显示总数
  - [x] SubTask 6.3: 聊天区：标题/类型/成员数、会话内搜索、消息类型筛选、日期筛选、回到最新；原始会话 ID 仅放入详情弹层
  - [x] SubTask 6.4: 消息时间线：正序渲染、日期分隔含年份、消息时间悬浮完整时间、自动定位最新、上滑加载更早、滚动位置保持、“已加载全部 N 条消息”
  - [x] SubTask 6.5: 实现各类型渲染器：文本/图片（灯箱放大）/文件（下载）/视频/语音（转写+播放）/链接/应用卡片/会议/通话/引用/表情/系统/未知
  - [x] SubTask 6.6: 搜索面板：输入防抖、结果高亮、点击结果打开会话并定位该消息；空状态与错误重试
  - [x] SubTask 6.7: 窄屏适配：会话栏可收起；媒体不溢出；键盘 Esc 关闭图片查看器
  - [x] SubTask 6.8: 自动加载/手动“加载更多”双路径；接口失败显示可重试提示，不破坏已加载内容

- [x] Task 7: 依赖、兼容与端到端验收
  - [x] SubTask 7.1: 在 `pyproject.toml` 增加 `flask>=3.0` 依赖；确认 `python -m wecom_reader.web` 无新增安装步骤
  - [x] SubTask 7.2: 更新 README Web UI 使用说明（新界面能力、可选参数 `--media-dir`/`--self-id`）
  - [x] SubTask 7.3: 用真实目录启动：`python -m wecom_reader.web --db-dir "C:\Users\Administrator\Documents\airchina\1688849876550208_1970325081491960\Cache"`
  - [x] SubTask 7.4: 浏览器验证：会话加载超过 500 条；单聊/群聊/外部会话名称正常；图片/文件/视频/语音/链接卡片正常；消息翻页到底无重复；年份与顺序正确
  - [x] SubTask 7.5: 回归 CLI：`status`、`sessions`、`messages`、`search` 正常输出

- [x] Task 8: 修复验收发现的 6 个问题
  - [x] SubTask 8.1: 修复会话列表倒序：在分页/过滤前用最后消息时间回填 `last_message_time` 并按时间重排，保证 947 条全局有序
  - [x] SubTask 8.2: 修复打开会话未贴底：图片/媒体异步加载完成后若仍处于“跟随最新”状态则重新贴底，避免底部差 393px
  - [x] SubTask 8.3: 修复引用消息无发送人：从引用条目嵌套字段解析发送人姓名，缺失时显示“引用消息”
  - [x] SubTask 8.4: 修复系统消息显示内部 ID：`content_type=1002` 等不再把 token/成员 ID 当正文，降级为可读“系统消息”
  - [x] SubTask 8.5: 修复会议占位：`content_type=1011` 无可解析字段时显示“会议消息（暂无详情）”，不出现空卡片
  - [x] SubTask 8.6: 改进语音展示：解析时长，非浏览器可播放格式（.silk/.slk）显示时长与下载入口，不误用 Excel MIME
  - [x] SubTask 8.7: 复验 checklist 中编号 6、12、24、25、26、27 的失败项

# Task Dependencies

- Task 2 depends on Task 1（解析与媒体基础）
- Task 3 depends on Task 1
- Task 4 depends on Task 2、Task 3
- Task 5 depends on Task 4
- Task 6 depends on Task 5
- Task 7 depends on Task 6
