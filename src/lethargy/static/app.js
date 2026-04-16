"use strict";

const STAT_ORDER_V2 = ["STR", "PER", "END", "CHA", "INT", "AGI", "LUCK"];
const STAT_ORDER_V1 = ["STR", "DEX", "CON", "INT", "WIS", "CHA"];

const STAT_DISPLAY_NAMES_V2 = {
  STR: "Strength",
  PER: "Perception",
  END: "Endurance",
  CHA: "Charisma",
  INT: "Intelligence",
  AGI: "Agility",
  LUCK: "Luck",
};

const STAT_DISPLAY_NAMES_V1 = {
  STR: "Strength",
  DEX: "Dexterity",
  CON: "Constitution",
  INT: "Intelligence",
  WIS: "Wisdom",
  CHA: "Charisma",
};

const STAT_DESCRIPTIONS_V2 = {
  STR: "Raw infrastructure presence. Rolls helm charts, terraform modules, and Dockerfiles across your public repos. High STR means you build the things that keep other things running.",
  PER: "Watching the systems that watch the systems. Prometheus configs, Grafana dashboards, OpenTelemetry pipelines. High PER means you see your own failures before your users do.",
  END: "Long-haul presence in the git log. Commit streaks, PR throughput, and raw yearly commit count, each on a log2 curve. END rewards showing up, not sprinting.",
  CHA: "Working with and through other humans. PR reviews, issue comments, and activity on repos you don't own. High CHA means you block on nothing and unblock everyone.",
  INT: "Programming breadth by primary language. Rolls Python, JavaScript, and TypeScript repositories — whichever language wins the byte count in a repo, counts once.",
  AGI: "Automation reflexes. GitHub Actions workflows, Jenkins pipelines, GitLab CI configs. High AGI means a machine does the boring work for you.",
  LUCK: "Rolling with machines. Commits with AI co-author trailers, CLAUDE.md files, cursor and copilot instructions. The stat that wasn't possible two years ago.",
};

const STAT_DESCRIPTIONS_V1 = {
  STR: "Raw commit volume over the last year, squash-safe via the GraphQL authoritative count.",
  DEX: "Recent cadence and current streak length.",
  CON: "Sustained, low-variance weekly activity.",
  INT: "Breadth across distinct public repos touched, plus public gist count.",
  WIS: "Seniority weighted by review-to-commit ratio.",
  CHA: "Collaboration on repos you do not own.",
};

const SUB_STAT_DESCRIPTIONS = {
  helm: { parent: "STR", text: "Public repos containing a Chart.yaml or values.yaml file." },
  terraform: { parent: "STR", text: "Public repos containing any .tf or .tfvars file." },
  docker: { parent: "STR", text: "Public repos containing a Dockerfile." },
  prometheus: { parent: "PER", text: "Public repos containing prometheus.yml or a prometheus/ directory." },
  grafana: { parent: "PER", text: "Public repos with a grafana/ directory or embedded dashboard JSON." },
  otel: { parent: "PER", text: "Public repos with otel-* or opentelemetry-* YAML configs." },
  streak: { parent: "END", text: "round(log2(longest_streak_days + 1) × 0.5). Long streak = log curve points." },
  commits: { parent: "END", text: "round(log2(total_commit_contributions + 1) × 1.0). Year-over-year commit volume from GraphQL." },
  prs: { parent: "END", text: "round(log2(total_pr_contributions + 1) × 1.5). PRs weigh more than raw commits." },
  reviews: { parent: "CHA", text: "round(log2(total_pr_review_contributions + 1) × 1.2). PR reviews on any repo." },
  issue_comments: { parent: "CHA", text: "round(log2(issue_comment_events + 1) × 0.8). Issue comments in the recent public event window." },
  external_repos: { parent: "CHA", text: "Distinct non-owned repos you touched in your recent public events. Raw count." },
  python: { parent: "INT", text: "Public repos where Python is the primary language by byte count." },
  javascript: { parent: "INT", text: "Public repos where JavaScript is the primary language by byte count." },
  typescript: { parent: "INT", text: "Public repos where TypeScript is the primary language by byte count." },
  github_actions: { parent: "AGI", text: "Public repos with any .github/workflows/*.yml or .yaml file." },
  gitlab_ci: { parent: "AGI", text: "Public repos containing a .gitlab-ci.yml file." },
  jenkins: { parent: "AGI", text: "Public repos containing a Jenkinsfile." },
  ai_trailers: { parent: "LUCK", text: "Push-event commits whose message contains a Co-Authored-By: Claude/Copilot/ChatGPT/GPT trailer." },
  ai_configs: { parent: "LUCK", text: "Public repos containing CLAUDE.md, .cursorrules, or .github/copilot-instructions.md." },
};

