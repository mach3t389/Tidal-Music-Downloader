const state = {
  qualityLabels: [],
  defaultPath: "",
  previewTracks: [],
  running: false,
  counts: { downloaded: 0, skipped: 0 },
};

function el(id) { return document.getElementById(id); }

function populateQualitySelect(select) {
  select.innerHTML = "";
  for (const label of state.qualityLabels) {
    const option = document.createElement("option");
    option.value = label;
    option.textContent = label;
    if (label === "High") option.selected = true;
    select.appendChild(option);
  }
}

function setBanner(text, kind) {
  const banner = el("status-banner");
  banner.classList.remove("hidden", "error");
  if (kind === "error") banner.classList.add("error");
  el("status-text").textContent = text;
}

function hideBanner() {
  el("status-banner").classList.add("hidden");
  el("cancel-button").classList.add("hidden");
  el("open-folder-button").classList.add("hidden");
}

function appendLog(text) {
  const out = el("log-output");
  out.textContent += text + "\n";
  out.scrollTop = out.scrollHeight;
}

function renderPreview(tracks) {
  state.previewTracks = tracks;
  const container = el("preview-list");
  container.classList.remove("hidden");
  container.innerHTML = "";
  for (const track of tracks) {
    const row = document.createElement("div");
    row.className = "track-row";
    row.dataset.title = track.title;

    const label = document.createElement("span");
    label.textContent = `${track.artist} - ${track.title}`;

    const status = document.createElement("span");
    status.className = "track-status";
    status.textContent = "en attente";

    row.appendChild(label);
    row.appendChild(status);
    container.appendChild(row);
  }
}

function normalizeTitle(title) {
  return title.trim().toLowerCase();
}

function markTrack(title, status) {
  const target = normalizeTitle(title);
  const rows = document.querySelectorAll("#preview-list .track-row");
  for (const row of rows) {
    if (normalizeTitle(row.dataset.title) === target) {
      const statusEl = row.querySelector(".track-status");
      statusEl.textContent = status === "downloaded" ? "telechargee" : "deja presente";
      statusEl.className = "track-status " + status;
      return;
    }
  }
}

function setRunning(running) {
  state.running = running;
  el("favorites-start").disabled = running;
  el("link-start").disabled = running;
  el("login-button").disabled = running;
  el("cancel-button").classList.toggle("hidden", !running);
}

async function loadDefaults() {
  const defaults = await window.pywebview.api.get_defaults();
  state.qualityLabels = defaults.quality_labels;
  state.defaultPath = defaults.default_path;
  populateQualitySelect(el("favorites-quality"));
  populateQualitySelect(el("link-quality"));
  el("favorites-path").value = state.defaultPath;
  el("link-path").value = state.defaultPath;
}

async function refreshProfile() {
  const result = await window.pywebview.api.get_profile();
  if (result.ok) {
    el("login-button").classList.add("hidden");
    el("profile-info").classList.remove("hidden");
    el("profile-email").textContent = result.email;
    el("profile-country").textContent = result.country_code;
  } else {
    el("login-button").classList.remove("hidden");
    el("profile-info").classList.add("hidden");
  }
}

function switchPanel(name) {
  el("panel-favorites").classList.toggle("hidden", name !== "favorites");
  el("panel-link").classList.toggle("hidden", name !== "link");
  el("nav-favorites").classList.toggle("active", name === "favorites");
  el("nav-link").classList.toggle("active", name === "link");
  moveBannerNearActiveButton();
}

function moveBannerNearActiveButton() {
  const activeButton = el("panel-favorites").classList.contains("hidden")
    ? el("link-start")
    : el("favorites-start");
  activeButton.insertAdjacentElement("afterend", el("status-banner"));
}

let previewDebounce = null;

