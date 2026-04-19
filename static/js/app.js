/**
 * app.js — 全ページ共通ユーティリティ
 * Bootstrap 5 と internal_base.html の globalToastContainer に依存。
 */

/**
 * CSRF トークンを <meta name="csrf-token"> から取得する。
 * フォールバックとして csrftoken Cookie も参照する。
 * @returns {string}
 */
function getCsrf() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta && meta.content) return meta.content;
  const cookie = document.cookie.split(';').map(v => v.trim()).find(v => v.startsWith('csrftoken='));
  return cookie ? cookie.split('=')[1] : '';
}

/**
 * トースト通知を表示する。
 * @param {string} title   - 太字で表示するタイトル（1引数のみの場合はメッセージとして表示）
 * @param {string} [message=''] - タイトル下に表示する本文
 * @param {string} [type='success'] - 'success' | 'danger' | 'info' | 'warning' | 'error'
 * @param {boolean} [autohide=true]
 * @param {Function|null} [onClick=null]
 */
function showToast(title, message = '', type = 'success', autohide = true, onClick = null) {
  const container = document.getElementById('globalToastContainer');
  if (!container) { alert(message || title); return; }

  const bgClass = {
    success: 'bg-success',
    danger:  'bg-danger',
    error:   'bg-danger',
    info:    'bg-info',
    warning: 'bg-warning',
  }[type] || 'bg-info';

  const id = 'toast-' + Date.now();
  const bodyHtml = message
    ? `<strong>${title}</strong><br>${message}`
    : title;

  container.insertAdjacentHTML('beforeend', `
    <div id="${id}" class="toast align-items-center text-white ${bgClass} border-0"
         role="alert" aria-live="assertive" aria-atomic="true"
         ${autohide ? 'data-bs-autohide="true" data-bs-delay="5000"' : 'data-bs-autohide="false"'}>
      <div class="d-flex">
        <div class="toast-body">${bodyHtml}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto"
                data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>`);

  const el = document.getElementById(id);
  if (onClick) {
    el.style.cursor = 'pointer';
    el.addEventListener('click', onClick);
  }
  el.addEventListener('hidden.bs.toast', () => el.remove());
  new bootstrap.Toast(el).show();
}

/**
 * JSON API への fetch ラッパー。CSRF ヘッダーと credentials を自動付与する。
 * @param {string} url
 * @param {RequestInit} [options={}]
 * @returns {Promise<Response>}
 */
function apiFetch(url, options = {}) {
  const { headers: extraHeaders = {}, ...rest } = options;
  return fetch(url, {
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrf(),
      ...extraHeaders,
    },
    ...rest,
  });
}
