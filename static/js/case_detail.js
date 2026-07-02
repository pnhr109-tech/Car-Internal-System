/**
 * case_detail.js — 案件詳細画面の JS
 * 依存: app.js (getCsrf), Bootstrap 5
 * テンプレート側インライン宣言が必要な変数:
 *   ASSESSMENT_ID, REQUEST_ID, CONTRACT_ID (契約がある場合のみ)
 */

// ── DOMContentLoaded 初期化 ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // 契約手続書類 添付ファイルの初期表示
  _initContractFiles();
  // AA出品画像の初期表示
  _initAAImages();
  // その他費用明細の初期表示
  _initOtherFeeItems();
  // AA損益シミュレーションの初期描画
  _updateAASimulation();

  // 履歴入力の日時初期値
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const local = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
  const historyDateEl = document.getElementById('historyDate');
  if (historyDateEl) historyDateEl.value = local;

  // 契約日の初期値
  const dateEl = document.getElementById('contractDate');
  if (dateEl) dateEl.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;

  // 加修チェックで加修内容欄を表示（新規作成モーダル）
  const repairFlag = document.getElementById('contractRepairFlag');
  if (repairFlag) {
    repairFlag.addEventListener('change', () => {
      document.getElementById('repairNotesArea').style.display = repairFlag.checked ? '' : 'none';
    });
  }

  // 適格請求書「ある」選択で登録番号欄を表示（新規作成モーダル）
  document.querySelectorAll('input[name="qualified_invoice_registered"]').forEach(el => {
    el.addEventListener('change', () => {
      const area = document.getElementById('invoiceNumberArea');
      if (area) area.style.display = document.getElementById('qir_yes').checked ? '' : 'none';
    });
  });

  // 加修チェック（編集モーダル）
  const editRepairFlag = document.getElementById('editContractRepairFlag');
  if (editRepairFlag) {
    editRepairFlag.addEventListener('change', () => {
      document.getElementById('editRepairNotesArea').style.display = editRepairFlag.checked ? '' : 'none';
    });
  }

  // 適格請求書（編集モーダル）
  document.querySelectorAll('input[name="edit_qualified_invoice_registered"]').forEach(el => {
    el.addEventListener('change', () => {
      const area = document.getElementById('editInvoiceNumberArea');
      if (area) area.style.display = document.getElementById('edit_qir_yes').checked ? '' : 'none';
    });
  });

  // 査定システムID: フォーカスアウト時に自動保存
  const sateiIdInput = document.getElementById('assessmentSystemId');
  if (sateiIdInput) {
    sateiIdInput.dataset.original = sateiIdInput.value.trim();
    sateiIdInput.addEventListener('blur', () => {
      const newVal = sateiIdInput.value.trim();
      if (newVal === sateiIdInput.dataset.original) return;
      apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/save-assessment-system-id/`, {
        method: 'POST',
        body: JSON.stringify({ assessment_system_id: newVal }),
      })
      .then(r => r.json())
      .then(d => {
        if (d.success) {
          sateiIdInput.dataset.original = newVal;
          _updateAssessmentSystemIdDisplay(newVal);
        }
      });
    });
  }

  // 契約作成モーダル: 価格入力変更時にリアルタイム計算
  ['contractPriceExcl', 'contractRecycleAmount', 'contractTaxRate'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', _updateContractSummary);
  });

  // ゆうちょ銀行の初期状態設定（編集モーダル：既存データがゆうちょの場合）
  ['contractBankType', 'editContractBankType'].forEach(typeId => {
    const nameId = typeId === 'contractBankType' ? 'contractBankName' : 'editContractBankName';
    const sel = document.getElementById(typeId);
    if (sel) {
      onBankTypeChange(typeId, nameId);
      sel.addEventListener('change', () => onBankTypeChange(typeId, nameId));
    }
  });
});

// ── ヘルパー ─────────────────────────────────────────────────────────────

function prefillCreateContractModal() {
  // 査定システム取込値で初期入力（円単位）— モーダル表示はBootstrapに任せる
  if (typeof SATEI_PRICE_YEN !== 'undefined' && SATEI_PRICE_YEN > 0) {
    const recycleYen   = Number(SATEI_RECYCLE_YEN) || 0;
    const inclTaxPrice = Number(SATEI_PRICE_YEN) - recycleYen;
    const exclTaxPrice = Math.ceil(inclTaxPrice / 1.1);
    document.getElementById('contractPriceExcl').value    = exclTaxPrice;
    document.getElementById('contractRecycleAmount').value = recycleYen;
  }
  _updateContractSummary();
}

function _fmt(yen) {
  return Number(yen).toLocaleString() + ' 円';
}

function _updateContractSummary() {
  const exclTax  = Number(document.getElementById('contractPriceExcl')?.value)    || 0;
  const recycle  = Number(document.getElementById('contractRecycleAmount')?.value) || 0;
  const taxRate  = Number(document.getElementById('contractTaxRate')?.value)       || 0;
  const tax      = Math.round(exclTax * taxRate / 100);
  const inclTax  = exclTax + tax;
  const transfer = inclTax + recycle;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = _fmt(val); };
  set('summaryRecycle', recycle);
  set('summaryExcl',    exclTax);
  set('summaryTax',     tax);
  set('summaryTotal',   transfer);
}

function _getRadioValue(name) {
  const checked = document.querySelector(`input[name="${name}"]:checked`);
  if (!checked) return null;
  return checked.value === 'true';
}

// ── 金融機関種別変更ハンドラ ──────────────────────────────────────────────────

function onBankTypeChange(typeSelectId, nameInputId) {
  const type      = document.getElementById(typeSelectId).value;
  const nameInput = document.getElementById(nameInputId);
  if (type === 'yucho') {
    nameInput.value    = 'ゆうちょ銀行';
    nameInput.readOnly = true;
    nameInput.classList.add('bg-light');
  } else {
    if (nameInput.value === 'ゆうちょ銀行') nameInput.value = '';
    nameInput.readOnly = false;
    nameInput.classList.remove('bg-light');
  }
}

// ── 郵便番号→住所補完 ──────────────────────────────────────────────────────

function lookupPostalCode(postalInputId, addressInputId) {
  const zip = document.getElementById(postalInputId).value.replace(/[^0-9]/g, '');
  if (zip.length !== 7) { showToast('入力エラー', '郵便番号は7桁で入力してください', 'warning'); return; }
  fetch(`https://zipcloud.ibsnet.co.jp/api/search?zipcode=${zip}`)
    .then(r => r.json())
    .then(d => {
      if (d.status !== 200 || !d.results) { showToast('補完失敗', '該当する住所が見つかりませんでした', 'warning'); return; }
      const r = d.results[0];
      const addr = r.address1 + r.address2 + r.address3;
      const el = document.getElementById(addressInputId);
      el.value = addr;
      el.focus();
      el.setSelectionRange(addr.length, addr.length);
    })
    .catch(() => showToast('エラー', '郵便番号の検索に失敗しました', 'danger'));
}

// ── 契約作成 ─────────────────────────────────────────────────────────────

function saveContract() {
  const contractDate = document.getElementById('contractDate').value;
  const priceExcl    = document.getElementById('contractPriceExcl').value;
  if (!contractDate || !priceExcl) {
    showToast('入力エラー', '契約日と買取価格（税抜）は必須です', 'danger');
    return;
  }

  apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/create-contract/`, {
    method: 'POST',
    body: JSON.stringify({
      contract_date:                contractDate,
      purchase_price_excl_tax:      priceExcl,
      tax_rate:                     document.getElementById('contractTaxRate').value,
      recycle_amount:               document.getElementById('contractRecycleAmount').value || null,
      payment_scheduled_date:       document.getElementById('contractPaymentDate').value,
      auction_scheduled_date:       document.getElementById('contractAuctionDate').value,
      vehicle_handover_date:        document.getElementById('contractVehicleHandover').value,
      document_handover_date:       document.getElementById('contractDocumentHandover').value,
      repair_flag:                  document.getElementById('contractRepairFlag').checked,
      repair_notes:                 document.getElementById('contractRepairNotes').value,
      ownership_release_flag:       document.getElementById('contractOwnershipFlag').checked,
      debt_remaining_flag:          document.getElementById('contractDebtRemainingFlag').checked,
      remarks:                      document.getElementById('contractRemarks').value,
      manager1_id:                  document.getElementById('contractManager1').value || null,
      manager2_id:                  document.getElementById('contractManager2').value || null,
      repair_history_flag:          _getRadioValue('repair_history_flag'),
      meter_tampering:              _getRadioValue('meter_tampering'),
      flood_hail_damage:            _getRadioValue('flood_hail_damage'),
      malfunction:                  _getRadioValue('malfunction'),
      parking_violation:            _getRadioValue('parking_violation'),
      automobile_tax_unpaid:        _getRadioValue('automobile_tax_unpaid'),
      qualified_invoice_registered: _getRadioValue('qualified_invoice_registered'),
      invoice_registration_number:  document.getElementById('invoiceRegNumber')?.value || '',
      customer_name:                document.getElementById('contractCustName').value.trim() || null,
      customer_furigana:            document.getElementById('contractCustFurigana').value.trim() || null,
      customer_postal_code:         document.getElementById('contractCustPostal').value.trim() || null,
      customer_address:             document.getElementById('contractCustAddress').value.trim() || null,
      customer_birth_date:          document.getElementById('contractCustBirthDate').value || null,
      customer_license_number:      document.getElementById('contractCustLicense').value.trim() || null,
      customer_occupation:          document.getElementById('contractCustOccupation').value.trim() || null,
      bank_institution_type:        document.getElementById('contractBankType').value,
      bank_name:                    document.getElementById('contractBankName').value.trim() || null,
      branch_name:                  document.getElementById('contractBranchName').value.trim() || null,
      account_type:                 document.getElementById('contractAccountType').value,
      account_number:               document.getElementById('contractAccountNumber').value.trim() || null,
      account_holder:               document.getElementById('contractAccountHolder').value.trim() || null,
      required_inkan_count:         parseInt(document.getElementById('reqInkan').value) || 0,
      required_juminhyo_count:      parseInt(document.getElementById('reqJuminhyo').value) || 0,
      required_jotohyo_count:       parseInt(document.getElementById('reqJotohyo').value) || 0,
      required_ininjyo_count:       parseInt(document.getElementById('reqIninjyo').value) || 0,
      required_jotosho_count:       parseInt(document.getElementById('reqJotosho').value) || 0,
      required_kanpu_count:         parseInt(document.getElementById('reqKanpu').value) || 0,
    }),
  })
  .then(r => r.text())
  .then(text => {
    let d;
    try { d = JSON.parse(text); } catch (e) {
      showToast('エラー', 'サーバーエラーが発生しました:\n' + text.substring(0, 200), 'danger');
      return;
    }
    if (d.success) location.href = '?tab=contract';
    else showToast('エラー', d.message || '契約の作成に失敗しました', 'danger');
  })
  .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
}

// ── 対応履歴 ─────────────────────────────────────────────────────────────

function saveHistory() {
  const content = document.getElementById('historyContent').value.trim();
  if (!content) { alert('内容を入力してください'); return; }
  apiFetch('/sateiinfo/api/history/add/', {
    method: 'POST',
    body: JSON.stringify({
      assessment_request_id: REQUEST_ID,
      contact_method:        document.getElementById('historyMethod').value,
      contacted_at:          document.getElementById('historyDate').value,
      content,
    }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else alert(d.message || '追記に失敗しました');
  });
}

// ── 査定情報 ─────────────────────────────────────────────────────────────

function saveAssessmentInfo() {
  apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/update/`, {
    method: 'POST',
    body: JSON.stringify({
      assessment_datetime:  document.getElementById('editAssessmentDatetime').value,
      assessment_price:     document.getElementById('editAssessmentPrice').value,
      market_price_min:     document.getElementById('editMarketPriceMin').value,
      market_price_max:     document.getElementById('editMarketPriceMax').value,
      overall_rating:       document.getElementById('editOverallRating').value,
      remarks:              document.getElementById('editRemarks').value,
    }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else alert(d.message || '更新に失敗しました');
  });
}

// ── 顧客情報 ─────────────────────────────────────────────────────────────

function saveCustomer() {
  apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/update-customer/`, {
    method: 'POST',
    body: JSON.stringify({
      name:           document.getElementById('custName').value,
      furigana:       document.getElementById('custFurigana').value,
      phone_number:   document.getElementById('custPhone').value,
      email:          document.getElementById('custEmail').value,
      postal_code:    document.getElementById('custPostal').value,
      address:        document.getElementById('custAddress').value,
      birth_date:     document.getElementById('custBirthDate').value,
      age:            document.getElementById('custAge').value || null,
      occupation:     document.getElementById('custOccupation').value,
      license_number: document.getElementById('custLicense').value,
      gender:         document.getElementById('custGender').value,
    }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else alert(d.message || '顧客情報の更新に失敗しました');
  });
}

// ── 口座情報 ─────────────────────────────────────────────────────────────

function saveBankAccount() {
  const bankName   = document.getElementById('bankName').value.trim();
  const bankNumber = document.getElementById('bankNumber').value.trim();
  const bankHolder = document.getElementById('bankHolder').value.trim();
  if (!bankName || !bankNumber || !bankHolder) { alert('銀行名・口座番号・名義は必須です'); return; }
  apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/save-bank-account/`, {
    method: 'POST',
    body: JSON.stringify({
      bank_name:             bankName,
      branch_name:           document.getElementById('bankBranch').value,
      bank_institution_type: document.getElementById('bankInstitutionType').value,
      account_type:          document.getElementById('bankAccountType').value,
      account_number:        bankNumber,
      account_holder:        bankHolder,
      is_primary:            document.getElementById('bankIsPrimary').checked,
    }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else alert(d.message || '口座情報の保存に失敗しました');
  });
}

function deleteBankAccount(accountId, btn) {
  if (!confirm('この口座情報を削除しますか？')) return;
  apiFetch(`/sateiinfo/api/bank-accounts/${accountId}/delete/`, { method: 'POST' })
  .then(r => r.json())
  .then(d => {
    if (d.success) btn.closest('li').remove();
    else alert(d.message || '削除に失敗しました');
  });
}

// ── 車両情報 ─────────────────────────────────────────────────────────────

function saveVehicle() {
  apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/update-vehicle/`, {
    method: 'POST',
    body: JSON.stringify({
      maker:               document.getElementById('vehMaker').value,
      car_model:           document.getElementById('vehModel').value,
      year:                document.getElementById('vehYear').value,
      mileage:             document.getElementById('vehMileage').value,
      grade:               document.getElementById('vehGrade').value,
      color:               document.getElementById('vehColor').value,
      displacement:        document.getElementById('vehDisplacement').value,
      chassis_number:      document.getElementById('vehChassis').value,
      registration_number: document.getElementById('vehRegNumber').value,
      inspection_expiry:   document.getElementById('vehInspection').value,
      passenger_count:     document.getElementById('vehPassenger').value,
      body_type:           document.getElementById('vehBodyType').value,
      drive_type:          document.getElementById('vehDriveType').value,
    }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else alert(d.message || '車両情報の更新に失敗しました');
  });
}

function importFromAssessmentSystem() {
  const assessmentSystemId = document.getElementById('assessmentSystemId').value.trim();
  if (!assessmentSystemId) {
    alert('査定システムIDを入力してください');
    return;
  }

  _showImportOverlay();

  apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/import-assessment-system/`, {
    method: 'POST',
    body: JSON.stringify({ assessment_system_id: assessmentSystemId }),
  })
  .then(r => r.json())
  .then(d => {
    _hideImportOverlay();
    if (d.success) {
      _showImportConfirmModal(d);
    } else {
      alert(d.message || '取り込みに失敗しました');
    }
  })
  .catch(() => {
    _hideImportOverlay();
    alert('通信エラーが発生しました');
  });
}

function _showImportOverlay() {
  let overlay = document.getElementById('importLoadingOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'importLoadingOverlay';
    overlay.style.cssText = [
      'position:fixed', 'inset:0', 'z-index:9999',
      'background:rgba(0,0,0,0.55)',
      'display:flex', 'flex-direction:column',
      'align-items:center', 'justify-content:center', 'gap:16px',
    ].join(';');
    overlay.innerHTML = `
      <div class="spinner-border text-light" style="width:3rem;height:3rem;" role="status"></div>
      <div class="text-white fw-bold fs-5">査定システムから取り込み中...</div>
      <div class="text-white-50 small">完了するまでしばらくお待ちください</div>
    `;
    document.body.appendChild(overlay);
  }
  overlay.style.display = 'flex';
}

function _hideImportOverlay() {
  const overlay = document.getElementById('importLoadingOverlay');
  if (overlay) overlay.style.display = 'none';
}

function _updateAssessmentSystemIdDisplay(newId) {
  const el = document.getElementById('vehicleAssessmentSystemId');
  if (!el) return;
  if (newId) {
    el.textContent = newId;
    el.closest('div.vehicle-assessment-system-id-row').classList.remove('d-none');
  } else {
    el.closest('div.vehicle-assessment-system-id-row').classList.add('d-none');
  }
}

function _showImportConfirmModal(data) {
  const v = data.vehicle || {};
  const rows = [
    ['メーカー',     v.maker],
    ['車種',         v.car_model],
    ['年式',         v.year],
    ['走行距離',     v.mileage],
    ['グレード',     v.grade],
    ['カラー',       v.color],
    ['排気量',       v.displacement ? v.displacement + ' cc' : ''],
    ['車台番号',     v.chassis_number],
    ['登録番号',     v.registration_number],
    ['乗車定員',     v.passenger_count ? v.passenger_count + ' 人' : ''],
    ['ボディタイプ', v.body_type],
    ['駆動方式',     v.drive_type],
    ['車検有効期限', v.inspection_expiry],
  ].filter(([, val]) => val).map(([label, val]) =>
    `<tr><td class="text-muted">${label}</td><td class="fw-bold">${val}</td></tr>`
  ).join('');

  const priceRows = [
    data.assessment_price != null ? `<tr><td class="text-muted">買取金額（振込金額④）</td><td class="fw-bold text-success">${Number(data.assessment_price).toLocaleString()} 円</td></tr>` : '',
    data.recycle_amount   != null ? `<tr><td class="text-muted">リサイクル券</td><td class="fw-bold">${Number(data.recycle_amount).toLocaleString()} 円</td></tr>` : '',
    data.overall_rating   != null ? `<tr><td class="text-muted">総合評価</td><td class="fw-bold">${data.overall_rating}</td></tr>` : '',
  ].join('');

  let modal = document.getElementById('importConfirmModal');
  if (modal) modal.remove();

  modal = document.createElement('div');
  modal.id = 'importConfirmModal';
  modal.className = 'modal fade';
  modal.tabIndex = -1;
  modal.innerHTML = `
    <div class="modal-dialog modal-lg">
      <div class="modal-content">
        <div class="modal-header bg-warning-subtle">
          <h5 class="modal-title"><i class="bi bi-exclamation-triangle-fill text-warning"></i> 取り込み完了 — 内容を確認してください</h5>
        </div>
        <div class="modal-body">
          <p class="text-danger fw-bold mb-3">
            <i class="bi bi-exclamation-circle"></i>
            査定システムから取り込んだ情報です。内容に誤りがないか必ず確認してください。
          </p>
          <h6 class="border-bottom pb-1">車両情報</h6>
          <table class="table table-sm mb-3"><tbody>${rows}</tbody></table>
          ${priceRows ? `<h6 class="border-bottom pb-1">価格情報</h6><table class="table table-sm mb-0"><tbody>${priceRows}</tbody></table>` : ''}
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-primary" onclick="location.reload()">
            <i class="bi bi-check-circle"></i> 確認しました
          </button>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  new bootstrap.Modal(modal, { backdrop: 'static', keyboard: false }).show();
}

// ── チェック項目 ──────────────────────────────────────────────────────────

function saveCheckItem() {
  const checkType   = document.getElementById('checkItemType').value;
  const description = document.getElementById('checkItemDescription').value.trim();
  apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/check-items/add/`, {
    method: 'POST',
    body: JSON.stringify({ check_type: checkType, description }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) {
      const emptyEl = document.getElementById('check-item-empty');
      if (emptyEl) emptyEl.remove();
      const list = document.getElementById('checkItemList');
      const li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between align-items-center';
      li.id = `check-item-${d.item.id}`;
      li.innerHTML = `<div><span class="badge bg-secondary me-2">${d.item.check_type_display}</span>${d.item.description || '-'}</div>`
        + `<button class="btn btn-sm btn-outline-danger" onclick="deleteCheckItem(${d.item.id})"><i class="bi bi-trash"></i></button>`;
      list.appendChild(li);
      document.getElementById('checkItemDescription').value = '';
      bootstrap.Modal.getInstance(document.getElementById('addCheckItemModal')).hide();
    } else {
      alert(d.message || '追加に失敗しました');
    }
  });
}

