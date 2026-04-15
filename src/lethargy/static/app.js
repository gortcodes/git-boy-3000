"use strict";

const STAT_ORDER_V1 = ["STR", "DEX", "CON", "INT", "WIS", "CHA"];
const STAT_ORDER_V2 = ["STR", "AGI", "END", "INT", "PER", "CHA", "LUCK"];

const form = document.getElementById("lookup-form");
const usernameInput = document.getElementById("username-input");
const statusEl = document.getElementById("status");
const sheetEl = document.getElementById("sheet");
const sheetUsernameEl = document.getElementById("sheet-username");
const sheetEngineVersionEl = document.getElementById("sheet-engine-version");
const sheetCacheStatusEl = document.getElementById("sheet-cache-status");
const shareButton = document.getElementById("share-button");
const statsGridEl = document.getElementById("stats-grid");
const flavorBodyEl = document.getElementById("flavor-body");
const rawBodyEl = document.getElementById("raw-body");

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const username = usernameInput.value.trim();
  if (!username) return;
  loadSheet(username);
});

shareButton.addEventListener("click", async () => {
  const username = usernameInput.value.trim();
  if (!username) return;
  const url = `${window.location.origin}/?u=${encodeURIComponent(username)}`;
  try {
    await navigator.clipboard.writeText(url);
    const original = shareButton.textContent;
    shareButton.textContent = "Copied!";
    setTimeout(() => {
      shareButton.textContent = original;
    }, 1500);
  } catch (err) {
    setStatus(`could not copy: ${err.message}`, true);
  }
});

const params = new URLSearchParams(window.location.search);
const initialUsername = params.get("u");
if (initialUsername) {
  usernameInput.value = initialUsername;
  loadSheet(initialUsername);
}

async function loadSheet(username) {
  setStatus(`looking up ${username}...`);
  sheetEl.classList.add("hidden");

  try {
    const response = await fetch(
      `/v1/sheet/${encodeURIComponent(username)}/raw`
    );
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const detail = body.detail || `HTTP ${response.status}`;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    const data = await response.json();
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

function renderSheet(data, headers) {
  sheetEl.classList.remove("hidden");
  sheetUsernameEl.textContent = data.username;
  sheetCacheStatusEl.textContent = `cache: ${headers.get("x-cache-status") || "?"}`;

  if (data.engine_version === 2) {
    renderSheetV2(data);
  } else {
    renderSheetV1(data);
  }
}

function renderSheetV1(data) {
  sheetEngineVersionEl.textContent = `engine v${data.engine_version}`;

  statsGridEl.innerHTML = "";
  for (const name of STAT_ORDER_V1) {
    const stat = data.stats[name];
    if (!stat) continue;
    const card = document.createElement("div");
    card.className = "stat";
    card.innerHTML = `
      <div class="stat-name">${name}</div>
      <div class="stat-value">${stat.value}</div>
      <div class="stat-raw">raw ${stat.raw_score.toFixed(1)}</div>
      <div class="stat-bar"><div class="stat-bar-fill" style="width: ${
        (stat.value / 20) * 100
      }%"></div></div>
    `;
    statsGridEl.appendChild(card);
  }

  flavorBodyEl.innerHTML = "";
  const dl = document.createElement("dl");
  const rows = [
    ["account age", `${data.flavor.account_age_days ?? 0} days`],
    ["activity span", `${data.flavor.activity_span_days ?? 0} days`],
    ["current streak", `${data.flavor.current_streak_days ?? 0} days`],
    ["longest streak", `${data.flavor.longest_streak_days ?? 0} days`],
    [
      "restricted contributions",
      data.flavor.restricted_contribution_count ?? 0,
    ],
  ];
  for (const [key, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.textContent = value;
    dl.appendChild(dt);
    dl.appendChild(dd);
  }
  const wrapper = document.createElement("div");
  wrapper.className = "flavor-body";
  wrapper.appendChild(dl);
  flavorBodyEl.appendChild(wrapper);

  rawBodyEl.textContent = JSON.stringify(data.signals, null, 2);
}

function renderSheetV2(data) {
  const klass = data.class_name || "Engineer";
  sheetEngineVersionEl.textContent = `LVL ${data.character_level} · ${klass}`;

  statsGridEl.innerHTML = "";
  for (const name of STAT_ORDER_V2) {
    const stat = data.stats[name];
    if (!stat) continue;
    const card = document.createElement("div");
    card.className = "stat stat-v2";
    const subStatRows = (stat.sub_stats || [])
      .map(
        (s) =>
          `<li><span class="sub-name">${s.name}</span><span class="sub-level">${s.level}</span></li>`
      )
      .join("");
    card.innerHTML = `
      <div class="stat-name">${name}</div>
      <div class="stat-display">${stat.display}</div>
      <div class="stat-value">${stat.level}</div>
      <ul class="sub-stats">${subStatRows}</ul>
    `;
    statsGridEl.appendChild(card);
  }

  flavorBodyEl.innerHTML = "";
  const dl = document.createElement("dl");
  const rows = [
    ["account age", `${data.flavor.account_age_days ?? 0} days`],
    ["activity span", `${data.flavor.activity_span_days ?? 0} days`],
    ["current streak", `${data.flavor.current_streak_days ?? 0} days`],
    ["longest streak", `${data.flavor.longest_streak_days ?? 0} days`],
    ["active weeks", `${data.flavor.weekly_active_weeks ?? 0} / 52`],
  ];
  for (const [key, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.textContent = value;
    dl.appendChild(dt);
    dl.appendChild(dd);
  }
  const wrapper = document.createElement("div");
  wrapper.className = "flavor-body";
  wrapper.appendChild(dl);
  flavorBodyEl.appendChild(wrapper);

  rawBodyEl.textContent = JSON.stringify(data.signals, null, 2);
}
