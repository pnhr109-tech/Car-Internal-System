/**
 * sidebar.js — サイドバー関連の JS
 * 勤怠タイマー と グローバル通知ポーリング
 * _internal_header_sidebar.html の <script> タグから切り出したもの。
 */

// ── 勤怠タイマー ──────────────────────────────────────────────────────────
(function () {
  const durationEl = document.getElementById('attendanceWorkDuration');
  if (!durationEl) return;

  const initialMinutes = Number(durationEl.dataset.initialMinutes || '0');
  const clockedOut = durationEl.dataset.clockedOut === 'true';

  const formatMinutes = (totalMinutes) => {
    const safeMinutes = Math.max(totalMinutes, 0);
    const hours = Math.floor(safeMinutes / 60);
    const minutes = safeMinutes % 60;
    return `${hours}時間 ${minutes}分`;
  };

  if (clockedOut) {
    durationEl.textContent = formatMinutes(initialMinutes);
    return;
  }

  const loginAtIso = durationEl.dataset.loginAt;
  if (!loginAtIso) {
    durationEl.textContent = formatMinutes(initialMinutes);
    return;
  }

  const loginAt = new Date(loginAtIso);
  if (Number.isNaN(loginAt.getTime())) {
    durationEl.textContent = formatMinutes(initialMinutes);
    return;
  }

  const updateDuration = () => {
    const now = new Date();
    const diffMs = Math.max(now - loginAt, 0);
    const totalMinutes = Math.floor(diffMs / 60000);
    durationEl.textContent = formatMinutes(totalMinutes);
  };

  updateDuration();
  setInterval(updateDuration, 30000);
})();

// ── グローバル通知ポーリング ──────────────────────────────────────────────
(function () {
  const storageKey    = 'globalLatestAssessmentId';
  const recentKey     = 'globalRecentAssessmentNotifications';
  const maxRecentItems = 15;
  const badgeEl    = document.getElementById('globalNotificationBadge');
  const panelEl    = document.getElementById('globalNotificationPanel');
  const listEl     = document.getElementById('globalNotificationList');
  const clearBtnEl = document.getElementById('globalNotificationClearBtn');

  if (!badgeEl || !panelEl || !listEl || !clearBtnEl) return;

  const toInt = (v) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  };

  const getRecent = () => {
    try {
      const items = JSON.parse(localStorage.getItem(recentKey) || '[]');
      return Array.isArray(items) ? items : [];
    } catch {
      return [];
    }
  };

  const setRecent = (items) => {
    localStorage.setItem(recentKey, JSON.stringify(items.slice(0, maxRecentItems)));
  };

  let unseenCount = 0;

  const renderBadge = () => {
    if (unseenCount <= 0) {
      badgeEl.classList.add('d-none');
      return;
    }
    badgeEl.textContent = unseenCount > 99 ? '99+' : String(unseenCount);
    badgeEl.classList.remove('d-none');
  };

  const clearRecent = () => {
    localStorage.removeItem(recentKey);
    unseenCount = 0;
    renderBadge();
    renderRecentList();
  };

  const currentPath = window.location.pathname;

  const applyNotificationAction = () => {
    if (currentPath === '/' || currentPath === '/home/' || currentPath === '/home') {
      window.location.reload();
      return;
    }
    if (currentPath.startsWith('/sateiinfo/')) {
      if (typeof window.resetAndLoad === 'function') {
        window.resetAndLoad();
      } else {
        window.location.reload();
      }
      return;
    }
    window.location.href = '/';
  };

  const showGlobalNewToast = (records, count) => {
    const container = document.getElementById('globalToastContainer');
    if (!container || typeof bootstrap === 'undefined') return;

    const first = records[0] || {};
    const summary = `${first.application_number || '-'} ${first.customer_name || ''}`.trim();
    const message = count > 1 ? `${summary} ほか ${count - 1}件` : summary;
    const toastId = `global-toast-${Date.now()}`;

    container.insertAdjacentHTML('beforeend', `
      <div id="${toastId}" class="toast align-items-center text-white bg-info border-0"
           role="alert" aria-live="assertive" aria-atomic="true"
           data-bs-autohide="true" data-bs-delay="6000">
        <div class="d-flex">
          <div class="toast-body">
            <strong>${count}件の新着申込</strong><br>${message}
          </div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto"
                  data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
      </div>`);

    const toastEl = document.getElementById(toastId);
    if (!toastEl) return;
    toastEl.style.cursor = 'pointer';
    toastEl.addEventListener('click', applyNotificationAction);
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
    new bootstrap.Toast(toastEl).show();
  };

  const renderRecentList = () => {
    const items = getRecent();
    if (items.length === 0) {
      listEl.innerHTML = '<div class="list-group-item text-muted">通知はまだありません</div>';
      return;
    }
    listEl.innerHTML = items.map((item) => `
      <button type="button" class="list-group-item list-group-item-action" data-notification-id="${item.id}">
        <div class="fw-semibold">${item.title}</div>
        <div class="small text-muted">${item.body}</div>
        <div class="small text-muted mt-1">${item.time}</div>
      </button>`).join('');

    listEl.querySelectorAll('[data-notification-id]').forEach((button) => {
      button.addEventListener('click', applyNotificationAction);
    });
  };

  panelEl.addEventListener('shown.bs.offcanvas', () => {
    unseenCount = 0;
    renderBadge();
  });

  clearBtnEl.addEventListener('click', clearRecent);

  const ensureBaseline = async () => {
    const existing = toInt(localStorage.getItem(storageKey));
    if (existing > 0) return existing;
    const res = await fetch('/sateiinfo/api/latest-id/');
    if (!res.ok) return 0;
    const data = await res.json();
    const latestId = toInt(data.latest_id);
    localStorage.setItem(storageKey, String(latestId));
    return latestId;
  };

  const pollNewAssessments = async () => {
    const lastId = await ensureBaseline();
    if (lastId <= 0) return;

    const res = await fetch(`/sateiinfo/api/check-new/?last_id=${lastId}`);
    if (!res.ok) return;

    const data = await res.json();
    if (!data.success || !data.has_new || !Array.isArray(data.data) || data.data.length === 0) return;

    const latestId = Math.max(...data.data.map(item => toInt(item.id)));
    if (latestId > lastId) localStorage.setItem(storageKey, String(latestId));

    const first = data.data[0] || {};
    const recent = getRecent();
    recent.unshift({
      id:    Date.now(),
      title: `${data.count}件の新着申込`,
      body:  `${first.application_number || '-'} ${first.customer_name || ''}`.trim(),
      time:  new Date().toLocaleString('ja-JP'),
    });
    setRecent(recent);

    unseenCount += data.count;
    renderBadge();
    renderRecentList();
    showGlobalNewToast(data.data, data.count);
  };

  renderRecentList();
  renderBadge();
  ensureBaseline().catch(() => {});
  setInterval(() => { pollNewAssessments().catch(() => {}); }, 30000);
})();
