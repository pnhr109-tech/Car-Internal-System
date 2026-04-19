/**
 * assessment_list.js — 査定申込一覧画面の JS
 * 依存: app.js (getCsrf, showToast), Bootstrap 5
 * テンプレート側インライン宣言が必要な変数: currentUserDisplayName
 * window.resetAndLoad を公開し、sidebar.js の通知ポーリングから呼ばれる。
 */

let currentPage    = 1;
let perPage        = 100;
let totalPages     = 1;
let currentFilters = {};

let statusUpdateModal;
let assessmentDetailModal;

document.addEventListener('DOMContentLoaded', () => {
  statusUpdateModal    = new bootstrap.Modal(document.getElementById('statusUpdateModal'));
  assessmentDetailModal = new bootstrap.Modal(document.getElementById('assessmentDetailModal'));
  loadAssessments();
});

// ── ローディング ──────────────────────────────────────────────────────────

function showLoading() {
  document.getElementById('loadingOverlay').classList.add('active');
}

function hideLoading() {
  document.getElementById('loadingOverlay').classList.remove('active');
}

// ── データ読み込み ────────────────────────────────────────────────────────

function loadAssessments(page = 1) {
  showLoading();
  currentPage = page;

  const params = new URLSearchParams({ page: currentPage, per_page: perPage });
  fetch(`/sateiinfo/api/assessments/?${params}`)
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        renderTable(data.data);
        updatePagination(data);
      }
    })
    .catch(error => {
      console.error('Error:', error);
      showToast('エラー', 'データの読み込みに失敗しました', 'danger');
    })
    .finally(() => hideLoading());
}

// ── 検索 ─────────────────────────────────────────────────────────────────

function searchAssessments(page = 1) {
  showLoading();
  currentPage = page;

  currentFilters = {
    application_number: document.getElementById('applicationNumber').value,
    date_from:          document.getElementById('dateFrom').value,
    date_to:            document.getElementById('dateTo').value,
    address:            document.getElementById('address').value,
  };

  const params = new URLSearchParams({ ...currentFilters, page: currentPage, per_page: perPage });
  fetch(`/sateiinfo/api/assessments/?${params}`)
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        renderTable(data.data);
        updatePagination(data);
      }
    })
    .catch(error => {
      console.error('Error:', error);
      showToast('エラー', '検索に失敗しました', 'danger');
    })
    .finally(() => hideLoading());
}

function clearSearch() {
  document.getElementById('searchForm').reset();
  currentFilters = {};
}

function refreshCurrentList() {
  if (Object.values(currentFilters).some(v => v)) {
    searchAssessments(currentPage);
  } else {
    loadAssessments(currentPage);
  }
}

// window に公開（sidebar.js の通知ポーリングから参照される）
window.resetAndLoad = function resetAndLoad() {
  clearSearch();
  currentPage = 1;
  loadAssessments(1);
};

// ── ページネーション ──────────────────────────────────────────────────────

function updatePagination(data) {
  document.getElementById('totalCount').textContent = data.total_count.toLocaleString();
  const start = data.total_count > 0 ? (data.page - 1) * data.per_page + 1 : 0;
  const end   = Math.min(data.page * data.per_page, data.total_count);
  document.getElementById('pageStart').textContent = start.toLocaleString();
  document.getElementById('pageEnd').textContent   = end.toLocaleString();
  totalPages = data.total_pages;
  renderPagination(data);
}

function renderPagination(data) {
  const containerTop    = document.getElementById('paginationContainerTop');
  const containerBottom = document.getElementById('paginationContainerBottom');
  const rowTop          = document.getElementById('paginationTopRow');
  const rowBottom       = document.getElementById('paginationBottomRow');

  if (data.total_pages <= 1) {
    rowTop.style.display    = 'none';
    rowBottom.style.display = 'none';
    return;
  }

  rowTop.style.display    = 'block';
  rowBottom.style.display = 'block';
  let html = '';

  html += `
    <li class="page-item ${!data.has_previous ? 'disabled' : ''}">
      <a class="page-link" href="#" onclick="event.preventDefault(); ${data.has_previous ? 'goToPage(' + (data.page - 1) + ')' : ''}">
        <i class="bi bi-chevron-left"></i> 前へ
      </a>
    </li>`;

  const maxButtons = 5;
  let startPage = Math.max(1, data.page - Math.floor(maxButtons / 2));
  let endPage   = Math.min(data.total_pages, startPage + maxButtons - 1);
  if (endPage - startPage < maxButtons - 1) startPage = Math.max(1, endPage - maxButtons + 1);

  if (startPage > 1) {
    html += `<li class="page-item"><a class="page-link" href="#" onclick="event.preventDefault(); goToPage(1)">1</a></li>`;
    if (startPage > 2) html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
  }

  for (let i = startPage; i <= endPage; i++) {
    html += `
      <li class="page-item ${i === data.page ? 'active' : ''}">
        <a class="page-link" href="#" onclick="event.preventDefault(); goToPage(${i})">${i}</a>
      </li>`;
  }

  if (endPage < data.total_pages) {
    if (endPage < data.total_pages - 1) html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
    html += `<li class="page-item"><a class="page-link" href="#" onclick="event.preventDefault(); goToPage(${data.total_pages})">${data.total_pages}</a></li>`;
  }

  html += `
    <li class="page-item ${!data.has_next ? 'disabled' : ''}">
      <a class="page-link" href="#" onclick="event.preventDefault(); ${data.has_next ? 'goToPage(' + (data.page + 1) + ')' : ''}">
        次へ <i class="bi bi-chevron-right"></i>
      </a>
    </li>`;

  containerTop.innerHTML    = html;
  containerBottom.innerHTML = html;
}

