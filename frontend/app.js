// Helpix Knowledge Base Client Application

const API_BASE = ""; // Relative to host
let currentTab = "search";
let searchMode = "hybrid";
let currentSearchId = null;
let currentSearchQuery = "";
let currentViewingArticleId = null;
let trendChart = null;
let categoriesList = [];
let allArticlesList = [];

const DEMO_CREDENTIALS = {
  admin: { username: "admin", password: "admin123" },
  moderator: { username: "moderator", password: "moderator123" },
  operator: { username: "operator", password: "operator123" }
};

const ROLE_NAMES = {
  admin: "Администратор",
  moderator: "Модератор",
  operator: "Оператор ТП"
};

const TAB_TITLES = {
  search: "Поиск",
  dashboard: "Аналитика",
  clusters: "Кластеры пробелов",
  articles: "Статьи",
  logs: "Все запросы"
};

let currentAuthToken = localStorage.getItem("helpix_token") || null;
let currentUser = null;
let currentPrimaryRole = localStorage.getItem("helpix_primary_role") || null; // 'admin', 'moderator', 'operator'
let currentRole = localStorage.getItem("helpix_active_role") || currentPrimaryRole || "operator"; // active view role

// Authenticated fetch wrapper
async function apiFetch(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (currentAuthToken) {
    headers["Authorization"] = `Bearer ${currentAuthToken}`;
  }
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401 && !url.includes("/auth/login")) {
    logoutUser();
  }
  return res;
}

// ==================== АВТОРИЗАЦИЯ И УПРАВЛЕНИЕ СЕССИЕЙ ====================

function showLoginModal() {
  const modal = document.getElementById("loginModal");
  if (!modal) return;
  modal.classList.remove("hidden");
  document.body.style.overflow = "hidden";
  const errBox = document.getElementById("loginErrorBox");
  if (errBox) errBox.classList.add("hidden");
  const uInput = document.getElementById("loginUsername");
  if (uInput) setTimeout(() => uInput.focus(), 150);
  lucide.createIcons();
}

function hideLoginModal() {
  const modal = document.getElementById("loginModal");
  if (!modal) return;
  modal.classList.add("hidden");
  document.body.style.overflow = "";
}

function togglePasswordVisibility() {
  const input = document.getElementById("loginPassword");
  const icon = document.getElementById("passwordToggleIcon");
  if (!input || !icon) return;
  if (input.type === "password") {
    input.type = "text";
    icon.setAttribute("data-lucide", "eye-off");
  } else {
    input.type = "password";
    icon.setAttribute("data-lucide", "eye");
  }
  lucide.createIcons();
}

async function quickLogin(role) {
  const creds = DEMO_CREDENTIALS[role];
  if (!creds) return;
  const uInput = document.getElementById("loginUsername");
  const pInput = document.getElementById("loginPassword");
  if (uInput) uInput.value = creds.username;
  if (pInput) pInput.value = creds.password;
  await executeLogin(creds.username, creds.password);
}

async function handleLoginSubmit(event) {
  if (event) event.preventDefault();
  const uInput = document.getElementById("loginUsername");
  const pInput = document.getElementById("loginPassword");
  const username = uInput ? uInput.value.trim() : "";
  const password = pInput ? pInput.value : "";
  if (!username || !password) return;
  await executeLogin(username, password);
}

async function executeLogin(username, password) {
  const btn = document.getElementById("btnLoginSubmit");
  const errBox = document.getElementById("loginErrorBox");
  const errText = document.getElementById("loginErrorText");
  if (errBox) errBox.classList.add("hidden");

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Проверка данных...</span>`;
    lucide.createIcons();
  }

  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    if (!res.ok) {
      let msg = "Неверный логин или пароль";
      try {
        const errData = await res.json();
        if (errData && errData.detail) msg = errData.detail;
      } catch (_) {}
      if (errBox && errText) {
        errText.textContent = msg;
        errBox.classList.remove("hidden");
        lucide.createIcons();
      }
      return;
    }

    const data = await res.json();
    currentAuthToken = data.access_token;
    currentUser = data.user;
    currentPrimaryRole = data.user.role;
    currentRole = data.user.role;

    localStorage.setItem("helpix_token", currentAuthToken);
    localStorage.setItem("helpix_primary_role", currentPrimaryRole);
    localStorage.setItem("helpix_active_role", currentRole);

    hideLoginModal();
    renderUserHeader();
    applyRolePermissions(currentRole);

    showToast(`Добро пожаловать, ${currentUser.full_name || currentUser.username}! (${ROLE_NAMES[currentRole]})`, "success");

    // Load initial application data
    await loadCategories();
    await loadClustersCountBadge();
    if (currentTab === "dashboard") loadDashboard();
    if (currentTab === "clusters") loadClusters();
    if (currentTab === "articles") loadArticles();
    if (currentTab === "logs") loadSearchLogs();
    await loadPopularArticles();
  } catch (err) {
    console.error("Login request error:", err);
    if (errBox && errText) {
      errText.textContent = "Ошибка связи с сервером. Повторите попытку.";
      errBox.classList.remove("hidden");
      lucide.createIcons();
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="log-in" class="w-4 h-4"></i><span>Войти в систему</span>`;
      lucide.createIcons();
    }
  }
}

function logoutUser() {
  localStorage.removeItem("helpix_token");
  localStorage.removeItem("helpix_primary_role");
  localStorage.removeItem("helpix_active_role");
  localStorage.removeItem("vkr_token");
  localStorage.removeItem("vkr_role");

  currentAuthToken = null;
  currentUser = null;
  currentPrimaryRole = null;
  currentRole = "operator";

  // Reset password field
  const pInput = document.getElementById("loginPassword");
  if (pInput) pInput.value = "";

  renderUserHeader();
  showLoginModal();
  showToast("Вы вышли из системы", "info");
}

function renderUserHeader() {
  const staticBadge = document.getElementById("userStaticRoleBadge");
  const staticIcon = document.getElementById("userStaticRoleIcon");
  const staticName = document.getElementById("userStaticRoleName");
  const adminSwitcher = document.getElementById("adminRoleSwitcherContainer");
  const roleSelect = document.getElementById("userRoleSelect");
  const userNameEl = document.getElementById("headerUserName");

  if (userNameEl) {
    userNameEl.textContent = currentUser ? (currentUser.full_name || currentUser.username) : "";
  }

  if (currentPrimaryRole === "admin") {
    // Administrator: show role dropdown for viewing site from other roles' perspective
    if (staticBadge) {
      staticBadge.classList.add("hidden");
      staticBadge.classList.remove("flex");
    }
    if (adminSwitcher) {
      adminSwitcher.classList.remove("hidden");
      adminSwitcher.classList.add("flex");
    }
    if (roleSelect) {
      roleSelect.value = currentRole;
    }
  } else if (currentPrimaryRole) {
    // Operator or Moderator: show ONLY static badge, NO dropdown
    if (adminSwitcher) {
      adminSwitcher.classList.add("hidden");
      adminSwitcher.classList.remove("flex");
    }
    if (staticBadge) {
      staticBadge.classList.remove("hidden");
      staticBadge.classList.add("flex");
      if (currentPrimaryRole === "moderator") {
        staticBadge.className = "flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border bg-amber-50 text-amber-700 border-amber-200 text-xs font-semibold shadow-xs";
        if (staticIcon) staticIcon.setAttribute("data-lucide", "shield-check");
        if (staticName) staticName.textContent = "Модератор";
      } else {
        staticBadge.className = "flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border bg-sky-50 text-sky-700 border-sky-200 text-xs font-semibold shadow-xs";
        if (staticIcon) staticIcon.setAttribute("data-lucide", "headphones");
        if (staticName) staticName.textContent = "Оператор ТП";
      }
    }
  } else {
    // Not logged in
    if (adminSwitcher) adminSwitcher.classList.add("hidden");
    if (staticBadge) staticBadge.classList.add("hidden");
    if (userNameEl) userNameEl.textContent = "";
  }
  lucide.createIcons();
}

async function switchAdminViewingRole(newRole) {
  if (currentPrimaryRole !== "admin") return;
  currentRole = newRole;
  localStorage.setItem("helpix_active_role", newRole);

  // Switch authentication token to match the viewed role for complete backend permission fidelity
  const creds = DEMO_CREDENTIALS[newRole];
  if (creds) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(creds)
      });
      if (res.ok) {
        const data = await res.json();
        currentAuthToken = data.access_token;
        localStorage.setItem("helpix_token", currentAuthToken);
      }
    } catch (err) {
      console.error("Error switching viewing role auth:", err);
    }
  }

  applyRolePermissions(newRole);
  renderUserHeader();
  showToast(`Просмотр от лица: ${ROLE_NAMES[newRole]}`, "info");

  // Refresh current tab data
  if (currentTab === "dashboard") loadDashboard();
  if (currentTab === "clusters") loadClusters();
  if (currentTab === "articles") loadArticles();
  if (currentTab === "logs") loadSearchLogs();
  loadClustersCountBadge();
}

// Backward compatibility alias
async function changeUserRole(role) {
  if (currentPrimaryRole === "admin") {
    await switchAdminViewingRole(role);
  }
}

// ==================== ИНИЦИАЛИЗАЦИЯ ====================
document.addEventListener("DOMContentLoaded", async () => {
  lucide.createIcons();
  
  // Set browser tab title
  document.title = `Helpix - ${TAB_TITLES[currentTab] || "Поиск"}`;

  // Check stored auth session
  const storedToken = localStorage.getItem("helpix_token");
  const storedPrimaryRole = localStorage.getItem("helpix_primary_role");
  const storedActiveRole = localStorage.getItem("helpix_active_role");

  if (storedToken && storedPrimaryRole) {
    currentAuthToken = storedToken;
    currentPrimaryRole = storedPrimaryRole;
    currentRole = storedActiveRole || storedPrimaryRole;

    try {
      const res = await apiFetch(`${API_BASE}/api/v1/auth/me`);
      if (res.ok) {
        currentUser = await res.json();
        hideLoginModal();
        renderUserHeader();
        applyRolePermissions(currentRole);

        await loadCategories();
        await loadClustersCountBadge();
        await loadPopularArticles();
      } else {
        // Token expired or invalid -> open login modal
        logoutUser();
      }
    } catch (_) {
      // Offline fallback: keep session if valid
      hideLoginModal();
      renderUserHeader();
      applyRolePermissions(currentRole);
      await loadCategories();
      await loadClustersCountBadge();
      await loadPopularArticles();
    }
  } else {
    // Not authenticated -> show login modal right at startup!
    showLoginModal();
  }

  // Listen to input changes in search input
  const searchInputEl = document.getElementById("searchInput");
  if (searchInputEl) {
    searchInputEl.addEventListener("input", (e) => {
      if (!e.target.value.trim()) {
        loadPopularArticles();
      }
    });
  }

  // Always display popular articles on initial load
  await loadPopularArticles();

  // Escape key closes modals
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeClusterDetailModal();
      closeArticleViewModal();
      closeArticleEditModal();
    }
  });
});