// === DOM refs ===
const form = document.getElementById("lookup-form");
const usernameInput = document.getElementById("username-input");
const statusEl = document.getElementById("status");
const sheetEl = document.getElementById("sheet");

const characterUsernameEl = document.getElementById("character-username");
const shareButton = document.getElementById("share-button");

const topTabButtons = document.querySelectorAll(".top-tab");
const subTabRow = document.getElementById("sub-tab-row");
const subTabButtons = document.querySelectorAll(".sub-tab");

const tabPlaceholder = document.getElementById("tab-placeholder");
const tabStatus = document.getElementById("tab-status");
const tabSpecial = document.getElementById("tab-special");
const tabSkills = document.getElementById("tab-skills");

const statusListEl = document.getElementById("status-list");
const avatarEl = document.getElementById("avatar");
const statusTitleEl = document.getElementById("status-title");
const statusDescEl = document.getElementById("status-desc");

const statListEl = document.getElementById("stat-list");
const specialAvatarEl = document.getElementById("special-avatar");
const statDetailNameEl = document.getElementById("stat-detail-name");
const statDetailDescEl = document.getElementById("stat-detail-desc");
const statDetailSubsEl = document.getElementById("stat-detail-subs");

const skillListEl = document.getElementById("skill-list");
const skillDetailNameEl = document.getElementById("skill-detail-name");
const skillDetailDescEl = document.getElementById("skill-detail-desc");
const skillDetailRatingEl = document.getElementById("skill-detail-rating");
const skillDetailParentEl = document.getElementById("skill-detail-parent");

const hpValueEl = document.getElementById("hp-value");
const levelValueEl = document.getElementById("level-value");
const apValueEl = document.getElementById("ap-value");

const ALL_TAB_PANELS = [tabPlaceholder, tabStatus, tabSpecial, tabSkills];

let currentData = null;

// === Form ===
form.addEventListener("submit", (event) => {
  event.preventDefault();
  const username = usernameInput.value.trim();
  if (!username) return;
  loadSheet(username);
});

// === Share ===
shareButton.addEventListener("click", async () => {
  if (!currentData) return;
  const url = `${window.location.origin}/?u=${encodeURIComponent(currentData.username)}`;
  try {
    await navigator.clipboard.writeText(url);
    const original = shareButton.textContent;
    shareButton.textContent = "COPIED!";
    setTimeout(() => { shareButton.textContent = original; }, 1500);
  } catch (err) {
    setStatus(`clipboard failed: ${err.message}`, true);
  }
});

// Auto-load via ?u=
const params = new URLSearchParams(window.location.search);
const initialUsername = params.get("u");
if (initialUsername) {
  usernameInput.value = initialUsername;
  loadSheet(initialUsername);
}

// === Top-level tabs ===
topTabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const top = btn.dataset.top;
    topTabButtons.forEach((b) => b.classList.toggle("active", b === btn));

    if (top === "stat") {
      subTabRow.style.display = "";
      showSubTab(document.querySelector(".sub-tab.active").dataset.tab);
    } else {
      subTabRow.style.display = "none";
      showPanel(tabPlaceholder);
    }
  });
});

// === Sub-tabs ===
subTabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    subTabButtons.forEach((b) => b.classList.toggle("active", b === btn));
    showSubTab(btn.dataset.tab);
  });
});

function showSubTab(tab) {
  const map = { status: tabStatus, special: tabSpecial, skills: tabSkills };
  showPanel(map[tab] || tabStatus);
}

function showPanel(panel) {
  ALL_TAB_PANELS.forEach((p) => p.classList.toggle("hidden", p !== panel));
}

