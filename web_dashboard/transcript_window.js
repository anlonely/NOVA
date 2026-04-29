const CHARS = ["a", "b", "c"];

const params = new URLSearchParams(window.location.search || "");
const alias = CHARS.includes((params.get("alias") || "").toLowerCase()) ? (params.get("alias") || "a").toLowerCase() : "a";
const aliasUpper = alias.toUpperCase();
const uiLanguage = /^zh/i.test((params.get("lang") || navigator.language || "").toLowerCase()) ? "zh" : "en";
const isZh = uiLanguage === "zh";
const POLL_FAST_MS = 420;
const POLL_IDLE_MS = 1100;
const POLL_IDLE_STREAK_THRESHOLD = 8;

const TRANSLATIONS = {
  en: {
    eyebrow: "Channel",
    liveTranslation: "Live Translation",
    statusIdle: "Idle",
    noTranscript: "No transcript yet.",
    pinOnTop: "Pin on Top",
    unpin: "Unpin",
    close: "Close",
    closePopup: "Close popup",
    bridgeMissing: "Desktop bridge missing, showing placeholders.",
    statusRunning: "Running",
    statusListening: "Listening",
    statusTranslating: "Translating",
    statusIdleFallback: "Idle",
  },
  zh: {
    eyebrow: "通道",
    liveTranslation: "实时翻译",
    statusIdle: "待机",
    noTranscript: "暂无字幕",
    pinOnTop: "置顶",
    unpin: "取消置顶",
    close: "关闭",
    closePopup: "关闭弹窗",
    bridgeMissing: "未检测到桌面桥接，当前仅展示占位信息。",
    statusRunning: "运行中",
    statusListening: "监听中",
    statusTranslating: "翻译中",
    statusIdleFallback: "待机",
  },
};

function t(key, fallback = "") {
  return TRANSLATIONS[uiLanguage]?.[key] || TRANSLATIONS.en[key] || fallback || String(key);
}

const refs = {
  root: document.body,
  eyebrow: document.getElementById("twEyebrow"),
  title: document.getElementById("twTitle"),
  status: document.getElementById("twStatus"),
  liveSource: document.getElementById("twLiveSource"),
  liveTarget: document.getElementById("twLiveTarget"),
  transcript: document.getElementById("twTranscript"),
  notice: document.getElementById("twNotice"),
  pinButton: document.getElementById("twPinButton"),
  closeButton: document.getElementById("twCloseButton"),
};

let backendBridge = null;
let backendMode = false;
let pollTimer = null;
let pollInFlight = false;
let lastPinned = false;
let quietPolls = 0;
let lastRenderState = null;