// ==================== НАВИГАЦИЯ ====================
function switchTab(tab) {
  if (currentRole === "operator" && tab !== "search" && tab !== "articles") {
    showToast("Доступ ограничен: для роли Оператор доступны только разделы Поиск и Статьи", "warning");
    return;
  }
  currentTab = tab;

  // Update dynamic browser tab title
  const pageTitle = TAB_TITLES[tab] || "Поиск";
  document.title = `Helpix - ${pageTitle}`;
  
  // Hide all sections
  ["search", "dashboard", "clusters", "articles", "logs"].forEach(t => {
    const el = document.getElementById(`tab-${t}`);
    const btn = document.getElementById(`tab-btn-${t}`);
    if (el) el.classList.add("hidden");
    if (btn) {
      btn.className = "nav-tab px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition flex items-center space-x-1.5";
    }
  });

  // Activate selected section
  const activeEl = document.getElementById(`tab-${tab}`);
  const activeBtn = document.getElementById(`tab-btn-${tab}`);
  if (activeEl) activeEl.classList.remove("hidden");
  if (activeBtn) {
    activeBtn.className = "nav-tab px-3 py-2 rounded-lg text-sm font-medium transition flex items-center space-x-1.5 bg-indigo-50 text-indigo-700";
  }

  // Load specific tab data
  if (tab === "search") {
    const q = document.getElementById("searchInput")?.value.trim();
    if (!q) loadPopularArticles();
  }
  if (tab === "dashboard") loadDashboard();
  if (tab === "clusters") loadClusters();
  if (tab === "articles") loadArticles();
  if (tab === "logs") loadSearchLogs();

  lucide.createIcons();
}


function applyRolePermissions(role) {
  const tabDashboard = document.getElementById("tab-btn-dashboard");
  const tabClusters = document.getElementById("tab-btn-clusters");
  const tabArticles = document.getElementById("tab-btn-articles");
  const tabLogs = document.getElementById("tab-btn-logs");
  const createBtn = document.getElementById("createArticleBtn");

  if (role === "operator") {
    // Operator: Search and Articles (read-only)
    if (tabDashboard) tabDashboard.style.display = "none";
    if (tabClusters) tabClusters.style.display = "none";
    if (tabArticles) tabArticles.style.display = "";
    if (tabLogs) tabLogs.style.display = "none";
    if (createBtn) createBtn.style.display = "none";

    // Switch back to search if currently on protected tab (dashboard, clusters, logs)
    if (currentTab !== "search" && currentTab !== "articles") {
      switchTab("search");
    }
  } else if (role === "moderator") {
    // Moderator: search, analytics, clusters, articles, logs
    if (tabDashboard) tabDashboard.style.display = "";
    if (tabClusters) tabClusters.style.display = "";
    if (tabArticles) tabArticles.style.display = "";
    if (tabLogs) tabLogs.style.display = "";
    if (createBtn) createBtn.style.display = "";
  } else if (role === "admin") {
    // Admin: full access
    if (tabDashboard) tabDashboard.style.display = "";
    if (tabClusters) tabClusters.style.display = "";
    if (tabArticles) tabArticles.style.display = "";
    if (tabLogs) tabLogs.style.display = "";
    if (createBtn) createBtn.style.display = "";
  }

  // Re-render articles table if currently in articles tab to show/hide action buttons
  if (currentTab === "articles" && allArticlesList.length > 0) {
    renderArticlesTable(allArticlesList);
  }
  if (currentTab === "clusters") {
    loadClusters();
  }
  lucide.createIcons();
}

// ==================== КАТЕГОРИИ ====================
async function loadCategories() {
  try {
    const res = await apiFetch(`${API_BASE}/api/v1/articles/categories`);
    if (res.ok) {
      categoriesList = await res.json();
      
      const searchCat = document.getElementById("searchCategory");
      const editCat = document.getElementById("editCategory");
      
      searchCat.innerHTML = '<option value="">Все категории</option>';
      editCat.innerHTML = '';
      
      categoriesList.forEach(c => {
        searchCat.innerHTML += `<option value="${c.id}">${c.name}</option>`;
        editCat.innerHTML += `<option value="${c.id}">${c.name}</option>`;
      });
    }
  } catch (err) {
    console.error("Failed to load categories:", err);
  }
}

// ==================== ПОИСК (ГИБРИДНЫЙ, ТЕКСТОВЫЙ, СЕМАНТИЧЕСКИЙ) ====================
function setSearchMode(mode) {
  searchMode = mode;
  ["hybrid", "text", "semantic"].forEach(m => {
    const btn = document.getElementById(`mode-${m}`);
    if (btn) {
      if (m === mode) {
        btn.className = "px-3 py-1 text-xs font-medium rounded-md bg-white text-indigo-700 shadow-sm border border-slate-200/60";
      } else {
        btn.className = "px-3 py-1 text-xs font-medium rounded-md text-slate-600 hover:text-slate-900";
      }
    }
  });

  const query = document.getElementById("searchInput").value.trim();
  if (query) {
    executeSearch();
  }
}

function clearSearchInput() {
  const input = document.getElementById("searchInput");
  if (input) {
    input.value = "";
    input.focus();
  }
  loadPopularArticles();
}

function handleCategoryChange() {
  const query = document.getElementById("searchInput")?.value.trim();
  if (query) {
    executeSearch();
  } else {
    loadPopularArticles();
  }
}

async function loadPopularArticles() {
  const resultsList = document.getElementById("resultsList");
  const searchMeta = document.getElementById("searchMeta");
  const catVal = document.getElementById("searchCategory")?.value;

  if (!resultsList) return;

  if (searchMeta) {
    searchMeta.classList.remove("hidden");
    const countText = document.getElementById("resultsCountText");
    const metricsText = document.getElementById("searchMetricsText");
    if (countText) {
      countText.innerHTML = `
        <span class="inline-flex items-center space-x-1.5 font-semibold text-slate-800">
          <i data-lucide="flame" class="w-4 h-4 text-amber-500"></i>
          <span>Часто запрашиваемые решения и популярные статьи</span>
        </span>
      `;
    }
    if (metricsText) {
      metricsText.innerHTML = `<span class="text-xs text-slate-400">Топ решений по просмотрам и полезности</span>`;
    }
  }

  resultsList.innerHTML = `
    <div class="bg-white rounded-2xl p-8 text-center border border-slate-200 text-slate-400 animate-pulse">
      <i data-lucide="loader-2" class="w-6 h-6 mx-auto mb-2 text-indigo-600 animate-spin"></i>
      <p class="text-xs font-medium text-slate-600">Загрузка рекомендуемых статей...</p>
    </div>
  `;
  lucide.createIcons();

  try {
    const url = catVal
      ? `${API_BASE}/api/v1/articles?category_id=${catVal}&sort_by=popular&limit=5`
      : `${API_BASE}/api/v1/articles?sort_by=popular&limit=5`;

    const res = await apiFetch(url);
    if (!res.ok) throw new Error("Не удалось загрузить популярные статьи");
    const popularArticles = await res.json();

    if (popularArticles.length === 0) {
      resultsList.innerHTML = `
        <div class="bg-white rounded-2xl p-8 text-center border border-slate-200 text-slate-400">
          <p class="text-xs">В выбранной категории пока нет опубликованных статей</p>
        </div>
      `;
      return;
    }

    let html = `
      <div class="flex items-center justify-between pb-1 px-1">
        <span class="text-xs font-medium text-slate-500">
          Быстрый доступ к решениям (введите запрос в строку выше для точного поиска по всей базе):
        </span>
      </div>
    `;

    popularArticles.forEach((item, index) => {
      const catBadge = item.category_name 
        ? `<span class="px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded text-xs font-medium border border-indigo-100">${escapeHtml(item.category_name)}</span>`
        : "";

      const totalVotes = (item.helpful_count || 0) + (item.unhelpful_count || 0);
      const ratingPercent = totalVotes > 0 ? Math.round((item.helpful_count / totalVotes) * 100) : 100;

      html += `
        <div class="bg-white rounded-2xl p-5 border border-slate-200 hover:border-indigo-400 hover:shadow-md transition space-y-2 cursor-pointer group" onclick="openArticleView(${item.id})">
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center space-x-2">
              <span class="w-7 h-7 rounded-xl bg-amber-50 text-amber-700 border border-amber-200 flex items-center justify-center text-xs font-bold shrink-0 group-hover:bg-indigo-600 group-hover:text-white group-hover:border-indigo-600 transition">
                #${index + 1}
              </span>
              <h4 class="font-bold text-slate-900 group-hover:text-indigo-600 text-base transition leading-snug">
                ${escapeHtml(item.title)}
              </h4>
            </div>
            <div class="flex items-center space-x-1.5 shrink-0">
              ${catBadge}
            </div>
          </div>

          <p class="text-xs text-slate-600 leading-relaxed pl-9">
            ${escapeHtml(item.summary || "")}
          </p>

          <div class="pl-9 pt-2 flex flex-wrap items-center gap-3 text-[11px] text-slate-400 border-t border-slate-50">
            <span class="flex items-center space-x-1 text-slate-600 font-medium">
              <i data-lucide="eye" class="w-3.5 h-3.5 text-slate-400"></i>
              <span>${item.views_count || 0} просмотров</span>
            </span>
            <span class="flex items-center space-x-1 text-emerald-600 font-medium">
              <i data-lucide="thumbs-up" class="w-3.5 h-3.5"></i>
              <span>${ratingPercent}% оценили положительно (${item.helpful_count || 0})</span>
            </span>
            ${item.tags ? `<span class="text-slate-400 truncate max-w-xs">Теги: ${escapeHtml(item.tags)}</span>` : ""}
          </div>
        </div>
      `;
    });

    resultsList.innerHTML = html;
    lucide.createIcons();
  } catch (err) {
    resultsList.innerHTML = `
      <div class="bg-slate-50 text-slate-600 p-6 rounded-2xl text-center text-xs border border-slate-200">
        ${escapeHtml(err.message)}
      </div>
    `;
  }
}