// === Loading ===
async function loadSheet(username) {
  setStatus(`ROLLING ${username.toUpperCase()}...`);
  sheetEl.classList.add("hidden");

  try {
    const response = await fetch(`/v1/sheet/${encodeURIComponent(username)}/raw`);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const detail = body.detail || `HTTP ${response.status}`;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    const data = await response.json();
    currentData = data;
    renderSheet(data, response.headers);
    const cacheStatus = response.headers.get("x-cache-status") || "?";
    setStatus(`engine v${data.engine_version} · ${cacheStatus}`);
  } catch (err) {
    setStatus(`error: ${err.message}`, true);
  }
}

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", isError);
}

// === Rendering ===
function renderSheet(data, headers) {
  sheetEl.classList.remove("hidden");

  const isV2 = data.engine_version === 2;
  const avatarUrl = `https://github.com/${encodeURIComponent(data.username)}.png?size=200`;

  characterUsernameEl.textContent = data.username;

  // Avatars (STATUS + SPECIAL tabs share the same image)
  avatarEl.src = avatarUrl;
  avatarEl.alt = `${data.username} avatar`;
  specialAvatarEl.src = avatarUrl;
  specialAvatarEl.alt = `${data.username} avatar`;

  // Reset to STAT > STATUS
  topTabButtons.forEach((b) => b.classList.toggle("active", b.dataset.top === "stat"));
  subTabRow.style.display = "";
  subTabButtons.forEach((b) => b.classList.toggle("active", b.dataset.tab === "status"));
  showSubTab("status");

  // SKILLS tab visibility (v2 only)
  const skillsBtn = document.querySelector('[data-tab="skills"]');
  if (skillsBtn) skillsBtn.style.display = isV2 ? "" : "none";

  renderStatusTab(data);
  renderSpecialTab(data);
  if (isV2) renderSkillsTab(data);
  renderStatusBar(data);
}