function onLinkInput() {
  clearTimeout(previewDebounce);
  const url = el("link-url").value.trim();
  if (!url) {
    el("preview-list").classList.add("hidden");
    return;
  }
  previewDebounce = setTimeout(async () => {
    const result = await window.pywebview.api.get_preview(url);
    if (result.ok) {
      renderPreview(result.tracks);
    } else {
      el("preview-list").classList.add("hidden");
    }
  }, 500);
}

async function startFavorites() {
  hideBanner();
  state.counts = { downloaded: 0, skipped: 0 };
  const result = await window.pywebview.api.start_favorites(
    el("favorites-quality").value,
    el("favorites-path").value
  );
  if (result.ok) {
    setRunning(true);
    setBanner("Telechargement en cours...", "info");
  } else {
    setBanner(result.error, "error");
  }
}

async function startLink() {
  hideBanner();
  state.counts = { downloaded: 0, skipped: 0 };
  const url = el("link-url").value.trim();
  if (!url) {
    setBanner("Colle un lien Tidal avant de telecharger.", "error");
    return;
  }
  const result = await window.pywebview.api.start_url(
    url,
    el("link-quality").value,
    el("link-path").value
  );
  if (result.ok) {
    setRunning(true);
    setBanner("Telechargement en cours...", "info");
  } else {
    setBanner(result.error, "error");
  }
}

async function browsePath(inputId) {
  const result = await window.pywebview.api.browse_folder(el(inputId).value);
  if (result.ok) {
    el(inputId).value = result.path;
  }
}

window.onTiddlEvent = function (message) {
  if (message.type === "line") {
    appendLog(message.text);
    if (message.track_event) {
      markTrack(message.track_event.title, message.track_event.status);
      if (message.track_event.status === "downloaded") {
        state.counts.downloaded += 1;
      } else if (message.track_event.status === "skipped") {
        state.counts.skipped += 1;
      }
      if (state.running) {
        const total = state.previewTracks.length;
        const done = state.counts.downloaded + state.counts.skipped;
        const suffix = total > 0 ? ` (${done}/${total})` : "";
        setBanner(
          `Telechargement en cours... ${state.counts.downloaded} nouvelles, ${state.counts.skipped} deja presentes${suffix}`,
          "info"
        );
      }
    }
    return;
  }

  setRunning(false);
  appendLog(`[termine, code ${message.code}]`);

  if (message.code === 0) {
    if (message.kind === "login") {
      refreshProfile();
      hideBanner();
    } else {
      setBanner(
        `Telechargement termine avec succes. ${state.counts.downloaded} nouvelles, ${state.counts.skipped} deja presentes.`,
        "success"
      );
      el("open-folder-button").classList.remove("hidden");
    }
  } else if (message.cancelled) {
    setBanner("Telechargement annule.", "info");
  } else {
    setBanner(`Echec (code ${message.code}). Voir les details.`, "error");
  }
};

window.addEventListener("pywebviewready", async () => {
  await loadDefaults();
  await refreshProfile();
  moveBannerNearActiveButton();

  el("login-button").addEventListener("click", async () => {
    hideBanner();
    const result = await window.pywebview.api.start_login();
    if (result.ok) {
      setRunning(true);
      setBanner("Connexion en cours, regarde le lien dans les details...", "info");
    } else {
      setBanner(result.error, "error");
    }
  });

  el("nav-favorites").addEventListener("click", () => switchPanel("favorites"));
  el("nav-link").addEventListener("click", () => switchPanel("link"));

  el("favorites-start").addEventListener("click", startFavorites);
  el("link-start").addEventListener("click", startLink);
  el("favorites-browse").addEventListener("click", () => browsePath("favorites-path"));
  el("link-browse").addEventListener("click", () => browsePath("link-path"));
  el("link-url").addEventListener("input", onLinkInput);

  el("cancel-button").addEventListener("click", async () => {
    await window.pywebview.api.cancel();
  });

  el("open-folder-button").addEventListener("click", async () => {
    const path = el("panel-favorites").classList.contains("hidden")
      ? el("link-path").value
      : el("favorites-path").value;
    await window.pywebview.api.open_folder(path);
  });
});