async function executeSearch() {
  const query = document.getElementById("searchInput").value.trim();
  if (!query) {
    loadPopularArticles();
    return;
  }

  const resultsList = document.getElementById("resultsList");
  const searchMeta = document.getElementById("searchMeta");
  const catVal = document.getElementById("searchCategory").value;

  resultsList.innerHTML = `
    <div class="bg-white rounded-2xl p-10 text-center border border-slate-200 text-slate-400 animate-pulse">
      <i data-lucide="loader-2" class="w-8 h-8 mx-auto mb-2 text-indigo-600 animate-spin"></i>
      <p class="font-medium text-slate-700 text-sm">Выполняется ${searchMode === 'hybrid' ? 'гибридный поиск (RRF)' : (searchMode === 'text' ? 'полнотекстовый поиск' : 'семантический векторный поиск')}...</p>
    </div>
  `;
  lucide.createIcons();

  try {
    const payload = {
      query: query,
      search_mode: searchMode,
      category_id: catVal ? parseInt(catVal) : null,
      top_k: 8
    };

    const res = await apiFetch(`${API_BASE}/api/v1/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("Search request failed");
    const data = await res.json();
    currentSearchId = data.search_id;
    currentSearchQuery = query;

    // Show meta
    searchMeta.classList.remove("hidden");
    document.getElementById("resultsCountText").textContent = `Найдено решений: ${data.results_count}`;
    document.getElementById("searchMetricsText").textContent = `Режим: ${(data.search_mode || "HYBRID").toUpperCase()} | Время: ${data.execution_time_ms} мс`;

    if (data.results.length === 0) {
      if (data.is_search_gap) {
        // ALL 3 ALGORITHMS FOUND 0: Explicit search gap!
        resultsList.innerHTML = `
          <div class="bg-amber-50 rounded-2xl p-8 border border-amber-200 text-center space-y-3">
            <div class="w-12 h-12 bg-amber-100 text-amber-700 rounded-full flex items-center justify-center mx-auto">
              <i data-lucide="alert-circle" class="w-6 h-6"></i>
            </div>
            <div>
              <h4 class="font-bold text-amber-900 text-base">По вашему запросу не найдено подходящих решений</h4>
              <p class="text-xs text-amber-700 mt-1 max-w-lg mx-auto">
                По всем трем алгоритмам (текстовый, семантический, гибридный) результат: 0 решений.<br>
                Запрос <strong>«${escapeHtml(query)}»</strong> автоматически зарегистрирован системой как <span class="font-semibold text-rose-700">поисковый пробел</span>. Он будет учтён модулем кластеризации для создания новой статьи модератором.
              </p>
            </div>
            <button onclick="registerGapAndGoToClusters('${escapeHtml(query)}')" class="inline-flex items-center space-x-1.5 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-sm transition">
              <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
              <span>Посмотреть темы в очереди на написание</span>
            </button>
          </div>
        `;
      } else {
        // At least one algorithm has results, do not automatically add as gap
        const otherInfo = [
          data.text_count > 0 ? `текстовый: ${data.text_count}` : null,
          data.semantic_count > 0 ? `семантический: ${data.semantic_count}` : null,
          data.hybrid_count > 0 ? `гибридный: ${data.hybrid_count}` : null
        ].filter(Boolean).join(', ');

        resultsList.innerHTML = `
          <div class="bg-amber-50 rounded-2xl p-8 border border-amber-200 text-center space-y-3">
            <div class="w-12 h-12 bg-amber-100 text-amber-700 rounded-full flex items-center justify-center mx-auto">
              <i data-lucide="info" class="w-6 h-6"></i>
            </div>
            <div>
              <h4 class="font-bold text-amber-900 text-base">В выбранном режиме не найдено решений</h4>
              <p class="text-xs text-amber-700 mt-1 max-w-lg mx-auto">
                В других алгоритмах найдены решения (${escapeHtml(otherInfo)}).<br>
                Попробуйте переключить алгоритм поиска выше. Запрос не добавлен в пробелы автоматически.
              </p>
            </div>
            <button onclick="registerGapAndGoToClusters('${escapeHtml(query)}')" class="inline-flex items-center space-x-1.5 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-sm transition">
              <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
              <span>Посмотреть темы в очереди на написание</span>
            </button>
          </div>
        `;
      }
      lucide.createIcons();
      return;
    }

    // Render search results
    let html = "";
    data.results.forEach((item, index) => {
      const catBadge = item.category_name 
        ? `<span class="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-xs font-medium">${escapeHtml(item.category_name)}</span>`
        : "";

      const simPercent = item.semantic_similarity 
        ? Math.round(item.semantic_similarity * 100)
        : null;

      html += `
        <div class="bg-white rounded-2xl p-5 border border-slate-200 hover:border-indigo-300 hover:shadow-md transition space-y-2 cursor-pointer group" onclick="openArticleView(${item.id})">
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center space-x-2">
              <span class="w-6 h-6 rounded-full bg-slate-100 text-slate-600 flex items-center justify-center text-xs font-bold group-hover:bg-indigo-600 group-hover:text-white transition">
                ${index + 1}
              </span>
              <h4 class="font-bold text-slate-900 group-hover:text-indigo-600 text-base transition leading-snug">
                ${escapeHtml(item.title)}
              </h4>
            </div>
            <div class="flex items-center space-x-1.5 shrink-0">
              ${catBadge}
            </div>
          </div>

          <p class="text-xs text-slate-600 leading-relaxed pl-8">
            ${escapeHtml(item.content_snippet || item.summary || "")}
          </p>

          <!-- Техническая плашка оценки ранжирования (RRF) -->
          <div class="pl-8 pt-2 flex flex-wrap items-center gap-3 text-[11px] text-slate-500 border-t border-slate-50">
            <span class="font-mono bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded font-semibold">
              RRF Score: ${item.rrf_score}
            </span>
            ${item.text_rank ? `<span>Текстовый ранг: <strong>#${item.text_rank}</strong></span>` : `<span class="text-slate-400">Текст: —</span>`}
            ${item.semantic_rank ? `<span>Семантический ранг: <strong>#${item.semantic_rank}</strong></span>` : `<span class="text-slate-400">Семантика: —</span>`}
            ${simPercent !== null ? `<span class="text-emerald-700 font-medium">Сходство: ${simPercent}%</span>` : ""}
          </div>
        </div>
      `;
    });

    resultsList.innerHTML = html;
    lucide.createIcons();

  } catch (err) {
    resultsList.innerHTML = `
      <div class="bg-rose-50 text-rose-700 p-4 rounded-xl text-center text-xs border border-rose-200">
        Ошибка при выполнении поиска: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

// ==================== ПРОСМОТР СТАТЬИ И ОБРАТНАЯ СВЯЗЬ ====================
async function openArticleView(articleId) {
  currentViewingArticleId = articleId;
  const modal = document.getElementById("articleViewModal");
  const titleEl = document.getElementById("modalArticleTitle");
  const catEl = document.getElementById("modalArticleCategory");
  const contentEl = document.getElementById("modalArticleContent");
  const btnGroup = document.getElementById("feedbackButtonsGroup");

  titleEl.textContent = "Загрузка...";
  contentEl.innerHTML = `<div class="py-8 text-center text-slate-400">Загрузка содержимого...</div>`;
  modal.classList.remove("hidden");

  // Show feedback rating bar ONLY if opened from Search tab; hide if opened from Articles catalog
  const feedbackContainer = document.getElementById("articleFeedbackContainer");
  const closeOnlyFooter = document.getElementById("articleCloseOnlyFooter");

  if (currentTab === "search") {
    if (feedbackContainer) feedbackContainer.classList.remove("hidden");
    if (closeOnlyFooter) closeOnlyFooter.classList.add("hidden");
    if (btnGroup) btnGroup.style.display = "flex";
  } else {
    if (feedbackContainer) feedbackContainer.classList.add("hidden");
    if (closeOnlyFooter) closeOnlyFooter.classList.remove("hidden");
    if (btnGroup) btnGroup.style.display = "none";
  }

  try {
    const res = await apiFetch(`${API_BASE}/api/v1/articles/${articleId}`);
    if (!res.ok) throw new Error("Failed to load article");
    const article = await res.json();

    titleEl.textContent = article.title;
    catEl.textContent = article.category ? article.category.name : "Общее";
    
    // Parse markdown
    contentEl.innerHTML = marked.parse(article.content || "");

  } catch (err) {
    contentEl.innerHTML = `<div class="text-rose-600">Ошибка загрузки: ${err.message}</div>`;
  }
  lucide.createIcons();
}

function closeArticleViewModal() {
  document.getElementById("articleViewModal").classList.add("hidden");
  currentViewingArticleId = null;
}

async function submitArticleFeedback(isHelpful) {
  if (currentTab !== "search" || (!currentSearchId && !currentViewingArticleId)) {
    closeArticleViewModal();
    return;
  }

  try {
    if (currentSearchId !== null || currentViewingArticleId) {
      await apiFetch(`${API_BASE}/api/v1/search/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          search_id: currentSearchId || 0,
          query: currentSearchQuery || "",
          search_mode: searchMode || "hybrid",
          clicked_article_id: currentViewingArticleId,
          is_helpful: isHelpful,
          feedback_notes: isHelpful ? "Решение подошло" : "Ответ не помог / информация неполная"
        })
      });
    }

    const toastMsg = isHelpful 
      ? "Спасибо за отзыв! Рейтинг статьи повышен."
      : "Спасибо! Запрос зарегистрирован как пробел в базе знаний для модератора.";
    
    showToast(toastMsg, isHelpful ? "success" : "warning");
    closeArticleViewModal();
    loadClustersCountBadge();

  } catch (err) {
    console.error("Feedback error:", err);
    closeArticleViewModal();
  }
}

async function registerGapAndGoToClusters(query) {
  const q = (query || currentSearchQuery || "").trim();
  try {
    // If not already registered in DB as a gap, register now since operator clicked "Посмотреть темы в очереди на написание"
    if (q && (!currentSearchId || currentSearchId === 0)) {
      const res = await apiFetch(`${API_BASE}/api/v1/search/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          search_id: 0,
          query: q,
          search_mode: searchMode || "hybrid",
          is_helpful: false,
          feedback_notes: "Добавлен оператором через переход к темам на написание"
        })
      });
      if (res.ok) {
        const data = await res.json();
        currentSearchId = data.search_id;
        showToast(`Запрос «${q}» зарегистрирован как поисковый пробел`, "warning");
      }
    }
  } catch (err) {
    console.error("Failed to register search gap:", err);
  } finally {
    loadClustersCountBadge();
    switchTab('clusters');
  }
}
window.registerGapAndGoToClusters = registerGapAndGoToClusters;

