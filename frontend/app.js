// HelpDesk Knowledge Base Client Application

const API_BASE = ""; // Relative to host
let currentTab = "search";
let searchMode = "hybrid";
let currentSearchId = null;
let currentViewingArticleId = null;
let trendChart = null;
let categoriesList = [];
let allArticlesList = [];

// ==================== ИНИЦИАЛИЗАЦИЯ ====================
document.addEventListener("DOMContentLoaded", async () => {
  lucide.createIcons();
  await loadCategories();
  await loadClustersCountBadge();
});

// ==================== НАВИГАЦИЯ ====================
function switchTab(tab) {
  currentTab = tab;
  
  // Hide all sections
  ["search", "dashboard", "clusters", "articles"].forEach(t => {
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
  if (tab === "dashboard") loadDashboard();
  if (tab === "clusters") loadClusters();
  if (tab === "articles") loadArticles();

  lucide.createIcons();
}

function changeUserRole(role) {
  // Simple role switcher for demo purposes
  const roleNames = { moderator: "Модератор", operator: "Оператор ТП", admin: "Администратор" };
  console.log("Active role:", role);
}

// ==================== КАТЕГОРИИ ====================
async function loadCategories() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/articles/categories`);
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

async function executeSearch() {
  const query = document.getElementById("searchInput").value.trim();
  if (!query) return;

  const resultsList = document.getElementById("resultsList");
  const searchMeta = document.getElementById("searchMeta");
  const catVal = document.getElementById("searchCategory").value;
  const langVal = document.getElementById("searchLanguage").value;

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
      language: langVal || null,
      top_k: 8
    };

    const res = await fetch(`${API_BASE}/api/v1/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("Search request failed");
    const data = await res.json();
    currentSearchId = data.search_id;

    // Show meta
    searchMeta.classList.remove("hidden");
    document.getElementById("resultsCountText").textContent = `Найдено решений: ${data.results_count}`;
    document.getElementById("searchMetricsText").textContent = `Режим: ${data.search_mode.toUpperCase()} | Время: ${data.execution_time_ms} мс`;

    if (data.results.length === 0) {
      // ZERO RESULTS: Explicit search gap!
      resultsList.innerHTML = `
        <div class="bg-amber-50 rounded-2xl p-8 border border-amber-200 text-center space-y-3">
          <div class="w-12 h-12 bg-amber-100 text-amber-700 rounded-full flex items-center justify-center mx-auto">
            <i data-lucide="alert-circle" class="w-6 h-6"></i>
          </div>
          <div>
            <h4 class="font-bold text-amber-900 text-base">По вашему запросу не найдено подходящих решений</h4>
            <p class="text-xs text-amber-700 mt-1 max-w-lg mx-auto">
              Запрос <strong>«${escapeHtml(query)}»</strong> автоматически зарегистрирован системой как <span class="font-semibold text-rose-700">поисковый пробел</span>. Он будет учтён модулем кластеризации для создания новой статьи модератором.
            </p>
          </div>
          <button onclick="switchTab('clusters')" class="inline-flex items-center space-x-1.5 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold shadow-sm transition">
            <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
            <span>Посмотреть темы в очереди на написание</span>
          </button>
        </div>
      `;
      lucide.createIcons();
      return;
    }

    // Render search results
    let html = "";
    data.results.forEach((item, index) => {
      const langBadge = item.language === "en" 
        ? `<span class="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px] font-bold">EN</span>`
        : `<span class="px-1.5 py-0.5 bg-slate-100 text-slate-700 rounded text-[10px] font-bold">RU</span>`;
      
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
              ${langBadge}
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
  const langEl = document.getElementById("modalArticleLang");
  const contentEl = document.getElementById("modalArticleContent");
  const btnGroup = document.getElementById("feedbackButtonsGroup");

  titleEl.textContent = "Загрузка...";
  contentEl.innerHTML = `<div class="py-8 text-center text-slate-400">Загрузка содержимого...</div>`;
  modal.classList.remove("hidden");
  btnGroup.style.display = "flex";

  try {
    const res = await fetch(`${API_BASE}/api/v1/articles/${articleId}`);
    if (!res.ok) throw new Error("Failed to load article");
    const article = await res.json();

    titleEl.textContent = article.title;
    catEl.textContent = article.category ? article.category.name : "Общее";
    langEl.textContent = article.language;
    
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
  if (!currentSearchId && !currentViewingArticleId) {
    closeArticleViewModal();
    return;
  }

  try {
    if (currentSearchId) {
      await fetch(`${API_BASE}/api/v1/search/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          search_id: currentSearchId,
          clicked_article_id: currentViewingArticleId,
          is_helpful: isHelpful,
          feedback_notes: isHelpful ? "Решение подошло" : "Ответ не помог / информация неполная"
        })
      });
    } else if (currentViewingArticleId) {
      await fetch(`${API_BASE}/api/v1/articles/${currentViewingArticleId}/rate?helpful=${isHelpful}`, {
        method: "POST"
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

// ==================== АНАЛИТИКА (МОДЕРАТОР) ====================
async function loadDashboard() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/stats/dashboard`);
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
        const clusterBadge = g.cluster_title 
          ? `<span class="px-1.5 py-0.5 bg-indigo-50 text-indigo-700 rounded text-[10px] font-medium truncate max-w-[150px]">${escapeHtml(g.cluster_title)}</span>`
          : `<span class="text-[10px] text-amber-600">Не в кластере</span>`;
        gHtml += `
          <div class="p-2 rounded-lg bg-rose-50/50 border border-rose-100 flex items-center justify-between">
            <div>
              <div class="text-xs text-slate-800 font-medium">«${escapeHtml(g.query_text)}»</div>
              <div class="text-[10px] text-slate-400">${new Date(g.timestamp).toLocaleString("ru-RU")}</div>
            </div>
            ${clusterBadge}
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
    const res = await fetch(`${API_BASE}/api/v1/gaps/clusters?status_filter=new`);
    if (res.ok) {
      const data = await res.json();
      const badge = document.getElementById("nav-clusters-count");
      if (badge) badge.textContent = data.length;
    }
  } catch (e) {}
}

async function loadClusters() {
  const grid = document.getElementById("clustersGrid");
  const filter = document.getElementById("clusterFilter").value;
  grid.innerHTML = `<div class="col-span-2 py-8 text-center text-slate-400 animate-pulse">Загрузка кластеров...</div>`;

  try {
    let url = `${API_BASE}/api/v1/gaps/clusters`;
    if (filter) url += `?status_filter=${filter}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load clusters");
    const clusters = await res.json();

    loadClustersCountBadge();

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

      html += `
        <div class="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3 flex flex-col justify-between">
          <div class="space-y-2">
            <div class="flex items-start justify-between gap-2">
              <h4 class="font-bold text-slate-900 text-base leading-snug">
                ${escapeHtml(c.title)}
              </h4>
              ${statusMap[c.status] || ""}
            </div>

            <div class="flex items-center space-x-2 text-xs text-slate-500">
              <span class="font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded">
                ${c.query_count} неудачных запросов
              </span>
              <span>•</span>
              <span>Координаты: (${c.pca_x}, ${c.pca_y})</span>
            </div>

            <!-- Ключевые слова темы (TF-IDF) -->
            <div class="flex flex-wrap gap-1 pt-1">
              ${keywordsHtml}
            </div>

            <!-- Примеры запросов пользователей -->
            <div class="pt-2">
              <div class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">Примеры запросов операторов:</div>
              <ul class="space-y-1">
                ${queriesHtml}
              </ul>
            </div>
          </div>

          <!-- Действия модератора -->
          <div class="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
            <select onchange="updateClusterStatus(${c.id}, this.value)" class="text-xs border border-slate-200 rounded px-2 py-1 bg-slate-50 font-medium">
              <option value="new" ${c.status === 'new' ? 'selected' : ''}>Статус: Новый</option>
              <option value="in_progress" ${c.status === 'in_progress' ? 'selected' : ''}>Статус: В работе</option>
              <option value="resolved" ${c.status === 'resolved' ? 'selected' : ''}>Статус: Решен</option>
            </select>

            <button onclick="createArticleFromCluster(${c.id}, '${escapeHtml(c.title)}', '${(c.keywords || []).join(", ")}')" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition">
              <i data-lucide="edit-3" class="w-3.5 h-3.5"></i>
              <span>Написать статью</span>
            </button>
          </div>
        </div>
      `;
    });

    grid.innerHTML = html;
    lucide.createIcons();

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
    const res = await fetch(`${API_BASE}/api/v1/gaps/clusterize`, { method: "POST" });
    if (!res.ok) throw new Error("Clustering execution failed");
    const result = await res.json();

    banner.className = "p-4 rounded-xl border border-emerald-200 bg-emerald-50 flex items-center justify-between text-xs text-emerald-900";
    banner.classList.remove("hidden");
    bannerText.innerHTML = `<strong>${result.message}</strong> (Алгоритм: ${result.algorithm})`;
    
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
    await fetch(`${API_BASE}/api/v1/gaps/clusters/${clusterId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: status })
    });
    showToast("Статус темы обновлен", "success");
    loadClustersCountBadge();
  } catch (e) {}
}

function createArticleFromCluster(clusterId, title, tags) {
  openArticleModal();
  document.getElementById("editTitle").value = title;
  document.getElementById("editTags").value = tags;
  document.getElementById("editSummary").value = `Решение проблемы: ${title}`;
  document.getElementById("fromClusterId").value = clusterId;
  document.getElementById("editModalHeader").textContent = "Создание статьи по выявленному пробелу";
}

// ==================== УПРАВЛЕНИЕ СТАТЬЯМИ (КАТАЛОГ И РЕДАКТОР) ====================
async function loadArticles() {
  const tbody = document.getElementById("articlesTableBody");
  tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-slate-400">Загрузка каталога статей...</td></tr>`;

  try {
    const res = await fetch(`${API_BASE}/api/v1/articles?limit=100`);
    if (!res.ok) throw new Error("Failed to load articles");
    allArticlesList = await res.json();
    renderArticlesTable(allArticlesList);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-rose-600 text-xs">${err.message}</td></tr>`;
  }
}

function renderArticlesTable(articles) {
  const tbody = document.getElementById("articlesTableBody");
  const countBadge = document.getElementById("articlesCountBadge");
  countBadge.textContent = `Всего статей: ${articles.length}`;

  if (articles.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-6 text-slate-400 text-xs">Статьи не найдены</td></tr>`;
    return;
  }

  let html = "";
  articles.forEach(a => {
    const totalRated = a.helpful_count + a.unhelpful_count;
    const rate = totalRated > 0 ? Math.round((a.helpful_count / totalRated) * 100) : 100;

    html += `
      <tr class="hover:bg-slate-50 transition">
        <td class="px-4 py-3 font-mono text-xs text-slate-400">#${a.id}</td>
        <td class="px-4 py-3 font-medium text-slate-900 cursor-pointer hover:text-indigo-600" onclick="openArticleView(${a.id})">
          ${escapeHtml(a.title)}
        </td>
        <td class="px-4 py-3 text-xs text-slate-500">${escapeHtml(a.category_name || "—")}</td>
        <td class="px-4 py-3">
          <span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${a.language === 'en' ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-700'}">
            ${a.language.toUpperCase()}
          </span>
        </td>
        <td class="px-4 py-3 text-center text-xs font-semibold text-slate-600">${a.views_count}</td>
        <td class="px-4 py-3 text-center text-xs font-bold text-emerald-600">${rate}% 👍</td>
        <td class="px-4 py-3 text-right">
          <button onclick="editArticleModal(${a.id})" class="text-indigo-600 hover:text-indigo-800 text-xs font-medium mr-2">Редактировать</button>
        </td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}

function filterArticlesTable() {
  const q = document.getElementById("articleFilterInput").value.toLowerCase();
  const filtered = allArticlesList.filter(a => a.title.toLowerCase().includes(q) || (a.category_name && a.category_name.toLowerCase().includes(q)));
  renderArticlesTable(filtered);
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
    const res = await fetch(`${API_BASE}/api/v1/articles/${articleId}`);
    if (!res.ok) return;
    const a = await res.json();

    document.getElementById("editArticleId").value = a.id;
    document.getElementById("fromClusterId").value = "";
    document.getElementById("editTitle").value = a.title;
    document.getElementById("editSummary").value = a.summary || "";
    document.getElementById("editTags").value = a.tags || "";
    document.getElementById("editLanguage").value = a.language;
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
    language: document.getElementById("editLanguage").value,
    category_id: parseInt(document.getElementById("editCategory").value) || null,
    content: document.getElementById("editContent").value.trim(),
    is_published: true
  };

  try {
    let savedArticle = null;
    if (articleId) {
      // Update
      const res = await fetch(`${API_BASE}/api/v1/articles/${articleId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Save failed");
      savedArticle = await res.json();
      showToast("Статья успешно обновлена и переиндексирована!", "success");
    } else {
      // Create
      const res = await fetch(`${API_BASE}/api/v1/articles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Creation failed");
      savedArticle = await res.json();
      showToast("Новая статья создана и добавлен векторный эмбеддинг!", "success");

      // If created from cluster, mark cluster resolved!
      if (clusterId && savedArticle) {
        await fetch(`${API_BASE}/api/v1/gaps/clusters/${clusterId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "resolved", created_article_id: savedArticle.id })
        });
        showToast("Пробел знаний помечен как решённый!", "success");
      }
    }

    closeArticleEditModal();
    if (currentTab === "articles") loadArticles();
    if (currentTab === "clusters") loadClusters();

  } catch (err) {
    showToast("Ошибка сохранения: " + err.message, "error");
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
