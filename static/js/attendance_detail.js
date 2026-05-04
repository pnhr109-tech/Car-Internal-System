/**
 * attendance_detail.js — 勤務表画面
 * 依存: app.js (apiFetch, showToast), Bootstrap 5
 * テンプレート側インライン宣言: ATTENDANCE_UPDATE_URL
 */

// 月合計を再集計してサマリーカードとフッターを更新する
function _refreshTotals() {
  let totalDays = 0;
  let totalWork = 0;
  let totalOvertime = 0;

  document.querySelectorAll('tbody tr').forEach(row => {
    const workCell = row.querySelector('[id^="cell-work-"]');
    const overtimeCell = row.querySelector('[id^="cell-overtime-"]');
    const loginCell = row.querySelector('[id^="cell-login-"]');
    if (!workCell) return;

    const workText = workCell.textContent.trim();
    const otText = overtimeCell ? overtimeCell.textContent.trim() : '-';
    const loginText = loginCell ? loginCell.textContent.trim() : '-';

    if (loginText && loginText !== '-') totalDays += 1;
    totalWork += _parseHM(workText);
    totalOvertime += _parseHM(otText);
  });

  const daysEl = document.getElementById('summaryDays');
  const workEl = document.getElementById('summaryWork');
  const otEl   = document.getElementById('summaryOvertime');
  const fDays  = document.getElementById('footerDays');
  const fWork  = document.getElementById('footerWork');
  const fOt    = document.getElementById('footerOvertime');

  if (daysEl) daysEl.innerHTML = totalDays + '<span class="fs-6 fw-normal text-muted ms-1">日</span>';
  if (workEl) workEl.textContent = _minutesToHM(totalWork);
  if (otEl)  {
    otEl.textContent = _minutesToHM(totalOvertime);
    otEl.className = 'fs-5 fw-bold' + (totalOvertime > 0 ? ' text-danger' : '');
  }
  if (fDays) fDays.textContent = totalDays + '日';
  if (fWork) fWork.textContent = _minutesToHM(totalWork);
  if (fOt)  {
    fOt.textContent = _minutesToHM(totalOvertime);
    fOt.className = totalOvertime > 0 ? 'text-danger' : '';
  }
}

function _minutesToHM(minutes) {
  if (!minutes || minutes <= 0) return '-';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h + '時間' + String(m).padStart(2, '0') + '分';
}

// 「X時間YY分」形式を分数に変換（合計再集計用）
function _parseHM(text) {
  if (!text || text === '-') return 0;
  const m = text.match(/(\d+)時間(\d+)分/);
  if (!m) return 0;
  return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
}

// モーダル表示時にデータをセット
document.getElementById('editDayModal').addEventListener('show.bs.modal', function (event) {
  const btn = event.relatedTarget;
  document.getElementById('editDayLabel').textContent = btn.dataset.dateLabel;
  document.getElementById('editWorkDate').value  = btn.dataset.date;
  document.getElementById('editLoginTime').value = btn.dataset.login || '';
  document.getElementById('editLogoutTime').value = btn.dataset.logout || '';
});

// 保存ボタン
document.getElementById('editDaySaveBtn').addEventListener('click', function () {
  const workDate   = document.getElementById('editWorkDate').value;
  const loginTime  = document.getElementById('editLoginTime').value;
  const logoutTime = document.getElementById('editLogoutTime').value;

  if (!loginTime) {
    showToast('入力エラー', '出勤時刻は必須です', 'danger');
    return;
  }

  const saveBtn = this;
  saveBtn.disabled = true;

  apiFetch(ATTENDANCE_UPDATE_URL, {
    method: 'POST',
    body: JSON.stringify({ work_date: workDate, login_time: loginTime, logout_time: logoutTime }),
  })
    .then(res => res.json())
    .then(data => {
      if (!data.success) {
        showToast('エラー', data.message, 'danger');
        return;
      }

      const dateKey = workDate.replace(/-/g, '');
      const loginCell   = document.getElementById('cell-login-'   + dateKey);
      const logoutCell  = document.getElementById('cell-logout-'  + dateKey);
      const workCell    = document.getElementById('cell-work-'    + dateKey);
      const overtimeCell = document.getElementById('cell-overtime-' + dateKey);

      if (loginCell)  loginCell.textContent = data.login_time || '-';

      if (logoutCell) {
        if (data.logout_time) {
          logoutCell.innerHTML = data.overtime_minutes > 0
            ? '<span class="text-danger">' + data.logout_time + '</span>'
            : data.logout_time;
        } else if (data.login_time) {
          logoutCell.innerHTML = '<span class="text-warning">未退勤</span>';
        } else {
          logoutCell.textContent = '-';
        }
      }

      if (workCell) workCell.textContent = _minutesToHM(data.work_minutes);

      if (overtimeCell) {
        overtimeCell.innerHTML = data.overtime_minutes > 0
          ? '<span class="text-danger fw-semibold">' + _minutesToHM(data.overtime_minutes) + '</span>'
          : '-';
      }

      // 編集ボタンの data 属性も更新しておく（再編集時に正しい値が入るよう）
      const row = document.getElementById('row-' + dateKey);
      if (row) {
        const editBtn = row.querySelector('[data-bs-target="#editDayModal"]');
        if (editBtn) {
          editBtn.dataset.login  = data.login_time || '';
          editBtn.dataset.logout = data.logout_time || '';
        }
      }

      _refreshTotals();
      bootstrap.Modal.getInstance(document.getElementById('editDayModal')).hide();
      showToast('保存しました', '', 'success');
    })
    .catch(() => showToast('エラー', '通信エラーが発生しました', 'danger'))
    .finally(() => { saveBtn.disabled = false; });
});