// ==================== ВСПОМОГАТЕЛЬНЫЕ ФОРМАТИРОВАНИЯ ====================
function formatShortClusterTitle(title) {
  if (!title) return "Не в кластере";
  const lower = title.toLowerCase();
  
  if (lower.includes("сбп") || lower.includes("оплат")) return "Оплата по СБП";
  if (lower.includes("p2p") || lower.includes("камер")) return "P2P камеры";
  if (lower.includes("домофон")) return "Умный домофон";
  if (lower.includes("эквайринг") || lower.includes("сбербанк")) return "Эквайринг";
  if (lower.includes("терминал") || lower.includes("4119")) return "POS-терминалы";
  if (lower.includes("касс") || lower.includes("офд")) return "Онлайн-кассы";
  if (lower.includes("mesh") || lower.includes("роуминг")) return "Mesh Wi-Fi";
  if (lower.includes("ipv6")) return "Настройка IPv6";
  if (lower.includes("родительск") || lower.includes("сайтов") || lower.includes("dns")) return "Родительский контроль";
  if (lower.includes("видеонаблюден")) return "Видеонаблюдение";
  if (lower.includes("vpn") || lower.includes("wireguard")) return "VPN WireGuard";

  let t = title.replace(/^как (настроить|включить|подключить|сделать)\s+/i, "")
               .replace(/^почему не (работает|приходят|проходит)\s+/i, "")
               .replace(/^ошибка (подключения к|связи с|авторизации в)\s+/i, "")
               .replace(/\.\.\.$/, "")
               .trim();
  t = t.charAt(0).toUpperCase() + t.slice(1);
  if (t.length > 22) {
    t = t.slice(0, 20) + "…";
  }
  return t;
}

// ==================== АНАЛИТИКА (МОДЕРАТОР) ====================
async function loadDashboard() {
  try {
    const res = await apiFetch(`${API_BASE}/api/v1/stats/dashboard`);
    if (!res.ok) return;
    const stats = await res.json();

    // KPIs
    document.getElementById("kpi-articles").textContent = stats.total_articles;
    document.getElementById("kpi-searches").textContent = stats.total_searches;
    document.getElementById("kpi-gaps").textContent = stats.total_gaps;
    document.getElementById("kpi-gap-rate").textContent = `${stats.gap_rate}% от всех поисков`;
    document.getElementById("kpi-clusters").textContent = stats.active_clusters_count;

    // Daily Trend Chart (Chart.js)
    const ctx = document.getElementById("searchTrendChart").getContext("2d");
    if (trendChart) trendChart.destroy();

    const labels = stats.daily_stats.map(d => d.date);
    const totalData = stats.daily_stats.map(d => d.total_searches);
    const gapsData = stats.daily_stats.map(d => d.gaps_count);

    trendChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Всего поисков",
            data: totalData,
            backgroundColor: "rgba(99, 102, 241, 0.7)",
            borderRadius: 6
          },
          {
            label: "Поисковые пробелы (0 рез. / не помогло)",
            data: gapsData,
            backgroundColor: "rgba(244, 63, 94, 0.8)",
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } }
        },
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 } },
          x: { grid: { display: false } }
        }
      }
    });

    // Top Queries
    const topQEl = document.getElementById("topQueriesList");
    if (stats.top_queries.length === 0) {
      topQEl.innerHTML = `<p class="text-xs text-slate-400">Пока нет данных</p>`;
    } else {
      let qHtml = "";
      stats.top_queries.forEach(q => {
        const gapBadge = q.is_gap 
          ? `<span class="px-1.5 py-0.2 text-[10px] bg-rose-100 text-rose-700 rounded font-semibold">Пробел</span>`
          : `<span class="px-1.5 py-0.2 text-[10px] bg-emerald-100 text-emerald-700 rounded font-semibold">Успех</span>`;
        qHtml += `
          <div class="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-100">
            <span class="text-xs text-slate-800 font-medium truncate max-w-[200px]">${escapeHtml(q.query)}</span>
            <div class="flex items-center space-x-2">
              ${gapBadge}
              <span class="text-xs font-bold text-slate-600">${q.count}</span>
            </div>
          </div>
        `;
      });
      topQEl.innerHTML = qHtml;
    }

    // Top Articles
    const topArtEl = document.getElementById("topArticlesList");
    if (stats.top_articles.length === 0) {
      topArtEl.innerHTML = `<p class="text-xs text-slate-400">Пока нет статей</p>`;
    } else {
      let aHtml = "";
      stats.top_articles.forEach(a => {
        aHtml += `
          <div class="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100 cursor-pointer hover:bg-slate-100" onclick="openArticleView(${a.id})">
            <span class="text-xs text-slate-800 font-medium truncate max-w-[280px]">${escapeHtml(a.title)}</span>
            <div class="flex items-center space-x-3 text-xs">
              <span class="text-slate-500">${a.views_count} просм.</span>
              <span class="font-bold text-emerald-600">${a.helpfulness_rate}% 👍</span>
            </div>
          </div>
        `;
      });
      topArtEl.innerHTML = aHtml;
    }

    // Recent Gaps
    const recentGapsEl = document.getElementById("recentGapsList");
    if (stats.recent_gaps.length === 0) {
      recentGapsEl.innerHTML = `<p class="text-xs text-slate-400">Пробелы не зафиксированы</p>`;
    } else {
      let gHtml = "";
      stats.recent_gaps.forEach(g => {
        const shortTitle = formatShortClusterTitle(g.cluster_title);
        const clusterBadge = g.cluster_title 
          ? `<span class="inline-flex items-center space-x-1.5 px-2 py-0.5 bg-indigo-50 text-indigo-700 border border-indigo-100 rounded-md text-[10px] font-semibold whitespace-nowrap shrink-0" title="Тема кластера: ${escapeHtml(g.cluster_title)}">
               <span class="w-1.5 h-1.5 rounded-full bg-indigo-500 shrink-0"></span>
               <span>${escapeHtml(shortTitle)}</span>
             </span>`
          : `<span class="inline-flex items-center space-x-1 px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded-md text-[10px] font-medium whitespace-nowrap shrink-0">
               <span class="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0"></span>
               <span>Не в кластере</span>
             </span>`;

        gHtml += `
          <div class="p-2.5 rounded-xl bg-rose-50/50 border border-rose-100 hover:bg-rose-50/90 transition space-y-1.5">
            <div class="text-xs text-slate-900 font-medium leading-snug break-words">
              «${escapeHtml(g.query_text)}»
            </div>
            <div class="flex items-center justify-between gap-2 pt-1 border-t border-rose-100/70 text-[11px]">
              <span class="text-slate-400 font-normal shrink-0">
                ${new Date(g.timestamp).toLocaleString("ru-RU")}
              </span>
              ${clusterBadge}
            </div>
          </div>
        `;
      });
      recentGapsEl.innerHTML = gHtml;
    }

  } catch (err) {
    console.error("Dashboard load error:", err);
  }
}

// ==================== КЛАСТЕРИЗАЦИЯ ПРОБЕЛОВ ====================
async function loadClustersCountBadge() {
  try {
    const res = await apiFetch(`${API_BASE}/api/v1/gaps/clusters?status_filter=new`);
    if (res.ok) {
      const data = await res.json();
      const badge = document.getElementById("nav-clusters-count");
      if (badge) badge.textContent = data.length;
    }
  } catch (e) {}
}