function deleteCheckItem(id) {
  if (!confirm('このチェック項目を削除しますか？')) return;
  apiFetch(`/sateiinfo/api/check-items/${id}/delete/`, { method: 'POST' })
  .then(r => r.json())
  .then(d => {
    if (d.success) {
      const el = document.getElementById(`check-item-${id}`);
      if (el) el.remove();
      const list = document.getElementById('checkItemList');
      if (list && list.children.length === 0) {
        const li = document.createElement('li');
        li.className = 'list-group-item text-muted';
        li.id = 'check-item-empty';
        li.textContent = 'チェック項目なし';
        list.appendChild(li);
      }
    } else {
      alert(d.message || '削除に失敗しました');
    }
  });
}

// ── ステータス変更・承認申請 ──────────────────────────────────────────────

function onStatusSelectChange() {
  const status = document.getElementById('newStatusSelect').value;
  const wrap = document.getElementById('approverSelectWrap');
  wrap.classList.toggle('d-none', status !== 'contracted');
}

function submitStatusChange() {
  const status = document.getElementById('newStatusSelect').value;

  if (typeof PROCEDURE_COMPLETED !== 'undefined' && !PROCEDURE_COMPLETED) {
    if (!confirm('契約手続（必要書類受領・所有権解除・残債返済）が完了していませんが、ステータスを変更しますか？')) return;
  }

  if (status === 'contracted') {
    const approverId = document.getElementById('statusChangeApproverSelect').value;
    if (!approverId) { showToast('エラー', '承認申請先を選択してください', 'danger'); return; }
    apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/request-approval/`, {
      method: 'POST',
      body: JSON.stringify({ approver_id: parseInt(approverId) }),
    })
    .then(r => r.json())
    .then(d => {
      if (d.success) location.reload();
      else showToast('エラー', d.message, 'danger');
    })
    .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
  } else {
    apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/update/`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    })
    .then(r => r.json())
    .then(d => {
      if (d.success) location.reload();
      else showToast('エラー', d.message, 'danger');
    })
    .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
  }
}

