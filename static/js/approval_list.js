/**
 * approval_list.js — 承認待ち一覧画面の JS
 * 依存: app.js (getCsrf, apiFetch)
 */

function promoteToCase(requestId) {
  if (!confirm('この申込を商談昇格しますか？')) return;
  fetch(`/sateiinfo/api/assessments/${requestId}/promote/`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrf(),
    },
  })
  .then(r => r.text())
  .then(text => {
    console.log('[promoteToCase] response:', text);
    let d;
    try { d = JSON.parse(text); } catch (e) {
      alert('サーバーエラー（レスポンス解析失敗）:\n' + text.substring(0, 300));
      return;
    }
    if (d.success) location.reload();
    else alert(d.message || '更新に失敗しました');
  })
  .catch(err => {
    console.error('[promoteToCase] fetch error:', err);
    alert('通信エラー: ' + err.message);
  });
}

function approveAssessment(id, action) {
  const reason = action === 'reject' ? prompt('差し戻し理由') : '';
  if (action === 'reject' && !reason) return;
  apiFetch(`/sateiinfo/api/cases/${id}/approve/`, {
    method: 'POST',
    body: JSON.stringify({ action, reason }),
  }).then(r => r.json()).then(d => { if (d.success) location.reload(); else alert(d.message); });
}

function approveContract(id, action) {
  const reason = action === 'reject' ? prompt('差し戻し理由') : '';
  if (action === 'reject' && !reason) return;
  apiFetch(`/sateiinfo/api/contracts/${id}/approve/`, {
    method: 'POST',
    body: JSON.stringify({ action, reason }),
  }).then(r => r.json()).then(d => { if (d.success) location.reload(); else alert(d.message); });
}

function approveCorrection(id, action) {
  const reason = action === 'reject' ? prompt('差し戻し理由') : '';
  if (action === 'reject' && !reason) return;
  apiFetch(`/sateiinfo/api/contracts/${id}/approve-correction/`, {
    method: 'POST',
    body: JSON.stringify({ action, reason }),
  }).then(r => r.json()).then(d => { if (d.success) location.reload(); else alert(d.message); });
}