function formatClusterDate(dateVal) {
  if (!dateVal) return "—";
  try {
    const normalized = typeof dateVal === "string" ? dateVal.replace(" ", "T") : dateVal;
    const d = new Date(normalized);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleString("ru-RU", { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return "—";
  }
}

function pluralizeQueries(n) {
  const count = Math.abs(n || 0);
  const mod100 = count % 100;
  const mod10 = count % 10;
  if (mod100 >= 11 && mod100 <= 19) return `${count} запросов`;
  if (mod10 === 1) return `${count} запрос`;
  if (mod10 >= 2 && mod10 <= 4) return `${count} запроса`;
  return `${count} запросов`;
}

function pluralizeTopics(n) {
  const count = Math.abs(n || 0);
  const mod100 = count % 100;
  const mod10 = count % 10;
  if (mod100 >= 11 && mod100 <= 19) return `${count} тем`;
  if (mod10 === 1) return `${count} тема`;
  if (mod10 >= 2 && mod10 <= 4) return `${count} темы`;
  return `${count} тем`;
}

async function loadClusters() {
  const grid = document.getElementById("clustersGrid");
  const filter = document.getElementById("clusterFilter").value;
  grid.innerHTML = `<div class="col-span-2 py-8 text-center text-slate-400 animate-pulse">Загрузка кластеров...</div>`;

  try {
    let url = `${API_BASE}/api/v1/gaps/clusters`;
    if (filter) url += `?status_filter=${filter}`;
    const res = await apiFetch(url);
    if (!res.ok) throw new Error("Failed to load clusters");
    const clusters = await res.json();

    loadClustersCountBadge();

    const headerBadge = document.getElementById("clustersCountHeaderBadge");
    if (headerBadge) headerBadge.textContent = pluralizeTopics(clusters.length);

    if (clusters.length === 0) {
      grid.innerHTML = `
        <div class="col-span-2 bg-white rounded-2xl p-10 text-center border border-slate-200">
          <i data-lucide="check-circle" class="w-12 h-12 mx-auto text-emerald-500 mb-2"></i>
          <h4 class="font-bold text-slate-800">Нет неразобранных пробелов</h4>
          <p class="text-xs text-slate-500 mt-1">Все неудачные поисковые запросы либо решены написанием статей, либо нажмите кнопку «Запустить кластеризацию» выше.</p>
        </div>
      `;
      lucide.createIcons();
      return;
    }

    let html = "";
    clusters.forEach(c => {
      const statusMap = {
        new: `<span class="px-2 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded text-xs font-semibold">Новый</span>`,
        in_progress: `<span class="px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded text-xs font-semibold">В работе</span>`,
        resolved: `<span class="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded text-xs font-semibold">Решено</span>`
      };

      const keywordsHtml = (c.keywords || []).map(k => 
        `<span class="px-2 py-0.5 bg-slate-100 text-slate-700 rounded-md text-[11px] font-mono">#${escapeHtml(k)}</span>`
      ).join(" ");

      const queriesHtml = (c.sample_queries || []).map(q => 
        `<li class="text-xs text-slate-600 pl-2 border-l-2 border-indigo-200">«${escapeHtml(q)}»</li>`
      ).join("");

      const dateBadgeHtml = (c.status === "resolved")
        ? `<span class="inline-flex items-center text-emerald-700 text-xs bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200" title="Дата решения темы"><i data-lucide="check-circle" class="w-3.5 h-3.5 mr-1 text-emerald-600 shrink-0"></i><span>Решен: ${formatClusterDate(c.resolved_at || c.updated_at)}</span></span>`
        : `<span class="inline-flex items-center text-slate-600 text-xs bg-slate-100/90 px-2 py-0.5 rounded border border-slate-200" title="Дата выявления темы"><i data-lucide="calendar" class="w-3.5 h-3.5 mr-1 text-slate-500 shrink-0"></i><span>Выявлен: ${formatClusterDate(c.created_at)}</span></span>`;

      html += `
        <div onclick="openClusterDetailModal(${c.id})" class="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3 flex flex-col justify-between hover:border-indigo-300 hover:shadow-md transition-all cursor-pointer group">
          <div class="space-y-2.5">
            <div class="flex items-start justify-between gap-2">
              <h4 class="font-bold text-slate-900 text-base leading-snug group-hover:text-indigo-600 transition">
                ${escapeHtml(c.title)}
              </h4>
              <div class="shrink-0">
                ${statusMap[c.status] || ""}
              </div>
            </div>

            <div class="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span class="font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded">
                ${pluralizeQueries(c.query_count)}
              </span>
              <span>•</span>
              ${dateBadgeHtml}
              <span>•</span>
              <span class="font-mono text-[11px] bg-slate-100 px-1.5 py-0.5 rounded text-slate-600" title="3D координаты центроида (PCA)">Координаты: (${c.pca_x}, ${c.pca_y}, ${c.pca_z ?? 0})</span>
            </div>

            <!-- Ключевые слова темы (TF-IDF) -->
            <div class="flex flex-wrap gap-1 pt-1">
              ${keywordsHtml}
            </div>

            <!-- Примеры запросов пользователей -->
            <div class="pt-1.5">
              <div class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Примеры запросов операторов:</div>
              <ul class="space-y-1">
                ${queriesHtml}
              </ul>
            </div>
          </div>
        </div>
      `;
    });

    grid.innerHTML = html;
    lucide.createIcons();

    if (currentClusterViewMode === "3d") {
      load3dVisualization();
    }

  } catch (err) {
    grid.innerHTML = `<div class="col-span-2 text-rose-600 text-center text-xs">Ошибка загрузки кластеров: ${err.message}</div>`;
  }
}

async function runClustering() {
  const btn = document.getElementById("btnRunClustering");
  const banner = document.getElementById("clusteringMetricsBanner");
  const bannerText = document.getElementById("clusteringBannerText");
  const silBadge = document.getElementById("clusteringSilhouetteBadge");

  btn.disabled = true;
  btn.innerHTML = `<i data-lucide="loader-2" class="w-5 h-5 animate-spin"></i><span>Выполняется NLP анализ...</span>`;
  lucide.createIcons();

  try {
    const res = await apiFetch(`${API_BASE}/api/v1/gaps/clusterize`, { method: "POST" });
    if (!res.ok) throw new Error("Clustering execution failed");
    const result = await res.json();

    banner.className = "p-4 rounded-xl border border-emerald-200 bg-emerald-50 flex items-center justify-between text-xs text-emerald-900";
    banner.classList.remove("hidden");
    bannerText.innerHTML = `<strong>${result.message}</strong>`;
    
    if (result.silhouette_score !== null) {
      silBadge.innerHTML = `Метрика силуэта (Silhouette): <span class="text-indigo-700 font-bold">${result.silhouette_score}</span>`;
      silBadge.classList.remove("hidden");
    } else {
      silBadge.classList.add("hidden");
    }

    showToast(result.message, "success");
    await loadClusters();

  } catch (err) {
    showToast("Ошибка при кластеризации: " + err.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i data-lucide="cpu" class="w-5 h-5"></i><span>Запустить кластеризацию</span>`;
    lucide.createIcons();
  }
}

async function updateClusterStatus(clusterId, status) {
  try {
    const res = await apiFetch(`${API_BASE}/api/v1/gaps/clusters/${clusterId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: status })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Недостаточно прав для изменения статуса");
    }
    showToast("Статус темы обновлен", "success");
    loadClustersCountBadge();
    await loadClusters();
  } catch (e) {
    showToast(e.message, "error");
    await loadClusters();
  }
}

function createArticleFromCluster(clusterId, title, tags) {
  openArticleModal();
  document.getElementById("editTitle").value = title;
  document.getElementById("editTags").value = tags;
  document.getElementById("editSummary").value = `Решение проблемы: ${title}`;
  document.getElementById("fromClusterId").value = clusterId;
  document.getElementById("editModalHeader").textContent = "Создание статьи по выявленному пробелу";
}

let activeDetailClusterId = null;

async function openClusterDetailModal(clusterId) {
  activeDetailClusterId = clusterId;
  const modal = document.getElementById("clusterDetailModal");
  if (!modal) return;

  modal.classList.remove("hidden");
  document.body.style.overflow = "hidden";

  const titleEl = document.getElementById("detailClusterTitle");
  const idEl = document.getElementById("detailClusterIdBadge");
  const statusEl = document.getElementById("detailClusterStatusBadge");
  const dateEl = document.getElementById("detailClusterDate");
  const queriesBadge = document.getElementById("detailMetricQueries");
  const coordsMetric = document.getElementById("detailMetricCoords");
  const statusSelect = document.getElementById("detailClusterStatusSelect");
  const descEl = document.getElementById("detailClusterDescription");
  const kwEl = document.getElementById("detailClusterKeywords");
  const tableBody = document.getElementById("detailQueriesTableBody");
  const tableCountBadge = document.getElementById("detailQueriesTableBadge");
  const resolvedBanner = document.getElementById("detailResolvedArticleBanner");
  const resolvedTitle = document.getElementById("detailResolvedArticleTitle");
  const btnViewResolved = document.getElementById("btnViewResolvedArticle");
  const btnDelete = document.getElementById("btnDeleteClusterModal");
  const btnWrite = document.getElementById("btnWriteArticleClusterModal");

  titleEl.textContent = "Загрузка информации о теме...";
  idEl.textContent = `#${clusterId}`;
  tableBody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-slate-400">Загрузка запросов темы...</td></tr>`;

  try {
    const res = await apiFetch(`${API_BASE}/api/v1/gaps/clusters/${clusterId}`);
    if (!res.ok) throw new Error("Не удалось загрузить данные темы");
    const cluster = await res.json();

    const statusMap = {
      new: `<span class="px-2 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded text-xs font-semibold">Новый</span>`,
      in_progress: `<span class="px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded text-xs font-semibold">В работе</span>`,
      resolved: `<span class="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded text-xs font-semibold">Решено</span>`
    };

    titleEl.textContent = (cluster.title || "").replace(/\.{3,}$/, "").trim();
    statusEl.innerHTML = statusMap[cluster.status] || "";
    dateEl.innerHTML = `<i data-lucide="calendar" class="w-3.5 h-3.5 mr-1 text-slate-400"></i>Выявлен: ${formatClusterDate(cluster.created_at)}${cluster.resolved_at ? ` • <span class="text-emerald-600 font-semibold">Решен: ${formatClusterDate(cluster.resolved_at)}</span>` : ''}`;
    queriesBadge.textContent = pluralizeQueries(cluster.query_count || (cluster.queries ? cluster.queries.length : 0));
    coordsMetric.textContent = `(${cluster.pca_x}, ${cluster.pca_y}, ${cluster.pca_z ?? 0})`;

    // Status select with Admin-only protection for 'resolved'
    if (currentRole !== "admin") {
      if (cluster.status === "resolved") {
        statusSelect.disabled = true;
        statusSelect.title = "Только Администратор может изменять статус решенной темы";
        statusSelect.className = "text-xs border border-slate-200 rounded px-2 py-1 bg-slate-100 font-medium text-slate-500 cursor-not-allowed w-full";
        statusSelect.innerHTML = `<option value="resolved" selected>Решен</option>`;
      } else {
        statusSelect.disabled = false;
        statusSelect.className = "text-xs border border-slate-200 rounded px-2 py-1 bg-white font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 w-full";
        statusSelect.innerHTML = `
          <option value="new" ${cluster.status === 'new' ? 'selected' : ''}>Новый</option>
          <option value="in_progress" ${cluster.status === 'in_progress' ? 'selected' : ''}>В работе</option>
          <option value="resolved" disabled class="text-slate-400">Решен (только Администратор)</option>
        `;
        statusSelect.value = cluster.status;
      }
    } else {
      statusSelect.disabled = false;
      statusSelect.className = "text-xs border border-slate-200 rounded px-2 py-1 bg-white font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500 w-full";
      statusSelect.innerHTML = `
        <option value="new" ${cluster.status === 'new' ? 'selected' : ''}>Новый</option>
        <option value="in_progress" ${cluster.status === 'in_progress' ? 'selected' : ''}>В работе</option>
        <option value="resolved" ${cluster.status === 'resolved' ? 'selected' : ''}>Решен</option>
      `;
      statusSelect.value = cluster.status;
    }

    descEl.textContent = cluster.description || `Тема выявлена алгоритмом NLP на основе ${cluster.query_count} поисковых запросов операторов.`;

    kwEl.innerHTML = (cluster.keywords || []).map(k => 
      `<span class="px-2.5 py-1 bg-indigo-50 text-indigo-700 rounded-lg text-xs font-mono font-medium border border-indigo-100">#${escapeHtml(k)}</span>`
    ).join(" ") || `<span class="text-slate-400 text-xs">Ключевые слова не выделены</span>`;

    // Resolved article banner
    if (cluster.created_article_id && cluster.created_article_title) {
      resolvedBanner.classList.remove("hidden");
      resolvedTitle.textContent = cluster.created_article_title;
      btnViewResolved.onclick = () => {
        closeClusterDetailModal();
        openArticleView(cluster.created_article_id);
      };
    } else {
      resolvedBanner.classList.add("hidden");
    }

    // Delete button (admin only)
    if (currentRole === "admin") {
      btnDelete.classList.remove("hidden");
      btnDelete.onclick = (e) => deleteClusterConfirm(cluster.id, e, cluster.title);
    } else {
      btnDelete.classList.add("hidden");
    }

    // Write article button
    btnWrite.onclick = () => {
      closeClusterDetailModal();
      createArticleFromCluster(cluster.id, (cluster.title || "").replace(/\.{3,}$/, "").trim(), (cluster.keywords || []).join(", "));
    };

    // Queries table
    const queries = cluster.queries || [];
    tableCountBadge.textContent = queries.length;
    if (queries.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-slate-400 text-xs">В данной теме пока нет привязанных запросов</td></tr>`;
    } else {
      let qHtml = "";
      queries.forEach(q => {
        const helpfulBadge = q.is_helpful === true
          ? `<span class="px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded text-[11px] font-medium">👍 Помогло</span>`
          : q.is_helpful === false
          ? `<span class="px-2 py-0.5 bg-rose-50 text-rose-700 rounded text-[11px] font-medium">👎 Не помогло</span>`
          : `<span class="px-2 py-0.5 bg-slate-100 text-slate-500 rounded text-[11px]">Без отметки</span>`;

        const typeBadge = `<span class="font-mono text-[10px] uppercase text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded font-medium">${escapeHtml(q.search_type || "hybrid")}</span>`;
        const qDateStr = formatClusterDate(q.timestamp);

        qHtml += `
          <tr class="hover:bg-slate-50 transition">
            <td class="px-3.5 py-2.5 font-mono text-[11px] text-slate-400">#${q.id}</td>
            <td class="px-3.5 py-2.5 font-medium text-slate-900 max-w-xs break-words">
              «${escapeHtml(q.query_text)}»
            </td>
            <td class="px-3.5 py-2.5 text-center">${typeBadge}</td>
            <td class="px-3.5 py-2.5 text-center font-mono text-slate-600">${q.results_count}</td>
            <td class="px-3.5 py-2.5 text-center">${helpfulBadge}</td>
            <td class="px-3.5 py-2.5 text-right text-slate-400 font-mono text-[11px] whitespace-nowrap">${qDateStr}</td>
            <td class="px-3.5 py-2.5 text-center whitespace-nowrap">
              <div class="flex items-center justify-center space-x-1">
                <button onclick="closeClusterDetailModal(); searchQueryFromLogs('${escapeHtml(q.query_text)}')" class="p-1 hover:bg-slate-100 text-indigo-600 rounded transition" title="Проверить запрос в поиске">
                  <i data-lucide="search" class="w-4 h-4"></i>
                </button>
                <button onclick="closeClusterDetailModal(); createArticleFromQuery('${escapeHtml(q.query_text)}')" class="p-1 hover:bg-emerald-50 text-emerald-600 rounded transition" title="Создать статью по запросу">
                  <i data-lucide="file-plus" class="w-4 h-4"></i>
                </button>
              </div>
            </td>
          </tr>
        `;
      });
      tableBody.innerHTML = qHtml;
    }

    lucide.createIcons();
  } catch (err) {
    titleEl.textContent = "Ошибка загрузки";
    tableBody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-rose-500 text-xs">${escapeHtml(err.message)}</td></tr>`;
  }
}

function closeClusterDetailModal() {
  const modal = document.getElementById("clusterDetailModal");
  if (modal) modal.classList.add("hidden");
  document.body.style.overflow = "";
  activeDetailClusterId = null;
}

async function updateClusterStatusFromModal(newStatus) {
  if (!activeDetailClusterId) return;
  await updateClusterStatus(activeDetailClusterId, newStatus);
  await openClusterDetailModal(activeDetailClusterId);
  await loadClusters();
}

async function deleteClusterConfirm(clusterId, event, clusterTitle = "") {
  if (event) event.stopPropagation();
  if (currentRole !== "admin") {
    showToast("Удаление кластеров доступно только Администратору", "error");
    return;
  }
  const titleHint = clusterTitle ? ` «${clusterTitle}»` : ` #${clusterId}`;
  if (!confirm(`Вы действительно хотите удалить тему пробелов${titleHint}? Запросы операторов останутся в журнале и будут отвязаны от темы.`)) {
    return;
  }

  try {
    const res = await apiFetch(`${API_BASE}/api/v1/gaps/clusters/${clusterId}`, {
      method: "DELETE"
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Не удалось удалить кластер");
    }
    showToast("Кластер успешно удален", "success");
    closeClusterDetailModal();
    await loadClusters();
    loadClustersCountBadge();
  } catch (err) {
    showToast("Ошибка удаления кластера: " + err.message, "error");
  }
}

// ==================== 3D СЕМАНТИЧЕСКАЯ ВИЗУАЛИЗАЦИЯ (PLOTLY 3D) ====================
let currentClusterViewMode = "grid";
let visualization3dData = null;

function setClusterViewMode(mode) {
  currentClusterViewMode = mode;
  const gridEl = document.getElementById("clustersGrid");
  const view3dEl = document.getElementById("clusters3dView");
  const btnGrid = document.getElementById("cluster-view-btn-grid");
  const btn3d = document.getElementById("cluster-view-btn-3d");
  const filterWrapper = document.getElementById("clusterFilterWrapper");

  if (mode === "3d") {
    if (gridEl) gridEl.classList.add("hidden");
    if (view3dEl) view3dEl.classList.remove("hidden");
    if (filterWrapper) filterWrapper.classList.add("hidden");

    if (btnGrid) btnGrid.className = "px-3 py-1.5 rounded-lg font-semibold transition flex items-center space-x-1.5 text-slate-600 hover:text-slate-900";
    if (btn3d) btn3d.className = "px-3 py-1.5 rounded-lg font-semibold transition flex items-center space-x-1.5 bg-white text-indigo-700 shadow-sm";

    load3dVisualization();
  } else {
    if (gridEl) gridEl.classList.remove("hidden");
    if (view3dEl) view3dEl.classList.add("hidden");
    if (filterWrapper) filterWrapper.classList.remove("hidden");

    if (btnGrid) btnGrid.className = "px-3 py-1.5 rounded-lg font-semibold transition flex items-center space-x-1.5 bg-white text-indigo-700 shadow-sm";
    if (btn3d) btn3d.className = "px-3 py-1.5 rounded-lg font-semibold transition flex items-center space-x-1.5 text-slate-600 hover:text-slate-900";
  }
  lucide.createIcons();
}

async function load3dVisualization() {
  const container = document.getElementById("plotly3dContainer");
  const loader = document.getElementById("plotly3dLoader");
  if (loader) loader.classList.remove("hidden");

  try {
    const res = await apiFetch(`${API_BASE}/api/v1/gaps/visualization/3d`);
    if (!res.ok) throw new Error("Ошибка загрузки данных 3D визуализации");
    const data = await res.json();
    visualization3dData = data;

    // Update metrics
    const ptsEl = document.getElementById("metric3dPoints");
    const clsEl = document.getElementById("metric3dClusters");
    const varEl = document.getElementById("metric3dVariance");
    if (ptsEl) ptsEl.textContent = data.total_points;
    if (clsEl) clsEl.textContent = data.clusters.length;
    if (varEl) varEl.textContent = `${data.total_variance}%`;

    const traces = [];

    // 1. Trace for each cluster's member queries
    data.clusters.forEach(c => {
      const cPoints = data.points.filter(p => p.cluster_id === c.id);
      if (cPoints.length === 0) return;

      traces.push({
        type: 'scatter3d',
        mode: 'markers',
        name: `${c.title} (${cPoints.length})`,
        x: cPoints.map(p => p.x),
        y: cPoints.map(p => p.y),
        z: cPoints.map(p => p.z),
        text: cPoints.map(p => p.query_text),
        customdata: cPoints.map(p => c.title),
        hovertemplate: 
          '<b>Запрос:</b> «%{text}»<br>' +
          '<b>Тема:</b> %{customdata}<br>' +
          '<b>Координаты:</b> X: %{x:.2f}, Y: %{y:.2f}, Z: %{z:.2f}' +
          '<extra></extra>',
        marker: {
          size: 5,
          color: c.color,
          opacity: 0.85
        }
      });
    });

    // 2. Centroids trace (larger diamond markers with label)
    if (data.clusters.length > 0) {
      const centroidHoverTexts = data.clusters.map(c => {
        const dStr = formatClusterDate(c.created_at);
        return `<b>Центр темы:</b> ${c.title}<br>` +
               `<b>Количество запросов:</b> ${c.query_count} запросов<br>` +
               `<b>Дата выявления:</b> ${dStr}<br>` +
               `<b>Центроид:</b> X: ${c.x.toFixed(2)}, Y: ${c.y.toFixed(2)}, Z: ${c.z.toFixed(2)}`;
      });

      traces.push({
        type: 'scatter3d',
        mode: 'markers+text',
        name: '★ Центроиды тем',
        showlegend: false,
        x: data.clusters.map(c => c.x),
        y: data.clusters.map(c => c.y),
        z: data.clusters.map(c => c.z),
        text: data.clusters.map(c => c.title),
        textposition: 'top center',
        textfont: {
          color: '#ffffff',
          size: 11,
          family: 'Inter, sans-serif'
        },
        hoverinfo: 'text',
        hovertext: centroidHoverTexts,
        marker: {
          size: 10,
          symbol: 'diamond',
          color: data.clusters.map(c => c.color),
          line: {
            color: '#ffffff',
            width: 2
          }
        }
      });
    }

    const layout = {
      margin: { l: 0, r: 0, b: 0, t: 0 },
      paper_bgcolor: '#0f172a', // slate-900
      plot_bgcolor: '#0f172a',
      scene: {
        aspectratio: { x: 1, y: 1, z: 0.8 },
        xaxis: {
          title: 'Семантическая ось X',
          color: '#94a3b8',
          gridcolor: '#1e293b',
          zerolinecolor: '#334155',
          backgroundcolor: '#0f172a'
        },
        yaxis: {
          title: 'Семантическая ось Y',
          color: '#94a3b8',
          gridcolor: '#1e293b',
          zerolinecolor: '#334155',
          backgroundcolor: '#0f172a'
        },
        zaxis: {
          title: 'Семантическая ось Z',
          color: '#94a3b8',
          gridcolor: '#1e293b',
          zerolinecolor: '#334155',
          backgroundcolor: '#0f172a'
        },
        camera: {
          eye: { x: 1.6, y: 1.6, z: 1.3 }
        }
      },
      legend: {
        font: { color: '#e2e8f0', size: 11, family: 'Inter, sans-serif' },
        bgcolor: 'rgba(15, 23, 42, 0.85)',
        bordercolor: '#334155',
        borderwidth: 1,
        orientation: 'v',
        x: 1,
        xanchor: 'right',
        y: 0.98
      }
    };

    const config = {
      responsive: true,
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToRemove: ['sendDataToCloud']
    };

    if (window.Plotly && container) {
      await Plotly.newPlot(container, traces, layout, config);
      
      // Clicking a centroid in 3D space opens detailed view of the cluster
      if (container.removeAllListeners) container.removeAllListeners('plotly_click');
      container.on('plotly_click', (eventData) => {
        if (!eventData || !eventData.points || eventData.points.length === 0) return;
        const pt = eventData.points[0];
        if (pt.data && pt.data.name === '★ Центроиды тем') {
          const clusterObj = data.clusters[pt.pointNumber];
          if (clusterObj && clusterObj.id) {
            openClusterDetailModal(clusterObj.id);
          }
        }
      });
    }

  } catch (err) {
    console.error("3D visualization error:", err);
    showToast("Ошибка 3D визуализации: " + err.message, "error");
  } finally {
    if (loader) loader.classList.add("hidden");
  }
}

function reset3dCamera() {
  const container = document.getElementById("plotly3dContainer");
  if (window.Plotly && container) {
    Plotly.relayout(container, {
      'scene.camera.eye': { x: 1.6, y: 1.6, z: 1.3 }
    });
  }
}

window.setClusterViewMode = setClusterViewMode;
window.reset3dCamera = reset3dCamera;

// ==================== УПРАВЛЕНИЕ СТАТЬЯМИ (КАТАЛОГ И РЕДАКТОР) ====================
let currentArticleSort = { field: "id", order: "asc" };

function updateArticleSortIcons() {
  const fields = ["id", "title", "category", "views", "rating"];
  fields.forEach(f => {
    const el = document.getElementById(`sort-art-${f}`);
    if (!el) return;
    if (currentArticleSort.field === f) {
      el.textContent = currentArticleSort.order === "asc" ? "▲" : "▼";
      el.className = "text-[11px] text-indigo-600 font-bold";
    } else {
      el.textContent = "↕";
      el.className = "text-[11px] text-slate-300 font-mono";
    }
  });
}

function sortArticles(field) {
  if (currentArticleSort.field === field) {
    currentArticleSort.order = currentArticleSort.order === "asc" ? "desc" : "asc";
  } else {
    currentArticleSort.field = field;
    currentArticleSort.order = "asc";
  }
  updateArticleSortIcons();
  filterArticlesTable();
}

function sortArticlesList(list) {
  const { field, order } = currentArticleSort;
  const factor = order === "asc" ? 1 : -1;

  return [...list].sort((a, b) => {
    switch (field) {
      case "id":
        return (Number(a.id) - Number(b.id)) * factor;
      case "title":
        return (a.title || "").localeCompare(b.title || "", "ru", { sensitivity: "base", numeric: true }) * factor;
      case "category":
        return (a.category_name || "—").localeCompare(b.category_name || "—", "ru", { sensitivity: "base", numeric: true }) * factor;
      case "views":
        return ((Number(a.views_count) || 0) - (Number(b.views_count) || 0)) * factor;
      case "rating": {
        const totalA = (Number(a.helpful_count) || 0) + (Number(a.unhelpful_count) || 0);
        const rateA = totalA > 0 ? (a.helpful_count / totalA) * 100 : 100;
        const totalB = (Number(b.helpful_count) || 0) + (Number(b.unhelpful_count) || 0);
        const rateB = totalB > 0 ? (b.helpful_count / totalB) * 100 : 100;
        return (rateA - rateB) * factor;
      }
      default:
        return 0;
    }
  });
}

async function loadArticles() {
  const tbody = document.getElementById("articlesTableBody");
  tbody.innerHTML = `<tr><td colspan="6" class="text-center py-8 text-slate-400">Загрузка каталога статей...</td></tr>`;

  try {
    const res = await apiFetch(`${API_BASE}/api/v1/articles?limit=500`);
    if (!res.ok) throw new Error("Failed to load articles");
    allArticlesList = await res.json();
    filterArticlesTable();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-rose-600 text-xs">${err.message}</td></tr>`;
  }
}

function renderArticlesTable(articles) {
  const tbody = document.getElementById("articlesTableBody");
  const countBadge = document.getElementById("articlesCountBadge");
  if (countBadge) {
    countBadge.textContent = `Статей: ${articles.length} из ${allArticlesList.length}`;
  }

  if (articles.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-slate-400 text-xs">Статьи не найдены</td></tr>`;
    return;
  }

  let html = "";
  articles.forEach(a => {
    const totalRated = (a.helpful_count || 0) + (a.unhelpful_count || 0);
    const rate = totalRated > 0 ? Math.round((a.helpful_count / totalRated) * 100) : 100;

    let actionsHtml = `<div class="flex items-center justify-center space-x-1">`;
    if (currentRole === "admin" || currentRole === "moderator") {
      actionsHtml += `
        <button onclick="editArticleModal(${a.id})" class="p-1 hover:bg-indigo-50 text-indigo-600 rounded transition" title="Редактировать статью">
          <i data-lucide="edit-3" class="w-4 h-4"></i>
        </button>
      `;
    }
    if (currentRole === "admin") {
      actionsHtml += `
        <button onclick="deleteArticleConfirm(${a.id})" class="p-1 hover:bg-rose-50 text-rose-600 rounded transition" title="Удалить статью">
          <i data-lucide="trash-2" class="w-4 h-4"></i>
        </button>
      `;
    }
    if (currentRole === "operator") {
      actionsHtml += `
        <button onclick="openArticleView(${a.id})" class="p-1 hover:bg-slate-100 text-slate-600 rounded transition" title="Читать статью">
          <i data-lucide="eye" class="w-4 h-4"></i>
        </button>
      `;
    }
    actionsHtml += `</div>`;

    html += `
      <tr class="hover:bg-slate-50 transition">
        <td class="px-4 py-3 font-mono text-xs text-slate-400">#${a.id}</td>
        <td class="px-4 py-3 font-medium text-slate-900 cursor-pointer hover:text-indigo-600" onclick="openArticleView(${a.id})">
          ${escapeHtml(a.title)}
        </td>
        <td class="px-4 py-3 text-xs text-slate-500">${escapeHtml(a.category_name || "—")}</td>
        <td class="px-4 py-3 text-center text-xs font-semibold text-slate-600">${a.views_count}</td>
        <td class="px-4 py-3 text-center text-xs font-bold text-emerald-600">${rate}% 👍</td>
        <td class="px-4 py-3 text-center">
          ${actionsHtml}
        </td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
  lucide.createIcons();
}

async function deleteArticleConfirm(articleId) {
  if (!confirm("Вы действительно хотите удалить эту статью? Действие необратимо.")) return;
  try {
    const res = await apiFetch(`${API_BASE}/api/v1/articles/${articleId}`, {
      method: "DELETE"
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Недостаточно прав (только Администратор)");
    }
    showToast("Статья успешно удалена", "success");
    loadArticles();
  } catch (err) {
    showToast("Ошибка удаления: " + err.message, "error");
  }
}

function filterArticlesTable() {
  const q = (document.getElementById("articleFilterInput")?.value || "").toLowerCase().trim();
  const filtered = allArticlesList.filter(a => 
    !q || 
    (a.title && a.title.toLowerCase().includes(q)) || 
    (a.category_name && a.category_name.toLowerCase().includes(q))
  );
  const sorted = sortArticlesList(filtered);
  renderArticlesTable(sorted);
}

function openArticleModal() {
  document.getElementById("articleForm").reset();
  document.getElementById("editArticleId").value = "";
  document.getElementById("fromClusterId").value = "";
  document.getElementById("editModalHeader").textContent = "Создание статьи базы знаний";
  document.getElementById("articleEditModal").classList.remove("hidden");
}

function closeArticleEditModal() {
  document.getElementById("articleEditModal").classList.add("hidden");
}

async function editArticleModal(articleId) {
  try {
    const res = await apiFetch(`${API_BASE}/api/v1/articles/${articleId}`);
    if (!res.ok) return;
    const a = await res.json();

    document.getElementById("editArticleId").value = a.id;
    document.getElementById("fromClusterId").value = "";
    document.getElementById("editTitle").value = a.title;
    document.getElementById("editSummary").value = a.summary || "";
    document.getElementById("editTags").value = a.tags || "";
    document.getElementById("editCategory").value = a.category_id || "";
    document.getElementById("editContent").value = a.content;
    document.getElementById("editModalHeader").textContent = "Редактирование статьи";
    document.getElementById("articleEditModal").classList.remove("hidden");
  } catch (e) {}
}

async function saveArticle(event) {
  event.preventDefault();
  const articleId = document.getElementById("editArticleId").value;
  const clusterId = document.getElementById("fromClusterId").value;

  const payload = {
    title: document.getElementById("editTitle").value.trim(),
    summary: document.getElementById("editSummary").value.trim(),
    tags: document.getElementById("editTags").value.trim(),
    category_id: parseInt(document.getElementById("editCategory").value) || null,
    content: document.getElementById("editContent").value.trim(),
    is_published: true
  };

  try {
    let savedArticle = null;
    if (articleId) {
      // Update
      const res = await apiFetch(`${API_BASE}/api/v1/articles/${articleId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Save failed");
      savedArticle = await res.json();
      showToast("Статья успешно обновлена и переиндексирована!", "success");
    } else {
      // Create
      const res = await apiFetch(`${API_BASE}/api/v1/articles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Creation failed");
      savedArticle = await res.json();
      showToast("Новая статья создана и добавлен векторный эмбеддинг!", "success");

      // If created from cluster, mark cluster resolved (if admin) or in_progress (if moderator)
      if (clusterId && savedArticle) {
        const targetStatus = (currentRole === "admin") ? "resolved" : "in_progress";
        await apiFetch(`${API_BASE}/api/v1/gaps/clusters/${clusterId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: targetStatus, created_article_id: savedArticle.id })
        });
        if (currentRole === "admin") {
          showToast("Пробел знаний помечен как решённый!", "success");
        } else {
          showToast("Статья создана и привязана к кластеру пробела (тема в работе)", "info");
        }
      }
    }

    closeArticleEditModal();
    if (currentTab === "articles") loadArticles();
    if (currentTab === "clusters") loadClusters();

  } catch (err) {
    showToast("Ошибка сохранения: " + err.message, "error");
  }
}