function submitCancelContracted() {
  apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/cancel-contracted/`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else showToast('エラー', d.message, 'danger');
  })
  .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
}

// ── 査定承認 ─────────────────────────────────────────────────────────────

function approveAssessment(action) {
  apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/approve/`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else alert(d.message);
  });
}

// ── 契約編集 ─────────────────────────────────────────────────────────────

function updateContract() {
  const contractDate = document.getElementById('editContractDate').value;
  const priceExcl    = document.getElementById('editContractPriceExcl').value;
  if (!contractDate || !priceExcl) { alert('契約日と買取価格（税抜）は必須です'); return; }

  apiFetch(`/sateiinfo/api/contracts/${CONTRACT_ID}/update/`, {
    method: 'POST',
    body: JSON.stringify({
      contract_date:                contractDate,
      purchase_price_excl_tax:      priceExcl,
      tax_rate:                     document.getElementById('editContractTaxRate').value,
      recycle_amount:               document.getElementById('editContractRecycleAmount').value || null,
      payment_scheduled_date:       document.getElementById('editContractPaymentDate').value,
      auction_scheduled_date:       document.getElementById('editContractAuctionDate').value,
      vehicle_handover_date:        document.getElementById('editContractVehicleHandover').value,
      document_handover_date:       document.getElementById('editContractDocumentHandover').value,
      repair_flag:                  document.getElementById('editContractRepairFlag').checked,
      repair_notes:                 document.getElementById('editContractRepairNotes').value,
      ownership_release_flag:       document.getElementById('editContractOwnershipFlag').checked,
      debt_remaining_flag:          document.getElementById('editContractDebtRemainingFlag').checked,
      remarks:                      document.getElementById('editContractRemarks').value,
      manager1_id:                  document.getElementById('editContractManager1').value || null,
      manager2_id:                  document.getElementById('editContractManager2').value || null,
      repair_history_flag:          _getRadioValue('edit_repair_history_flag'),
      meter_tampering:              _getRadioValue('edit_meter_tampering'),
      flood_hail_damage:            _getRadioValue('edit_flood_hail_damage'),
      malfunction:                  _getRadioValue('edit_malfunction'),
      parking_violation:            _getRadioValue('edit_parking_violation'),
      automobile_tax_unpaid:        _getRadioValue('edit_automobile_tax_unpaid'),
      qualified_invoice_registered: _getRadioValue('edit_qualified_invoice_registered'),
      invoice_registration_number:  document.getElementById('editInvoiceRegNumber')?.value || '',
      customer_name:                document.getElementById('editContractCustName').value.trim() || null,
      customer_furigana:            document.getElementById('editContractCustFurigana').value.trim() || null,
      customer_postal_code:         document.getElementById('editContractCustPostal').value.trim() || null,
      customer_address:             document.getElementById('editContractCustAddress').value.trim() || null,
      customer_birth_date:          document.getElementById('editContractCustBirthDate').value || null,
      customer_license_number:      document.getElementById('editContractCustLicense').value.trim() || null,
      customer_occupation:          document.getElementById('editContractCustOccupation').value.trim() || null,
      bank_institution_type:        document.getElementById('editContractBankType').value,
      bank_name:                    document.getElementById('editContractBankName').value.trim() || null,
      branch_name:                  document.getElementById('editContractBranchName').value.trim() || null,
      account_type:                 document.getElementById('editContractAccountType').value,
      account_number:               document.getElementById('editContractAccountNumber').value.trim() || null,
      account_holder:               document.getElementById('editContractAccountHolder').value.trim() || null,
      required_inkan_count:         parseInt(document.getElementById('editReqInkan').value) || 0,
      required_juminhyo_count:      parseInt(document.getElementById('editReqJuminhyo').value) || 0,
      required_jotohyo_count:       parseInt(document.getElementById('editReqJotohyo').value) || 0,
      required_ininjyo_count:       parseInt(document.getElementById('editReqIninjyo').value) || 0,
      required_jotosho_count:       parseInt(document.getElementById('editReqJotosho').value) || 0,
      required_kanpu_count:         parseInt(document.getElementById('editReqKanpu').value) || 0,
    }),
  })
  .then(r => r.text())
  .then(text => {
    let d; try { d = JSON.parse(text); } catch (e) { showToast('エラー', 'サーバーエラーが発生しました', 'danger'); return; }
    if (d.success) location.href = '?tab=contract';
    else showToast('エラー', d.message || '契約の更新に失敗しました', 'danger');
  })
  .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
}

