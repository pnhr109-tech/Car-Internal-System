/**
 * approval_list.js — 承認待ち一覧画面の JS
 * 依存: app.js (getCsrf, apiFetch)
 */

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