// === STATUS tab ===
function renderStatusTab(data) {
  const isV2 = data.engine_version === 2;
  const klass = data.class_name || (isV2 ? "Engineer" : "Initiate");

  statusListEl.innerHTML = "";
  const items = [
    ["class", klass],
    ["account age", `${data.flavor.account_age_days ?? 0} days`],
    ["activity span", `${data.flavor.activity_span_days ?? 0} days`],
    ["current streak", `${data.flavor.current_streak_days ?? 0} days`],
    ["longest streak", `${data.flavor.longest_streak_days ?? 0} days`],
  ];
  if (isV2) {
    items.push(["active weeks", `${data.flavor.weekly_active_weeks ?? 0} / 52`]);
  }

  for (const [key, value] of items) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="label">${key}</span><span class="level">${value}</span>`;
    statusListEl.appendChild(li);
  }

  statusTitleEl.textContent = data.username;
  statusDescEl.textContent = isV2
    ? `Level ${data.character_level} ${klass}. ${Object.keys(data.stats).length} SPECIAL stats tracked across ${
        Object.values(data.stats).reduce((n, s) => n + (s.sub_stats?.length || 0), 0)
      } sub-skills.`
    : `Engine v${data.engine_version}. ${Object.keys(data.stats).length} stats tracked.`;
}

// === SPECIAL tab ===
function renderSpecialTab(data) {
  const isV2 = data.engine_version === 2;
  const order = isV2 ? STAT_ORDER_V2 : STAT_ORDER_V1;

  statListEl.innerHTML = "";
  for (const key of order) {
    const stat = data.stats[key];
    if (!stat) continue;
    const li = document.createElement("li");
    li.dataset.stat = key;
    const value = isV2 ? stat.level : stat.value;
    const displayName = (isV2 ? STAT_DISPLAY_NAMES_V2 : STAT_DISPLAY_NAMES_V1)[key] || key;
    li.innerHTML = `<span class="label">${displayName}</span><span class="level">${value}</span>`;
    li.addEventListener("click", () => selectStat(key, data));
    statListEl.appendChild(li);
  }

  if (order.length > 0) selectStat(order[0], data);
}

function selectStat(key, data) {
  statListEl.querySelectorAll("li").forEach((li) => {
    li.classList.toggle("selected", li.dataset.stat === key);
  });

  const stat = data.stats[key];
  if (!stat) return;
  const isV2 = data.engine_version === 2;
  const displayNames = isV2 ? STAT_DISPLAY_NAMES_V2 : STAT_DISPLAY_NAMES_V1;
  const descriptions = isV2 ? STAT_DESCRIPTIONS_V2 : STAT_DESCRIPTIONS_V1;

  statDetailNameEl.textContent = displayNames[key] || key;
  statDetailDescEl.textContent = descriptions[key] || "—";

  statDetailSubsEl.innerHTML = "";
  if (isV2 && Array.isArray(stat.sub_stats)) {
    for (const sub of stat.sub_stats) {
      const dt = document.createElement("dt");
      dt.textContent = sub.name;
      const dd = document.createElement("dd");
      dd.textContent = sub.level;
      statDetailSubsEl.appendChild(dt);
      statDetailSubsEl.appendChild(dd);
    }
  } else if (!isV2 && stat.inputs && typeof stat.inputs === "object") {
    for (const [k, v] of Object.entries(stat.inputs)) {
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = typeof v === "number" ? v.toFixed(1) : String(v);
      statDetailSubsEl.appendChild(dt);
      statDetailSubsEl.appendChild(dd);
    }
  }
}

// === SKILLS tab (v2 only) ===
function renderSkillsTab(data) {
  skillListEl.innerHTML = "";
  const flattened = [];
  for (const parentKey of STAT_ORDER_V2) {
    const stat = data.stats[parentKey];
    if (!stat || !Array.isArray(stat.sub_stats)) continue;
    for (const sub of stat.sub_stats) {
      flattened.push({ parent: parentKey, name: sub.name, level: sub.level });
    }
  }

  for (const sub of flattened) {
    const li = document.createElement("li");
    li.dataset.skill = sub.name;
    li.innerHTML = `
      <span class="label">${sub.name}</span>
      <span class="level">${sub.level}<span class="parent-stat"> ${sub.parent}</span></span>
    `;
    li.addEventListener("click", () => selectSkill(sub));
    skillListEl.appendChild(li);
  }

  if (flattened.length > 0) selectSkill(flattened[0]);
}

function selectSkill(sub) {
  skillListEl.querySelectorAll("li").forEach((li) => {
    li.classList.toggle("selected", li.dataset.skill === sub.name);
  });

  const meta = SUB_STAT_DESCRIPTIONS[sub.name] || {};
  skillDetailNameEl.textContent = sub.name;
  skillDetailDescEl.textContent = meta.text || "—";

  const parentDisplay = STAT_DISPLAY_NAMES_V2[sub.parent] || sub.parent;
  skillDetailParentEl.textContent = `under: ${parentDisplay}`;

  const maxStars = 10;
  const filled = Math.min(maxStars, Math.max(0, sub.level));
  const stars = [];
  for (let i = 0; i < maxStars; i++) {
    stars.push(`<span class="star ${i < filled ? "filled" : ""}">${i < filled ? "★" : "☆"}</span>`);
  }
  const overflow = sub.level > maxStars ? `+${sub.level - maxStars}` : "";
  skillDetailRatingEl.innerHTML = `${stars.join("")} <span class="level-num">${sub.level}${overflow ? " " + overflow : ""}</span>`;
}

// === Status bar: HP / LEVEL / AP ===
function renderStatusBar(data) {
  const isV2 = data.engine_version === 2;

  if (isV2) {
    const level = data.character_level || 0;
    const end = data.stats.END?.level || 1;
    const agi = data.stats.AGI?.level || 1;
    const klass = data.class_name || "Engineer";

    // HP = 80 + Endurance × 5 + (Level - 1) × floor(Endurance/2 + 2.5)
    const hp = 80 + end * 5 + (level - 1) * Math.floor(end / 2 + 2.5);
    // AP = 60 + 10 × Agility
    const ap = 60 + 10 * agi;

    hpValueEl.textContent = `${hp}/${hp}`;
    levelValueEl.textContent = `${level} · ${klass}`;
    apValueEl.textContent = String(ap);
  } else {
    hpValueEl.textContent = "--/--";
    levelValueEl.textContent = `v${data.engine_version}`;
    apValueEl.textContent = "--";
  }
}
