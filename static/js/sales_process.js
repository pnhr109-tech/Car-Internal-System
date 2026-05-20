/**
 * 売掛管理 — ステップバッジのクリックによる AJAX トグル処理
 */
(function () {
  'use strict';

  document.addEventListener('click', function (e) {
    const btn = e.target.closest('.step-badge[data-process-id]');
    if (!btn) return;

    const processId = btn.dataset.processId;
    const step      = btn.dataset.step;
    const label     = btn.dataset.label;
    const isDone    = btn.classList.contains('step-badge--done');
    const nextState = isDone ? '未済' : '済';

    const confirmMsg = step === 'transfer' && !isDone
      ? `「振込」を完了にするとこのレコードは削除されます。\n続行しますか？`
      : `「${label}」を${nextState}に変更しますか？`;

    if (!confirm(confirmMsg)) return;

    btn.classList.add('step-badge--loading');

    apiFetch(`/sateiinfo/api/sales-process/${processId}/toggle/`, {
      method: 'POST',
      body: JSON.stringify({ step }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data.success) {
          showToast(data.message || 'エラーが発生しました', 'danger');
          btn.classList.remove('step-badge--loading');
          return;
        }

        if (data.deleted) {
          // 振込完了 → 行を削除してトースト
          const rowId  = `sp-row-${processId}`;
          const cardId = `sp-card-${processId}`;
          const row    = document.getElementById(rowId);
          const card   = document.getElementById(cardId);
          if (row)  row.remove();
          if (card) card.remove();
          showToast('振込完了 — レコードを削除しました', 'success');

          // グループが空になったら見出しごと消す
          _removeEmptyGroups();
          return;
        }

        // ステータス切り替え
        const icon = btn.querySelector('i');
        if (data.new_value) {
          btn.classList.remove('step-badge--pending');
          btn.classList.add('step-badge--done');
          if (icon) { icon.className = 'bi bi-check-circle-fill'; }
        } else {
          btn.classList.remove('step-badge--done');
          btn.classList.add('step-badge--pending');
          if (icon) { icon.className = 'bi bi-circle'; }
        }
        btn.classList.remove('step-badge--loading');
        showToast(`${label} を ${data.new_value ? '済' : '未済'} にしました`, 'success');
      })
      .catch(function () {
        showToast('通信エラーが発生しました', 'danger');
        btn.classList.remove('step-badge--loading');
      });
  });

  function _removeEmptyGroups() {
    document.querySelectorAll('.mb-4').forEach(function (group) {
      const rows  = group.querySelectorAll('tbody tr');
      const cards = group.querySelectorAll('.dash-feed-item');
      if (rows.length === 0 && cards.length === 0) {
        group.remove();
      }
    });
  }
})();