function resetContract() {
  apiFetch(`/sateiinfo/api/contracts/${CONTRACT_ID}/reset/`, { method: 'POST' })
  .then(r => r.text())
  .then(text => {
    let d; try { d = JSON.parse(text); } catch (e) { showToast('エラー', 'サーバーエラーが発生しました', 'danger'); return; }
    if (d.success) location.href = '?tab=contract';
    else showToast('エラー', d.message || '契約のリセットに失敗しました', 'danger');
  })
  .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
}

// ── 契約承認申請 ──────────────────────────────────────────────────────────

function requestContractApproval() {
  const approverId = document.getElementById('contractApproverSelect').value;
  if (!approverId) { showToast('エラー', '承認申請先を選択してください', 'danger'); return; }
  apiFetch(`/sateiinfo/api/contracts/${CONTRACT_ID}/request-approval/`, {
    method: 'POST',
    body: JSON.stringify({ approver_id: parseInt(approverId) }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else showToast('エラー', d.message, 'danger');
  })
  .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
}

// ── 契約承認 ─────────────────────────────────────────────────────────────

function approveContract(action) {
  apiFetch(`/sateiinfo/api/contracts/${CONTRACT_ID}/approve/`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else alert(d.message);
  });
}

// ── 先払い入金 ───────────────────────────────────────────────────────────