// ==================== ЖУРНАЛ ЗАПРОСОВ (ВСЕ ЗАПРОСЫ) ====================
let allSearchLogsList = [];
let currentLogsSort = { field: "id", order: "desc" };

function updateLogsSortIcons() {
  const fields = ["id", "query", "status", "target", "algorithm", "date"];
  fields.forEach(f => {
    const el = document.getElementById(`sort-log-${f}`);
    if (!el) return;
    if (currentLogsSort.field === f) {
      el.textContent = currentLogsSort.order === "asc" ? "▲" : "▼";
      el.className = "text-[11px] text-indigo-600 font-bold";
    } else {
      el.textContent = "↕";
      el.className = "text-[11px] text-slate-300 font-mono";
    }
  });
}

function sortLogs(field) {
  if (currentLogsSort.field === field) {
    currentLogsSort.order = currentLogsSort.order === "asc" ? "desc" : "asc";
  } else {
    currentLogsSort.field = field;
    currentLogsSort.order = "asc";
  }
  updateLogsSortIcons();
  filterLogsTable();
}

function sortLogsList(list) {
  const { field, order } = currentLogsSort;
  const factor = order === "asc" ? 1 : -1;

  return [...list].sort((a, b) => {
    switch (field) {
      case "id":
        return (Number(a.id) - Number(b.id)) * factor;
      case "query":
        return (a.query_text || "").localeCompare(b.query_text || "", "ru", { sensitivity: "base", numeric: true }) * factor;
      case "status": {
        const valA = a.is_helpful === true ? "1_Успех" : "2_Пробел";
        const valB = b.is_helpful === true ? "1_Успех" : "2_Пробел";
        return valA.localeCompare(valB, "ru") * factor;
      }
      case "target": {
        const valA = a.clicked_article_title || (a.cluster_title ? formatShortClusterTitle(a.cluster_title) : "—");
        const valB = b.clicked_article_title || (b.cluster_title ? formatShortClusterTitle(b.cluster_title) : "—");
        return valA.localeCompare(valB, "ru", { sensitivity: "base", numeric: true }) * factor;
      }
      case "algorithm":
        return (a.search_type || "hybrid").localeCompare(b.search_type || "hybrid", "ru") * factor;
      case "date": {
        const timeA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
        const timeB = b.timestamp ? new Date(b.timestamp).getTime() : 0;
        return (timeA - timeB) * factor;
      }
      default:
        return 0;
    }
  });
}