function resolvePollInterval(hasRecentActivity) {
  if (!hasRecentActivity && quietPolls >= POLL_IDLE_STREAK_THRESHOLD) {
    return POLL_IDLE_MS;
  }
  return POLL_FAST_MS;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function resolveMode(snapshot) {
  return snapshot?.values?.[`${alias}-subtitle`] || "bilingual";
}

function hasRecentActivity(snapshot) {
  if (!snapshot) {
    return false;
  }
  const runtime = snapshot?.runtime?.channels?.[alias] || {};
  const pane = String(runtime.pane || runtime.label || "").toLowerCase();
  const hasRuntimeActivity = pane === "running" || pane === "listening" || pane === "translating";
  const partial = snapshot?.partials?.[alias] || {};
  const hasLiveSource = Boolean(String(partial.source || "").trim());
  const hasLiveTarget = Boolean(String(partial.target || "").trim());
  return hasRuntimeActivity || hasLiveSource || hasLiveTarget;
}

function buildRenderState(snapshot) {
  const mode = resolveMode(snapshot || {});
  const runtime = snapshot?.runtime?.channels?.[alias] || {};
  const partial = snapshot?.partials?.[alias] || {};
  const source = mode === "target_only" ? "" : String(partial.source || "");
  const target = mode === "source_only" ? "" : String(partial.target || "");
  const entries = Array.isArray(snapshot?.transcripts?.[alias]) ? snapshot.transcripts[alias] : [];
  const transcriptDigest = entries
    .map((entry) => `${entry?.time || ""}|${entry?.source || ""}|${entry?.target || ""}`)
    .join("\n");
  return {
    mode,
    source,
    target,
    pane: String(runtime.pane || runtime.label || "Idle"),
    transcriptCount: Array.isArray(entries) ? entries.length : 0,
    transcriptDigest,
  };
}

function shouldSkipRender(nextState) {
  if (!nextState || !lastRenderState) {
    return false;
  }
  return (
    lastRenderState.mode === nextState.mode &&
    lastRenderState.source === nextState.source &&
    lastRenderState.target === nextState.target &&
    lastRenderState.pane === nextState.pane &&
    lastRenderState.transcriptCount === nextState.transcriptCount &&
    lastRenderState.transcriptDigest === nextState.transcriptDigest
  );
}

function buildEntry(entry, mode) {
  const source = entry.source || "";
  const target = entry.target || "";
  const showSource = mode !== "target_only" && source;
  const showTarget = mode !== "source_only" && target;
  return `
    <article class="tw-entry">
      <div class="tw-entry-time">${entry.time || "--:--:--"}</div>
      ${showSource ? `<div class="tw-entry-source">${escapeHtml(source)}</div>` : ""}
      ${showTarget ? `<div class="tw-entry-target">${escapeHtml(target)}</div>` : ""}
    </article>
  `;
}

function statusLabel(value) {
  const normalized = String(value || "idle").toLowerCase();
  const map = {
    idle: t("statusIdleFallback"),
    listening: t("statusListening"),
    running: t("statusRunning"),
    translating: t("statusTranslating"),
  };
  if (Object.prototype.hasOwnProperty.call(map, normalized)) {
    return map[normalized];
  }
  return String(value || t("statusIdleFallback")).replace(/^\w/, (first) => first.toUpperCase());
}

function setPinnedUi(pinned) {
  lastPinned = Boolean(pinned);
  if (!refs.pinButton) {
    return;
  }
  refs.pinButton.textContent = lastPinned ? "📍" : "📌";
  refs.pinButton.title = lastPinned ? t("unpin") : t("pinOnTop");
  refs.pinButton.setAttribute("aria-label", lastPinned ? t("unpin") : t("pinOnTop"));
}

function setChannelLabel(snapshot) {
  const channelPrefix = t("eyebrow");
  const eyebrowLabel = `${channelPrefix} ${aliasUpper}`;
  const titleLabel = `${channelPrefix} ${aliasUpper} ${t("liveTranslation")}`;
  refs.eyebrow.textContent = eyebrowLabel;
  refs.title.textContent = titleLabel;
  document.title = titleLabel;
  document.documentElement.lang = isZh ? "zh-CN" : "en-US";
  document.body.dataset.channel = alias;
  if (refs.closeButton) {
    refs.closeButton.title = t("closePopup");
    refs.closeButton.setAttribute("aria-label", t("close"));
  }
  if (alias === "a") {
    document.documentElement.style.setProperty("--accent", "#3b82f6");
  } else if (alias === "b") {
    document.documentElement.style.setProperty("--accent", "#10b981");
  } else {
    document.documentElement.style.setProperty("--accent", "#f59e0b");
  }
}

function render(snapshot) {
  const state = buildRenderState(snapshot || {});
  if (shouldSkipRender(state)) {
    return false;
  }
  lastRenderState = state;

  const mode = state.mode;
  const entries = Array.isArray(snapshot?.transcripts?.[alias]) ? snapshot.transcripts[alias] : [];

  refs.liveSource.textContent = state.source;
  refs.liveTarget.textContent = state.target;
  refs.transcript.innerHTML = entries.map((entry) => buildEntry(entry, mode)).join("");
  refs.status.textContent = statusLabel(state.pane);
  if (!state.transcriptCount) {
    refs.notice.textContent = t("noTranscript");
  } else {
    refs.notice.textContent = "";
    refs.transcript.scrollTop = refs.transcript.scrollHeight;
  }
  return true;
}

function applyChannelAccent() {
  if (alias === "a") {
    refs.liveTarget.style.color = "var(--accent-a, #3b82f6)";
  } else if (alias === "b") {
    refs.liveTarget.style.color = "var(--accent-b, #10b981)";
  } else {
    refs.liveTarget.style.color = "var(--accent-c, #f59e0b)";
  }
}

async function connectBackend() {
  if (!(window.qt && window.QWebChannel)) {
    return false;
  }
  await new Promise((resolve) => {
    new QWebChannel(window.qt.webChannelTransport, (channel) => {
      backendBridge = channel.objects.novaBridge;
      resolve();
    });
  });
  backendMode = Boolean(backendBridge);
  return backendMode;
}

async function callBackend(method, payload) {
  if (!backendMode || !backendBridge || typeof backendBridge[method] !== "function") {
    return null;
  }
  return new Promise((resolve) => {
    const callback = (result) => {
      if (typeof result !== "string") {
        resolve(result);
        return;
      }
      try {
        resolve(JSON.parse(result));
      } catch {
        resolve(result);
      }
    };
    if (payload === undefined) {
      backendBridge[method](callback);
      return;
    }
    backendBridge[method](JSON.stringify(payload), callback);
  });
}

async function queryInitialState() {
  const response = await callBackend("get_state");
  if (response) {
    setChannelLabel(response);
    render(response);
    const openState = await callBackend("is_transcript_window_open", { alias });
    if (openState && typeof openState.pinned === "boolean") {
      setPinnedUi(openState.pinned);
    }
  }
}

async function pollState() {
  if (!backendMode || pollInFlight) {
    if (backendMode) {
      scheduleNextPoll(null);
    }
    return;
  }
  pollInFlight = true;
  let polledPayload = null;
  try {
    const response = await callBackend("poll_state");
    if (response) {
      render(response);
      polledPayload = response;
    }
  } finally {
    pollInFlight = false;
  }
  scheduleNextPoll(polledPayload);
}

async function setPinned(nextPinned) {
  setPinnedUi(nextPinned);
  if (!backendMode) {
    return;
  }
  const response = await callBackend("set_transcript_window_topmost", {
    alias,
    pinned: Boolean(nextPinned),
  });
  if (response && typeof response.pinned === "boolean") {
    setPinnedUi(response.pinned);
  }
}

async function closeWindow() {
  if (backendMode) {
    await callBackend("close_transcript_window", { alias });
  }
  window.close();
}

function startPolling() {
  scheduleNextPoll(null, true);
}

function scheduleNextPoll(snapshot, forceFast = false) {
  const nextPollHasActivity = forceFast ? true : hasRecentActivity(snapshot);
  const nextInterval = resolvePollInterval(nextPollHasActivity);
  quietPolls = forceFast ? 0 : nextPollHasActivity ? 0 : quietPolls + 1;
  if (pollTimer !== null) {
    window.clearTimeout(pollTimer);
  }
  pollTimer = window.setTimeout(() => {
    void pollState();
  }, nextInterval);
}

refs.pinButton?.addEventListener("click", () => {
  setPinned(!lastPinned);
});

refs.closeButton?.addEventListener("click", () => {
  void closeWindow();
});

window.addEventListener("beforeunload", () => {
  if (pollTimer !== null) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
  if (backendMode) {
    void callBackend("close_transcript_window", { alias });
  }
});

async function run() {
  applyChannelAccent();
  setChannelLabel({});
  setPinnedUi(false);
  await connectBackend();
  if (!backendMode) {
    refs.notice.textContent = t("bridgeMissing");
    return;
  }
  await queryInitialState();
  startPolling();
}

void run();
