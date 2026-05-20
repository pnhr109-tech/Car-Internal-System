/**
 * vehicle_list.js — 車両一覧画面
 */

// ── 車両新規登録 ──────────────────────────────────────────────────────────────

function submitVehicleCreate() {
  const maker    = document.getElementById('vcMaker').value.trim();
  const carModel = document.getElementById('vcCarModel').value.trim();

  if (!maker || !carModel) {
    showToast('エラー', 'メーカーと車種は必須です', 'danger');
    return;
  }

  const mileageNum = document.getElementById('vcMileageNum').value.trim();
  const mileage    = mileageNum ? `${mileageNum}万Km` : '';

  apiFetch('/sateiinfo/api/vehicles/create/', {
    method: 'POST',
    body: JSON.stringify({
      maker:               maker,
      car_model:           carModel,
      year:                document.getElementById('vcYear').value,
      mileage:             mileage,
      grade:               document.getElementById('vcGrade').value.trim(),
      color:               document.getElementById('vcColor').value.trim(),
      displacement:        document.getElementById('vcDisplacement').value.trim(),
      drive_type:          document.getElementById('vcDriveType').value.trim(),
      body_type:           document.getElementById('vcBodyType').value.trim(),
      passenger_count:     document.getElementById('vcPassengerCount').value.trim(),
      chassis_number:      document.getElementById('vcChassisNumber').value.trim(),
      registration_number: document.getElementById('vcRegistrationNumber').value.trim(),
      inspection_expiry:   document.getElementById('vcInspectionExpiry').value,
      remarks:             document.getElementById('vcRemarks').value.trim(),
    }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) {
      showToast('成功', d.message, 'success');
      setTimeout(() => location.reload(), 800);
    } else {
      showToast('エラー', d.message, 'danger');
    }
  })
  .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
}


// ── 出力モーダル ──────────────────────────────────────────────────────────────

let _currentDocKey = 'vehicle_list';

/**
 * 出力ボタンから呼ぶ。モーダルを開いて対応する資料カードをアクティブにする。
 * @param {string} docKey  - 資料を識別するキー ('vehicle_list' など)
 * @param {string} docLabel - 表示名（未使用だが将来の多様化に備えて受け取る）
 */
function openExportModal(docKey, docLabel) {
  _currentDocKey = docKey;

  // 対応するカードをアクティブ化
  document.querySelectorAll('.export-doc-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.doc === docKey);
    btn.classList.toggle('btn-primary', btn.dataset.doc === docKey);
    btn.classList.toggle('btn-outline-primary', btn.dataset.doc !== docKey);
  });

  bootstrap.Modal.getOrCreateInstance(document.getElementById('exportModal')).show();
}

/**
 * 資料カードを選択したとき呼ぶ。
 */
function selectExportDoc(btn) {
  _currentDocKey = btn.dataset.doc;
  document.querySelectorAll('.export-doc-btn').forEach(b => {
    b.classList.toggle('active', b === btn);
    b.classList.toggle('btn-primary', b === btn);
    b.classList.toggle('btn-outline-primary', b !== btn);
  });
}

/**
 * CSV または PDF を出力する。
 * @param {'csv'|'pdf'} format
 */
function doExport(format) {
  const urlEl = format === 'pdf'
    ? document.getElementById('exportUrlPdf')
    : document.getElementById('exportUrlCsv');

  if (!urlEl) {
    showToast('エラー', '出力URLが見つかりません', 'danger');
    return;
  }

  // モーダルを閉じてからダウンロード
  bootstrap.Modal.getOrCreateInstance(document.getElementById('exportModal')).hide();
  window.location.href = urlEl.dataset.url;
}