function goToPage(page) {
  if (Object.values(currentFilters).some(v => v)) {
    searchAssessments(page);
  } else {
    loadAssessments(page);
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── テーブル描画 ──────────────────────────────────────────────────────────

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = value ?? '';
  return div.innerHTML;
}

function formatOwnerName(value) {
  const raw = (value || '').trim();
  if (!raw || raw === '-') return '';
  return raw.split(/\s+/).filter(Boolean).map(part => escapeHtml(part)).join('<br>');
}

function renderTable(data) {
  const tbody = document.getElementById('assessmentTableBody');

  if (data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="15" class="text-center text-muted">データがありません</td></tr>';
    return;
  }

  const followStatusClsMap = {
    '未対応':       'secondary',
    '不通':         'dark',
    '再コール予定': 'warning text-dark',
    '商談確定':     'primary',
    '商談昇格済':   'info text-dark',
    '成約':         'success',
    '見送り':       'danger',
  };
  const caseStatusClsMap = {
    in_progress: 'primary',
    contracted:  'success',
    lost:        'danger',
    pre_cancel:  'danger',
    managed:     'secondary',
  };
  const caseStatusLabelMap = {
    in_progress: '査定中',
    contracted:  '成約',
    lost:        '没',
    pre_cancel:  '査定前キャンセル',
    managed:     '管理',
  };

  const statusBadge = (item) => {
    const follow = item.follow_status || '未対応';
    if (follow === '商談昇格済' && item.case_status) {
      const cls   = caseStatusClsMap[item.case_status] || 'secondary';
      const label = caseStatusLabelMap[item.case_status] || item.case_status;
      return `<span class="badge bg-${cls}">${escapeHtml(label)}</span>`;
    }
    const cls = followStatusClsMap[follow] || 'secondary';
    return `<span class="badge bg-${cls}">${escapeHtml(follow)}</span>`;
  };

  const renderAction = (item) => {
    const owner = (item.sales_owner_name || '').trim();
    if (!owner || owner === currentUserDisplayName) {
      const encodedStatus = encodeURIComponent(item.follow_status || '未対応');
      const encodedNote   = encodeURIComponent(item.sales_note || '');
      return `<button class="btn btn-sm btn-outline-success" onclick="openStatusModal(${item.id}, '${encodedStatus}', '${encodedNote}')">更新</button>`;
    }
    return '<span class="text-muted small">担当確定済</span>';
  };

  const renderPhoneLink = (assessmentId, phoneNumber) => {
    const raw = phoneNumber || '';
    const tel = raw.replace(/[^0-9+]/g, '');
    if (!tel) return '-';
    return `<a href="tel:${tel}" class="text-decoration-none" onclick="recordCallAndDial(event, ${assessmentId})">${escapeHtml(raw)}</a>`;
  };

  tbody.innerHTML = data.map(item => `
    <tr>
      <td class="application-number-cell"><a href="/sateiinfo/${item.id}/" class="text-decoration-none fw-semibold">${escapeHtml(item.application_number)}</a></td>
      <td>${item.application_datetime}</td>
      <td class="owner-name-cell">${formatOwnerName(item.sales_owner_name)}</td>
      <td>${statusBadge(item)}</td>
      <td>${item.customer_name}</td>
      <td>${renderPhoneLink(item.id, item.phone_number)}</td>
      <td id="call-count-${item.id}" class="call-count-cell">${item.call_count || 0}</td>
      <td>${item.desired_sale_timing}</td>
      <td>${item.maker}</td>
      <td>${item.car_model}</td>
      <td>${item.year}</td>
      <td>${item.mileage}</td>
      <td>${item.address}</td>
      <td>${item.email}</td>
      <td>${renderAction(item)}</td>
    </tr>`).join('');
}

// ── 通話記録 ─────────────────────────────────────────────────────────────

function recordCallAndDial(event, assessmentId) {
  incrementCallCount(assessmentId);
}

function incrementCallCount(assessmentId) {
  fetch(`/sateiinfo/api/assessments/${assessmentId}/call/`, {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrf() },
    credentials: 'same-origin',
  })
  .then(async (response) => {
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.message || '通話数更新に失敗しました');
    const countCell = document.getElementById(`call-count-${assessmentId}`);
    if (countCell) countCell.textContent = data.call_count;
  })
  .catch(error => showToast('エラー', error.message, 'danger'));
}