function addAdvancePayment() {
  const amount = document.getElementById('apAmount').value;
  if (!amount) { showToast('入力エラー', '入金予定額を入力してください', 'warning'); return; }
  apiFetch(`/sateiinfo/api/contracts/${CONTRACT_ID}/advance-payments/add/`, {
    method: 'POST',
    body: JSON.stringify({
      expected_amount: amount,
      payment_date:    document.getElementById('apPaymentDate').value || null,
    }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else showToast('エラー', d.message || '追加に失敗しました', 'danger');
  });
}

function deleteAdvancePayment(apId, btn) {
  if (!confirm('この先払い入金を削除しますか？')) return;
  apiFetch(`/sateiinfo/api/advance-payments/${apId}/delete/`, { method: 'POST' })
  .then(r => r.json())
  .then(d => {
    if (d.success) btn.closest('li').remove();
    else showToast('エラー', d.message || '削除に失敗しました', 'danger');
  });
}

function approveAdvancePayment(apId) {
  const paymentDate = prompt('入金日を入力してください（例: 2026-04-23）');
  if (paymentDate === null) return;
  apiFetch(`/sateiinfo/api/advance-payments/${apId}/approve/`, {
    method: 'POST',
    body: JSON.stringify({ payment_date: paymentDate || null }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else showToast('エラー', d.message || '承認に失敗しました', 'danger');
  });
}

// ── 必要書類 受取確認 ────────────────────────────────────────────────────

function _formatDateDisplay(isoStr) {
  if (!isoStr) return '-';
  const d = new Date(isoStr + 'T00:00:00');
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
}

function toggleRequiredDoc(key, received) {
  const btn = document.getElementById(`doc_btn_${key}`);
  if (btn) btn.disabled = true;

  const payload = { [`${key}_received`]: received };

  apiFetch(`/sateiinfo/api/contracts/${CONTRACT_ID}/required-docs/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) {
      const badge    = document.getElementById(`doc_badge_${key}`);
      const dateText = document.getElementById(`doc_date_text_${key}`);
      if (badge) {
        badge.className = `badge ${received ? 'bg-success' : 'bg-secondary'}`;
        badge.textContent = received ? '✓ 受領済' : '未済';
      }
      if (dateText) {
        const dateIso = (d.updated_dates || {})[key];
        dateText.textContent = dateIso ? _formatDateDisplay(dateIso) : '-';
      }
      if (btn) {
        btn.className = `btn btn-sm ${received ? 'btn-outline-secondary' : 'btn-success'}`;
        btn.textContent = received ? '取消' : '受領済にする';
        btn.onclick = () => toggleRequiredDoc(key, !received);
        btn.disabled = false;
      }
      if (d.auto_doc_done) {
        showToast('保存', '全書類受取済 — 書類ステップが自動完了しました', 'success');
        if (typeof _updateStepCard === 'function') _updateStepCard('document', true);
      } else if (d.auto_doc_undone) {
        showToast('保存', '未受領の書類があります — 書類ステップを未完了に戻しました', 'warning');
        if (typeof _updateStepCard === 'function') _updateStepCard('document', false);
      } else {
        showToast('保存', received ? '受領済にしました' : '未済に戻しました', 'success');
      }
    } else {
      showToast('エラー', d.message || '更新に失敗しました', 'danger');
      if (btn) btn.disabled = false;
    }
  });
}

// ── 契約手続書類 添付ファイル ───────────────────────────────────────────────

const DOC_FILE_TYPES = {
  inkan: '印鑑証明', juminhyo: '住民票', jotohyo: '除票',
  ininjyo: '委任状', jotosho: '譲渡書', kanpu: '還付',
  contract_signed: '契約書（署名後）',
};

let _contractFiles = {};
let _currentDocFileType = null;

function _initContractFiles() {
  const el = document.getElementById('contract-files-data');
  _contractFiles = el ? JSON.parse(el.textContent) : {};
  Object.keys(DOC_FILE_TYPES).forEach(_updateDocFileBadge);
}

function _updateDocFileBadge(key) {
  const badge = document.getElementById(`docfile_badge_${key}`);
  if (!badge) return;
  const count = (_contractFiles[key] || []).length;
  badge.textContent = count > 0 ? `${count}件` : '未添付';
}

function openDocFileModal(key) {
  _currentDocFileType = key;
  document.getElementById('docFileModalLabel').textContent = `${DOC_FILE_TYPES[key]} — 添付ファイル`;
  _renderDocFileList();
  new bootstrap.Modal(document.getElementById('docFileModal')).show();
}

function _renderDocFileList() {
  const container = document.getElementById('docFileModalList');
  const files = _contractFiles[_currentDocFileType] || [];
  if (files.length === 0) {
    container.innerHTML = '<p class="text-muted small mb-0">添付ファイルはまだありません</p>';
    return;
  }
  container.innerHTML = files.map(f => `
    <div class="d-flex justify-content-between align-items-center border-bottom py-2">
      <a href="${f.url}" target="_blank" rel="noopener">
        <i class="bi bi-file-earmark-text"></i> ${escapeHtml(f.filename)}
      </a>
      <div class="text-end">
        <div class="text-muted small">${escapeHtml(f.uploaded_by)} ${f.uploaded_at}</div>
        <button class="btn btn-sm btn-outline-danger" onclick="deleteDocFile(${f.id})">
          <i class="bi bi-trash"></i>
        </button>
      </div>
    </div>
  `).join('');
}

function triggerDocFileUpload() {
  const input = document.getElementById(`docFileInput_${_currentDocFileType}`);
  if (input) input.click();
}

function handleDocFileSelected(input) {
  // capture 属性でカメラ起動後、端末によってはページがバックグラウンドで再読込され
  // JS変数の状態が失われることがあるため、書類種別は input 自身の data 属性から読み取る
  const docType = input.dataset.docType;
  const files = Array.from(input.files || []);
  input.value = '';
  files.forEach(file => uploadDocFile(file, docType));
}

function uploadDocFile(file, docType) {
  const formData = new FormData();
  formData.append('doc_type', docType);
  formData.append('file', file);
  apiFetch(`/sateiinfo/api/contracts/${CONTRACT_ID}/documents/upload/`, {
    method: 'POST',
    body: formData,
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) {
      const key = d.data.doc_type;
      if (key === 'contract_signed') {
        // 契約手続の完了ステータス（バッジ・案件フロー）に影響するため再読込して同期する
        location.reload();
        return;
      }
      if (!_contractFiles[key]) _contractFiles[key] = [];
      _contractFiles[key].unshift(d.data);
      _updateDocFileBadge(key);
      if (_currentDocFileType === key) _renderDocFileList();
      showToast('保存', 'ファイルを保存しました', 'success');
    } else {
      showToast('エラー', d.message || 'アップロードに失敗しました', 'danger');
    }
  })
  .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
}

function deleteDocFile(fileId) {
  if (!confirm('このファイルを削除しますか？')) return;
  apiFetch(`/sateiinfo/api/contract-files/${fileId}/delete/`, { method: 'POST' })
  .then(r => r.json())
  .then(d => {
    if (d.success) {
      if (_currentDocFileType === 'contract_signed') {
        // 契約手続の完了ステータス（バッジ・案件フロー）に影響するため再読込して同期する
        location.reload();
        return;
      }
      Object.keys(_contractFiles).forEach(key => {
        _contractFiles[key] = (_contractFiles[key] || []).filter(f => f.id !== fileId);
      });
      _updateDocFileBadge(_currentDocFileType);
      _renderDocFileList();
      showToast('削除', 'ファイルを削除しました', 'success');
    } else {
      showToast('エラー', d.message || '削除に失敗しました', 'danger');
    }
  })
  .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
}

// ── AA出品 画像 ─────────────────────────────────────────────────────────────

const AA_IMAGE_TYPES = {
  listing_screen:     '出品画面',
  flow_screen:        '流れ画面',
  winning_bid_screen: '落札画面',
};

let _aaImages = {};

function _initAAImages() {
  const el = document.getElementById('aa-images-data');
  _aaImages = el ? JSON.parse(el.textContent) : {};
  _renderAAImageList();
}

function _renderAAImageList() {
  const container = document.getElementById('aaImageList');
  if (!container) return;

  const html = Object.entries(AA_IMAGE_TYPES).map(([key, label]) => {
    const images = _aaImages[key] || [];
    const badge  = images.length > 0
      ? ` <span class="badge bg-secondary ms-1">${images.length}</span>` : '';
    const rows = images.length === 0
      ? '<div class="text-muted small px-3 py-2">なし</div>'
      : images.map(img => `
          <div class="d-flex align-items-center gap-2 px-3 py-2 border-bottom">
            <a href="${img.url}" target="_blank" rel="noopener" class="flex-shrink-0">
              <img src="${img.url}" alt="${escapeHtml(img.filename)}"
                style="width:72px;height:54px;object-fit:cover;border-radius:4px;border:1px solid #dee2e6;">
            </a>
            <div class="flex-grow-1 overflow-hidden">
              <div class="small fw-semibold text-truncate">${escapeHtml(img.filename)}</div>
              <div class="text-muted small">${escapeHtml(img.uploaded_by)} · ${img.uploaded_at}</div>
            </div>
            <button class="btn btn-sm btn-outline-danger flex-shrink-0" onclick="deleteAAImage(${img.id})">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        `).join('');

    return `
      <div>
        <div class="px-3 py-2 bg-light border-bottom fw-semibold small">${escapeHtml(label)}${badge}</div>
        ${rows}
      </div>`;
  }).join('');

  container.innerHTML = html;
}

function openAAImageUploadModal() {
  const sel = document.getElementById('aaImgUploadType');
  const inp = document.getElementById('aaImgUploadFile');
  if (sel) sel.value = '';
  if (inp) inp.value = '';
  new bootstrap.Modal(document.getElementById('aaImageUploadModal')).show();
}

function doUploadAAImages() {
  const sel   = document.getElementById('aaImgUploadType');
  const inp   = document.getElementById('aaImgUploadFile');
  const files = Array.from(inp?.files || []);

  if (!sel?.value) {
    showToast('エラー', '画面の種類を選択してください', 'danger');
    return;
  }
  if (files.length === 0) {
    showToast('エラー', '画像ファイルを選択してください', 'danger');
    return;
  }

  const imageType = sel.value;
  bootstrap.Modal.getInstance(document.getElementById('aaImageUploadModal'))?.hide();
  files.forEach(file => _uploadAAImage(file, imageType));
}

function _uploadAAImage(file, imageType) {
  const formData = new FormData();
  formData.append('image_type', imageType);
  formData.append('file', file);
  apiFetch(`/sateiinfo/api/sales-process/${SALES_PROCESS_ID}/aa-images/upload/`, {
    method: 'POST',
    body: formData,
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) {
      const key = d.data.image_type;
      if (!_aaImages[key]) _aaImages[key] = [];
      _aaImages[key].unshift(d.data);
      _renderAAImageList();
      showToast('保存', '画像を保存しました', 'success');
    } else {
      showToast('エラー', d.message || 'アップロードに失敗しました', 'danger');
    }
  })
  .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
}

function deleteAAImage(imageId) {
  if (!confirm('この画像を削除しますか？')) return;
  apiFetch(`/sateiinfo/api/aa-images/${imageId}/delete/`, { method: 'POST' })
  .then(r => r.json())
  .then(d => {
    if (d.success) {
      Object.keys(_aaImages).forEach(key => {
        _aaImages[key] = (_aaImages[key] || []).filter(img => img.id !== imageId);
      });
      _renderAAImageList();
      showToast('削除', '画像を削除しました', 'success');
    } else {
      showToast('エラー', d.message || '削除に失敗しました', 'danger');
    }
  })
  .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
}

// ── AA 損益シミュレーション ──────────────────────────────────────────────

function _updateAASimulation() {
  const fmt = n => Math.round(n).toLocaleString() + ' 円';

  const purchasePrice    = typeof PURCHASE_PRICE !== 'undefined' ? PURCHASE_PRICE : 0;
  const entryFee         = parseFloat(document.getElementById('aaFeeEntryFee')?.value)         || 0;
  const contractFee      = parseFloat(document.getElementById('aaFeeContractFee')?.value)       || 0;
  const transPersonal    = parseFloat(document.getElementById('aaFeeTransportPersonal')?.value) || 0;
  const transAuction     = parseFloat(document.getElementById('aaFeeTransportAuction')?.value)  || 0;
  const otherFee         = _otherFeeItems.reduce((s, i) => s + i.amount, 0);
  const totalCost        = purchasePrice + entryFee + contractFee + transPersonal + transAuction + otherFee;

  const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };

  setText('simPurchasePrice',    purchasePrice ? fmt(purchasePrice) : '—');
  setText('simEntryFee',         fmt(entryFee));
  setText('simContractFee',      fmt(contractFee));
  setText('simTransportPersonal', fmt(transPersonal));
  setText('simTransportAuction', fmt(transAuction));
  setText('simOtherFee',         fmt(otherFee));
  setText('simTotalCost',        fmt(totalCost));
  setText('simBreakEven',        purchasePrice ? fmt(totalCost) : '—');

  const box = document.getElementById('simResultBox');

  const priceMin = typeof MARKET_PRICE_MIN !== 'undefined' ? MARKET_PRICE_MIN : null;
  const priceMax = typeof MARKET_PRICE_MAX !== 'undefined' ? MARKET_PRICE_MAX : null;

  if (priceMin !== null || priceMax !== null) {
    const mid = (priceMin !== null && priceMax !== null)
      ? (priceMin + priceMax) / 2
      : (priceMin ?? priceMax);

    let compareText = '';
    if (priceMin !== null && priceMax !== null) {
      compareText = `相場 ${Math.round(priceMin).toLocaleString()}〜${Math.round(priceMax).toLocaleString()} 円`;
    } else if (priceMin !== null) {
      compareText = `相場下限 ${Math.round(priceMin).toLocaleString()} 円`;
    } else {
      compareText = `相場上限 ${Math.round(priceMax).toLocaleString()} 円`;
    }
    if (purchasePrice && totalCost > 0) {
      const breakEven = totalCost;
      if (priceMin !== null && priceMin >= breakEven) {
        compareText += ' ✅ 相場下限でも利益が出ます';
        if (box) box.className = box.className.replace(/border-\S+/g, 'border-success');
      } else if (priceMax !== null && priceMax < breakEven) {
        compareText += ' ⚠️ 相場上限でも赤字になります';
        if (box) box.className = box.className.replace(/border-\S+/g, 'border-danger');
      } else {
        compareText += ' 📊 相場内での損益分岐点あり';
        if (box) box.className = box.className.replace(/border-\S+/g, 'border-warning');
      }
    }
    setText('simMarketCompare', compareText);

    if (purchasePrice && totalCost > 0) {
      const estProfit = mid - totalCost;
      const profitEl = document.getElementById('simEstProfit');
      if (profitEl) {
        profitEl.textContent = (estProfit >= 0 ? '+' : '') + Math.round(estProfit).toLocaleString() + ' 円';
        profitEl.className = 'fw-semibold ' + (estProfit >= 0 ? 'text-success' : 'text-danger');
      }
    } else {
      setText('simEstProfit', '—');
    }
  } else {
    setText('simMarketCompare', '査定タブで市場相場を入力してください');
    setText('simEstProfit', '—');
  }
}

// ── その他費用 明細 ──────────────────────────────────────────────────────

let _otherFeeItems = [];

function _initOtherFeeItems() {
  const el = document.getElementById('other-fee-items-data');
  _otherFeeItems = el ? JSON.parse(el.textContent) : [];
  _renderOtherFeeItems();
}

function _renderOtherFeeItems() {
  const container = document.getElementById('otherFeeItemList');
  if (!container) return;
  if (_otherFeeItems.length === 0) {
    container.innerHTML = '<p class="text-muted small mb-0">明細はまだ登録されていません</p>';
  } else {
    container.innerHTML = _otherFeeItems.map(item => `
      <div class="d-flex align-items-center gap-2 py-1 border-bottom" data-fee-item-id="${item.id}">
        <span class="badge bg-secondary">${item.category_label}</span>
        <span class="fw-semibold">${item.amount.toLocaleString()} 円</span>
        ${item.receipt_url ? `<a href="${item.receipt_url}" target="_blank" class="btn btn-sm btn-outline-secondary py-0 px-1"><i class="bi bi-paperclip"></i> 領収書</a>` : ''}
        <span class="text-muted small ms-auto">${item.created_by} ${item.created_at}</span>
        <button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" onclick="deleteOtherFeeItem(${item.id})">
          <i class="bi bi-trash"></i>
        </button>
      </div>
    `).join('');
  }
  _updateOtherFeeTotal();
}

function _updateOtherFeeTotal() {
  const total = _otherFeeItems.reduce((sum, item) => sum + item.amount, 0);
  const el = document.getElementById('otherFeeTotal');
  if (el) el.textContent = total.toLocaleString();
  const saleEl = document.getElementById('saleOtherFee');
  if (saleEl) {
    saleEl.value = total;
    if (typeof updateSaleProfit === 'function') updateSaleProfit();
  }
  _updateAASimulation();
}

function addOtherFeeItem() {
  const category = document.getElementById('newOtherFeeCategory').value;
  const amount   = document.getElementById('newOtherFeeAmount').value;
  const receipt  = document.getElementById('newOtherFeeReceipt').files[0];
  if (!category) { showToast('エラー', '種別を選択してください', 'danger'); return; }
  if (!amount || parseFloat(amount) <= 0) { showToast('エラー', '金額を入力してください', 'danger'); return; }

  const formData = new FormData();
  formData.append('category', category);
  formData.append('amount', amount);
  if (receipt) formData.append('receipt_image', receipt);

  apiFetch(`/sateiinfo/api/sales-process/${SALES_PROCESS_ID}/other-fee-items/add/`, {
    method: 'POST',
    body: formData,
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) {
      _otherFeeItems.push(d.data);
      _renderOtherFeeItems();
      document.getElementById('newOtherFeeCategory').value = '';
      document.getElementById('newOtherFeeAmount').value = '';
      document.getElementById('newOtherFeeReceipt').value = '';
      showToast('追加', '費用を追加しました', 'success');
    } else {
      showToast('エラー', d.message || '追加に失敗しました', 'danger');
    }
  })
  .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
}

function deleteOtherFeeItem(itemId) {
  if (!confirm('この費用を削除しますか？')) return;
  apiFetch(`/sateiinfo/api/other-fee-items/${itemId}/delete/`, { method: 'POST' })
  .then(r => r.json())
  .then(d => {
    if (d.success) {
      _otherFeeItems = _otherFeeItems.filter(item => item.id !== itemId);
      _renderOtherFeeItems();
      showToast('削除', '費用を削除しました', 'success');
    } else {
      showToast('エラー', d.message || '削除に失敗しました', 'danger');
    }
  })
  .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
}

// ── 所有権解除・残債管理 ─────────────────────────────────────────────────

function updateContractProcedure() {
  const payload = {};
  const ownershipStatusEl = document.getElementById('procOwnershipReleaseStatus');
  if (ownershipStatusEl) {
    payload.ownership_release_status          = ownershipStatusEl.value;
    payload.ownership_release_requested_date  = document.getElementById('procOwnershipReleaseRequestedDate').value || null;
    payload.ownership_release_completed_date  = document.getElementById('procOwnershipReleaseCompletedDate').value || null;
  }
  const orPatternEl = document.getElementById('orPattern');
  if (orPatternEl) {
    payload.or_pattern                  = orPatternEl.value;
    payload.or_status                   = document.getElementById('orStatus').value;
    payload.or_inquiry_status           = document.getElementById('orInquiryStatus').value;
    payload.or_dealer_doc_sent_date     = document.getElementById('orDocSentDate').value || null;
    payload.or_debt_transfer_date       = document.getElementById('orDebtTransferDate').value || null;
    payload.or_dealer_doc_returned_date = document.getElementById('orDocReturnedDate').value || null;
  }

  apiFetch(`/sateiinfo/api/contracts/${CONTRACT_ID}/procedure/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else showToast('エラー', d.message || '保存に失敗しました', 'danger');
  })
  .catch(err => showToast('エラー', '通信エラー: ' + err.message, 'danger'));
}
