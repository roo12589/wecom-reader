(function () {
  'use strict';

  /* ======================================================================
   * 常量 / 图标
   * ==================================================================== */

  var SESSION_PAGE_SIZE = 50;
  var MESSAGE_PAGE_SIZE = 50;
  var SEARCH_PAGE_SIZE = 50;
  var SEARCH_DEBOUNCE = 300;

  var WEEK_NAMES = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];

  var ICONS = {
    image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"></rect><circle cx="8.5" cy="9" r="1.4"></circle><path d="m3 16 5-5 4 4 3-3 6 6"></path></svg>',
    file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2.5h7l5 5v14H6z"></path><path d="M13 2.5v5h5"></path></svg>',
    video: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="6" width="13" height="12" rx="2"></rect><path d="m15.5 10 5-3v10l-5-3z"></path></svg>',
    play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l10-6.5z"></path></svg>',
    pause: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 5h3v14H7zM14 5h3v14h-3z"></path></svg>',
    link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10.5 13.5a4.5 4.5 0 0 0 6.4 0l2-2a4.5 4.5 0 0 0-6.4-6.4l-1 1"></path><path d="M13.5 10.5a4.5 4.5 0 0 0-6.4 0l-2 2a4.5 4.5 0 0 0 6.4 6.4l1-1"></path></svg>',
    app: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><rect x="3" y="3" width="7" height="7" rx="1.4"></rect><rect x="14" y="3" width="7" height="7" rx="1.4"></rect><rect x="3" y="14" width="7" height="7" rx="1.4"></rect><rect x="14" y="14" width="7" height="7" rx="1.4"></rect></svg>',
    forward: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="11" height="9" rx="1.6"></rect><path d="M7 8h3M7 10.5h2"></path><path d="M14 8h3.5a3 3 0 0 1 3 3v6.5"></path><path d="m17.6 15.6 2.9 2.9 2.9-2.9" transform="translate(-4 0)"></path></svg>',
    calendar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><rect x="3.5" y="5" width="17" height="15.5" rx="2"></rect><path d="M3.5 9.5h17M8 3v4M16 3v4"></path></svg>',
    phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7.5 3.5 10 3l2 4-2 2a12 12 0 0 0 4.8 4.8l2-2 4 2-.5 2.5a2 2 0 0 1-2.2 1.7C10.8 17.4 6.6 13.2 5.8 5.7A2 2 0 0 1 7.5 3.5Z"></path></svg>',
    smile: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="12" cy="12" r="9"></circle><path d="M8.5 10h.01M15.5 10h.01M8.5 14.5c1.6 1.8 5.4 1.8 7 0"></path></svg>',
    warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M12 3.5 2.9 19.5h18.2L12 3.5Z"></path><path d="M12 9.5v4.2"></path><circle cx="12" cy="16.8" r="1" fill="currentColor" stroke="none"></circle></svg>',
    copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><rect x="8.5" y="8.5" width="11" height="11" rx="2"></rect><path d="M15.5 5.5v-1a2 2 0 0 0-2-2h-8a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h1"></path></svg>',
    chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20.5 11.2a8.3 8.3 0 0 1-8.4 8.2 8.9 8.9 0 0 1-3.5-.7L4 20l1.3-4a8 8 0 0 1-.8-3.6A8.3 8.3 0 0 1 12.9 3a8.2 8.2 0 0 1 7.6 8.2Z"></path></svg>',
    external: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6"></path><path d="M20 4 11 13"></path><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"></path></svg>',
    download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v11"></path><path d="m7.5 10 4.5 4.5L16.5 10"></path><path d="M4 19.5h16"></path></svg>'
  };

  /* ======================================================================
   * 状态
   * ==================================================================== */

  var state = {
    status: null,

    sessions: [],
    sessionTotal: 0,
    sessionHasMore: false,
    sessionsLoading: false,
    sessionType: 'all',

    keyword: '',
    searchMode: 'session',
    searchResults: [],
    searchTotal: 0,
    searchOffset: 0,
    searchHasMore: false,
    searchLoading: false,
    globalPanelOpen: false,

    currentSession: null,
    messages: [],
    msgNextOffset: 0,
    msgHasMore: false,
    msgTotal: 0,
    msgTypes: [],
    datePreset: 'all',
    customStart: '',
    customEnd: '',
    highlightKeyword: '',
    msgLoading: false,
    olderLoading: false,
    msgLoadedOlder: false,
    msgError: '',
    followLatest: false,
    programmaticScroll: false,

    chatSearchOpen: false,
    chatSearchKeyword: '',
    chatSearchResults: [],
    chatSearchTotal: 0,
    chatSearchLoading: false,

    tokens: { sessions: 0, messages: 0, search: 0, chatSearch: 0 },
    suppressScrollLoad: false
  };

  var ui = {};

  var AVATAR_COLORS = [
    '#3b7ddd', '#2f9e63', '#e0782f', '#7b61c9',
    '#2aa3a3', '#c9527d', '#5b6ac9', '#8a6d3b'
  ];

  var TYPE_LABELS = {
    group: '群聊',
    single: '单聊',
    wechat: '微信',
    app: '应用',
    system: '系统',
    external: '外部会话',
    other: '其它'
  };

  /* ======================================================================
   * 通用工具
   * ==================================================================== */

  function makeEl(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function iconEl(name, className) {
    var span = makeEl('span', 'icon ' + (className || ''));
    span.setAttribute('aria-hidden', 'true');
    span.innerHTML = ICONS[name] || '';
    return span;
  }

  function fmtNum(value) {
    var number = Number(value);
    if (!isFinite(number)) return '—';
    try {
      return number.toLocaleString('zh-CN');
    } catch (err) {
      return String(number);
    }
  }

  function pad2(value) {
    return value < 10 ? '0' + value : String(value);
  }

  function toDate(ts) {
    var number = Number(ts);
    if (!isFinite(number) || number <= 0) return null;
    return new Date(number > 1e12 ? number : number * 1000);
  }

  function dateKey(ts) {
    var d = toDate(ts);
    if (!d) return 'unknown';
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  }

  function formatClock(ts) {
    var d = toDate(ts);
    if (!d) return '';
    return pad2(d.getHours()) + ':' + pad2(d.getMinutes());
  }

  function formatFull(ts) {
    var d = toDate(ts);
    if (!d) return '未知时间';
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) +
      ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
  }

  function formatDateTime(ts) {
    var d = toDate(ts);
    if (!d) return '未知';
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) +
      ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
  }

  function startOfDay(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate());
  }

  function formatSessionTime(ts) {
    var d = toDate(ts);
    if (!d) return '';
    var now = new Date();
    var today = startOfDay(now);
    var day = startOfDay(d);
    var diff = today.getTime() - day.getTime();
    if (diff === 0) return formatClock(ts);
    if (diff === 86400000) return '昨天';
    var monday = new Date(today);
    var weekday = (today.getDay() + 6) % 7;
    monday.setDate(monday.getDate() - weekday);
    if (day.getTime() >= monday.getTime() && day.getTime() < today.getTime()) {
      return WEEK_NAMES[d.getDay()];
    }
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  }

  function formatDateSeparator(ts) {
    var d = toDate(ts);
    if (!d) return '时间未知';
    return d.getFullYear() + '年' + (d.getMonth() + 1) + '月' + d.getDate() + '日 ' + WEEK_NAMES[d.getDay()];
  }

  function formatBytes(size) {
    var bytes = Number(size);
    if (!isFinite(bytes) || bytes <= 0) return '0 B';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(bytes < 10240 ? 1 : 0) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB';
    return (bytes / 1024 / 1024 / 1024).toFixed(1) + ' GB';
  }

  var RAW_ID_RE = /^(?:WN[0-9A-Za-z~._+\-]{3,}|[0-9]{6,}|[0-9a-fA-F]{32}|[0-9A-Za-z]{8}-[0-9A-Za-z-]{8,}|[RSMOY]:[0-9A-Za-z_:]+)$/;

  function isRawId(value) {
    var text = String(value == null ? '' : value).trim();
    return !!text && RAW_ID_RE.test(text);
  }

  function cleanDisplay(value) {
    var text = String(value == null ? '' : value).trim();
    if (!text || isRawId(text)) return '';
    return text
      .replace(/WEDRIVE_FILE\s*\{[^}]*\}/gi, '')
      .replace(/WEDRIVE_FILE/gi, '')
      .trim();
  }

  function displayName(value, fallback) {
    var text = cleanDisplay(value);
    return text || fallback || '未命名会话';
  }

  function typeLabel(type, label) {
    var clean = cleanDisplay(label);
    if (clean) return clean;
    return TYPE_LABELS[type] || '会话';
  }

  function avatarFallback(name) {
    var text = String(name || '').trim();
    if (!text) return '?';
    if (/^[\x00-\x7F]+$/.test(text)) {
      return text.charAt(0).toUpperCase();
    }
    return text.slice(-2);
  }

  function avatarColor(name) {
    var text = String(name || '');
    var hash = 0;
    for (var i = 0; i < text.length; i += 1) {
      hash = (hash * 31 + text.charCodeAt(i)) % 100000;
    }
    return AVATAR_COLORS[hash % AVATAR_COLORS.length];
  }

  function avatarNode(name, url, extraClass) {
    var wrap = makeEl('div', 'avatar ' + (extraClass || ''));
    var fallback = makeEl('span', 'avatar-fallback', avatarFallback(name));
    fallback.style.background = avatarColor(name);
    wrap.appendChild(fallback);
    if (url) {
      var img = document.createElement('img');
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.src = url;
      img.addEventListener('error', function () {
        img.remove();
      });
      wrap.appendChild(img);
    }
    return wrap;
  }

  function debounce(fn, wait) {
    var timer = null;
    function wrapped() {
      var args = arguments;
      var self = this;
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        fn.apply(self, args);
      }, wait);
    }
    wrapped.cancel = function () {
      window.clearTimeout(timer);
    };
    return wrapped;
  }

  function nextToken(key) {
    state.tokens[key] = (state.tokens[key] || 0) + 1;
    return state.tokens[key];
  }

  function isStale(key, token) {
    return state.tokens[key] !== token;
  }

  function buildUrl(path, params) {
    if (!params) return path;
    var query = new URLSearchParams();
    Object.keys(params).forEach(function (key) {
      var value = params[key];
      if (value === undefined || value === null || value === '') return;
      query.set(key, String(value));
    });
    var text = query.toString();
    return text ? path + '?' + text : path;
  }

  async function api(path, options) {
    var opts = options || {};
    var timeout = opts.timeout || 30000;
    var controller = new AbortController();
    var timer = window.setTimeout(function () {
      controller.abort();
    }, timeout);
    var init = {
      method: opts.method || 'GET',
      signal: controller.signal,
      cache: 'no-store',
      headers: {}
    };
    if (opts.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(opts.body);
    }
    var response;
    try {
      response = await fetch(buildUrl(path, opts.params), init);
    } catch (err) {
      window.clearTimeout(timer);
      if (err && err.name === 'AbortError') {
        throw new Error('请求超时，请稍后重试');
      }
      throw new Error('网络请求失败，请确认服务是否运行');
    }
    window.clearTimeout(timer);

    var text = '';
    try {
      text = await response.text();
    } catch (err) {
      text = '';
    }
    var data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (err) {
        data = null;
      }
    }
    if (!response.ok) {
      var detail = data && data.error ? data.error : ('HTTP ' + response.status);
      throw new Error('请求失败：' + detail);
    }
    return data || {};
  }

  var toastTimer = null;

  function toast(message, isError) {
    if (!ui.toast) return;
    ui.toast.textContent = message;
    ui.toast.classList.toggle('is-error', !!isError);
    ui.toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      ui.toast.hidden = true;
    }, 2600);
  }

  function showBootError(message) {
    if (!ui.bootError) return;
    ui.bootErrorText.textContent = message || '请确认后端服务已启动后重试。';
    ui.bootError.hidden = false;
  }

  function setStatusLine() {
    var data = state.status || {};
    var sessions = data.sessions !== undefined ? fmtNum(data.sessions) : '—';
    var messages = data.messages !== undefined && data.messages !== null ? fmtNum(data.messages) : '—';
    ui.statusLine.textContent = '会话 ' + sessions + ' · 消息 ' + messages;
  }

  /* ======================================================================
   * 会话列表
   * ==================================================================== */

  function renderSessionSkeleton() {
    var list = ui.sessionList;
    list.textContent = '';
    for (var i = 0; i < 7; i += 1) {
      var row = makeEl('div', 'skeleton-item pulse');
      var avatar = makeEl('div', 'skeleton-avatar');
      var lines = makeEl('div', 'skeleton-lines');
      var line1 = makeEl('div', 'skeleton-line');
      line1.style.width = (46 + (i % 3) * 12) + '%';
      var line2 = makeEl('div', 'skeleton-line short');
      lines.appendChild(line1);
      lines.appendChild(line2);
      row.appendChild(avatar);
      row.appendChild(lines);
      list.appendChild(row);
    }
  }

  function sessionItem(session) {
    var node = makeEl('button', 'session-item');
    node.type = 'button';
    node.setAttribute('role', 'listitem');
    node.dataset.sessionId = session.id;

    if (state.currentSession && state.currentSession.id === session.id) {
      node.classList.add('is-active');
      node.setAttribute('aria-current', 'true');
    }

    var name = displayName(session.name, '未命名会话');
    var avatarUrl = session.avatar_url ||
      ('/api/avatar/' + encodeURIComponent(session.avatar_cid || session.id || ''));
    node.appendChild(avatarNode(name, avatarUrl));

    var body = makeEl('div', 'session-body');
    var top = makeEl('div', 'session-row');
    var nameEl = makeEl('span', 'session-name', name);
    top.appendChild(nameEl);
    var timeEl = makeEl('span', 'session-time', formatSessionTime(session.last_message_time));
    top.appendChild(timeEl);

    var bottom = makeEl('div', 'session-row');
    var preview = cleanDisplay(session.last_preview) || kindPreview(session.last_preview_kind);
    var previewEl = makeEl('span', 'session-preview', preview);
    bottom.appendChild(previewEl);

    var label = typeLabel(session.type, session.type_label);
    var badge = makeEl('span', 'badge', label);
    if (session.type === 'external' || session.is_external) {
      badge.classList.add('badge-external');
    } else if (session.type === 'group') {
      badge.classList.add('badge-group');
    }
    bottom.appendChild(badge);

    body.appendChild(top);
    body.appendChild(bottom);
    node.appendChild(body);
    return node;
  }

  function kindPreview(kind) {
    var map = {
      image: '[图片]',
      file: '[文件]',
      video: '[视频]',
      voice: '[语音]',
      link: '[链接]',
      app: '[应用]',
      forward: '[聊天记录]',
      sticker: '[表情]',
      call: '[通话]',
      meeting: '[会议]',
      system: '[系统消息]'
    };
    return map[kind] || '[消息]';
  }

  function renderSessions() {
    var list = ui.sessionList;
    var previousTop = list.scrollTop;
    list.textContent = '';

    if (!state.sessions.length) {
      list.appendChild(emptyBlock(
        state.keyword ? '没有匹配的会话' : '没有会话',
        state.keyword ? '试试其它关键词，或切换搜索范围' : '当前筛选条件下没有会话数据'
      ));
      return;
    }

    var frag = document.createDocumentFragment();
    for (var i = 0; i < state.sessions.length; i += 1) {
      frag.appendChild(sessionItem(state.sessions[i]));
    }
    list.appendChild(frag);
    list.scrollTop = previousTop;
  }

  function emptyBlock(titleText, subText) {
    var box = makeEl('div', 'empty-block');
    var title = makeEl('strong', '', titleText);
    box.appendChild(title);
    if (subText) box.appendChild(makeEl('span', '', subText));
    return box;
  }

  function updateSessionFooter() {
    var loaded = state.sessions.length;
    if (state.sessionsLoading && !loaded) {
      ui.sessionFooterText.textContent = '正在加载会话…';
      ui.loadMoreSessions.hidden = true;
      return;
    }
    var prefix = '共 ' + fmtNum(state.sessionTotal) + ' 个会话 · 已加载 ' + fmtNum(loaded);
    ui.sessionFooterText.textContent = prefix;
    ui.loadMoreSessions.hidden = !state.sessionHasMore;
    ui.loadMoreSessions.disabled = state.sessionsLoading;
    ui.loadMoreSessions.textContent = state.sessionsLoading ? '加载中…' : '加载更多';
  }

  async function loadSessions(reset) {
    var isReset = !!reset;
    if (state.sessionsLoading && !isReset) return;

    var token = nextToken('sessions');
    state.sessionsLoading = true;

    if (isReset) {
      state.sessions = [];
      state.sessionTotal = 0;
      state.sessionHasMore = false;
      renderSessionSkeleton();
      updateSessionFooter();
    } else {
      updateSessionFooter();
    }

    var offset = isReset ? 0 : state.sessions.length;
    var params = {
      limit: SESSION_PAGE_SIZE,
      offset: offset,
      type: state.sessionType === 'all' ? '' : state.sessionType,
      keyword: state.searchMode === 'session' ? state.keyword : ''
    };

    try {
      var data = await api('/api/sessions', { params: params });
      if (isStale('sessions', token)) return;

      var items = data.sessions || [];
      state.sessionTotal = Number(data.total) || 0;
      state.sessionHasMore = !!data.has_more;
      state.sessions = isReset ? items : state.sessions.concat(items);
      renderSessions();
    } catch (err) {
      if (isStale('sessions', token)) return;
      if (isReset) {
        ui.sessionList.textContent = '';
      }
      ui.sessionList.appendChild(sessionErrorBlock(err.message));
    } finally {
      if (!isStale('sessions', token)) {
        state.sessionsLoading = false;
        updateSessionFooter();
      }
    }
  }

  function sessionErrorBlock(message) {
    var box = makeEl('div', 'error-block');
    box.appendChild(makeEl('p', '', '会话加载失败：' + message));
    var retry = makeEl('button', 'retry-btn', '重新加载');
    retry.type = 'button';
    retry.addEventListener('click', function () {
      box.remove();
      loadSessions(true);
    });
    box.appendChild(retry);
    return box;
  }

  /* ======================================================================
   * 打开会话与消息加载
   * ==================================================================== */

  function fillAvatar(container, name, url) {
    container.textContent = '';
    var fallback = makeEl('span', 'avatar-fallback', avatarFallback(name));
    fallback.style.background = avatarColor(name);
    container.appendChild(fallback);
    if (!url) return;
    var img = document.createElement('img');
    img.alt = '';
    img.loading = 'lazy';
    img.decoding = 'async';
    img.src = url;
    img.addEventListener('error', function () {
      img.remove();
    });
    container.appendChild(img);
  }

  function sessionAvatarUrl(session) {
    if (!session) return '';
    return session.avatar_url ||
      ('/api/avatar/' + encodeURIComponent(session.avatar_cid || session.id || ''));
  }

  function chatMetaText(session) {
    if (!session) return '';
    var parts = [typeLabel(session.type, session.type_label)];
    var count = Number(session.member_count);
    if (count > 1) parts.push(fmtNum(count) + ' 人');
    if (session.is_external && session.type !== 'external') parts.push('外部会话');
    return parts.join(' · ');
  }

  function refreshChatHeader() {
    var session = state.currentSession;
    if (!session) return;
    var name = displayName(session.name, '未命名会话');
    ui.chatName.textContent = name;
    ui.chatName.title = name;
    ui.chatMeta.textContent = chatMetaText(session);
    fillAvatar(ui.chatAvatar, name, sessionAvatarUrl(session));
  }

  function updateConversationMeta(conversation) {
    if (!conversation || !state.currentSession) return;
    if (conversation.id && conversation.id !== state.currentSession.id) return;
    if (conversation.name) state.currentSession.name = conversation.name;
    if (conversation.type) state.currentSession.type = conversation.type;
    if (conversation.type_label) state.currentSession.type_label = conversation.type_label;
    if (conversation.member_count) {
      state.currentSession.member_count = conversation.member_count;
    }
    refreshChatHeader();
  }

  async function openSession(session, options) {
    if (!session || !session.id) return;
    var opts = options || {};
    var sameSession = !!(state.currentSession && state.currentSession.id === session.id);

    state.currentSession = {
      id: session.id,
      name: session.name || '',
      type: session.type || 'other',
      type_label: session.type_label || '',
      member_count: session.member_count || 0,
      is_external: !!session.is_external,
      avatar_url: session.avatar_url || sessionAvatarUrl(session),
      avatar_cid: session.avatar_cid || session.id,
      last_message_time: session.last_message_time || 0
    };

    state.highlightKeyword = opts.keyword || '';
    state.chatSearchOpen = false;
    state.chatSearchKeyword = '';
    state.chatSearchResults = [];
    state.chatSearchTotal = 0;
    state.msgTypes = [];
    state.datePreset = 'all';
    state.customStart = '';
    state.customEnd = '';
    state.msgLoadedOlder = false;
    state.msgError = '';

    ui.chatSearchBar.hidden = true;
    ui.chatSearchInput.value = '';

    resetFilterControls();
    closeGlobalSearchPanel();
    hideChatSearchPanel();

    refreshChatHeader();
    ui.emptyState.hidden = true;
    ui.chatView.hidden = false;

    renderSessions();
    if (window.innerWidth <= 900) closeSidebar();

    var anchorId = opts.anchorId !== undefined && opts.anchorId !== null ? opts.anchorId : null;
    if (anchorId !== null) {
      ui.latestBtn.hidden = false;
    } else {
      ui.latestBtn.hidden = true;
    }

    if (sameSession && !anchorId) {
      ui.messageScroll.scrollTop = 0;
    }

    await loadMessages({ reset: true, anchorId: anchorId });
  }

  function messageSortKey(message) {
    return [
      Number(message.send_time) || 0,
      Number(message.sequence) || 0,
      Number(message.message_id) || 0
    ];
  }

  function compareMessages(a, b) {
    var ka = messageSortKey(a);
    var kb = messageSortKey(b);
    for (var i = 0; i < ka.length; i += 1) {
      if (ka[i] !== kb[i]) return ka[i] - kb[i];
    }
    return 0;
  }

  function messageUniqueKey(message) {
    if (message.message_id !== undefined && message.message_id !== null) {
      return 'id:' + message.message_id;
    }
    return 'x:' + [
      message.send_time,
      message.sequence,
      message.sender_id,
      message.content_type
    ].join(':');
  }

  function mergeMessages(pageMessages) {
    var map = Object.create(null);
    state.messages.forEach(function (message) {
      map[messageUniqueKey(message)] = message;
    });
    pageMessages.forEach(function (message) {
      if (!message) return;
      map[messageUniqueKey(message)] = message;
    });
    var merged = [];
    Object.keys(map).forEach(function (key) {
      merged.push(map[key]);
    });
    merged.sort(compareMessages);
    state.messages = merged;
  }

  function dateSeparatorNode(ts) {
    var node = makeEl('div', 'date-separator');
    node.appendChild(makeEl('span', '', formatDateSeparator(ts)));
    return node;
  }

  function renderMessages() {
    var list = ui.messageList;
    list.textContent = '';

    if (!state.messages.length) {
      list.appendChild(emptyBlock(
        '暂无消息',
        hasActiveMessageFilters() ? '当前筛选条件下没有消息' : '这个会话还没有可显示的消息'
      ));
      return;
    }

    var frag = document.createDocumentFragment();
    var lastKey = null;
    var isGroup = !!(state.currentSession && state.currentSession.type === 'group');

    for (var i = 0; i < state.messages.length; i += 1) {
      var message = state.messages[i];
      var key = dateKey(message.send_time);
      if (key !== lastKey) {
        frag.appendChild(dateSeparatorNode(message.send_time));
        lastKey = key;
      }
      frag.appendChild(messageNode(message, isGroup));
    }
    list.appendChild(frag);
  }

  function renderMessageSkeleton() {
    ui.messageList.textContent = '';
    for (var i = 0; i < 5; i += 1) {
      var row = makeEl('div', 'message-skeleton pulse' + (i % 2 === 0 ? ' out' : ''));
      if (i % 2 === 0) {
        row.appendChild(makeEl('div', 'sk-bubble'));
        row.appendChild(makeEl('div', 'sk-avatar'));
      } else {
        row.appendChild(makeEl('div', 'sk-avatar'));
        row.appendChild(makeEl('div', 'sk-bubble'));
      }
      ui.messageList.appendChild(row);
    }
  }

  function pinToBottom() {
    var scroll = ui.messageScroll;
    state.programmaticScroll = true;
    scroll.scrollTop = scroll.scrollHeight;
    window.requestAnimationFrame(function () {
      window.requestAnimationFrame(function () {
        state.programmaticScroll = false;
      });
    });
  }

  function scrollToBottom() {
    state.followLatest = true;
    window.requestAnimationFrame(pinToBottom);
    window.setTimeout(stickToBottomIfFollowing, 300);
  }

  function stickToBottomIfFollowing() {
    if (!state.followLatest) return;
    window.requestAnimationFrame(function () {
      if (state.followLatest) pinToBottom();
    });
  }

  var messageListObserver = null;

  function watchMessageList() {
    if (!window.ResizeObserver || !ui.messageList || messageListObserver) return;
    // Keep the newest message visible when lazy images/videos grow the list.
    messageListObserver = new ResizeObserver(function () {
      if (state.followLatest) stickToBottomIfFollowing();
    });
    messageListObserver.observe(ui.messageList);
  }

  function scrollToMessage(messageId, shouldFlash) {
    var selector = '[data-message-id="' + String(messageId) + '"]';
    var node = ui.messageList.querySelector(selector);
    if (!node) return;
    window.requestAnimationFrame(function () {
      node.scrollIntoView({ block: 'center', behavior: 'auto' });
      if (shouldFlash === false) return;
      var target = node.querySelector('.bubble, .sticker-card, .info-card, .file-card, .link-card, .forward-card, .msg-system span') || node;
      target.classList.remove('flash');
      void target.offsetWidth;
      target.classList.add('flash');
      window.setTimeout(function () {
        target.classList.remove('flash');
      }, 2200);
    });
  }

  function restoreScrollPosition(before) {
    var scroll = ui.messageScroll;
    scroll.scrollTop = scroll.scrollHeight - before.height + before.top;
  }

  function updateLatestButton() {
    ui.latestBtn.hidden = !state.msgLoadedOlder;
  }

  function updateOlderSentinel() {
    if (!state.currentSession) {
      ui.loadOlderBtn.hidden = true;
      ui.loadOlderStatus.textContent = '';
      return;
    }
    if (state.olderLoading) {
      ui.loadOlderBtn.hidden = true;
      ui.loadOlderStatus.textContent = '正在加载更早消息…';
      return;
    }
    if (state.msgLoading && !state.messages.length) {
      ui.loadOlderBtn.hidden = true;
      ui.loadOlderStatus.textContent = '正在加载消息…';
      return;
    }
    if (!state.msgHasMore) {
      ui.loadOlderBtn.hidden = true;
      var loaded = state.messages.length;
      var total = state.msgTotal;
      if (total <= 0) {
        ui.loadOlderStatus.textContent = '暂无消息';
      } else if (loaded >= total) {
        ui.loadOlderStatus.textContent = '已加载全部 ' + fmtNum(total) + ' 条消息';
      } else {
        ui.loadOlderStatus.textContent = '已加载 ' + fmtNum(loaded) + ' / ' + fmtNum(total) + ' 条消息';
      }
      return;
    }
    ui.loadOlderBtn.hidden = false;
    ui.loadOlderBtn.disabled = false;
    ui.loadOlderStatus.textContent = '';
  }

  function clearMessageError() {
    var nodes = ui.messageList.querySelectorAll('.msg-error');
    for (var i = 0; i < nodes.length; i += 1) nodes[i].remove();
  }

  function messageErrorNode(message, retryFn) {
    var box = makeEl('div', 'msg-error');
    box.appendChild(makeEl('span', '', '消息加载失败：' + message));
    var retry = makeEl('button', 'retry-btn', '重试');
    retry.type = 'button';
    retry.addEventListener('click', function () {
      box.remove();
      retryFn();
    });
    box.appendChild(retry);
    return box;
  }

  async function loadMessages(options) {
    var opts = options || {};
    var reset = !!opts.reset;
    var anchorId = opts.anchorId !== undefined && opts.anchorId !== null ? opts.anchorId : null;

    if (!state.currentSession) return;
    if (!reset && (state.olderLoading || !state.msgHasMore)) return;
    if (!reset && state.msgNextOffset <= 0) return;

    var token = nextToken('messages');
    var scroll = ui.messageScroll;
    var before = { height: scroll.scrollHeight, top: scroll.scrollTop };
    var previous = reset ? {
      messages: state.messages.slice(),
      msgHasMore: state.msgHasMore,
      msgTotal: state.msgTotal,
      msgNextOffset: state.msgNextOffset,
      msgLoadedOlder: state.msgLoadedOlder
    } : null;

    if (reset) {
      state.msgLoading = true;
      state.msgError = '';
      state.msgLoadedOlder = anchorId !== null;
      renderMessageSkeleton();
    } else {
      state.olderLoading = true;
    }
    updateOlderSentinel();
    updateLatestButton();

    var params = {
      session_id: state.currentSession.id,
      limit: MESSAGE_PAGE_SIZE,
      offset: reset ? 0 : state.msgNextOffset,
      types: state.msgTypes.join(','),
      start_time: computeDateRange().start,
      end_time: computeDateRange().end
    };
    if (anchorId !== null) params.anchor_message_id = anchorId;

    try {
      var data = await api('/api/messages', { params: params });
      if (isStale('messages', token)) return;

      var page = data.messages || [];
      if (reset) state.messages = [];
      mergeMessages(page);

      state.msgTotal = Number(data.total) || 0;
      state.msgHasMore = !!data.has_more;
      state.msgNextOffset = (Number(data.offset) || 0) + page.length;
      if (!reset) state.msgLoadedOlder = true;
      if (data.conversation) updateConversationMeta(data.conversation);

      clearMessageError();
      renderMessages();
      updateOlderSentinel();
      updateLatestButton();

      if (reset) {
        if (anchorId !== null) {
          scrollToMessage(anchorId, true);
        } else {
          scrollToBottom();
        }
      } else {
        restoreScrollPosition(before);
      }
      state.msgError = '';
    } catch (err) {
      if (isStale('messages', token)) return;
      state.msgError = err.message;
      if (reset && previous) {
        state.messages = previous.messages;
        state.msgHasMore = previous.msgHasMore;
        state.msgTotal = previous.msgTotal;
        state.msgNextOffset = previous.msgNextOffset;
        state.msgLoadedOlder = previous.msgLoadedOlder;
        renderMessages();
        updateOlderSentinel();
        updateLatestButton();
      }
      var retryFn = function () {
        if (reset) {
          loadMessages({ reset: true, anchorId: anchorId });
        } else {
          loadMessages({ reset: false });
        }
      };
      var node = messageErrorNode(err.message, retryFn);
      if (state.messages.length) {
        var first = ui.messageList.firstChild;
        if (first) ui.messageList.insertBefore(node, first);
        else ui.messageList.appendChild(node);
      } else {
        ui.messageList.appendChild(node);
      }
      toast('消息加载失败：' + err.message, true);
    } finally {
      if (!isStale('messages', token)) {
        state.msgLoading = false;
        state.olderLoading = false;
        updateOlderSentinel();
      } else if (!reset) {
        state.olderLoading = false;
      }
    }
  }

  function loadOlderMessages() {
    if (!state.currentSession || state.olderLoading || !state.msgHasMore) return;
    loadMessages({ reset: false });
  }

  function loadLatestMessages() {
    if (!state.currentSession) return;
    state.msgLoadedOlder = false;
    loadMessages({ reset: true, anchorId: null });
    ui.latestBtn.hidden = true;
  }

  /* ======================================================================
   * 消息渲染
   * ==================================================================== */

  function messageNode(message, isGroup) {
    if (message.kind === 'system') return systemMessageNode(message);

    var outgoing = !!message.is_send;
    var row = makeEl('div', 'msg-row ' + (outgoing ? 'out' : 'in'));
    if (message.message_id !== undefined && message.message_id !== null) {
      row.dataset.messageId = String(message.message_id);
    }

    var senderName = displayName(message.sender_name, '未知发送人');

    if (!outgoing && message.sender_avatar) {
      var avatarWrap = avatarNode(senderName, message.sender_avatar);
      row.appendChild(avatarWrap);
    } else if (!outgoing) {
      row.appendChild(avatarNode(senderName, ''));
    }

    var main = makeEl('div', 'msg-main');
    var meta = makeEl('div', 'msg-meta');

    if (!outgoing && isGroup) {
      meta.appendChild(makeEl('span', 'msg-sender', senderName));
    }

    var time = makeEl('time', 'msg-time', formatClock(message.send_time));
    if (message.send_time) {
      time.title = formatFull(message.send_time);
      time.dateTime = toDate(message.send_time) ? toDate(message.send_time).toISOString() : '';
    }
    meta.appendChild(time);
    main.appendChild(meta);

    var bubble = makeEl('div', 'bubble');
    bubble.appendChild(bubbleContent(message));
    main.appendChild(bubble);
    row.appendChild(main);
    return row;
  }

  function systemMessageNode(message) {
    var row = makeEl('div', 'msg-system');
    if (message.message_id !== undefined && message.message_id !== null) {
      row.dataset.messageId = String(message.message_id);
    }
    var text = cleanDisplay(message.text) || cleanDisplay(message.summary) || '系统消息';
    var span = makeEl('span', '', text);
    span.title = formatFull(message.send_time);
    row.appendChild(span);
    var clock = cleanDisplay(formatClock(message.send_time));
    if (clock) row.appendChild(makeEl('time', 'msg-system-time', clock)).title = formatFull(message.send_time);
    return row;
  }

  function bubbleContent(message) {
    var wrap = makeEl('div', 'bubble-body');
    if (message.quote) wrap.appendChild(quoteBox(message.quote));

    var kind = message.kind || 'unknown';
    switch (kind) {
      case 'text':
        appendText(wrap, message.text || message.summary);
        break;
      case 'image':
        appendImageMedia(wrap, message);
        break;
      case 'file':
        appendFileMedia(wrap, message);
        break;
      case 'video':
        appendVideoMedia(wrap, message);
        break;
      case 'voice':
        appendVoiceMedia(wrap, message);
        break;
      case 'link':
        wrap.appendChild(linkCardNode(message));
        break;
      case 'app':
        wrap.appendChild(appCardNode(message));
        break;
      case 'forward':
        wrap.appendChild(forwardCardNode(message));
        break;
      case 'meeting':
        wrap.appendChild(meetingCardNode(message));
        break;
      case 'call':
        wrap.appendChild(callCardNode(message));
        break;
      case 'sticker':
        wrap.appendChild(stickerCardNode(message));
        break;
      case 'quote':
        appendText(wrap, message.text);
        appendGenericAttachments(wrap, message);
        break;
      case 'system':
        appendText(wrap, message.text || message.summary);
        break;
      case 'unknown':
        appendUnknown(wrap, message);
        break;
      default:
        if (cleanDisplay(message.text) || cleanDisplay(message.summary)) {
          appendText(wrap, message.text || message.summary);
        } else if (mediaOf(message).length) {
          appendGenericAttachments(wrap, message);
        } else {
          appendUnknown(wrap, message);
        }
    }

    if (!wrap.childNodes.length) {
      wrap.appendChild(makeEl('span', 'unknown-note', '此消息暂无可用内容'));
    }
    return wrap;
  }

  function appendText(container, rawText) {
    var text = cleanDisplay(rawText);
    if (!text) return;
    var p = makeEl('p', 'msg-text');
    appendRichText(p, text, state.highlightKeyword);
    container.appendChild(p);
  }

  function appendRichText(container, text, keyword) {
    var URL_RE = /(https?:\/\/[^\s<>"'，。；！、（）]+)/g;
    var lastIndex = 0;
    var match;
    while ((match = URL_RE.exec(text)) !== null) {
      if (match.index > lastIndex) {
        appendMarked(container, text.slice(lastIndex, match.index), keyword);
      }
      var link = makeEl('a', '', match[0]);
      link.href = match[0];
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      container.appendChild(link);
      lastIndex = match.index + match[0].length;
    }
    if (lastIndex < text.length) {
      appendMarked(container, text.slice(lastIndex), keyword);
    }
  }

  function appendMarked(container, text, keyword) {
    if (!text) return;
    var needle = String(keyword || '').trim();
    if (!needle) {
      container.appendChild(document.createTextNode(text));
      return;
    }
    var haystack = text.toLowerCase();
    var target = needle.toLowerCase();
    var start = 0;
    while (start < text.length) {
      var index = haystack.indexOf(target, start);
      if (index < 0) {
        container.appendChild(document.createTextNode(text.slice(start)));
        break;
      }
      if (index > start) {
        container.appendChild(document.createTextNode(text.slice(start, index)));
      }
      container.appendChild(makeEl('mark', '', text.slice(index, index + needle.length)));
      start = index + needle.length;
    }
  }

  function quoteBox(quote) {
    var box = makeEl('div', 'quote-box');
    var sender = cleanDisplay(quote.sender);
    var text = cleanDisplay(quote.text);
    if (sender) {
      var strong = makeEl('b', '', '发送人：' + sender);
      box.appendChild(strong);
    } else {
      box.appendChild(makeEl('b', '', '引用：'));
    }
    if (text) box.appendChild(document.createTextNode(text));
    return box;
  }

  function mediaOf(message) {
    if (!Array.isArray(message.media)) return [];
    return message.media.filter(function (item) {
      return item && typeof item === 'object';
    });
  }

  function mediaIndex(item, position) {
    if (item && item.index !== undefined && item.index !== null) return item.index;
    return position;
  }

  function mediaUrl(message, item, position, download) {
    if (message.message_id === undefined || message.message_id === null) return '';
    var index = mediaIndex(item, position);
    return '/api/media/' + message.message_id + '?i=' + index + (download ? '&download=1' : '');
  }

  function forwardMediaUrl(name, download) {
    return '/api/media/forward?name=' + encodeURIComponent(String(name == null ? '' : name)) +
      (download ? '&download=1' : '');
  }

  var IMAGE_EXT_RE = /^(png|jpg|jpeg|gif|bmp|webp|heic|tif|tiff)$/;

  function isForwardImage(file) {
    if (!file) return false;
    if (file.kind === 'image') return true;
    return IMAGE_EXT_RE.test(fileExtension(file.name));
  }

  function missingMediaCard(titleText, subText, iconName) {
    var card = makeEl('div', 'media-missing');
    var iconWrap = makeEl('div', 'ph-icon');
    iconWrap.appendChild(iconEl(iconName || 'file'));
    var body = makeEl('div', 'ph-body');
    var title = cleanDisplay(titleText) || '未命名附件';
    body.appendChild(makeEl('div', 'ph-title', title));
    body.title = title;
    body.appendChild(makeEl('div', 'ph-sub', subText || '原图未缓存'));
    card.appendChild(iconWrap);
    card.appendChild(body);
    return card;
  }

  function appendImageMedia(container, message) {
    var media = mediaOf(message);
    if (!media.length) {
      var fallbackName = cleanDisplay(message.text) || '图片';
      container.appendChild(missingMediaCard(fallbackName, '原图未缓存', 'image'));
      return;
    }
    var grid = makeEl('div', 'media-grid');
    media.forEach(function (item, position) {
      var src = item.exists ? mediaUrl(message, item, position, false) : '';
      if (!src) {
        grid.appendChild(missingMediaCard(
          item.name || '图片',
          formatBytes(item.size) + ' · 原图未缓存',
          'image'
        ));
        return;
      }
      var thumb = makeEl('button', 'img-thumb');
      thumb.type = 'button';
      thumb.title = '点击查看大图';
      var displayName = cleanDisplay(item.name) || '图片';
      var downloadHref = mediaUrl(message, item, position, true);
      thumb.setAttribute('data-src', src);
      thumb.setAttribute('data-download', downloadHref);
      thumb.setAttribute('data-name', displayName);
      thumb.setAttribute('data-message-id', String(message.message_id));
      var img = document.createElement('img');
      img.src = src;
      img.alt = displayName;
      img.loading = 'lazy';
      img.decoding = 'async';
      img.addEventListener('load', function () {
        if (img.naturalWidth > 0) {
          thumb.classList.add('is-loaded');
        }
        stickToBottomIfFollowing();
      });
      img.addEventListener('error', function () {
        var placeholder = missingMediaCard(
          item.name || '图片',
          formatBytes(item.size) + ' · 原图未缓存',
          'image'
        );
        if (thumb.parentNode) thumb.parentNode.replaceChild(placeholder, thumb);
      });
      thumb.appendChild(img);
      thumb.addEventListener('click', function () {
        openLightboxFromThumb(thumb);
      });
      grid.appendChild(thumb);
    });
    container.appendChild(grid);
  }

  function fileExtension(name) {
    var text = String(name || '');
    var index = text.lastIndexOf('.');
    if (index < 0 || index === text.length - 1) return '';
    return text.slice(index + 1).toLowerCase();
  }

  function fileTone(ext) {
    if (/^(doc|docx|wps|rtf|txt|md)$/.test(ext)) return 'tone-doc';
    if (/^(xls|xlsx|csv|et)$/.test(ext)) return 'tone-sheet';
    if (/^(ppt|pptx|dps)$/.test(ext)) return 'tone-slide';
    if (/^(pdf)$/.test(ext)) return 'tone-pdf';
    if (/^(zip|rar|7z|tar|gz|bz2)$/.test(ext)) return 'tone-archive';
    if (/^(png|jpg|jpeg|gif|bmp|webp|heic|tif|tiff)$/.test(ext)) return 'tone-image';
    if (/^(mp4|mov|avi|mkv|wmv|flv|mp3|wav|amr|silk|slk)$/.test(ext)) return 'tone-media';
    return 'tone-other';
  }

  function fileCardNode(message, item, position) {
    var name = cleanDisplay(item && item.name) || cleanDisplay(message.text) || '未命名文件';
    var ext = fileExtension(name);
    var card = makeEl('div', 'file-card');

    var badge = makeEl('div', 'file-ext ' + fileTone(ext), ext ? ext.slice(0, 4) : 'FILE');
    card.appendChild(badge);

    var info = makeEl('div', 'file-info');
    var nameEl = makeEl('div', 'file-name', name);
    nameEl.title = name;
    info.appendChild(nameEl);

    var subParts = [];
    if (item && item.size) subParts.push(formatBytes(item.size));
    if (!item || !item.exists) subParts.push('本地未缓存');
    if (!subParts.length) subParts.push('文件');
    info.appendChild(makeEl('div', 'file-sub', subParts.join(' · ')));
    card.appendChild(info);

    var actions = makeEl('div', 'file-actions');
    var exists = !!(item && item.exists);
    var href = exists ? mediaUrl(message, item, position, true) : '';
    if (href) {
      var link = makeEl('a', 'file-download', '下载');
      link.href = href;
      link.download = name;
      link.title = '下载 ' + name;
      actions.appendChild(link);
    } else {
      actions.appendChild(makeEl('span', 'file-download is-disabled', '本地未缓存'));
    }
    card.appendChild(actions);
    return card;
  }

  function appendFileMedia(container, message) {
    var media = mediaOf(message);
    if (!media.length) {
      container.appendChild(fileCardNode(message, null, 0));
      return;
    }
    var stack = makeEl('div', 'file-stack');
    media.forEach(function (item, position) {
      stack.appendChild(fileCardNode(message, item, position));
    });
    container.appendChild(stack);
  }

  function appendVideoMedia(container, message) {
    var media = mediaOf(message);
    if (!media.length) {
      container.appendChild(missingMediaCard(
        cleanDisplay(message.text) || '视频',
        '视频文件本地未缓存',
        'video'
      ));
      return;
    }
    var stack = makeEl('div', 'file-stack');
    media.forEach(function (item, position) {
      if (item.exists) {
        var video = document.createElement('video');
        video.className = 'media-video';
        video.controls = true;
        video.preload = 'metadata';
        video.src = mediaUrl(message, item, position, false);
        video.title = cleanDisplay(item.name) || '视频';
        video.addEventListener('loadedmetadata', stickToBottomIfFollowing);
        video.addEventListener('error', function () {
          var placeholder = missingMediaCard(
            item.name || '视频',
            formatBytes(item.size) + ' · 视频文件无法播放',
            'video'
          );
          if (video.parentNode) video.parentNode.replaceChild(placeholder, video);
        });
        stack.appendChild(video);
      } else {
        stack.appendChild(missingMediaCard(
          item.name || '视频',
          formatBytes(item.size) + ' · 视频文件本地未缓存',
          'video'
        ));
      }
    });
    container.appendChild(stack);
  }

  function appendVoiceMedia(container, message) {
    var media = mediaOf(message);
    if (!media.length) {
      container.appendChild(missingMediaCard('语音', '语音文件本地未缓存', 'play'));
    } else {
      var stack = makeEl('div', 'file-stack');
      media.forEach(function (item, position) {
        stack.appendChild(item.exists
          ? voiceCardNode(message, item, position)
          : missingMediaCard(item.name || '语音', '语音文件本地未缓存', 'play'));
      });
      container.appendChild(stack);
    }
    var transcript = cleanDisplay(message.text);
    if (transcript) {
      var p = makeEl('p', 'voice-text');
      appendRichText(p, transcript, state.highlightKeyword);
      container.appendChild(p);
    }
  }

  function voiceCardNode(message, item, position) {
    var cardInfo = (message && message.card) ? message.card : {};
    var duration = cleanDisplay(cardInfo.duration);
    var labelText = duration ? '语音 ' + duration : '语音';
    var ext = fileExtension(item && item.name);
    var playable = /^(mp3|wav|ogg|m4a|aac|amr)$/.test(ext);

    var card = makeEl('div', 'voice-card');

    if (!playable) {
      card.title = '企业微信语音格式，浏览器暂不支持在线播放';
      card.appendChild(makeEl('span', 'voice-label', labelText));
      card.appendChild(makeEl('span', 'voice-note', '企业微信语音格式，浏览器暂不支持在线播放'));
      var href = mediaUrl(message, item, position, true);
      if (href) {
        var download = makeEl('a', 'file-download', '下载');
        download.href = href;
        download.download = cleanDisplay(item && item.name) || 'voice';
        download.title = '下载语音文件';
        card.appendChild(download);
      }
      return card;
    }

    var button = makeEl('button', 'voice-play');
    button.type = 'button';
    button.title = '播放语音';
    button.setAttribute('aria-label', '播放语音');
    button.appendChild(iconEl('play'));

    var wave = makeEl('span', 'wave');
    for (var i = 0; i < 12; i += 1) {
      var bar = makeEl('i');
      bar.style.height = String(5 + ((i * 7) % 11)) + 'px';
      bar.style.setProperty('--i', String(i));
      wave.appendChild(bar);
    }

    var label = makeEl('span', 'voice-label', labelText);
    card.appendChild(button);
    card.appendChild(wave);
    card.appendChild(label);

    var audio = document.createElement('audio');
    audio.preload = 'none';
    audio.src = mediaUrl(message, item, position, false);
    audio.hidden = true;

    var playing = false;
    function updateUi() {
      button.textContent = '';
      button.appendChild(iconEl(playing ? 'pause' : 'play'));
      wave.classList.toggle('is-playing', playing);
    }

    button.addEventListener('click', function () {
      if (playing) {
        audio.pause();
        return;
      }
      var promise = audio.play();
      if (promise && promise.catch) {
        promise.catch(function () {
          toast('语音播放失败，文件可能未缓存', true);
        });
      }
    });
    audio.addEventListener('play', function () {
      playing = true;
      updateUi();
    });
    audio.addEventListener('pause', function () {
      playing = false;
      updateUi();
    });
    audio.addEventListener('ended', function () {
      playing = false;
      updateUi();
    });

    card.appendChild(audio);
    return card;
  }

  function appendGenericAttachments(container, message) {
    var media = mediaOf(message);
    if (!media.length) return;
    var images = media.filter(function (item) {
      return item.kind === 'image';
    });
    if (images.length) appendImageMedia(container, message);
    var others = media.filter(function (item) {
      return item.kind !== 'image';
    });
    if (!others.length) return;
    var stack = makeEl('div', 'file-stack');
    others.forEach(function (item, index) {
      var position = media.indexOf(item);
      if (item.kind === 'voice' && item.exists) {
        stack.appendChild(voiceCardNode(message, item, position));
      } else if (item.kind === 'video' && item.exists) {
        var video = document.createElement('video');
        video.className = 'media-video';
        video.controls = true;
        video.preload = 'metadata';
        video.src = mediaUrl(message, item, position, false);
        video.addEventListener('loadedmetadata', stickToBottomIfFollowing);
        stack.appendChild(video);
      } else {
        stack.appendChild(fileCardNode(message, item, position));
      }
    });
    container.appendChild(stack);
  }

  function appendUnknown(container, message) {
    var type = message.content_type;
    var note = makeEl('div', 'unknown-note',
      type === undefined || type === null || type === ''
        ? '暂不支持的消息类型'
        : ('暂不支持的消息类型（' + type + '）'));
    container.appendChild(note);
    var summary = cleanDisplay(message.summary);
    if (summary) {
      container.appendChild(makeEl('div', 'unknown-sub', summary));
    }
    if (mediaOf(message).length) {
      appendGenericAttachments(container, message);
    }
  }

  /* ======================================================================
   * 链接 / 应用 / 会议 / 通话 / 转发 / 表情卡片
   * ==================================================================== */

  function domainOf(url) {
    var text = String(url || '').trim();
    if (!text) return '';
    try {
      var parsed = new URL(text);
      return parsed.hostname.replace(/^www\./, '');
    } catch (err) {
      return '';
    }
  }

  function safeUrl(url) {
    var text = String(url || '').trim();
    if (!text) return '';
    return /^https?:\/\//i.test(text) ? text : '';
  }

  function cardHead(iconName, card) {
    var head = makeEl('div', 'card-head');
    var icon = makeEl('div', 'card-icon');
    icon.appendChild(iconEl(iconName));
    head.appendChild(icon);
    head.appendChild(card);
    return head;
  }

  function linkCardNode(message) {
    var card = message.card || {};
    var url = safeUrl(card.url);
    var title = cleanDisplay(card.title) || cleanDisplay(message.text) || '链接';
    var description = cleanDisplay(card.description);
    var source = cleanDisplay(card.source) || domainOf(url);

    var node = makeEl(url ? 'a' : 'div', 'link-card');
    if (url) {
      node.href = url;
      node.target = '_blank';
      node.rel = 'noopener noreferrer';
    }

    var body = makeEl('div', 'card-body');
    var titleEl = makeEl('div', 'card-title', title);
    titleEl.title = title;
    body.appendChild(titleEl);
    if (description) {
      var desc = makeEl('div', 'card-desc', description);
      desc.title = description;
      body.appendChild(desc);
    }
    if (source) {
      body.appendChild(makeEl('div', 'card-domain', source));
    }
    node.appendChild(cardHead('link', body));
    return node;
  }

  function appCardNode(message) {
    var card = message.card || {};
    var url = safeUrl(card.url);
    var title = cleanDisplay(card.title) || cleanDisplay(message.text) || '应用消息';
    var description = cleanDisplay(card.description);
    var source = cleanDisplay(card.source);
    var items = Array.isArray(card.items) ? card.items : [];

    var node = makeEl('div', 'app-card');
    var body = makeEl('div', 'card-body');
    var titleEl = makeEl('div', 'card-title', title);
    titleEl.title = title;
    body.appendChild(titleEl);
    if (description) {
      var desc = makeEl('div', 'card-desc', description);
      desc.title = description;
      body.appendChild(desc);
    }
    if (source) body.appendChild(makeEl('div', 'card-source', source));
    node.appendChild(cardHead('app', body));

    if (items.length) {
      var list = makeEl('div', 'news-list');
      items.forEach(function (item) {
        if (!item) return;
        var itemUrl = safeUrl(item.url);
        var row = makeEl(itemUrl ? 'a' : 'div', 'news-item');
        if (itemUrl) {
          row.href = itemUrl;
          row.target = '_blank';
          row.rel = 'noopener noreferrer';
        }
        var itemTitle = cleanDisplay(item.title);
        if (itemTitle) {
          var t = makeEl('div', 'news-title', itemTitle);
          t.title = itemTitle;
          row.appendChild(t);
        }
        var itemDesc = cleanDisplay(item.description);
        if (itemDesc) {
          var d = makeEl('div', 'news-desc', itemDesc);
          d.title = itemDesc;
          row.appendChild(d);
        }
        var itemSource = cleanDisplay(item.source) || domainOf(itemUrl);
        if (itemSource) row.appendChild(makeEl('div', 'news-source', itemSource));
        list.appendChild(row);
      });
      node.appendChild(list);
    } else if (url) {
      var linkRow = makeEl('div', 'card-link-row');
      var link = makeEl('a', '', '查看详情');
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      linkRow.appendChild(link);
      node.appendChild(linkRow);
    }

    return node;
  }

  function meetingCardNode(message) {
    var card = message.card || {};
    var node = makeEl('div', 'info-card');
    var title = cleanDisplay(card.title) || cleanDisplay(message.text) || '会议消息';
    var description = cleanDisplay(card.description);
    var timeText = cleanDisplay(card.time_text);
    var location = cleanDisplay(card.location);
    var url = safeUrl(card.url);

    var body = makeEl('div', 'card-body');
    var titleEl = makeEl('div', 'card-title', title);
    titleEl.title = title;
    body.appendChild(titleEl);
    if (description) {
      var desc = makeEl('div', 'card-desc', description);
      desc.title = description;
      body.appendChild(desc);
    }
    node.appendChild(cardHead('calendar', body));

    if (timeText && (!description || description.indexOf(timeText) === -1)) {
      var timeRow = makeEl('div', 'card-meta-row');
      timeRow.appendChild(makeEl('span', 'card-meta-label', '会议时间'));
      timeRow.appendChild(makeEl('span', '', timeText));
      node.appendChild(timeRow);
    }
    if (location && (!description || description.indexOf(location) === -1)) {
      var locRow = makeEl('div', 'card-meta-row');
      locRow.appendChild(makeEl('span', 'card-meta-label', '会议地点'));
      locRow.appendChild(makeEl('span', '', location));
      node.appendChild(locRow);
    }
    if (url) {
      var linkRow = makeEl('div', 'card-link-row');
      var link = makeEl('a', '', '加入会议');
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      linkRow.appendChild(link);
      node.appendChild(linkRow);
    }
    return node;
  }

  function callCardNode(message) {
    var card = message.card || {};
    var duration = cleanDisplay(card.duration);
    var text = cleanDisplay(card.description) || cleanDisplay(message.text);
    var node = makeEl('div', 'info-card');

    var body = makeEl('div', 'card-body');
    body.appendChild(makeEl('div', 'card-title', '通话记录'));
    if (duration) {
      body.appendChild(makeEl('div', 'card-domain', '通话时长 ' + duration));
    }
    var redundant = text.replace(/\s+/g, '') === duration.replace(/\s+/g, '') ||
      (!!duration && text === '通话时长' + duration);
    if (text && !redundant) {
      var desc = makeEl('div', 'card-desc', text);
      desc.title = text;
      body.appendChild(desc);
    }
    node.appendChild(cardHead('phone', body));
    return node;
  }

  function forwardFileCardNode(file) {
    var data = file || {};
    var rawName = String(data.name == null ? '' : data.name).trim();
    var name = cleanDisplay(rawName) || '未命名文件';
    var ext = fileExtension(name);
    var exists = !!data.exists;
    var card = makeEl('div', 'file-card');

    var badge = makeEl('div', 'file-ext ' + fileTone(ext), ext ? ext.slice(0, 4) : 'FILE');
    card.appendChild(badge);

    var info = makeEl('div', 'file-info');
    var nameEl = makeEl('div', 'file-name', name);
    nameEl.title = name;
    info.appendChild(nameEl);

    var subParts = [];
    if (data.size) subParts.push(formatBytes(data.size));
    if (!exists) subParts.push('本地未缓存');
    if (!subParts.length) subParts.push('文件');
    info.appendChild(makeEl('div', 'file-sub', subParts.join(' · ')));
    card.appendChild(info);

    var actions = makeEl('div', 'file-actions');
    if (exists) {
      var link = makeEl('a', 'file-download', '下载');
      link.href = forwardMediaUrl(rawName, true);
      link.download = rawName || name;
      link.title = '下载 ' + name;
      actions.appendChild(link);
    } else {
      actions.appendChild(makeEl('span', 'file-download is-disabled', '本地未缓存'));
    }
    card.appendChild(actions);
    return card;
  }

  function forwardImageNode(file, message) {
    var data = file || {};
    var rawName = String(data.name == null ? '' : data.name).trim();
    var name = cleanDisplay(rawName) || '图片';
    if (!data.exists) {
      return missingMediaCard(name, formatBytes(data.size) + ' · 原图未缓存', 'image');
    }
    var src = forwardMediaUrl(rawName, false);
    var downloadHref = forwardMediaUrl(rawName, true);
    var thumb = makeEl('button', 'img-thumb');
    thumb.type = 'button';
    thumb.title = '点击查看大图';
    thumb.setAttribute('data-src', src);
    thumb.setAttribute('data-download', downloadHref);
    thumb.setAttribute('data-name', name);
    thumb.setAttribute('data-message-id', String(message.message_id));
    var img = document.createElement('img');
    img.src = src;
    img.alt = name;
    img.loading = 'lazy';
    img.decoding = 'async';
    img.addEventListener('load', function () {
      if (img.naturalWidth > 0) thumb.classList.add('is-loaded');
      stickToBottomIfFollowing();
    });
    img.addEventListener('error', function () {
      var placeholder = missingMediaCard(name, formatBytes(data.size) + ' · 原图未缓存', 'image');
      if (thumb.parentNode) thumb.parentNode.replaceChild(placeholder, thumb);
    });
    thumb.appendChild(img);
    thumb.addEventListener('click', function () {
      openLightboxFromThumb(thumb);
    });
    return thumb;
  }

  function forwardCardNode(message) {
    var items = Array.isArray(message.items) ? message.items : [];
    var node = makeEl('div', 'forward-card');

    var head = makeEl('div', 'forward-head');
    head.appendChild(iconEl('forward'));
    head.appendChild(makeEl('span', '', '聊天记录'));
    head.appendChild(makeEl('span', 'forward-count', items.length ? items.length + ' 条' : ''));
    node.appendChild(head);

    if (items.length) {
      var list = makeEl('ul', 'forward-items');
      items.forEach(function (item) {
        if (!item) return;
        var row = makeEl('li', 'forward-item');
        var sender = cleanDisplay(item.sender);
        if (sender) row.appendChild(makeEl('div', 'forward-sender', sender));
        var text = cleanDisplay(item.text);
        if (text) row.appendChild(makeEl('div', 'forward-text', text));
        var files = Array.isArray(item.files) ? item.files : [];
        var images = [];
        var others = [];
        files.forEach(function (file) {
          if (!file) return;
          if (isForwardImage(file)) images.push(file);
          else others.push(file);
        });
        if (images.length) {
          var grid = makeEl('div', 'media-grid forward-media-grid');
          images.forEach(function (file) {
            grid.appendChild(forwardImageNode(file, message));
          });
          row.appendChild(grid);
        }
        if (others.length) {
          var stack = makeEl('div', 'forward-files');
          others.forEach(function (file) {
            stack.appendChild(forwardFileCardNode(file));
          });
          row.appendChild(stack);
        }
        if (!sender && !text && !files.length) {
          row.appendChild(makeEl('div', 'forward-text', '此条记录暂无内容'));
        }
        list.appendChild(row);
      });
      node.appendChild(list);
    } else {
      var fallback = cleanDisplay(message.text);
      if (fallback) node.appendChild(makeEl('div', 'card-desc', fallback));
    }
    return node;
  }

  function stickerCardNode(message) {
    var card = message.card || {};
    var text = cleanDisplay(message.text) || cleanDisplay(message.summary) || '自定义表情';
    var node = makeEl('div', 'sticker-card');
    node.appendChild(iconEl('smile'));
    node.appendChild(makeEl('span', '', '[表情] ' + (text || '自定义表情')));
    return node;
  }

  /* ======================================================================
   * 灯箱
   * ==================================================================== */

  var lbState = {
    items: [],
    index: 0,
    scale: 1,
    panX: 0,
    panY: 0,
    dragging: false,
    moved: false,
    startX: 0,
    startY: 0,
    startPanX: 0,
    startPanY: 0
  };

  var LB_MIN_SCALE = 0.25;
  var LB_MAX_SCALE = 8;
  var LB_ZOOM_STEP = 1.25;

  function collectGalleryItems() {
    var items = [];
    if (!ui.messageList) return items;
    var nodes = ui.messageList.querySelectorAll('.img-thumb[data-src]');
    for (var i = 0; i < nodes.length; i += 1) {
      var el = nodes[i];
      var src = el.getAttribute('data-src');
      if (!src) continue;
      items.push({
        src: src,
        download: el.getAttribute('data-download') || src,
        name: el.getAttribute('data-name') || '',
        messageId: el.getAttribute('data-message-id') || '',
        el: el
      });
    }
    return items;
  }

  function openLightboxFromThumb(thumb) {
    var items = collectGalleryItems();
    var index = -1;
    for (var i = 0; i < items.length; i += 1) {
      if (items[i].el === thumb) {
        index = i;
        break;
      }
    }
    if (index < 0) {
      var src = thumb && thumb.getAttribute ? thumb.getAttribute('data-src') : '';
      if (!src) return;
      items = [{
        src: src,
        download: thumb.getAttribute('data-download') || src,
        name: thumb.getAttribute('data-name') || '',
        messageId: thumb.getAttribute('data-message-id') || '',
        el: thumb
      }];
      index = 0;
    }
    lbState.items = items;
    showLightboxAt(index);
  }

  function showLightboxAt(index) {
    if (!lbState.items.length) return;
    var next = Number(index);
    if (!isFinite(next)) next = 0;
    if (next < 0) next = 0;
    if (next > lbState.items.length - 1) next = lbState.items.length - 1;
    lbState.index = next;
    lbState.scale = 1;
    lbState.panX = 0;
    lbState.panY = 0;
    lbState.dragging = false;
    lbState.moved = false;

    var item = lbState.items[next];
    ui.lightboxImg.src = item.src;
    ui.lightboxImg.alt = item.name || '图片预览';
    ui.lightboxImg.style.transform = '';
    ui.lightboxDownload.href = item.download || item.src;
    if (item.name) {
      ui.lightboxDownload.setAttribute('download', item.name);
      ui.lightboxDownload.title = '下载 ' + item.name;
    } else {
      ui.lightboxDownload.removeAttribute('download');
      ui.lightboxDownload.title = '下载原图';
    }
    ui.lightbox.classList.remove('is-zoomed', 'is-dragging');
    ui.lightbox.hidden = false;
    updateLightboxNav();
    updateLightboxZoom();
  }

  function updateLightboxNav() {
    var total = lbState.items.length;
    var index = lbState.index;
    if (ui.lightboxPrev) ui.lightboxPrev.disabled = index <= 0;
    if (ui.lightboxNext) ui.lightboxNext.disabled = index >= total - 1;
    if (ui.lightboxCounter) {
      ui.lightboxCounter.textContent = (total ? index + 1 : 0) + ' / ' + total;
    }
  }

  function updateLightboxZoom() {
    if (ui.lightboxPercent) {
      ui.lightboxPercent.textContent = Math.round(lbState.scale * 100) + '%';
    }
    if (ui.lightbox) ui.lightbox.classList.toggle('is-zoomed', lbState.scale > 1);
  }

  function applyLightboxTransform() {
    if (!ui.lightboxImg) return;
    ui.lightboxImg.style.transform = 'translate(' + Math.round(lbState.panX) + 'px, ' +
      Math.round(lbState.panY) + 'px) scale(' + lbState.scale + ')';
  }

  function clampLightboxPan() {
    if (!ui.lightboxStage || !ui.lightboxImg) return;
    var displayWidth = ui.lightboxImg.clientWidth * lbState.scale;
    var displayHeight = ui.lightboxImg.clientHeight * lbState.scale;
    var maxX = Math.max(0, (displayWidth - ui.lightboxStage.clientWidth) / 2);
    var maxY = Math.max(0, (displayHeight - ui.lightboxStage.clientHeight) / 2);
    if (lbState.panX > maxX) lbState.panX = maxX;
    if (lbState.panX < -maxX) lbState.panX = -maxX;
    if (lbState.panY > maxY) lbState.panY = maxY;
    if (lbState.panY < -maxY) lbState.panY = -maxY;
  }

  function zoomLightbox(factor) {
    if (!ui.lightbox || ui.lightbox.hidden || !lbState.items.length) return;
    var scale = lbState.scale * factor;
    scale = Math.max(LB_MIN_SCALE, Math.min(LB_MAX_SCALE, scale));
    if (Math.abs(scale - lbState.scale) < 0.0001) return;
    lbState.scale = scale;
    if (scale <= 1) {
      lbState.panX = 0;
      lbState.panY = 0;
    } else {
      clampLightboxPan();
    }
    applyLightboxTransform();
    updateLightboxZoom();
  }

  function fitLightbox() {
    lbState.scale = 1;
    lbState.panX = 0;
    lbState.panY = 0;
    applyLightboxTransform();
    updateLightboxZoom();
  }

  function actualLightboxSize() {
    if (!ui.lightbox || ui.lightbox.hidden || !lbState.items.length) return;
    fitLightbox();
    var img = ui.lightboxImg;
    var naturalWidth = img.naturalWidth;
    var fitWidth = img.clientWidth;
    if (!naturalWidth || !fitWidth) {
      toast('图片尚未加载完成', true);
      return;
    }
    lbState.scale = naturalWidth / fitWidth;
    lbState.panX = 0;
    lbState.panY = 0;
    applyLightboxTransform();
    updateLightboxZoom();
  }

  function onLightboxPointerDown(event) {
    lbState.moved = false;
    if (!ui.lightbox || ui.lightbox.hidden || lbState.scale <= 1) return;
    if (event.button !== undefined && event.button !== 0) return;
    lbState.dragging = true;
    lbState.startX = event.clientX;
    lbState.startY = event.clientY;
    lbState.startPanX = lbState.panX;
    lbState.startPanY = lbState.panY;
    ui.lightbox.classList.add('is-dragging');
  }

  function onLightboxPointerMove(event) {
    if (!lbState.dragging) return;
    var dx = event.clientX - lbState.startX;
    var dy = event.clientY - lbState.startY;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) lbState.moved = true;
    lbState.panX = lbState.startPanX + dx;
    lbState.panY = lbState.startPanY + dy;
    clampLightboxPan();
    applyLightboxTransform();
    event.preventDefault();
  }

  function onLightboxPointerUp() {
    if (!lbState.dragging) return;
    lbState.dragging = false;
    ui.lightbox.classList.remove('is-dragging');
  }

  function locateLightboxImage() {
    var item = lbState.items[lbState.index];
    var messageId = item ? item.messageId : '';
    closeLightbox();
    if (messageId) scrollToMessage(messageId, true);
  }

  function closeLightbox() {
    if (!ui.lightbox) return;
    ui.lightbox.hidden = true;
    ui.lightbox.classList.remove('is-zoomed', 'is-dragging');
    ui.lightboxImg.removeAttribute('src');
    ui.lightboxImg.style.transform = '';
    ui.lightboxDownload.href = '#';
    ui.lightboxDownload.removeAttribute('download');
    lbState.items = [];
    lbState.index = 0;
    lbState.scale = 1;
    lbState.panX = 0;
    lbState.panY = 0;
    lbState.dragging = false;
    lbState.moved = false;
    updateLightboxZoom();
  }

  /* ======================================================================
   * 会话详情抽屉
   * ==================================================================== */

  function openDrawer() {
    if (!ui.detailDrawer || ui.detailDrawer.hidden === false) return;
    ui.detailDrawer.hidden = false;
    window.requestAnimationFrame(function () {
      ui.detailDrawer.classList.add('is-open');
    });
  }

  function closeDrawer() {
    if (!ui.detailDrawer || ui.detailDrawer.hidden) return;
    ui.detailDrawer.classList.remove('is-open');
    window.setTimeout(function () {
      if (!ui.detailDrawer.classList.contains('is-open')) {
        ui.detailDrawer.hidden = true;
      }
    }, 230);
  }

  async function openSessionDetail() {
    var session = state.currentSession;
    if (!session) return;
    var cid = session.id;
    openDrawer();
    ui.drawerBody.textContent = '';
    renderDrawerSkeleton();

    try {
      var data = await api('/api/sessions/' + encodeURIComponent(cid) + '/detail');
      if (!state.currentSession || state.currentSession.id !== cid) return;
      renderDetail(data);
    } catch (err) {
      if (!state.currentSession || state.currentSession.id !== cid) return;
      ui.drawerBody.textContent = '';
      var box = makeEl('div', 'error-block');
      box.appendChild(makeEl('p', '', '会话详情加载失败：' + err.message));
      var retry = makeEl('button', 'retry-btn', '重试');
      retry.type = 'button';
      retry.addEventListener('click', openSessionDetail);
      box.appendChild(retry);
      ui.drawerBody.appendChild(box);
    }
  }

  function renderDrawerSkeleton() {
    for (var i = 0; i < 4; i += 1) {
      var row = makeEl('div', 'detail-row pulse');
      row.appendChild(makeEl('div', 'skeleton-line', ''));
      row.firstChild.style.width = (i === 0 ? 70 : 45) + '%';
      ui.drawerBody.appendChild(row);
    }
  }

  function renderDetail(data) {
    var detail = data || {};
    var name = displayName(detail.name, '未命名会话');
    ui.drawerBody.textContent = '';

    var hero = makeEl('div', 'detail-hero');
    hero.appendChild(avatarNode(name, detail.avatar_url || sessionAvatarUrl(state.currentSession), ''));
    var heroBody = makeEl('div', '');
    heroBody.style.minWidth = '0';
    heroBody.style.flex = '1';
    heroBody.appendChild(makeEl('h3', '', name));
    var typeText = typeLabel(detail.type, detail.type_label);
    var count = Number(detail.member_count) || 0;
    var metaText = typeText + (count > 1 ? ' · ' + fmtNum(count) + ' 人' : '');
    if (detail.is_external && detail.type !== 'external') metaText += ' · 外部会话';
    heroBody.appendChild(makeEl('p', '', metaText));
    hero.appendChild(heroBody);
    ui.drawerBody.appendChild(hero);

    var infoSection = makeEl('div', 'detail-section');
    infoSection.appendChild(makeEl('h4', '', '基本信息'));
    appendDetailRow(infoSection, '会话类型', typeText);
    appendDetailRow(infoSection, '成员数量', count > 0 ? fmtNum(count) + ' 人' : '未知');
    appendDetailRow(infoSection, '创建时间', formatDateTime(detail.create_time));
    appendDetailRow(infoSection, '最后消息', formatDateTime(detail.last_message_time));
    ui.drawerBody.appendChild(infoSection);

    var idSection = makeEl('div', 'detail-section');
    idSection.appendChild(makeEl('h4', '', '原始会话 ID'));
    var idBox = makeEl('div', 'detail-id');
    var code = makeEl('code', '', detail.id || state.currentSession.id);
    idBox.appendChild(code);
    var copyBtn = makeEl('button', 'copy-btn', '复制 ID');
    copyBtn.type = 'button';
    copyBtn.addEventListener('click', function () {
      copyText(detail.id || state.currentSession.id);
    });
    idBox.appendChild(copyBtn);
    idSection.appendChild(idBox);
    ui.drawerBody.appendChild(idSection);

    var members = Array.isArray(detail.members) ? detail.members : [];
    var names = Array.isArray(detail.member_names) ? detail.member_names : [];
    var memberSection = makeEl('div', 'detail-section');
    memberSection.appendChild(makeEl('h4', '', '成员列表'));

    if (members.length || names.length) {
      var list = makeEl('div', 'member-list');
      var shown = 0;
      if (members.length) {
        members.slice(0, 20).forEach(function (member) {
          if (!member) return;
          var memberName = displayName(member.name || member.nick_name, '成员');
          var item = makeEl('div', 'member-item');
          item.appendChild(avatarNode(memberName, member.user_id ? '/api/avatar/user/' + member.user_id : ''));
          item.appendChild(makeEl('span', 'member-name', memberName));
          list.appendChild(item);
          shown += 1;
        });
      } else {
        names.slice(0, 20).forEach(function (memberName) {
          var clean = cleanDisplay(memberName);
          if (!clean) return;
          var item = makeEl('div', 'member-item');
          item.appendChild(avatarNode(clean, ''));
          item.appendChild(makeEl('span', 'member-name', clean));
          list.appendChild(item);
          shown += 1;
        });
      }
      memberSection.appendChild(list);

      var total = count || members.length || names.length;
      if (total > shown) {
        memberSection.appendChild(makeEl('div', 'member-more', '等 ' + fmtNum(total) + ' 人'));
      }
    } else {
      memberSection.appendChild(makeEl('div', 'member-more', '暂无成员信息'));
    }
    ui.drawerBody.appendChild(memberSection);

    if (detail.name && state.currentSession) {
      state.currentSession.name = detail.name;
    }
    if (detail.member_count && state.currentSession) {
      state.currentSession.member_count = detail.member_count;
    }
    if (detail.type) state.currentSession.type = detail.type;
    if (detail.type_label) state.currentSession.type_label = detail.type_label;
    refreshChatHeader();
  }

  function appendDetailRow(parent, label, value) {
    var row = makeEl('div', 'detail-row');
    row.appendChild(makeEl('span', 'detail-label', label));
    row.appendChild(makeEl('span', 'detail-value', value));
    parent.appendChild(row);
  }

  async function copyText(text) {
    var value = String(text || '');
    if (!value) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(value);
        toast('已复制会话 ID');
        return;
      } catch (err) {
        /* 回退到选区复制 */
      }
    }
    var area = document.createElement('textarea');
    area.value = value;
    area.style.position = 'fixed';
    area.style.top = '-1000px';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try {
      ok = document.execCommand('copy');
    } catch (err) {
      ok = false;
    }
    area.remove();
    toast(ok ? '已复制会话 ID' : '复制失败，请手动选择文本', !ok);
  }

  /* ======================================================================
   * 筛选条件
   * ==================================================================== */

  function parseDateInput(value) {
    var text = String(value || '').trim();
    if (!text) return null;
    var parts = text.split('-');
    if (parts.length !== 3) return null;
    var year = Number(parts[0]);
    var month = Number(parts[1]);
    var day = Number(parts[2]);
    if (!year || !month || !day) return null;
    var date = new Date(year, month - 1, day);
    if (isNaN(date.getTime())) return null;
    return date;
  }

  function computeDateRange() {
    var range = { start: null, end: null };
    var now = new Date();
    if (state.datePreset === 'today' || state.datePreset === '7' || state.datePreset === '30') {
      var days = state.datePreset === '7' ? 7 : (state.datePreset === '30' ? 30 : 1);
      var start = startOfDay(now);
      if (days > 1) start.setDate(start.getDate() - (days - 1));
      var end = startOfDay(now);
      end.setDate(end.getDate() + 1);
      range.start = Math.round(start.getTime() / 1000);
      range.end = Math.round(end.getTime() / 1000);
    } else if (state.datePreset === 'custom') {
      var startDate = parseDateInput(state.customStart);
      var endDate = parseDateInput(state.customEnd);
      if (startDate) range.start = Math.round(startDate.getTime() / 1000);
      if (endDate) {
        var exclusiveEnd = new Date(endDate.getFullYear(), endDate.getMonth(), endDate.getDate() + 1);
        range.end = Math.round(exclusiveEnd.getTime() / 1000);
      }
    }
    return range;
  }

  function hasActiveMessageFilters() {
    return !!(state.msgTypes.length || state.datePreset !== 'all' || state.highlightKeyword);
  }

  function datePresetLabel() {
    var option = ui.dateSelect && ui.dateSelect.options[ui.dateSelect.selectedIndex];
    return option ? option.textContent : '全部时间';
  }

  function typeChipLabel(type) {
    var buttons = ui.typeChips ? ui.typeChips.querySelectorAll('.chip') : [];
    for (var i = 0; i < buttons.length; i += 1) {
      if (buttons[i].dataset.type === type) return buttons[i].textContent;
    }
    return type;
  }

  function resetFilterControls() {
    state.msgTypes = [];
    state.datePreset = 'all';
    state.customStart = '';
    state.customEnd = '';
    if (ui.typeChips) {
      var chips = ui.typeChips.querySelectorAll('.chip');
      for (var i = 0; i < chips.length; i += 1) {
        chips[i].classList.toggle('is-active', chips[i].dataset.type === '');
      }
    }
    if (ui.dateSelect) ui.dateSelect.value = 'all';
    if (ui.customDate) ui.customDate.hidden = true;
    if (ui.startDate) ui.startDate.value = '';
    if (ui.endDate) ui.endDate.value = '';
    updateActiveFilters();
  }

  function updateActiveFilters() {
    var active = hasActiveMessageFilters();
    ui.activeFilters.hidden = !active;
    ui.activeFilters.textContent = '';
    if (!active) return;

    if (state.msgTypes.length) {
      var typeNote = makeEl('span', 'filter-note', '类型：' + state.msgTypes.map(typeChipLabel).join('、'));
      ui.activeFilters.appendChild(typeNote);
    }
    if (state.datePreset !== 'all') {
      ui.activeFilters.appendChild(makeEl('span', 'filter-note', '时间：' + datePresetLabel()));
    }
    if (state.highlightKeyword) {
      ui.activeFilters.appendChild(makeEl('span', 'filter-note', '关键词：' + state.highlightKeyword));
    }

    var clear = makeEl('button', 'clear-inline', '清除全部筛选');
    clear.type = 'button';
    clear.addEventListener('click', function () {
      state.highlightKeyword = '';
      resetFilterControls();
      if (state.currentSession) loadMessages({ reset: true, anchorId: null });
    });
    ui.activeFilters.appendChild(clear);
  }

  function applyFilters() {
    updateActiveFilters();
    if (!state.currentSession) return;
    loadMessages({ reset: true, anchorId: null });
  }

  function setMessageType(type) {
    state.msgTypes = type ? [type] : [];
    if (ui.typeChips) {
      var chips = ui.typeChips.querySelectorAll('.chip');
      for (var i = 0; i < chips.length; i += 1) {
        var chipType = chips[i].dataset.type;
        chips[i].classList.toggle('is-active', type ? chipType === type : chipType === '');
      }
    }
    applyFilters();
  }

  /* ======================================================================
   * 会话内搜索
   * ==================================================================== */

  function hideChatSearchPanel() {
    if (ui.chatSearchPanel) ui.chatSearchPanel.hidden = true;
  }

  function toggleChatSearch(open) {
    var shouldOpen = open === undefined ? !state.chatSearchOpen : !!open;
    state.chatSearchOpen = shouldOpen;
    if (!ui.chatSearchBar) return;
    ui.chatSearchBar.hidden = !shouldOpen;
    if (shouldOpen) {
      window.setTimeout(function () {
        ui.chatSearchInput.focus();
      }, 30);
    } else {
      ui.chatSearchInput.value = '';
      state.chatSearchKeyword = '';
      state.chatSearchResults = [];
      hideChatSearchPanel();
      if (state.highlightKeyword) {
        state.highlightKeyword = '';
        updateActiveFilters();
        renderMessages();
      }
    }
  }

  async function runChatSearch() {
    var keyword = state.chatSearchKeyword.trim();
    if (!state.currentSession) return;
    if (!keyword) {
      state.chatSearchResults = [];
      hideChatSearchPanel();
      return;
    }

    var token = nextToken('chatSearch');
    state.chatSearchLoading = true;
    state.chatSearchError = '';
    ui.chatSearchPanel.hidden = false;
    renderChatSearchPanel();

    try {
      var data = await api('/api/search', {
        params: {
          q: keyword,
          session_id: state.currentSession.id,
          limit: SEARCH_PAGE_SIZE,
          offset: 0
        }
      });
      if (isStale('chatSearch', token)) return;
      state.chatSearchResults = data.results || [];
      state.chatSearchTotal = Number(data.total) || 0;
      renderChatSearchPanel();
    } catch (err) {
      if (isStale('chatSearch', token)) return;
      state.chatSearchError = err.message;
      state.chatSearchResults = [];
      renderChatSearchPanel();
    } finally {
      if (!isStale('chatSearch', token)) {
        state.chatSearchLoading = false;
        renderChatSearchPanel();
      }
    }
  }

  function renderChatSearchPanel() {
    var panel = ui.chatSearchPanel;
    panel.textContent = '';
    if (!state.chatSearchKeyword.trim()) {
      panel.hidden = true;
      return;
    }
    panel.hidden = false;

    var head = makeEl('div', 'chat-search-head');
    var info = makeEl('span', '');
    if (state.chatSearchLoading) {
      info.textContent = '正在搜索当前会话…';
    } else if (state.chatSearchError) {
      info.textContent = '搜索失败：' + state.chatSearchError;
    } else {
      info.textContent = '当前会话中找到 ' + fmtNum(state.chatSearchTotal) + ' 条结果';
    }
    head.appendChild(info);
    var close = makeEl('button', 'text-btn', '关闭结果');
    close.type = 'button';
    close.addEventListener('click', function () {
      hideChatSearchPanel();
    });
    head.appendChild(close);
    panel.appendChild(head);

    if (state.chatSearchLoading) return;

    if (state.chatSearchError) {
      var errorBox = makeEl('div', 'chat-search-empty');
      errorBox.appendChild(makeEl('div', '', state.chatSearchError));
      var retry = makeEl('button', 'retry-btn', '重试');
      retry.type = 'button';
      retry.style.marginTop = '6px';
      retry.addEventListener('click', runChatSearch);
      errorBox.appendChild(retry);
      panel.appendChild(errorBox);
      return;
    }

    if (!state.chatSearchResults.length) {
      panel.appendChild(makeEl('div', 'chat-search-empty', '当前会话中没有匹配的消息'));
      return;
    }

    state.chatSearchResults.forEach(function (result, index) {
      panel.appendChild(chatSearchResultNode(result, index));
    });
  }

  function chatSearchResultNode(result, index) {
    var node = makeEl('button', 'search-result');
    node.type = 'button';
    node.dataset.resultIndex = String(index);

    var top = makeEl('div', 'sr-top');
    var sender = result.is_send ? '我' : displayName(result.sender_name, '未知发送人');
    top.appendChild(makeEl('span', 'sr-name', sender));
    top.appendChild(makeEl('span', 'sr-time', formatDateTime(result.send_time)));
    node.appendChild(top);

    var snippet = cleanDisplay(result.snippet) ||
      cleanDisplay(result.summary) ||
      cleanDisplay(result.text) ||
      kindPreview(result.kind);
    var snippetEl = makeEl('div', 'sr-snippet');
    appendMarked(snippetEl, snippet, state.chatSearchKeyword);
    node.appendChild(snippetEl);
    return node;
  }

  function navigateChatSearchResult(result) {
    if (!result || !state.currentSession) return;
    var keyword = state.chatSearchKeyword;
    state.highlightKeyword = keyword;
    state.chatSearchResults = [];
    hideChatSearchPanel();

    /* 结果来自全类型搜索，锚点定位前清空类型/日期筛选，避免目标被筛掉 */
    state.msgTypes = [];
    state.datePreset = 'all';
    state.customStart = '';
    state.customEnd = '';
    if (ui.typeChips) {
      var chips = ui.typeChips.querySelectorAll('.chip');
      for (var i = 0; i < chips.length; i += 1) {
        chips[i].classList.toggle('is-active', chips[i].dataset.type === '');
      }
    }
    if (ui.dateSelect) ui.dateSelect.value = 'all';
    if (ui.customDate) ui.customDate.hidden = true;
    updateActiveFilters();

    loadMessages({ reset: true, anchorId: result.message_id });
    ui.latestBtn.hidden = false;
  }

  /* ======================================================================
   * 全局消息搜索
   * ==================================================================== */

  function closeGlobalSearchPanel() {
    state.globalPanelOpen = false;
    if (ui.searchPanel) ui.searchPanel.hidden = true;
  }

  function openGlobalSearchPanel() {
    state.globalPanelOpen = true;
    if (ui.searchPanel) ui.searchPanel.hidden = false;
  }

  async function runGlobalSearch(reset) {
    var keyword = state.keyword.trim();
    openGlobalSearchPanel();

    if (!keyword) {
      state.searchResults = [];
      state.searchTotal = 0;
      state.searchHasMore = false;
      state.searchOffset = 0;
      state.searchError = '';
      renderGlobalSearchPanel();
      return;
    }

    var token = nextToken('search');
    var isReset = reset !== false;
    state.searchLoading = true;
    state.searchError = '';
    if (isReset) {
      state.searchResults = [];
      state.searchOffset = 0;
      state.searchHasMore = false;
    }
    renderGlobalSearchPanel();

    try {
      var data = await api('/api/search', {
        params: {
          q: keyword,
          limit: SEARCH_PAGE_SIZE,
          offset: isReset ? 0 : state.searchOffset
        }
      });
      if (isStale('search', token)) return;
      var results = data.results || [];
      state.searchResults = isReset ? results : state.searchResults.concat(results);
      state.searchTotal = Number(data.total) || 0;
      state.searchHasMore = !!data.has_more;
      state.searchOffset = state.searchResults.length;
      renderGlobalSearchPanel();
    } catch (err) {
      if (isStale('search', token)) return;
      state.searchError = err.message;
      renderGlobalSearchPanel();
    } finally {
      if (!isStale('search', token)) {
        state.searchLoading = false;
        renderGlobalSearchPanel();
      }
    }
  }

  function renderGlobalSearchPanel() {
    var panel = ui.searchPanel;
    if (!panel) return;
    panel.textContent = '';

    var head = makeEl('div', 'search-panel-head');
    var title = makeEl('div', 'search-panel-title');
    title.appendChild(makeEl('h2', '', '全局消息搜索'));

    var subtitle = '输入关键词搜索全部会话的消息';
    if (state.keyword) {
      if (state.searchLoading) subtitle = '正在搜索“' + state.keyword + '”…';
      else if (state.searchError) subtitle = '搜索失败，请重试';
      else subtitle = '“' + state.keyword + '” · 共 ' + fmtNum(state.searchTotal) + ' 条结果';
    }
    title.appendChild(makeEl('p', '', subtitle));
    head.appendChild(title);

    var close = makeEl('button', 'text-btn', '关闭');
    close.type = 'button';
    close.dataset.closeSearch = '1';
    head.appendChild(close);
    panel.appendChild(head);

    var list = makeEl('div', 'search-panel-list');
    panel.appendChild(list);

    if (!state.keyword) {
      var prompt = makeEl('div', 'search-panel-empty');
      prompt.appendChild(makeEl('strong', '', '搜索全部聊天记录'));
      prompt.appendChild(makeEl('span', '', '输入关键词后按 Enter 或稍候，即可跨会话查找消息'));
      list.appendChild(prompt);
      return;
    }

    if (state.searchLoading && !state.searchResults.length) {
      var loading = makeEl('div', 'search-panel-empty pulse');
      loading.appendChild(makeEl('strong', '', '正在搜索…'));
      loading.appendChild(makeEl('span', '', '数据量较大时可能需要几秒钟'));
      list.appendChild(loading);
      return;
    }

    if (state.searchError) {
      var errorBox = makeEl('div', 'search-panel-empty');
      errorBox.appendChild(makeEl('strong', '', '搜索失败'));
      errorBox.appendChild(makeEl('span', '', state.searchError));
      var retry = makeEl('button', 'retry-btn', '重试');
      retry.type = 'button';
      retry.style.marginTop = '8px';
      retry.addEventListener('click', function () {
        runGlobalSearch(true);
      });
      errorBox.appendChild(retry);
      list.appendChild(errorBox);
      return;
    }

    if (!state.searchResults.length) {
      var empty = makeEl('div', 'search-panel-empty');
      empty.appendChild(makeEl('strong', '', '没有找到相关消息'));
      empty.appendChild(makeEl('span', '', '试试更换关键词，或检查会话是否已解密'));
      list.appendChild(empty);
      return;
    }

    state.searchResults.forEach(function (result, index) {
      list.appendChild(globalSearchResultNode(result, index));
    });

    if (state.searchHasMore) {
      var more = makeEl('div', 'search-more');
      var button = makeEl('button', 'ghost-btn', state.searchLoading ? '加载中…' : '加载更多结果');
      button.type = 'button';
      button.dataset.searchMore = '1';
      button.disabled = state.searchLoading;
      more.appendChild(button);
      list.appendChild(more);
    }
  }

  function globalSearchResultNode(result, index) {
    var node = makeEl('button', 'search-result');
    node.type = 'button';
    node.dataset.resultIndex = String(index);

    var top = makeEl('div', 'sr-top');
    var sessionName = displayName(result.session_name, '未命名会话');
    top.appendChild(makeEl('span', 'sr-name', sessionName));
    top.appendChild(makeEl('span', 'sr-time', formatDateTime(result.send_time)));
    node.appendChild(top);

    var meta = makeEl('div', 'sr-top');
    var sender = result.is_send ? '我' : displayName(result.sender_name, '未知发送人');
    var typeText = result.session_type_label || TYPE_LABELS[result.session_type] || '';
    meta.appendChild(makeEl('span', 'sr-name', [sender, typeText].filter(Boolean).join(' · ')));
    node.appendChild(meta);

    var snippet = cleanDisplay(result.snippet) ||
      cleanDisplay(result.summary) ||
      cleanDisplay(result.text) ||
      kindPreview(result.kind);
    var snippetEl = makeEl('div', 'sr-snippet');
    appendMarked(snippetEl, snippet, state.keyword);
    node.appendChild(snippetEl);
    return node;
  }

  function navigateGlobalSearchResult(result) {
    if (!result || !result.session_id) return;
    var keyword = state.keyword;
    closeGlobalSearchPanel();
    openSession({
      id: result.session_id,
      name: result.session_name,
      type: result.session_type,
      type_label: result.session_type_label,
      member_count: 0,
      is_external: result.session_type === 'external',
      avatar_url: ''
    }, {
      anchorId: result.message_id,
      keyword: keyword
    });
  }

  /* ======================================================================
   * 搜索模式 / 侧栏 / 刷新
   * ==================================================================== */

  function setSearchMode(mode) {
    if (mode !== 'session' && mode !== 'message') return;
    state.searchMode = mode;
    ui.modeSessions.classList.toggle('is-active', mode === 'session');
    ui.modeMessages.classList.toggle('is-active', mode === 'message');
    ui.modeSessions.setAttribute('aria-selected', mode === 'session' ? 'true' : 'false');
    ui.modeMessages.setAttribute('aria-selected', mode === 'message' ? 'true' : 'false');
    ui.searchInput.placeholder = mode === 'session' ? '搜索会话' : '搜索全部消息';

    if (mode === 'session') {
      closeGlobalSearchPanel();
      loadSessions(true);
    } else {
      loadSessions(true);
      if (state.keyword) {
        runGlobalSearch(true);
      } else {
        state.searchResults = [];
        state.searchTotal = 0;
        state.searchHasMore = false;
        state.searchError = '';
        openGlobalSearchPanel();
        renderGlobalSearchPanel();
      }
    }
  }

  function onSearchInput() {
    state.keyword = ui.searchInput.value.trim();
    ui.searchClear.hidden = !state.keyword;
    if (state.searchMode === 'session') {
      loadSessions(true);
      return;
    }
    if (state.keyword) {
      runGlobalSearch(true);
    } else {
      state.searchResults = [];
      state.searchTotal = 0;
      state.searchHasMore = false;
      state.searchError = '';
      openGlobalSearchPanel();
      renderGlobalSearchPanel();
    }
  }

  function clearSearchInput() {
    ui.searchInput.value = '';
    state.keyword = '';
    ui.searchClear.hidden = true;
    if (state.searchMode === 'session') {
      loadSessions(true);
    } else {
      closeGlobalSearchPanel();
    }
  }

  function openSidebar() {
    if (!ui.sidebar || window.innerWidth > 900) return;
    ui.sidebar.classList.add('is-open');
    ui.sidebarMask.hidden = false;
  }

  function closeSidebar() {
    if (!ui.sidebar) return;
    ui.sidebar.classList.remove('is-open');
    if (ui.sidebarMask) ui.sidebarMask.hidden = true;
  }

  async function reloadStatus() {
    try {
      state.status = await api('/api/status', { timeout: 60000 });
    } catch (err) {
      /* 保留旧状态 */
    }
    setStatusLine();
  }

  async function refreshData() {
    if (ui.refreshBtn.disabled) return;
    var confirmed = window.confirm('刷新将重新解密并载入最新数据，可能需要数秒，是否继续？');
    if (!confirmed) return;

    ui.refreshBtn.disabled = true;
    ui.refreshBtn.classList.add('is-loading');
    ui.statusLine.textContent = '正在刷新数据…';

    try {
      var result = await api('/api/refresh', { method: 'POST', timeout: 180000 });
      if (result && result.success === false) {
        throw new Error(result.error || '后端刷新失败');
      }
      await reloadStatus();
      await loadSessions(true);

      if (state.currentSession) {
        var currentId = state.currentSession.id;
        var found = null;
        for (var i = 0; i < state.sessions.length; i += 1) {
          if (state.sessions[i].id === currentId) {
            found = state.sessions[i];
            break;
          }
        }
        if (found) {
          await openSession(found);
        } else {
          await loadMessages({ reset: true, anchorId: null });
        }
      }
      toast('数据已刷新');
    } catch (err) {
      toast('刷新失败：' + err.message, true);
      setStatusLine();
    } finally {
      ui.refreshBtn.disabled = false;
      ui.refreshBtn.classList.remove('is-loading');
    }
  }

  /* ======================================================================
   * 事件绑定与启动
   * ==================================================================== */

  function cacheUi() {
    var ids = [
      'statusLine', 'refreshBtn', 'sidebar', 'sidebarMask', 'modeSessions', 'modeMessages',
      'searchInput', 'searchClear', 'filterTabs', 'sessionList', 'sessionFooterText',
      'loadMoreSessions', 'emptyState', 'chatView', 'sidebarToggle', 'chatAvatar',
      'chatName', 'chatMeta', 'chatSearchBtn', 'chatInfoBtn', 'latestBtn', 'typeChips',
      'dateSelect', 'customDate', 'startDate', 'endDate', 'clearFilters', 'chatSearchBar',
      'chatSearchInput', 'chatSearchClose', 'chatSearchPanel', 'activeFilters',
      'messageScroll', 'loadOlderBtn', 'loadOlderStatus', 'messageList', 'searchPanel',
      'detailDrawer', 'drawerClose', 'drawerBody', 'lightbox', 'lightboxClose',
      'lightboxImg', 'lightboxDownload', 'lightboxStage', 'lightboxPrev', 'lightboxNext',
      'lightboxZoomIn', 'lightboxZoomOut', 'lightboxFit', 'lightboxActual',
      'lightboxPercent', 'lightboxCounter', 'lightboxLocate',
      'toast', 'bootError', 'bootErrorText', 'bootRetry'
    ];
    ids.forEach(function (id) {
      ui[id] = document.getElementById(id);
    });
  }

  function bindEvents() {
    var debouncedSearch = debounce(onSearchInput, SEARCH_DEBOUNCE);
    var debouncedChatSearch = debounce(function () {
      state.chatSearchKeyword = ui.chatSearchInput.value.trim();
      runChatSearch();
    }, SEARCH_DEBOUNCE);

    ui.refreshBtn.addEventListener('click', refreshData);
    ui.modeSessions.addEventListener('click', function () {
      setSearchMode('session');
    });
    ui.modeMessages.addEventListener('click', function () {
      setSearchMode('message');
    });
    ui.searchInput.addEventListener('input', debouncedSearch);
    ui.searchInput.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        debouncedSearch.cancel();
        onSearchInput();
      }
    });
    ui.searchClear.addEventListener('click', clearSearchInput);

    ui.filterTabs.addEventListener('click', function (event) {
      var button = event.target.closest ? event.target.closest('.tab') : null;
      if (!button) return;
      state.sessionType = button.dataset.type || 'all';
      var tabs = ui.filterTabs.querySelectorAll('.tab');
      for (var i = 0; i < tabs.length; i += 1) {
        tabs[i].classList.toggle('is-active', tabs[i] === button);
      }
      loadSessions(true);
    });

    ui.sessionList.addEventListener('click', function (event) {
      var item = event.target.closest ? event.target.closest('.session-item') : null;
      if (!item) return;
      var id = item.dataset.sessionId;
      var session = null;
      for (var i = 0; i < state.sessions.length; i += 1) {
        if (state.sessions[i].id === id) {
          session = state.sessions[i];
          break;
        }
      }
      if (session) openSession(session);
    });

    ui.sessionList.addEventListener('scroll', function () {
      var list = ui.sessionList;
      if (!state.sessionHasMore || state.sessionsLoading) return;
      if (list.scrollTop + list.clientHeight >= list.scrollHeight - 120) {
        loadSessions(false);
      }
    });

    ui.loadMoreSessions.addEventListener('click', function () {
      loadSessions(false);
    });

    ui.sidebarToggle.addEventListener('click', function () {
      if (ui.sidebar.classList.contains('is-open')) closeSidebar();
      else openSidebar();
    });
    ui.sidebarMask.addEventListener('click', closeSidebar);

    ui.chatSearchBtn.addEventListener('click', function () {
      toggleChatSearch(!state.chatSearchOpen);
    });
    ui.chatSearchInput.addEventListener('input', debouncedChatSearch);
    ui.chatSearchInput.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        debouncedChatSearch.cancel();
        state.chatSearchKeyword = ui.chatSearchInput.value.trim();
        runChatSearch();
      }
    });
    ui.chatSearchClose.addEventListener('click', function () {
      toggleChatSearch(false);
      state.highlightKeyword = '';
      updateActiveFilters();
      if (state.currentSession) loadMessages({ reset: true, anchorId: null });
      ui.latestBtn.hidden = true;
    });

    ui.chatSearchPanel.addEventListener('click', function (event) {
      var resultButton = event.target.closest ? event.target.closest('.search-result') : null;
      if (!resultButton) return;
      var index = Number(resultButton.dataset.resultIndex);
      var result = state.chatSearchResults[index];
      if (result) navigateChatSearchResult(result);
    });

    ui.typeChips.addEventListener('click', function (event) {
      var chip = event.target.closest ? event.target.closest('.chip') : null;
      if (!chip) return;
      setMessageType(chip.dataset.type || '');
    });

    ui.dateSelect.addEventListener('change', function () {
      state.datePreset = ui.dateSelect.value;
      ui.customDate.hidden = state.datePreset !== 'custom';
      if (state.datePreset === 'custom') {
        state.customStart = ui.startDate.value;
        state.customEnd = ui.endDate.value;
      }
      applyFilters();
    });

    function onCustomDateChange() {
      state.customStart = ui.startDate.value;
      state.customEnd = ui.endDate.value;
      if (state.datePreset === 'custom') applyFilters();
    }
    ui.startDate.addEventListener('change', onCustomDateChange);
    ui.endDate.addEventListener('change', onCustomDateChange);

    ui.clearFilters.addEventListener('click', function () {
      state.highlightKeyword = '';
      resetFilterControls();
      if (state.currentSession) loadMessages({ reset: true, anchorId: null });
    });

    ui.loadOlderBtn.addEventListener('click', loadOlderMessages);
    ui.latestBtn.addEventListener('click', loadLatestMessages);

    ui.messageScroll.addEventListener('scroll', function () {
      if (state.programmaticScroll) return;
      var scroll = ui.messageScroll;
      var distance = scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight;
      state.followLatest = distance <= 60;
      if (!state.currentSession || state.msgLoading || state.olderLoading) return;
      if (scroll.scrollTop < 60 && state.msgHasMore) {
        loadOlderMessages();
      }
    });

    ui.chatInfoBtn.addEventListener('click', openSessionDetail);

    ui.searchPanel.addEventListener('click', function (event) {
      var closeButton = event.target.closest ? event.target.closest('[data-close-search]') : null;
      if (closeButton) {
        closeGlobalSearchPanel();
        return;
      }
      var moreButton = event.target.closest ? event.target.closest('[data-search-more]') : null;
      if (moreButton) {
        runGlobalSearch(false);
        return;
      }
      var resultButton = event.target.closest ? event.target.closest('.search-result') : null;
      if (!resultButton) return;
      var index = Number(resultButton.dataset.resultIndex);
      var result = state.searchResults[index];
      if (result) navigateGlobalSearchResult(result);
    });

    ui.drawerClose.addEventListener('click', closeDrawer);
    var drawerMask = ui.detailDrawer.querySelector('[data-close-drawer]');
    if (drawerMask) drawerMask.addEventListener('click', closeDrawer);

    if (ui.lightboxClose) ui.lightboxClose.addEventListener('click', closeLightbox);
    if (ui.lightboxPrev) {
      ui.lightboxPrev.addEventListener('click', function () {
        showLightboxAt(lbState.index - 1);
      });
    }
    if (ui.lightboxNext) {
      ui.lightboxNext.addEventListener('click', function () {
        showLightboxAt(lbState.index + 1);
      });
    }
    if (ui.lightboxZoomIn) {
      ui.lightboxZoomIn.addEventListener('click', function () {
        zoomLightbox(LB_ZOOM_STEP);
      });
    }
    if (ui.lightboxZoomOut) {
      ui.lightboxZoomOut.addEventListener('click', function () {
        zoomLightbox(1 / LB_ZOOM_STEP);
      });
    }
    if (ui.lightboxFit) ui.lightboxFit.addEventListener('click', fitLightbox);
    if (ui.lightboxActual) ui.lightboxActual.addEventListener('click', actualLightboxSize);
    if (ui.lightboxLocate) ui.lightboxLocate.addEventListener('click', locateLightboxImage);
    if (ui.lightboxImg) ui.lightboxImg.draggable = false;
    if (ui.lightboxStage) ui.lightboxStage.addEventListener('pointerdown', onLightboxPointerDown);
    window.addEventListener('pointermove', onLightboxPointerMove);
    window.addEventListener('pointerup', onLightboxPointerUp);
    window.addEventListener('pointercancel', onLightboxPointerUp);
    if (ui.lightbox) {
      ui.lightbox.addEventListener('click', function (event) {
        var onStage = event.target === ui.lightboxStage ||
          (event.target.classList && event.target.classList.contains('lightbox-stage'));
        var onBlank = event.target === ui.lightbox || onStage;
        if (onBlank && lbState.moved) {
          lbState.moved = false;
          return;
        }
        if (onBlank) closeLightbox();
      });
    }

    ui.bootRetry.addEventListener('click', function () {
      window.location.reload();
    });

    document.addEventListener('keydown', function (event) {
      if (ui.lightbox && !ui.lightbox.hidden) {
        if (event.key === 'Escape') {
          closeLightbox();
        } else if (event.key === 'ArrowLeft') {
          event.preventDefault();
          showLightboxAt(lbState.index - 1);
        } else if (event.key === 'ArrowRight') {
          event.preventDefault();
          showLightboxAt(lbState.index + 1);
        } else if (event.key === '+' || event.key === '=') {
          event.preventDefault();
          zoomLightbox(LB_ZOOM_STEP);
        } else if (event.key === '-' || event.key === '_') {
          event.preventDefault();
          zoomLightbox(1 / LB_ZOOM_STEP);
        }
        return;
      }
      if (event.key !== 'Escape') return;
      if (!ui.detailDrawer.hidden) {
        closeDrawer();
        return;
      }
      if (ui.sidebar.classList.contains('is-open')) {
        closeSidebar();
        return;
      }
      if (state.chatSearchOpen) {
        toggleChatSearch(false);
      }
    });

    window.addEventListener('resize', function () {
      if (window.innerWidth > 900) closeSidebar();
    });
  }

  async function init() {
    cacheUi();
    watchMessageList();
    bindEvents();
    renderSessionSkeleton();
    updateSessionFooter();

    try {
      state.status = await api('/api/status', { timeout: 90000 });
      setStatusLine();
    } catch (err) {
      showBootError('无法连接数据服务：' + err.message);
      return;
    }

    await loadSessions(true);

    if (state.sessions.length) {
      openSession(state.sessions[0]);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