// ── ステータス更新モーダル ────────────────────────────────────────────────

function openStatusModal(assessmentId, encodedStatus, encodedNote) {
  document.getElementById('modalAssessmentId').value    = assessmentId;
  document.getElementById('modalFollowStatus').value    = decodeURIComponent(encodedStatus || '未対応');
  document.getElementById('modalSalesNote').value       = decodeURIComponent(encodedNote || '');
  statusUpdateModal.show();
}

function saveStatusUpdate() {
  const assessmentId = document.getElementById('modalAssessmentId').value;
  const followStatus = document.getElementById('modalFollowStatus').value;
  const salesNote    = document.getElementById('modalSalesNote').value;

  fetch(`/sateiinfo/api/assessments/${assessmentId}/update/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
    credentials: 'same-origin',
    body: JSON.stringify({ follow_status: followStatus, sales_note: salesNote }),
  })
  .then(async (response) => {
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.message || '更新に失敗しました');
    statusUpdateModal.hide();
    showToast('成功', data.message || '更新しました', 'success');
    refreshCurrentList();
  })
  .catch(error => showToast('エラー', error.message, 'danger'));
}

// ── 申込詳細モーダル ──────────────────────────────────────────────────────

function openAssessmentDetailModal(assessmentId) {
  const body = document.getElementById('assessmentDetailBody');
  body.innerHTML = '読み込み中...';
  assessmentDetailModal.show();

  fetch(`/sateiinfo/api/assessments/${assessmentId}/detail/`)
    .then(r => r.json())
    .then(result => {
      if (!result.success) throw new Error(result.message || '詳細取得に失敗しました');
      const d = result.data;
      body.innerHTML = `
        <div class="row g-3">
          <div class="col-md-6"><strong>お申込番号</strong><div>${escapeHtml(d.application_number)}</div></div>
          <div class="col-md-6"><strong>お申込日時</strong><div>${escapeHtml(d.application_datetime || '-')}</div></div>
          <div class="col-md-6"><strong>担当営業</strong><div>${escapeHtml(d.sales_owner_name || '-')}</div></div>
          <div class="col-md-6"><strong>対応ステータス</strong><div>${escapeHtml(d.follow_status || '-')}</div></div>
          <div class="col-md-6"><strong>お名前</strong><div>${escapeHtml(d.customer_name || '-')}</div></div>
          <div class="col-md-6"><strong>電話番号</strong><div>${escapeHtml(d.phone_number || '-')}</div></div>
          <div class="col-md-6"><strong>通話数</strong><div>${escapeHtml(String(d.call_count ?? 0))}</div></div>
          <div class="col-md-6"><strong>希望売却時期</strong><div>${escapeHtml(d.desired_sale_timing || '-')}</div></div>
          <div class="col-md-6"><strong>メーカー / 車種</strong><div>${escapeHtml(d.maker || '-')} / ${escapeHtml(d.car_model || '-')}</div></div>
          <div class="col-md-6"><strong>年式 / 走行距離</strong><div>${escapeHtml(d.year || '-')} / ${escapeHtml(d.mileage || '-')}</div></div>
          <div class="col-md-6"><strong>住所</strong><div>${escapeHtml(d.address || '-')}</div></div>
          <div class="col-md-6"><strong>メールアドレス</strong><div>${escapeHtml(d.email || '-')}</div></div>
          <div class="col-md-6"><strong>担当確定日時</strong><div>${escapeHtml(d.sales_assigned_at || '-')}</div></div>
          <div class="col-12"><strong>コメント</strong><div class="border rounded p-2 bg-light">${escapeHtml(d.sales_note || '-')}</div></div>
          <div class="col-md-6"><strong>更新者</strong><div>${escapeHtml(d.status_updated_by || '-')}</div></div>
          <div class="col-md-6"><strong>更新日時</strong><div>${escapeHtml(d.status_updated_at || '-')}</div></div>
        </div>`;
    })
    .catch(error => {
      body.innerHTML = `<div class="text-danger">${escapeHtml(error.message)}</div>`;
    });
}