async function loadSearchLogs() {
  const tbody = document.getElementById("logsTableBody");
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-slate-400">Загрузка журнала запросов...</td></tr>`;

  try {
    const res = await apiFetch(`${API_BASE}/api/v1/search/logs?limit=500`);
    if (!res.ok) throw new Error("Не удалось загрузить журнал запросов");
    allSearchLogsList = await res.json();

    // Update KPI badges: Успех только при явном подтверждении оператора
    const total = allSearchLogsList.length;
    const success = allSearchLogsList.filter(l => l.is_helpful === true && l.clicked_article_title).length;
    const gaps = allSearchLogsList.filter(l => l.is_search_gap || l.is_helpful === false).length;
    const rate = total > 0 ? ((gaps / total) * 100).toFixed(1) : "0.0";

    const elTotal = document.getElementById("logs-kpi-total");
    const elSuccess = document.getElementById("logs-kpi-success");
    const elGaps = document.getElementById("logs-kpi-gaps");
    const elRate = document.getElementById("logs-kpi-rate");

    if (elTotal) elTotal.textContent = total;
    if (elSuccess) elSuccess.textContent = success;
    if (elGaps) elGaps.textContent = gaps;
    if (elRate) elRate.textContent = `${rate}%`;

    filterLogsTable();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-rose-600">${escapeHtml(err.message)}</td></tr>`;
  }
}

