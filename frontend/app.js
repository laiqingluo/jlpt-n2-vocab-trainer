const API = "";

const reviewSession = {
  all: [],
  allLoaded: false,
  queue: [],
  index: 0,
  mode: "new",
  revealed: false,
  stats: { known: 0, again: 0, hard: 0, good: 0 },
  weakWords: [],
  learned: [],
  listening: {
    queue: [],
    lastQueue: [],
    index: 0,
    stats: { total: 0, weak: 0, known: 0, need: 0, feedback: 0 },
    token: 0,
    handled: false,
  },
};

const screeningSession = {
  queue: [],
  index: 0,
  master: 0,
  fuzzy: 0,
  buffer: [],
  lastMilestone: 0,
};

// ── Planning page ────────────────────────────────────────────────────────────
const PLAN_TARGET = 6500;
let customDailyNet = null;
let customDailyNewWords = null;
let planBaseVocab = null;
let planCoef = null;

function selectCustomTime(el, net, dailyNew) {
  document.querySelectorAll(".custom-time-btn").forEach((b) => b.classList.remove("active"));
  el.classList.add("active");
  customDailyNet = net;
  customDailyNewWords = dailyNew;
  calculate();
  setTimeout(() => {
    if (planBaseVocab !== null) {
      document.getElementById("result-area")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, 100);
}

function selectBase(el, vocab, c) {
  document.querySelectorAll(".base-btn").forEach((b) => b.classList.remove("active"));
  el.classList.add("active");
  planBaseVocab = vocab;
  planCoef = c;
  calculate();
  setTimeout(() => {
    if (customDailyNet !== null) {
      document.getElementById("result-area")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, 100);
}

function calculate() {
  if (customDailyNet === null || planBaseVocab === null) {
    document.getElementById("result-area").classList.remove("visible");
    return;
  }

  const net = customDailyNet;
  const baseVocab = planBaseVocab;
  const coef = planCoef;
  const target = PLAN_TARGET - baseVocab;
  const adjustedNet = net * coef;
  const displayMonths = Math.round((target / adjustedNet / 30) * 10) / 10;

  const baseNoteMap = { 0: '零基础起点', 800: '已考虑 N5 基础', 1500: '已考虑 N4 基础', 3000: '已考虑 N3 基础', 5000: '已考虑 N2 基础' };

  document.getElementById("result-area").classList.add("visible");
  document.getElementById("result-num").textContent = displayMonths;
  document.getElementById("bd-target").textContent = target + " 个词";
  document.getElementById("bd-daily").textContent = net + " 个/天";
  document.getElementById("bd-base").textContent = baseNoteMap[baseVocab] || '已考虑当前基础';

  let hope = "";
  if (displayMonths <= 8) {
    hope = `按这个节奏，${displayMonths}个月后词汇量就能到位。`;
  } else if (displayMonths <= 12) {
    hope = `坚持${displayMonths}个月，你将具备N2词汇基础。每天的积累都在发生。`;
  } else if (displayMonths <= 18) {
    hope = `坚持${displayMonths}个月，一年半内你将具备N2词汇基础。`;
  } else if (displayMonths <= 24) {
    hope = `${displayMonths}个月是段需要耐心的旅程。增加每天投入时间，周期会明显缩短。`;
  } else {
    hope = `${displayMonths}个月周期较长。建议增加每天学习时间，或先筛掉已掌握的词。`;
  }
  document.getElementById("result-hope").innerHTML = hope;
}

function toggleExplain() {
  const explain = document.getElementById("result-explain");
  explain.classList.toggle("show");
  const isOpen = explain.classList.contains("show");
  document.querySelector("#screen-onboarding .hero").classList.toggle("explain-open", isOpen);
}

function flashMissing(selector) {
  const group = document.querySelector(selector);
  if (!group) return;
  group.classList.remove("input-missing");
  void group.offsetWidth; // force reflow to restart animation
  group.classList.add("input-missing");
  setTimeout(() => group.classList.remove("input-missing"), 600);
}

async function planGenerate() {
  if (customDailyNet === null) {
    toast("请先选择每天学习时间");
    flashMissing(".custom-time-btn");
    return;
  }
  if (planBaseVocab === null) {
    toast("请先选择日语基础");
    flashMissing(".base-btn");
    return;
  }

  const btn = document.querySelector(".generate-btn");
  btn.disabled = true;
  btn.textContent = "正在生成…";

  const net = customDailyNet;
  const baseVocab = planBaseVocab;
  const coef = planCoef;
  const target = PLAN_TARGET - baseVocab;
  const adjustedNet = net * coef;
  const months = Math.round((target / adjustedNet / 30) * 10) / 10;
  const dailyNew = customDailyNewWords ?? Math.round(net / 0.65);

  localStorage.setItem("n2plan", JSON.stringify({
    dailyNet: net, baseVocab, coef,
    months, dailyNew, generated: true,
  }));

  try {
    await apiFetch("/api/user/settings", {
      method: "POST",
      body: JSON.stringify({ declared_vocab_level: baseVocab, daily_word_count: dailyNew }),
    });
  } catch {}

  btn.disabled = false;
  btn.textContent = "生成我的学习计划 →";

  if (baseVocab > 0) {
    await startScreening();
  } else {
    await openVocabEntry();
  }
}

let toastTimer = null;

function setScreen(id) {
  document.querySelectorAll(".screen").forEach((screen) => {
    screen.classList.toggle("active", screen.id === id);
  });
}

function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 2000);
}

async function apiFetch(path, options = {}) {
  const token = localStorage.getItem("auth_token");
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`${API}${path}`, { ...options, headers });
}

// ── Auth ─────────────────────────────────────────────────────────────────────

function switchAuthTab(tab) {
  document.getElementById("auth-tab-login").classList.toggle("active", tab === "login");
  document.getElementById("auth-tab-register").classList.toggle("active", tab === "register");
  document.getElementById("auth-tab-mode").value = tab;
  document.getElementById("auth-submit-btn").textContent = tab === "login" ? "登录" : "注册";
  document.getElementById("auth-error").textContent = "";
}

async function authSubmit() {
  const mode     = document.getElementById("auth-tab-mode").value;
  const username = document.getElementById("auth-username").value.trim();
  const password = document.getElementById("auth-password").value;
  const errEl    = document.getElementById("auth-error");
  errEl.textContent = "";

  if (!username || !password) {
    errEl.textContent = "请填写用户名和密码";
    return;
  }

  const btn = document.getElementById("auth-submit-btn");
  btn.disabled = true;

  try {
    const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/register";
    const res = await fetch(`${API}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      errEl.textContent = data.detail || (mode === "login" ? "登录失败" : "注册失败");
      return;
    }
    localStorage.setItem("auth_token", data.token);
    localStorage.setItem("auth_username", data.username);
    await _afterAuth();
  } catch {
    errEl.textContent = "网络错误，请重试";
  } finally {
    btn.disabled = false;
  }
}

async function _afterAuth() {
  try {
    const res = await apiFetch("/api/user/settings");
    if (res.ok) {
      const settings = await res.json();
      if (settings.declared_vocab_level !== null && settings.declared_vocab_level !== undefined) {
        await openVocabEntry();
        return;
      }
    }
  } catch {}
  setScreen("screen-onboarding");
}

function guestContinue() {
  localStorage.removeItem("auth_token");
  localStorage.removeItem("auth_username");
  _afterAuth();
}

function logout() {
  localStorage.removeItem("auth_token");
  localStorage.removeItem("auth_username");
  setScreen("screen-auth");
}

function planHopeText(months) {
  if (!months) return "";
  if (months <= 8)  return `按这个节奏，${months}个月后词汇量就能到位。`;
  if (months <= 12) return `坚持${months}个月，你将具备N2词汇基础。每天的积累都在发生。`;
  if (months <= 18) return `坚持${months}个月，一年半内你将具备N2词汇基础。`;
  if (months <= 24) return `${months}个月是段需要耐心的旅程。增加每天投入时间，周期会明显缩短。`;
  return `${months}个月周期较长。建议增加每天学习时间，或先筛掉已掌握的词。`;
}

async function openVocabEntry() {
  setScreen("screen-entry");
  document.getElementById("vocab-entry-due").textContent = "…";
  document.getElementById("vocab-entry-learned").textContent = "…";
  document.getElementById("vocab-entry-today").textContent = "…";
  document.getElementById("vocab-entry-today-target").textContent = "…";
  document.getElementById("vocab-start-review").style.display = "none";

  const plan = JSON.parse(localStorage.getItem("n2plan") || "{}");
  const sub = document.getElementById("vocab-entry-sub");
  if (sub) {
    sub.textContent = plan.months
      ? `按当前节奏，预计约 ${plan.months} 个月完成 N2 词汇基础`
      : "基于 2010–2025 真题高频词 · 6500 词按优先级训练";
  }

  try {
    const response = await apiFetch("/api/n2/vocab/stats");
    if (!response.ok) throw new Error();
    const data = await response.json();
    const due = data.due || 0;
    const mastered = data.mastered || 0;
    const learnedToday = data.learned_today ?? 0;
    const dailyTarget = data.daily_target || 0;
    document.getElementById("vocab-entry-due").textContent = due;
    document.getElementById("vocab-entry-learned").textContent = mastered;
    document.getElementById("vocab-entry-today").textContent = learnedToday;
    document.getElementById("vocab-entry-today-target").textContent = dailyTarget || "—";

    // 等级进度条（主进度：已掌握 mastered；次进度：已学 learned）
    const byLevel = data.by_level || {};
    const levelOrder = [
      { key: "N2", label: "N2", note: "核心目标" },
      { key: "N1", label: "N1", note: "超纲词" },
      { key: "N3", label: "N3", note: "" },
      { key: "N4", label: "N4", note: "" },
      { key: "N5", label: "N5", note: "" },
    ];
    const lpEl = document.getElementById("ves-level-progress");
    lpEl.innerHTML = levelOrder
      .filter(({ key }) => byLevel[key] && byLevel[key].total > 0)
      .map(({ key, label, note }) => {
        const { total, learned: lvLearned, mastered: lvMastered = 0 } = byLevel[key];
        const pctLearned  = total > 0 ? Math.round((lvLearned  / total) * 100) : 0;
        const pctMastered = total > 0 ? Math.round((lvMastered / total) * 100) : 0;
        const noteHtml = note ? `<span class="ves-lp-note">${note}</span>` : "";
        return `<div class="ves-lp-row">
          <span class="ves-lp-badge ves-lp-${key.toLowerCase()}">${label}</span>
          <div class="ves-lp-bar-wrap">
            <div class="ves-lp-bar-fill ves-lp-fill-${key.toLowerCase()} ves-lp-learned" style="width:${pctLearned}%"></div>
            <div class="ves-lp-bar-fill ves-lp-fill-${key.toLowerCase()} ves-lp-mastered" style="width:${pctMastered}%"></div>
          </div>
          <span class="ves-lp-count">${lvMastered}<span class="ves-lp-total">/${total}</span></span>
          ${noteHtml}
        </div>`;
      }).join("");
    const newsDone = dailyTarget > 0 && learnedToday >= dailyTarget;
    const reviewPending = due > 0;

    // 复习按钮：有待复习则显示；新词已完成时升级为主色
    const reviewBtn = document.getElementById("vocab-start-review");
    reviewBtn.style.display = reviewPending ? "" : "none";
    reviewBtn.classList.toggle("veb-review--primary", newsDone && reviewPending);

    // 新词按钮：新词已完成时弱化
    const newBtn = document.getElementById("ves-new-btn");
    newBtn.classList.toggle("veb-new--done", newsDone);

    // 主按钮副文案
    const newSub = document.getElementById("ves-new-sub");
    if (newSub) {
      if (newsDone && !reviewPending) newSub.textContent = "今日任务全部完成 🎉";
      else if (newsDone)              newSub.textContent = "今日新词已完成 ✓";
      else if (dailyTarget)           newSub.textContent = `今天先完成 ${dailyTarget} 个新词`;
      else                            newSub.textContent = "继续积累新词";
    }

    // Usage test button
    const usagePending = data.usage_pending || 0;
    const testBtn = document.getElementById("ves-test-btn");
    const testSub = document.getElementById("ves-test-sub");
    if (testBtn) {
      testBtn.style.display = usagePending > 0 ? "" : "none";
      if (testSub) testSub.textContent = `${usagePending} 个词等待测验`;
    }

    // Screening button
    const newCount = data.new || 0;
    const screenBtn = document.getElementById("ves-screen-btn");
    const screenSub = document.getElementById("ves-screen-sub");
    if (screenBtn) {
      screenBtn.style.display = newCount > 0 ? "" : "none";
      if (screenSub) screenSub.textContent = `还有 ${newCount} 词未筛，标出已认识的可跳过`;
    }
  } catch {
    toast("加载词表失败");
  }
  // 后台预加载完整词表，使"已掌握"点击时能即时响应
  ensureVocabLoaded().catch(() => {});
}

async function ensureVocabLoaded() {
  if (reviewSession.allLoaded && reviewSession.all.length) return true;
  const response = await apiFetch("/api/n2/vocab");
  if (!response.ok) throw new Error();
  const data = await response.json();
  reviewSession.all = data.vocab || [];
  reviewSession.allLoaded = true;
  return true;
}

async function startVocabNew() {
  try {
    await ensureVocabLoaded();
  } catch {
    toast("加载词表失败");
    return;
  }
  reviewSession.mode = "new";
  reviewSession.queue = reviewSession.all
    .filter((word) => !word.review_result && !word.is_mastered)
    .sort(sortByFrequency);
  reviewSession.index = 0;
  reviewSession.stats = { known: 0, again: 0, hard: 0, good: 0 };
  reviewSession.weakWords = [];
  startVocabSession();
}

async function startVocabReview() {
  try {
    await ensureVocabLoaded();
  } catch {
    toast("加载词表失败");
    return;
  }
  reviewSession.mode = "review";
  const rank = { again: 0, hard: 1, good: 2, known: 3 };
  reviewSession.queue = reviewSession.all
    .filter((word) => word.is_due)
    .sort((a, b) => ((rank[a.review_result] ?? 0) - (rank[b.review_result] ?? 0)) || sortByFrequency(a, b));
  reviewSession.index = 0;
  reviewSession.stats = { known: 0, again: 0, hard: 0, good: 0 };
  reviewSession.weakWords = [];
  startVocabSession();
}

function startVocabSession() {
  if (!reviewSession.queue.length) {
    toast(reviewSession.mode === "review" ? "没有到期词" : "所有新词已学完");
    return;
  }
  setScreen("screen-card");
  renderCard();
}

function sortByFrequency(a, b) {
  return (Number(b.count) || 0) - (Number(a.count) || 0);
}

async function openLearnedVocabList() {
  const btn = document.getElementById("ves-learned-btn");
  const numEl = document.getElementById("vocab-entry-learned");
  const prevNum = numEl ? numEl.textContent : "";
  if (btn) btn.disabled = true;
  if (numEl) numEl.textContent = "…";
  try {
    await ensureVocabLoaded();
  } catch {
    toast("加载词表失败");
    if (btn) btn.disabled = false;
    if (numEl) numEl.textContent = prevNum;
    return;
  }
  if (btn) btn.disabled = false;
  if (numEl) numEl.textContent = prevNum;
  const learned = reviewSession.all
    .filter((word) => word.review_result)
    .sort(sortByFrequency);

  document.getElementById("vocab-learned-count").textContent = learned.length;
  const list = document.getElementById("vocab-learned-list");
  if (!learned.length) {
    list.innerHTML = '<div class="vl-empty">还没有已学词</div>';
  } else {
    list.innerHTML = learned.map((word) => `
      <div class="vl-row">
        <div class="vl-word">${escapeHtml(word.word)}</div>
        <div class="vl-reading">${escapeHtml(word.reading || "")}</div>
        <div class="vl-meaning">${escapeHtml(meaningSummary(word.meaning))}</div>
        <button class="vl-play" data-audio="${escapeHtml(word.reading || word.word)}" title="播放发音">▶</button>
      </div>
    `).join("");
  }
  reviewSession.learned = learned;
  setScreen("screen-learned");
}

function meaningSummary(text) {
  if (!text) return "—";
  const hasKana = (s) => /[぀-ヿ]/.test(s);
  const meanings = [];
  const segments = String(text).split(/(?=[①②③④⑤⑥⑦⑧⑨⑩])/);
  segments.forEach((segment) => {
    // 跳过 ① 之前的日语头部（如 "やる (やる) "）
    if (!/^[①②③④⑤⑥⑦⑧⑨⑩]/.test(segment)) return;
    const rest = segment.replace(/^[①②③④⑤⑥⑦⑧⑨⑩]\s*/, "").trim();
    if (!rest) return;
    const cn = rest.split("（")[0].trim();
    if (cn && !hasKana(cn)) {
      meanings.push(cn);
    } else {
      // 义项本身是日文时，从（例句｜中文翻译）里提取译文
      const m = rest.match(/[（(][^）)]*[｜|]([^）)]+)[）)]/);
      if (m) {
        const translation = m[1].replace(/[。.]\s*$/, "").trim();
        if (translation && !hasKana(translation)) meanings.push(translation);
      }
    }
  });
  if (meanings.length) return meanings.slice(0, 3).join("；");
  return String(text).split("（")[0].trim() || "—";
}

function renderCard() {
  const total = reviewSession.queue.length;
  const index = reviewSession.index;
  if (index >= total) {
    finishSession();
    return;
  }

  const word = reviewSession.queue[index];
  reviewSession.revealed = false;
  document.getElementById("vc-word").textContent = word.word;
  document.getElementById("vc-reading").textContent = word.reading || "";

  const badge = document.getElementById("vc-level-badge");
  const lvl = word.jlpt_level;
  if (lvl) {
    badge.textContent = "N" + lvl;
    badge.dataset.level = lvl;
    badge.style.display = "";
  } else {
    badge.textContent = "";
    badge.style.display = "none";
  }

  const contextEl = document.getElementById("vc-context");
  const context = frontContext(word);
  if (context) {
    contextEl.innerHTML = `<span class="vc-context-label">例</span>${escapeHtml(context)}`;
    contextEl.style.display = "";
  } else {
    contextEl.innerHTML = "";
    contextEl.style.display = "none";
  }

  document.getElementById("vc-meaning").innerHTML = "";
  document.getElementById("vc-meaning").style.display = "none";
  document.getElementById("vc-collocation").innerHTML = "";
  document.getElementById("vc-collocation").style.display = "none";
  document.getElementById("vc-cn-audio").style.display = "none";
  document.getElementById("vc-placeholder").style.display = "";
  document.getElementById("vc-btns-default").style.display = "flex";
  document.getElementById("vc-btns-revealed").style.display = "none";

  const pct = Math.round((index / total) * 100);
  document.getElementById("vc-progress-fill").style.width = `${pct}%`;
  document.getElementById("vc-counter").textContent =
    `${index + 1} / ${total}  ${reviewSession.mode === "review" ? "复习" : "未学新词"}`;
}

function frontContext(word) {
  const fromCollocation = cleanJapaneseContext(word.collocation || "");
  if (fromCollocation) return fromCollocation;
  const detail = word.meaning || "";
  const match = detail.match(/（([^（）]+)）/);
  if (!match) return "";
  return cleanJapaneseContext(match[1]);
}

function cleanJapaneseContext(text) {
  if (!text) return "";
  let jp = String(text).split("｜")[0].split("|")[0].split("（")[0].trim();
  jp = jp.replace(/^例[:：]\s*/, "").trim();
  if (!jp || jp.length > 24) return "";
  return /[\u3040-\u30ff\u3400-\u9fff]/.test(jp) ? jp : "";
}

function parseMeaningHtml(text) {
  if (!text) return '<span class="vc-meaning-cn">—</span>';
  const segments = text.split(/(?=[①②③④⑤⑥⑦⑧⑨⑩])/);
  return segments.map((segment) => {
    const markerMatch = segment.match(/^([①②③④⑤⑥⑦⑧⑨⑩])(.*)/s);
    if (!markerMatch) {
      return segment ? `<div class="vc-meaning-item"><span class="vc-meaning-cn">${escapeHtml(segment.trim())}</span></div>` : "";
    }
    const marker = markerMatch[1];
    const rest = markerMatch[2].trim();
    const parenIdx = rest.indexOf("（");
    if (parenIdx !== -1) {
      const cn = rest.slice(0, parenIdx).trim();
      const exampleText = rest.slice(parenIdx + 1).replace(/）\s*$/, "").trim();
      const [jp, zh] = splitExampleTranslation(exampleText);
      return `<div class="vc-meaning-item">
        <div class="vc-meaning-row"><span class="vc-meaning-marker">${marker}</span><span class="vc-meaning-cn">${escapeHtml(cn)}</span></div>
        ${jp ? `<div class="vc-meaning-jp-row"><span class="vc-meaning-jp">${escapeHtml(jp)}</span><button class="vc-ex-audio" data-text="${escapeHtml(jp)}" title="播放例句">▶</button></div>` : ""}
        ${zh ? `<div class="vc-meaning-zh">${escapeHtml(zh)}</div>` : ""}
      </div>`;
    }
    return `<div class="vc-meaning-item">
      <div class="vc-meaning-row"><span class="vc-meaning-marker">${marker}</span><span class="vc-meaning-cn">${escapeHtml(rest)}</span></div>
    </div>`;
  }).join("");
}

function splitExampleTranslation(text) {
  const idx = text.indexOf("｜") !== -1 ? text.indexOf("｜") : text.indexOf("|");
  if (idx === -1) return [text.trim(), ""];
  return [text.slice(0, idx).trim(), text.slice(idx + 1).trim()];
}

function parseCollocationHtml(text) {
  if (!text) return "";
  const parenIdx = text.indexOf("（");
  if (parenIdx !== -1) {
    const jp = text.slice(0, parenIdx).trim();
    const cn = text.slice(parenIdx + 1).replace(/）\s*$/, "").trim();
    return `<span class="vc-col-label">例</span><span class="vc-col-jp">${escapeHtml(jp)}</span><span class="vc-col-cn">${escapeHtml(cn)}</span>`;
  }
  return `<span class="vc-col-label">例</span><span class="vc-col-jp">${escapeHtml(text)}</span>`;
}

function vocabReveal() {
  if (reviewSession.revealed) return;
  reviewSession.revealed = true;
  const word = reviewSession.queue[reviewSession.index];

  document.getElementById("vc-placeholder").style.display = "none";
  const meaningEl = document.getElementById("vc-meaning");
  meaningEl.innerHTML = parseMeaningHtml(word.meaning_detail || word.meaning);
  meaningEl.style.display = "";

  const colEl = document.getElementById("vc-collocation");
  if (word.collocation) {
    colEl.innerHTML = parseCollocationHtml(word.collocation);
    colEl.style.display = "";
  }

  document.getElementById("vc-cn-audio").style.display = "";

  document.getElementById("vc-btns-default").style.display = "none";
  document.getElementById("vc-btns-revealed").style.display = "flex";
}

async function vocabAnswer(result) {
  const word = reviewSession.queue[reviewSession.index];
  if (!word) return;

  reviewSession.stats[result] = (reviewSession.stats[result] || 0) + 1;

  if ((result === "again" || result === "hard" || result === "good") && !reviewSession.weakWords.find((item) => item.word === word.word)) {
    reviewSession.weakWords.push(word);
  }

  if (result === "again") {
    reviewSession.queue.push(word);
  }

  reviewSession.index++;
  renderCard();

  apiFetch("/api/n2/review", {
    method: "POST",
    body: JSON.stringify({ word: word.word, result }),
  }).catch(() => {});
}

async function startLearnedListening() {
  stopListeningAudio();
  toast("正在生成今日推荐");
  try {
    const response = await apiFetch("/api/listening/session");
    if (!response.ok) throw new Error();
    const data = await response.json();
    let items = data.items || [];
    if (!items.length) {
      items = reviewSession.listening.lastQueue.slice();
      if (!items.length) {
        toast(data.message || "今天可听词已经完成，可以稍后再来");
        return;
      }
      toast("暂无新一轮，继续循环当前词");
    }
    reviewSession.listening.queue = items;
    reviewSession.listening.lastQueue = items.slice();
    reviewSession.listening.index = 0;
    reviewSession.listening.stats = { total: 0, weak: 0, known: 0, need: 0, feedback: 0 };

    // Pre-warm Chinese audio cache for all items in background
    items.forEach((w) => {
      const key = w.meaning || "暂无释义";
      if (!cnAudioCache[key]) {
        cnAudioCache[key] = fetchAudio("/api/cn_audio", key);
      }
    });

    setScreen("screen-listening");
    renderListeningItem();
    playListeningCurrent();
  } catch {
    toast("生成磨耳朵队列失败");
  }
}

function renderListeningItem() {
  const state = reviewSession.listening;
  const total = state.queue.length;
  if (state.index >= total) {
    finishListeningRound();
    return;
  }
  const word = state.queue[state.index];
  document.getElementById("listen-counter").textContent = `${state.index + 1} / ${total}`;
  document.getElementById("listen-word").textContent = word.word || "";
  document.getElementById("listen-reading").textContent = word.reading || "";
  document.getElementById("listen-meaning").textContent = word.meaning || "暂无释义";
  document.getElementById("listen-status").textContent =
    `本轮 ${state.index + 1} / ${total} · 弱词强化 ${state.stats.weak} 个`;
  state.handled = false;
}

async function playListeningCurrent() {
  const state = reviewSession.listening;
  const word = state.queue[state.index];
  if (!word) return;
  stopListeningAudio();
  const token = ++state.token;
  try {
    await playWordAudio(word);
    if (token !== state.token) return;
    await sleep(800);
    if (token !== state.token) return;
    await playChineseAudio(word.meaning || "暂无释义");
    if (token !== state.token) return;
    await sleep(1200);
    if (token !== state.token || state.handled) return;
    await autoAdvanceListeningItem(token);
  } catch {
    if (token === state.token) await autoAdvanceListeningItem(token);
  }
}

function replayListeningItem() {
  playListeningCurrent();
}

async function submitListeningFeedback(feedback) {
  const state = reviewSession.listening;
  const word = state.queue[state.index];
  if (!word || state.handled) return;
  state.handled = true;
  state.token += 1;
  stopListeningAudio();
  try {
    const response = await apiFetch("/api/listening/feedback", {
      method: "POST",
      body: JSON.stringify({ word_id: word.word_id, feedback }),
    });
    if (!response.ok) throw new Error();
  } catch {
    state.handled = false;
    toast("反馈保存失败");
    return;
  }

  countListeningFeedback(feedback);
  nextListeningItem();
}

async function autoAdvanceListeningItem(token) {
  const state = reviewSession.listening;
  const word = state.queue[state.index];
  if (!word || state.handled || token !== state.token) return;
  state.handled = true;
  try {
    await apiFetch("/api/listening/heard", {
      method: "POST",
      body: JSON.stringify({ word_id: word.word_id }),
    });
  } catch {}
  state.stats.total += 1;
  nextListeningItem();
}

function countListeningFeedback(feedback) {
  const state = reviewSession.listening;
  state.stats.total += 1;
  state.stats.feedback += 1;
  if (feedback === "unknown" || feedback === "recall_fail") {
    state.stats.weak += 1;
    state.stats.need += 1;
  }
  if (feedback === "known") state.stats.known += 1;
  if (feedback === "passive_known") state.stats.weak += 1;
}

function nextListeningItem() {
  const state = reviewSession.listening;
  state.index += 1;
  if (state.index >= state.queue.length) {
    finishListeningRound();
    return;
  }
  renderListeningItem();
  playListeningCurrent();
}

function finishListeningRound() {
  stopListeningAudio();
  reviewSession.listening.lastQueue = reviewSession.listening.queue.slice();
  const stats = reviewSession.listening.stats;
  if (stats.feedback === 0) {
    continueListeningLoop();
    return;
  }
  document.getElementById("ld-total").textContent = `${stats.total} 词`;
  document.getElementById("ld-weak").textContent = `${stats.weak} 词`;
  document.getElementById("ld-known").textContent = `${stats.known} 词`;
  document.getElementById("ld-need").textContent = `${stats.need} 词`;
  setScreen("screen-listening-done");
}

async function continueListeningLoop() {
  const previousQueue = reviewSession.listening.queue.length
    ? reviewSession.listening.queue.slice()
    : reviewSession.listening.lastQueue.slice();
  try {
    const response = await apiFetch("/api/listening/session");
    if (response.ok) {
      const data = await response.json();
      const items = data.items || [];
      reviewSession.listening.queue = items.length ? items : previousQueue;
    } else {
      reviewSession.listening.queue = previousQueue;
    }
  } catch {
    reviewSession.listening.queue = previousQueue;
  }

  if (!reviewSession.listening.queue.length) {
    toast("暂无可循环词");
    return;
  }

  reviewSession.listening.index = 0;
  reviewSession.listening.lastQueue = reviewSession.listening.queue.slice();
  reviewSession.listening.stats = { total: 0, weak: 0, known: 0, need: 0, feedback: 0 };
  setScreen("screen-listening");
  renderListeningItem();
  playListeningCurrent();
}

function quitListeningSession() {
  const ok = confirm("是否退出磨耳朵？\n\n已提交反馈的单词已保存，未反馈的单词不会记录。");
  if (!ok) return;
  stopListeningAudio();
  openLearnedVocabList();
}

function stopListeningAudio() {
  reviewSession.listening.token += 1;
  try {
    reviewAudio.pause();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  } catch {}
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function finishSession() {
  const stats = reviewSession.stats;
  document.getElementById("vd-known").textContent = stats.known;
  document.getElementById("vd-good").textContent = stats.good;
  document.getElementById("vd-hard").textContent = stats.hard;
  document.getElementById("vd-again").textContent = stats.again;

  const hint = document.getElementById("rd-next-hint");
  const learnNextBtn = document.getElementById("rd-learn-next");
  hint.style.display = "none";
  learnNextBtn.style.display = "none";

  try {
    const res = await apiFetch("/api/n2/vocab/stats");
    if (res.ok) {
      const data = await res.json();
      const learnedToday = data.learned_today ?? 0;
      const dailyTarget = data.daily_target || 0;
      const newWordsPending = dailyTarget > 0 && learnedToday < dailyTarget;
      if (newWordsPending) {
        const remaining = dailyTarget - learnedToday;
        hint.textContent = `今日还有 ${remaining} 个新词等你`;
        hint.style.display = "";
        learnNextBtn.style.display = "";
      } else {
        hint.textContent = "今日任务全部完成 🎉";
        hint.style.display = "";
      }
    }
  } catch {}

  setScreen("screen-done");
}

function vocabQuit() {
  const ok = confirm("是否退出学习？\n\n已完成的单词已保存，当前单词不会记录。");
  if (!ok) return;
  openVocabEntry();
}

function escapeHtml(text) {
  return String(text || "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

async function startScreening(maxCount) {
  try {
    const res = await apiFetch("/api/screen/queue");
    if (!res.ok) throw new Error();
    const data = await res.json();
    let pool = data.words || [];
    if (maxCount && maxCount > 0) pool = pool.slice(0, maxCount);
    if (!pool.length) {
      toast("没有可筛的词");
      if (maxCount) openVocabEntry();
      return;
    }
    screeningSession.queue = pool;
    screeningSession.index = 0;
    screeningSession.master = 0;
    screeningSession.fuzzy = 0;
    screeningSession.buffer = [];
    screeningSession.lastMilestone = 0;
    setScreen("screen-screening");
    renderScreeningCard();
    updateScreeningStats();
  } catch {
    toast("加载词表失败");
  }
}

function renderScreeningCard() {
  const { queue, index } = screeningSession;
  if (index >= queue.length) {
    finishScreening();
    return;
  }
  const word = queue[index];
  document.getElementById("sc-word").textContent = word.word;
  document.getElementById("sc-reading").textContent = word.reading || "";
  document.getElementById("sc-counter").textContent = `${index + 1} / ${queue.length}`;
  document.getElementById("sc-progress-fill").style.width =
    `${Math.round(index / queue.length * 100)}%`;
}

function updateScreeningStats() {
  const skip = screeningSession.index - screeningSession.master - screeningSession.fuzzy;
  document.getElementById("sc-stat-master").textContent = screeningSession.master;
  document.getElementById("sc-stat-fuzzy").textContent = screeningSession.fuzzy;
  document.getElementById("sc-stat-skip").textContent = skip;
}

async function screeningAnswer(result) {
  const word = screeningSession.queue[screeningSession.index];
  if (!word) return;
  if (result === "known") {
    screeningSession.master++;
    screeningSession.buffer.push({ word: word.word, result: "known" });
  } else if (result === "good") {
    screeningSession.fuzzy++;
    screeningSession.buffer.push({ word: word.word, result: "good" });
  }
  // "skip" — just advance without recording
  screeningSession.index++;
  if (screeningSession.buffer.length >= 100) {
    flushScreeningBuffer().catch(() => {});
  }
  updateScreeningStats();

  // Check daily limit milestone (fires at 1x, 2x, 3x … dailyNew)
  const skip = screeningSession.index - screeningSession.master - screeningSession.fuzzy;
  const plan = JSON.parse(localStorage.getItem("n2plan") || "{}");
  const dailyNew = plan.dailyNew || 10;
  const milestone = Math.floor(skip / dailyNew);
  if (skip > 0 && milestone > screeningSession.lastMilestone) {
    screeningSession.lastMilestone = milestone;
    showScreeningPause(skip, dailyNew, milestone);
    return;
  }

  renderScreeningCard();
}

function showScreeningPause(skip, dailyNew, milestone) {
  const msg = document.getElementById("sc-pause-msg");
  let text;
  if (milestone === 1) {
    text = `不认识的词已有 ${skip} 个，刚好够今天学了（每日计划 ${dailyNew} 词）。要继续筛，还是先去学习？`;
  } else {
    text = `不认识的词已达 ${skip} 个，是每日计划的 ${milestone} 倍。继续筛出来的词会在之后几天依次安排学习。`;
  }
  if (msg) msg.textContent = text;
  document.getElementById("sc-pause").style.display = "";
}

async function flushScreeningBuffer() {
  if (!screeningSession.buffer.length) return;
  const batch = screeningSession.buffer.splice(0);
  try {
    await apiFetch("/api/n2/screening/batch", {
      method: "POST",
      body: JSON.stringify({ results: batch }),
    });
  } catch {
    screeningSession.buffer.unshift(...batch);
  }
}

async function finishScreening() {
  await flushScreeningBuffer();
  reviewSession.allLoaded = false;
  const toLearn = screeningSession.index - screeningSession.master - screeningSession.fuzzy;
  toast(`筛词完成：完全掌握 ${screeningSession.master}，看懂不熟 ${screeningSession.fuzzy}，待学 ${toLearn}`);
  openVocabEntry();
}

async function quitScreening() {
  const done = screeningSession.index;
  const claimed = screeningSession.master + screeningSession.fuzzy;
  const ok = confirm(
    `退出筛词？\n\n已筛 ${done} 词（掌握 ${claimed} 个）。\n下次继续从未筛词开始。`
  );
  if (!ok) return;
  await flushScreeningBuffer();
  reviewSession.allLoaded = false;
  openVocabEntry();
}

function bindEntryPage() {
  document.getElementById("vocab-start-review").addEventListener("click", startVocabReview);
  document.getElementById("ves-listen-btn").addEventListener("click", startLearnedListening);
  document.getElementById("ves-new-btn").addEventListener("click", openLearnPreview);
  document.getElementById("ves-learned-btn").addEventListener("click", openLearnedVocabList);
  document.getElementById("ves-test-btn").addEventListener("click", startTestSession);
  document.getElementById("ves-screen-btn").addEventListener("click", () => startScreening());
  document.getElementById("ves-reset-btn").addEventListener("click", () => {
    if (confirm("重新设置学习计划？\n\n已有的学习进度不会丢失。")) {
      localStorage.removeItem("n2plan");
      setScreen("screen-onboarding");
    }
  });
}

function bindEvents() {
  document.getElementById("learned-back").addEventListener("click", openVocabEntry);
  document.getElementById("learned-start-listening").addEventListener("click", startLearnedListening);
  document.getElementById("listening-quit").addEventListener("click", quitListeningSession);
  document.getElementById("listen-replay").addEventListener("click", replayListeningItem);
  document.getElementById("listening-again").addEventListener("click", startLearnedListening);
  document.getElementById("listening-done-back").addEventListener("click", openLearnedVocabList);
  document.getElementById("vocab-quit").addEventListener("click", vocabQuit);
  document.getElementById("vocab-reveal").addEventListener("click", vocabReveal);
  document.getElementById("vc-placeholder").addEventListener("click", vocabReveal);
  document.getElementById("vc-word-audio").addEventListener("click", () => {
    playWordAudio(reviewSession.queue[reviewSession.index]);
  });
  document.getElementById("vc-cn-audio").addEventListener("click", () => {
    const word = reviewSession.queue[reviewSession.index];
    playChineseAudio(meaningSummary(word?.meaning || ""));
  });
  document.getElementById("done-continue").addEventListener("click", openVocabEntry);
  document.getElementById("rd-learn-next").addEventListener("click", openLearnPreview);
  document.getElementById("test-back").addEventListener("click", openVocabEntry);
  document.getElementById("test-options").addEventListener("click", (e) => {
    const btn = e.target.closest(".test-opt");
    if (btn && !btn.disabled) testSelectOption(btn.dataset.opt);
  });
  document.getElementById("screen-card").addEventListener("click", (e) => {
    const btn = e.target.closest(".vc-ex-audio");
    if (btn) playWordAudio(btn.dataset.text);
  });
  document.querySelectorAll("[data-result]").forEach((button) => {
    button.addEventListener("click", () => vocabAnswer(button.dataset.result));
  });
  document.querySelectorAll("[data-listen-feedback]").forEach((button) => {
    button.addEventListener("click", () => submitListeningFeedback(button.dataset.listenFeedback));
  });
  // Play buttons via event delegation
  document.getElementById("vocab-learned-list").addEventListener("click", (e) => {
    const btn = e.target.closest(".vl-play");
    if (btn) playWordAudio(btn.dataset.audio);
  });
  document.getElementById("lrv-list").addEventListener("click", (e) => {
    const btn = e.target.closest(".lrv-play");
    if (btn) playWordAudio(btn.dataset.audio);
  });
  // Learn preview
  document.getElementById("lrv-back").addEventListener("click", openVocabEntry);
  document.getElementById("lrv-start").addEventListener("click", startLearnFlow);
  // Learn 6-step
  document.getElementById("sl-quit").addEventListener("click", quitLearnFlow);
  document.getElementById("sl-s1-done").addEventListener("click", learnS1Done);
  document.getElementById("sl-s1-replay").addEventListener("click", learnS1Replay);
  document.getElementById("sl-s2-more").addEventListener("click", learnS2More);
  document.getElementById("sl-s2-done").addEventListener("click", learnS2Done);
  document.getElementById("sl-s3-no").addEventListener("click", learnS3Done);
  document.getElementById("sl-s3-yes").addEventListener("click", learnS3Done);
  document.getElementById("sl-s4-replay").addEventListener("click", learnS4Replay);
  document.getElementById("sl-s4-done").addEventListener("click", learnS4Done);
  document.getElementById("sl-s5-replay").addEventListener("click", learnS5Replay);
  document.getElementById("sl-s5-done").addEventListener("click", learnS5Done);
  document.querySelectorAll("[data-recall]").forEach((btn) => {
    btn.addEventListener("click", () => learnS6Recall(btn.dataset.recall));
  });
  // Learn done
  document.getElementById("sld-done").addEventListener("click", openVocabEntry);
  document.getElementById("sld-more").addEventListener("click", openLearnPreview);
  document.getElementById("sld-review-next").addEventListener("click", startVocabReview);
  document.getElementById("sc-quit").addEventListener("click", quitScreening);
  document.querySelectorAll("[data-sc-result]").forEach((button) => {
    button.addEventListener("click", () => screeningAnswer(button.dataset.scResult));
  });
  document.getElementById("sc-pause-learn").addEventListener("click", () => {
    document.getElementById("sc-pause").style.display = "none";
    finishScreening();
  });
  document.getElementById("sc-pause-keep").addEventListener("click", () => {
    document.getElementById("sc-pause").style.display = "none";
    renderScreeningCard();
  });
}

// ── Learn flow (6-step deep learning) ───────────────────────────────────────

const learnSession = {
  queue: [],
  index: 0,
  step: 1,
  story: null,
  loopToken: 0,
  stepResults: { listened: false, shadowed: false, sawExample: false },
  stats: { switches: 0, words: 0, meaning: 0, listening: 0, reading: 0, usage: 0 },
};

async function openLearnPreview() {
  try {
    const res = await apiFetch("/api/learn/queue");
    if (!res.ok) throw new Error();
    const data = await res.json();
    const words = data.words || [];
    if (!words.length) {
      toast("今日词汇已全部学完");
      return;
    }
    learnSession.queue = words;
    learnSession.index = 0;
    learnSession.stats = { switches: 0, words: 0, meaning: 0, listening: 0, reading: 0, usage: 0 };

    document.getElementById("lrv-hint").textContent = `今天要学 ${words.length} 个新词，快速扫一眼，不用记`;
    document.getElementById("lrv-list").innerHTML = words.map((w) => `
      <div class="lrv-row">
        <div class="lrv-word">${escapeHtml(w.word)}</div>
        <div class="lrv-meaning">${escapeHtml(meaningSummary(w.meaning))}</div>
        <button class="lrv-play" data-audio="${escapeHtml(w.reading || w.word)}" title="播放发音">▶</button>
      </div>
    `).join("");
    setScreen("screen-learn-preview");
  } catch {
    toast("加载今日词汇失败");
  }
}

async function startLearnFlow() {
  learnSession.index = 0;
  setScreen("screen-learn");
  await loadLearnWord();
}

async function loadLearnWord() {
  const word = learnSession.queue[learnSession.index];
  if (!word) { finishLearnSession(); return; }

  learnSession.story = null;
  learnSession.stepResults = { listened: false, shadowed: false, sawExample: false };

  // Fetch story in background; doesn't block word entry
  apiFetch(`/api/learn/story/${encodeURIComponent(word.word)}`)
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => { if (d) learnSession.story = d.story; })
    .catch(() => {});

  populateLearnContent(word);
  enterLearnStep(1);

  // Auto-play for step 1
  document.getElementById("sl-s1-hint").textContent = "正在播放…";
  await playWordAudio(word);
  document.getElementById("sl-s1-hint").textContent = "再次播放或点「有感觉了」";
}

// Extract best example {jp, zh} from word data
// Prefers meaning_detail (has Chinese translation), falls back to examples field
function getBestExample(word) {
  if (word.meaning_detail) {
    const m = word.meaning_detail.match(/（([^｜）]{2,}?)｜([^）]{1,}?)）/);
    if (m) return { jp: m[1].trim(), zh: m[2].trim() };
  }
  const raw = (word.examples || "").split("/").map((s) => s.trim()).filter(Boolean);
  for (const seg of raw) {
    const jp = seg.replace(/\d{4}年\d{2}月[^\s:：]*[：:]\s*/g, "").trim();
    if (jp.length > 4 && /[぀-ヿ㐀-鿿]/.test(jp)) return { jp, zh: "" };
  }
  return null;
}

function populateLearnContent(word) {
  document.getElementById("sl-s1-word").textContent = word.word;
  document.getElementById("sl-s2-word").textContent = word.word;
  document.getElementById("sl-s2-reading").textContent = word.reading || "";
  document.getElementById("sl-s2-meaning").textContent = meaningSummary(word.meaning);
  document.getElementById("sl-s3-word").textContent = word.word;
  document.getElementById("sl-s4-word").textContent = word.word;
  document.getElementById("sl-s4-reading").textContent = word.reading || word.word;
  document.getElementById("sl-s4-meaning").textContent = meaningSummary(word.meaning);
  document.getElementById("sl-s5-word").textContent = word.word;
  document.getElementById("sl-s6-reading").textContent = word.reading || word.word;

  const ex = getBestExample(word);
  document.getElementById("sl-s5-example-jp").textContent = ex ? ex.jp : "（暂无例句）";
  document.getElementById("sl-s5-example-cn").textContent = ex ? ex.zh : "";
}

function enterLearnStep(n) {
  learnSession.step = n;
  for (let i = 1; i <= 6; i++) {
    const panel = document.getElementById(`sl-panel-${i}`);
    panel.style.display = i === n ? "flex" : "none";
  }
  const total = learnSession.queue.length;
  const idx   = learnSession.index;
  document.getElementById("sl-progress-text").textContent = `${idx + 1} / ${total}`;
  document.getElementById("sl-progress-fill").style.width = `${Math.round(idx / total * 100)}%`;
  document.getElementById("sl-step-dots").innerHTML = [1, 2, 3, 4, 5, 6].map((i) => {
    const cls = i < n ? "sl-dot done" : i === n ? "sl-dot active" : "sl-dot";
    return `<div class="${cls}"></div>`;
  }).join("");
}

// Step 1 — 听音
function learnS1Done() {
  learnSession.stepResults.listened = true;
  enterLearnStep(2);
  document.getElementById("sl-s2-badge").textContent = "第 1 次";
  learnLoopAudio(5);
}

function learnS1Replay() {
  playWordAudio(learnSession.queue[learnSession.index]);
}

// Step 2 — 眼耳同步 (audio loop)
async function learnLoopAudio(count) {
  const token = ++learnSession.loopToken;
  const word  = learnSession.queue[learnSession.index];
  for (let i = 0; i < count; i++) {
    if (learnSession.loopToken !== token) return;
    document.getElementById("sl-s2-badge").textContent = `第 ${i + 1} 次`;
    await playWordAudio(word);
    if (learnSession.loopToken !== token) return;
    await sleep(350);
  }
}

function learnS2More() { learnLoopAudio(5); }

function learnS2Done() {
  learnSession.loopToken++;       // cancel any running loop
  enterLearnStep(3);
  learnEnterStep3();
}

// Step 3 — 联想故事 (skip if no story)
function learnEnterStep3() {
  if (!learnSession.story) {
    enterLearnStep(4);
    return;
  }
  document.getElementById("sl-s3-story").textContent = learnSession.story.content;
}

function learnS3Done() { enterLearnStep(4); }

// Step 4 — 跟读
function learnS4Replay() { playWordAudio(learnSession.queue[learnSession.index]); }

function learnS4Done() {
  learnSession.stepResults.shadowed = true;
  enterLearnStep(5);
  learnEnterStep5();
}

// Step 5 — 例句 (skip if no example)
function learnEnterStep5() {
  const word = learnSession.queue[learnSession.index];
  const ex   = getBestExample(word);
  if (!ex) {
    enterLearnStep(6);
    return;
  }
  learnSession.stepResults.sawExample = true;
  playWordAudio(ex.jp).catch(() => {});
}

function learnS5Replay() {
  const word = learnSession.queue[learnSession.index];
  const ex   = getBestExample(word);
  if (ex) playWordAudio(ex.jp).catch(() => {});
}

function learnS5Done() { enterLearnStep(6); }

// Step 6 — 延迟回想
async function learnS6Recall(recall) {
  const word = learnSession.queue[learnSession.index];
  const { listened, shadowed, sawExample } = learnSession.stepResults;

  try {
    const res = await apiFetch("/api/learn/complete", {
      method: "POST",
      body: JSON.stringify({
        word: word.word,
        recall,
        listened,
        shadowed,
        saw_example: sawExample,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      const lit  = data.switches_lit || 0;
      learnSession.stats.switches  += lit;
      learnSession.stats.words     += 1;
      if (recall !== "again") learnSession.stats.meaning++;
      learnSession.stats.listening++;
      if (shadowed)    learnSession.stats.reading++;
      if (sawExample && word.collocation) learnSession.stats.usage++;
    }
  } catch {}

  learnSession.index++;
  if (learnSession.index >= learnSession.queue.length) {
    finishLearnSession();
  } else {
    await loadLearnWord();
  }
}

async function finishLearnSession() {
  learnSession.loopToken++;
  try { reviewAudio.pause(); } catch {}

  const s = learnSession.stats;
  document.getElementById("sld-switches-num").textContent = s.switches;

  const total = learnSession.queue.length || 1;
  const barItems = [
    { label: "意思识别", count: s.meaning },
    { label: "听音识别", count: s.listening },
    { label: "读音掌握", count: s.reading },
    { label: "用法掌握", count: s.usage },
  ].filter((item) => item.count > 0);

  document.getElementById("sld-bars").innerHTML = barItems.length
    ? barItems.map(({ label, count }) => {
        const pct = Math.round((count / total) * 100);
        return `<div class="sld-bar-row">
          <div class="sld-bar-meta">
            <span class="sld-bar-label">${label}</span>
            <span class="sld-bar-count">${count} / ${total} 词</span>
          </div>
          <div class="sld-bar-track"><div class="sld-bar-fill" style="width:${pct}%"></div></div>
        </div>`;
      }).join("")
    : `<div style="font-size:13px;color:#a0aec0;text-align:center">今日第一次学习</div>`;

  // Check if more new words are available
  const moreBtn = document.getElementById("sld-more");
  moreBtn.style.display = "none";
  try {
    const res = await apiFetch("/api/learn/queue");
    if (res.ok) {
      const data = await res.json();
      const moreCount = (data.words || []).length;
      if (moreCount > 0) {
        moreBtn.textContent = `再学 ${moreCount} 词 →`;
        moreBtn.style.display = "";
      }
    }
  } catch {}

  // Check if review is pending
  const hint = document.getElementById("sld-next-hint");
  const reviewNextBtn = document.getElementById("sld-review-next");
  hint.style.display = "none";
  reviewNextBtn.style.display = "none";
  try {
    const res = await apiFetch("/api/n2/vocab/stats");
    if (res.ok) {
      const data = await res.json();
      const due = data.due || 0;
      if (due > 0) {
        hint.textContent = `今日还有 ${due} 个词待复习`;
        hint.style.display = "";
        reviewNextBtn.textContent = `去复习 ${due} 词 →`;
        reviewNextBtn.style.display = "";
      } else {
        hint.textContent = "今日任务全部完成 🎉";
        hint.style.display = "";
      }
    }
  } catch {}

  setScreen("screen-learn-done");
}

async function quitLearnFlow() {
  const ok = confirm("退出学习？\n\n当前单词不会保存，之前的词已记录。");
  if (!ok) return;
  learnSession.loopToken++;
  try { reviewAudio.pause(); } catch {}
  openVocabEntry();
}

// ── Usage Test Session ────────────────────────────────────────────────────────

const testSession = {
  queue: [],
  index: 0,
  currentQ: null,   // {q_type, question, options, answer, explanation}
  answered: false,
  stats: { total: 0, passed: 0, retry: 0 },
};

async function startTestSession() {
  try {
    const res = await apiFetch("/api/test/queue");
    if (!res.ok) throw new Error();
    const data = await res.json();
    const queue = data.queue || [];
    if (!queue.length) {
      toast("暂无需要测验的词");
      return;
    }
    testSession.queue = queue;
    testSession.index = 0;
    testSession.stats = { total: 0, passed: 0, retry: 0 };
    setScreen("screen-test");
    document.getElementById("test-main").style.display = "";
    document.getElementById("test-done").style.display = "none";
    await loadTestWord();
  } catch {
    toast("加载测验队列失败");
  }
}

const _Q_LABELS = {
  meaning_mcq:   "意思识别",
  reading_mcq:   "读音掌握",
  listening_mcq: "听音识别",
  context_mcq:   "文脈理解",
  fill_word:     "挖词",
  fill_particle: "填助词",
};

async function loadTestWord() {
  const word = testSession.queue[testSession.index];
  if (!word) {
    finishTestSession();
    return;
  }

  updateTestProgress();

  try {
    const res = await apiFetch(`/api/test/question/${encodeURIComponent(word.word)}`);
    if (!res.ok) throw new Error();
    const data = await res.json();

    testSession.currentQ = data;
    testSession.answered  = false;

    const isListening = data.q_type === "listening_mcq";
    const isContext   = data.q_type === "context_mcq";
    const isUsage     = data.q_type === "fill_word" || data.q_type === "fill_particle";

    // Hide word for listening (only audio cue) and context (word is the answer)
    // fill_word: word is the answer — hide word/reading/meaning; context sentence is the only clue
    const hideWord = isListening || isContext || data.q_type === "fill_word";
    document.getElementById("test-word").textContent    = hideWord ? "？？？" : data.word;
    const testReadingEl = document.getElementById("test-reading");
    testReadingEl.textContent = "";
    testReadingEl.style.display = "none";
    // Never reveal the Chinese translation before an ability-test answer.
    const testMeaningEl = document.getElementById("test-meaning");
    testMeaningEl.textContent = "";
    testMeaningEl.style.display = "none";

    // Streak dots: only show for usage (fill_word/fill_particle)
    const streakRow = document.querySelector(".test-streak-row");
    if (streakRow) streakRow.style.display = isUsage ? "" : "none";
    const streak = data.streak || 0;
    document.getElementById("test-dot-1").className =
      "test-streak-dot" + (streak >= 1 ? " filled" : "");
    document.getElementById("test-dot-2").className =
      "test-streak-dot" + (streak >= 2 ? " filled" : "");

    // Question text
    const label = _Q_LABELS[data.q_type] || data.q_type;
    const qEl = document.getElementById("test-question");
    if (isListening) {
      qEl.innerHTML =
        `<span class="test-q-label">${label}</span>` +
        `<button class="test-replay-btn" id="test-replay">▶ 再听一次</button>`;
      document.getElementById("test-replay").addEventListener("click", () => {
        playWordAudio(data.audio_word || data.word);
      });
    } else if (isUsage || data.q_type === "context_mcq") {
      qEl.innerHTML =
        `<span class="test-q-label">${label}</span>` +
        escapeHtml(data.question).replace("＿＿", '<span class="test-blank">＿＿</span>');
    } else {
      // meaning / reading
      const promptText = data.q_type === "meaning_mcq" ? "这个词的意思是？" : "这个词的读音是？";
      qEl.innerHTML =
        `<span class="test-q-label">${label}</span> ${escapeHtml(promptText)}`;
    }

    // Options
    const optEl = document.getElementById("test-options");
    optEl.innerHTML = (data.options || []).map((opt) =>
      `<button class="test-opt" data-opt="${escapeHtml(opt)}">${escapeHtml(opt)}</button>`
    ).join("");

    document.getElementById("test-feedback").style.display = "none";
    document.getElementById("test-next-btn").style.display = "none";

    // Auto-play audio for listening test
    if (isListening) {
      playWordAudio(data.audio_word || data.word).catch(() => {});
    }
  } catch {
    toast("加载题目失败，跳过该词");
    testSession.index++;
    await loadTestWord();
  }
}

async function testSelectOption(opt) {
  if (testSession.answered) return;
  testSession.answered = true;

  const q = testSession.currentQ;
  if (!q) return;

  // Visually mark selected option
  document.querySelectorAll(".test-opt").forEach((btn) => {
    btn.disabled = true;
    if (btn.dataset.opt === opt) btn.classList.add("test-opt--selected");
  });

  try {
    const res = await apiFetch("/api/test/answer", {
      method: "POST",
      body: JSON.stringify({ word: q.word, q_type: q.q_type, answer: opt }),
    });
    if (!res.ok) throw new Error();
    const data = await res.json();

    const correct = data.correct;
    const feedbackEl = document.getElementById("test-feedback");

    // Mark options correct/wrong
    document.querySelectorAll(".test-opt").forEach((btn) => {
      if (btn.dataset.opt === data.correct_answer) btn.classList.add("test-opt--correct");
      else if (btn.dataset.opt === opt && !correct) btn.classList.add("test-opt--wrong");
    });

    // Update streak dots immediately
    const streak = data.streak || 0;
    document.getElementById("test-dot-1").className =
      "test-streak-dot" + (streak >= 1 ? " filled" : "");
    document.getElementById("test-dot-2").className =
      "test-streak-dot" + (streak >= 2 ? " filled" : "");

    // Reveal the complete word card only after the answer has been submitted.
    const testMeaningEl = document.getElementById("test-meaning");
    testMeaningEl.textContent = meaningSummary(q.meaning);
    testMeaningEl.style.display = "";
    const testReadingEl = document.getElementById("test-reading");
    testReadingEl.textContent = q.reading;
    testReadingEl.style.display = "";
    if (q.q_type === "context_mcq" || q.q_type === "listening_mcq" || q.q_type === "fill_word") {
      document.getElementById("test-word").textContent    = q.word;
    }

    // Feedback text
    let feedbackText = correct ? "正确 ✓" : `错误 ✗  正确答案：${data.correct_answer}`;
    if (data.explanation) feedbackText += `\n${data.explanation}`;
    feedbackEl.textContent = feedbackText;
    feedbackEl.className   = "test-feedback " + (correct ? "test-feedback--ok" : "test-feedback--err");
    feedbackEl.style.display = "";

    testSession.stats.total++;

    // Word is fully done when server returns no next_q_type
    const wordDone = data.next_q_type === null || data.next_q_type === undefined;
    if (wordDone) {
      testSession.stats.passed++;
    } else if (!correct && data.streak === 0) {
      testSession.stats.retry++;
    }

    // Decide next step
    if (wordDone) {
      showTestNextBtn("下一词 →", async () => {
        testSession.index++;
        await loadTestWord();
      });
    } else if (correct && data.next_q_type) {
      // Continue to next stage for this word
      showTestNextBtn("继续 →", () => loadTestWord());
    } else {
      // Wrong answer — move to next word
      showTestNextBtn("下一词 →", async () => {
        testSession.index++;
        await loadTestWord();
      });
    }
  } catch {
    toast("提交答案失败");
    testSession.answered = false;
    document.querySelectorAll(".test-opt").forEach((btn) => { btn.disabled = false; });
  }
}

function showTestNextBtn(label, handler) {
  const btn = document.getElementById("test-next-btn");
  btn.textContent = label;
  btn.style.display = "";
  btn.onclick = handler;
}

function updateTestProgress() {
  const total = testSession.queue.length;
  const idx   = testSession.index;
  document.getElementById("test-progress-text").textContent = `${idx + 1} / ${total}`;
  document.getElementById("test-progress-fill").style.width =
    `${Math.round(idx / total * 100)}%`;
}

function finishTestSession() {
  const s = testSession.stats;
  document.getElementById("td-total").textContent  = s.total;
  document.getElementById("td-passed").textContent = s.passed;
  document.getElementById("td-retry").textContent  = s.retry;
  document.getElementById("test-main").style.display = "none";
  document.getElementById("test-done").style.display = "";
  // Invalidate vocab cache
  reviewSession.allLoaded = false;
}

// ── Bug report ───────────────────────────────────────────────────────────────

function _currentScreen() {
  const active = document.querySelector(".screen.active");
  return active ? active.id : "";
}

function openBugReport() {
  document.getElementById("bug-text").value = "";
  document.getElementById("bug-overlay").style.display = "";
  setTimeout(() => document.getElementById("bug-text").focus(), 50);
}

function closeBugReport() {
  document.getElementById("bug-overlay").style.display = "none";
}

async function submitBug() {
  const text = document.getElementById("bug-text").value.trim();
  if (!text) { toast("请先描述问题"); return; }
  const btn = document.getElementById("bug-submit");
  btn.disabled = true;
  try {
    const res = await apiFetch("/api/bugs", {
      method: "POST",
      body: JSON.stringify({ description: text, screen: _currentScreen() }),
    });
    if (res.ok) {
      closeBugReport();
      toast("已提交，谢谢反馈！");
    } else {
      toast("提交失败，请重试");
    }
  } catch {
    toast("网络错误");
  } finally {
    btn.disabled = false;
  }
}

// ── App init ─────────────────────────────────────────────────────────────────

async function appInit() {
  const token = localStorage.getItem("auth_token");
  if (token) {
    try {
      const res = await fetch(`${API}/api/auth/me`, {
        headers: { "Authorization": `Bearer ${token}` },
      });
      if (res.ok) {
        await _afterAuth();
        return;
      }
    } catch {}
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_username");
  }
  setScreen("screen-auth");
}

bindEvents();
bindEntryPage();
appInit();
