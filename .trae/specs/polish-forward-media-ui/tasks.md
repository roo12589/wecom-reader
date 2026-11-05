# Tasks

- [x] Task 1: 修复会话类型筛选按钮显示
  - [x] SubTask 1.1: 在 `wecom_reader/static/style.css` 将 `.filter-tabs` 由横向滚动改为自适应网格/换行布局，`.tab` 等分列并居中，保证 280–300px 侧栏与移动端抽屉下 6 个按钮完整可见
  - [x] SubTask 1.2: 验证 300px、280px 及移动端宽度下“全部/单聊/群聊/应用/系统/外部”均无截断、无横向滚动，选中态切换不引起布局跳动，会话过滤仍正确

- [x] Task 2: 转发聊天记录长文本完整展示
  - [x] SubTask 2.1: 在 `wecom_reader/static/style.css` 移除 `.forward-text` 的 `-webkit-line-clamp: 4` 与 `.forward-items` 的固定 `max-height`/内部滚动，增大 `.forward-card` 宽度并保持自适应
  - [x] SubTask 2.2: 检查 `wecom_reader/static/app.js` 的 `forwardCardNode`，确保文本完整换行渲染、长文件名不溢出
  - [x] SubTask 2.3: 验证 20 行以上长文本与多条目转发记录均可完整阅读，气泡与头像不被遮挡

- [x] Task 3: 转发附件与普通消息一致性及媒体读取
  - [x] SubTask 3.1: 在 `wecom_reader/reader.py` 的 `_enrich_message` 中为转发 `items[].files` 补充 `size`、`mimetype`、`exists`（使用 `MediaCatalog.find_file` 按文件名判断）
  - [x] SubTask 3.2: 在 `wecom_reader/reader.py` 新增 `media_by_name(name)`，仅返回媒体索引命中的文件路径与 mimetype，绝不解析索引外路径
  - [x] SubTask 3.3: 在 `wecom_reader/web.py` 新增 `GET /api/media/forward?name=<文件名>&download=0|1`，校验文件名与路径归属，未命中返回 404 结构化 JSON
  - [x] SubTask 3.4: 在 `wecom_reader/static/app.js` 为转发附件新增渲染：图片显示缩略图（未缓存显示占位），其他文件复用普通文件卡片样式（图标/文件名/大小/下载或“本地未缓存”），下载走新接口
  - [x] SubTask 3.5: 转发图片点击接入图片查看器，并携带外层转发消息的 message_id 用于定位
  - [x] SubTask 3.6: 验证缓存文件可下载、未缓存文件明确标注、转发图片可看大图、无纯蓝色文件名残留

- [x] Task 4: 图片查看器基础能力升级
  - [x] SubTask 4.1: 在 `wecom_reader/templates/index.html` 扩展灯箱结构：上一张/下一张按钮、图片计数、缩放工具栏（放大/缩小/原始大小/适应窗口/百分比）、下载、定位到聊天位置
  - [x] SubTask 4.2: 在 `wecom_reader/static/app.js` 维护图片画廊列表：从当前已加载消息收集普通图片与转发图片，记录 `src/download/name/message_id`；缩略图点击以当前项打开
  - [x] SubTask 4.3: 实现上一张/下一张切换、首尾禁用、计数更新，切换时重置缩放与平移
  - [x] SubTask 4.4: 实现放大/缩小/原始大小/适应窗口与百分比显示，放大后支持拖拽平移
  - [x] SubTask 4.5: 实现“定位到聊天位置”：关闭灯箱后复用 `scrollToMessage` 滚动并高亮所属消息
  - [x] SubTask 4.6: 增加键盘操作：←/→ 切换、+/- 缩放、Esc 关闭；保留点击遮罩关闭行为
  - [x] SubTask 4.7: 验证多图切换、缩放边界、原始大小、下载、定位高亮及切换重置均正确

- [x] Task 5: 回归与端到端验收
  - [x] SubTask 5.1: 普通图片/文件/视频/语音消息的渲染、下载与灯箱行为不回归
  - [x] SubTask 5.2: 会话筛选切换、消息类型筛选、日期筛选与分页均保持正常
  - [x] SubTask 5.3: 使用真实数据浏览器验收：窄侧栏 6 个筛选按钮完整、转发长文完整、转发附件缓存状态正确、图片查看器全部操作可用
  - [x] SubTask 5.4: 回归 CLI `status`、`sessions`、`messages`、`search` 输出正常

# Task Dependencies

- Task 2 不依赖其它任务，可与 Task 1 并行
- Task 3.4 与 3.5 依赖 Task 3.1–3.3（附件状态与新接口）
- Task 4.2 依赖 Task 3.5（转发图片需进入同一画廊）
- Task 5 依赖 Task 1–4