function filterLogsTable() {
  const query = (document.getElementById("logsFilterInput")?.value || "").toLowerCase().trim();
  const typeFilter = document.getElementById("logsTypeFilter")?.value || "all";

  let filtered = allSearchLogsList.filter(l => {
    const matchesQuery = !query || 
      (l.query_text && l.query_text.toLowerCase().includes(query)) || 
      (l.clicked_article_title && l.clicked_article_title.toLowerCase().includes(query)) ||
      (l.cluster_title && l.cluster_title.toLowerCase().includes(query));

    let matchesType = true;
    if (typeFilter === "success") matchesType = (l.is_helpful === true);
    if (typeFilter === "gaps") matchesType = (l.is_search_gap || l.is_helpful === false);

    return matchesQuery && matchesType;
  });

  const sorted = sortLogsList(filtered);
  renderLogsTable(sorted);
}

function renderLogsTable(logs) {
  const tbody = document.getElementById("logsTableBody");
  const countBadge = document.getElementById("logsCountBadge");
  if (!tbody) return;

  if (countBadge) {
    countBadge.textContent = `Запросов: ${logs.length} из ${allSearchLogsList.length}`;
  }

  if (logs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-slate-400">Запросы не найдены</td></tr>`;
    return;
  }

  let html = "";
  logs.forEach(l => {
    const isSuccess = l.is_helpful === true;
    const statusBadge = isSuccess
      ? `<span class="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded font-semibold text-[11px] inline-flex items-center space-x-1" title="Оператор подтвердил, что решение помогло">
           <i data-lucide="check" class="w-3 h-3 text-emerald-600"></i>
           <span>Успех</span>
         </span>`
      : `<span class="px-2 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded font-semibold text-[11px] inline-flex items-center space-x-1" title="Поисковый пробел (решение не найдено или не помогло)">
           <i data-lucide="alert-circle" class="w-3 h-3 text-rose-600"></i>
           <span>Пробел</span>
         </span>`;

    let targetHtml = `<span class="text-slate-400">—</span>`;
    if (l.clicked_article_title && l.clicked_article_id) {
      targetHtml = `
        <button onclick="openArticleView(${l.clicked_article_id})" class="text-indigo-600 hover:text-indigo-900 font-medium text-left flex items-center space-x-1.5 text-xs truncate max-w-[280px]" title="${escapeHtml(l.clicked_article_title)}">
          <i data-lucide="file-text" class="w-3.5 h-3.5 shrink-0 text-indigo-500"></i>
          <span class="truncate">${escapeHtml(l.clicked_article_title)}</span>
        </button>
      `;
    } else if (l.cluster_title) {
      const shortC = formatShortClusterTitle(l.cluster_title);
      targetHtml = `
        <span class="inline-flex items-center space-x-1 px-2 py-0.5 bg-indigo-50 text-indigo-700 border border-indigo-100 rounded text-[10px] font-semibold" title="Тема кластера: ${escapeHtml(l.cluster_title)}">
          <span class="w-1.5 h-1.5 rounded-full bg-indigo-500 shrink-0"></span>
          <span>${escapeHtml(shortC)}</span>
        </span>
      `;
    } else if (l.is_search_gap) {
      targetHtml = `<span class="text-slate-400 text-xs italic">Не в кластере</span>`;
    }

    const typeBadge = `<span class="font-mono text-[10px] uppercase text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded font-medium">${escapeHtml(l.search_type || "hybrid")}</span>`;
    const dateStr = l.timestamp ? new Date(l.timestamp).toLocaleString("ru-RU") : "—";

    let actions = `
      <div class="flex items-center justify-center space-x-1">
        <button onclick="searchQueryFromLogs('${escapeHtml(l.query_text)}')" class="p-1 hover:bg-slate-100 text-indigo-600 rounded transition" title="Проверить запрос в поиске">
          <i data-lucide="search" class="w-4 h-4"></i>
        </button>
    `;
    if (!isSuccess && (l.is_search_gap || l.is_helpful === false)) {
      actions += `
        <button onclick="createArticleFromQuery('${escapeHtml(l.query_text)}')" class="p-1 hover:bg-emerald-50 text-emerald-600 rounded transition" title="Создать статью по этому запросу">
          <i data-lucide="file-plus" class="w-4 h-4"></i>
        </button>
      `;
    }
    if (currentRole === "admin") {
      actions += `
        <button onclick="deleteSearchLogConfirm(${l.id})" class="p-1 hover:bg-rose-50 text-rose-600 rounded transition" title="Удалить запрос из журнала">
          <i data-lucide="trash-2" class="w-4 h-4"></i>
        </button>
      `;
    }
    actions += `</div>`;

    html += `
      <tr class="hover:bg-slate-50/80 transition">
        <td class="px-4 py-2.5 font-mono text-[11px] text-slate-400">#${l.id}</td>
        <td class="px-4 py-2.5 font-medium text-slate-900 max-w-sm">
          «${escapeHtml(l.query_text)}»
        </td>
        <td class="px-4 py-2.5 text-center">${statusBadge}</td>
        <td class="px-4 py-2.5">${targetHtml}</td>
        <td class="px-4 py-2.5 text-center">${typeBadge}</td>
        <td class="px-4 py-2.5 text-right text-slate-400 font-mono text-[11px] whitespace-nowrap">${dateStr}</td>
        <td class="px-4 py-2.5 text-center">${actions}</td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
  lucide.createIcons();
}

function searchQueryFromLogs(query) {
  switchTab("search");
  const input = document.getElementById("searchInput");
  if (input) {
    input.value = query;
    executeSearch();
  }
}

function createArticleFromQuery(query) {
  openArticleModal();
  const titleEl = document.getElementById("editTitle");
  const sumEl = document.getElementById("editSummary");
  if (titleEl) titleEl.value = query.charAt(0).toUpperCase() + query.slice(1);
  if (sumEl) sumEl.value = `Руководство по решению проблемы: ${query}`;
}

async function deleteSearchLogConfirm(logId) {
  if (!confirm(`Вы действительно хотите удалить запись запроса #${logId} из журнала? Действие необратимо.`)) {
    return;
  }

  try {
    const res = await apiFetch(`${API_BASE}/api/v1/search/logs/${logId}`, {
      method: "DELETE"
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Недостаточно прав (только Администратор)");
    }
    showToast("Запись поискового запроса успешно удалена", "success");
    await loadSearchLogs();
  } catch (err) {
    showToast("Ошибка удаления запроса: " + err.message, "error");
  }
}

// ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
function showToast(message, type = "info") {
  const toast = document.createElement("div");
  const bgColors = {
    success: "bg-emerald-600",
    warning: "bg-amber-600",
    error: "bg-rose-600",
    info: "bg-indigo-600"
  };
  toast.className = `fixed bottom-5 right-5 z-50 px-4 py-2.5 rounded-xl text-white text-xs font-semibold shadow-xl transition transform translate-y-2 opacity-0 flex items-center space-x-2 ${bgColors[type] || bgColors.info}`;
  toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.classList.remove("translate-y-2", "opacity-0");
  }, 10);

  setTimeout(() => {
    toast.classList.add("translate-y-2", "opacity-0");
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
