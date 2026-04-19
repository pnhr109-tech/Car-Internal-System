/**
 * case_detail.js — 案件詳細画面の JS
 * 依存: app.js (getCsrf), Bootstrap 5
 * テンプレート側インライン宣言が必要な変数:
 *   ASSESSMENT_ID, REQUEST_ID, CONTRACT_ID (契約がある場合のみ)
 */

// ── DOMContentLoaded 初期化 ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
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
});

// ── ヘルパー ─────────────────────────────────────────────────────────────

function _getRadioValue(name) {
  const checked = document.querySelector(`input[name="${name}"]:checked`);
  if (!checked) return null;
  return checked.value === 'true';
}

// ── 契約作成 ─────────────────────────────────────────────────────────────

function saveContract() {
  const contractDate = document.getElementById('contractDate').value;
  const priceExcl    = document.getElementById('contractPriceExcl').value;
  if (!contractDate || !priceExcl) { alert('契約日と買取価格（税抜）は必須です'); return; }

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
      remarks:                      document.getElementById('contractRemarks').value,
      manager1_id:                  document.getElementById('contractManager1').value || null,
      manager2_id:                  document.getElementById('contractManager2').value || null,
      meter_tampering:              _getRadioValue('meter_tampering'),
      flood_hail_damage:            _getRadioValue('flood_hail_damage'),
      malfunction:                  _getRadioValue('malfunction'),
      parking_violation:            _getRadioValue('parking_violation'),
      automobile_tax_unpaid:        _getRadioValue('automobile_tax_unpaid'),
      qualified_invoice_registered: _getRadioValue('qualified_invoice_registered'),
      invoice_registration_number:  document.getElementById('invoiceRegNumber')?.value || '',
      customer_furigana:            document.getElementById('contractCustFurigana').value.trim() || null,
      customer_birth_date:          document.getElementById('contractCustBirthDate').value || null,
      customer_license_number:      document.getElementById('contractCustLicense').value.trim() || null,
    }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.href = '?tab=contract';
    else alert(d.message || '契約の作成に失敗しました');
  });
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
      status:               document.getElementById('editStatus').value,
      assessment_datetime:  document.getElementById('editAssessmentDatetime').value,
      assessment_price:     document.getElementById('editAssessmentPrice').value,
      market_price:         document.getElementById('editMarketPrice').value,
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
  const rhVal = document.getElementById('vehRepairHistory').value;
  apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/update-vehicle/`, {
    method: 'POST',
    body: JSON.stringify({
      maker:               document.getElementById('vehMaker').value,
      car_model:           document.getElementById('vehModel').value,
      year:                document.getElementById('vehYear').value,
      mileage:             document.getElementById('vehMileage').value,
      grade:               document.getElementById('vehGrade').value,
      color:               document.getElementById('vehColor').value,
      model_type:          document.getElementById('vehModelType').value,
      displacement:        document.getElementById('vehDisplacement').value,
      fuel_type:           document.getElementById('vehFuelType').value,
      chassis_number:      document.getElementById('vehChassis').value,
      registration_number: document.getElementById('vehRegNumber').value,
      inspection_expiry:   document.getElementById('vehInspection').value,
      transmission_type:   document.getElementById('vehTransmission').value,
      passenger_count:     document.getElementById('vehPassenger').value,
      body_type:           document.getElementById('vehBodyType').value,
      drive_type:          document.getElementById('vehDriveType').value,
      repair_history_flag: rhVal === '' ? null : rhVal === 'true',
    }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else alert(d.message || '車両情報の更新に失敗しました');
  });
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
        + `<button class="btn btn-sm btn-link text-danger p-0" onclick="deleteCheckItem(${d.item.id})"><i class="bi bi-trash"></i></button>`;
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

// ── 査定承認 ─────────────────────────────────────────────────────────────

function approveAssessment(action) {
  const reason = action === 'reject' ? prompt('差し戻し理由を入力してください') : '';
  if (action === 'reject' && !reason) return;
  apiFetch(`/sateiinfo/api/cases/${ASSESSMENT_ID}/approve/`, {
    method: 'POST',
    body: JSON.stringify({ action, reason }),
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
      remarks:                      document.getElementById('editContractRemarks').value,
      manager1_id:                  document.getElementById('editContractManager1').value || null,
      manager2_id:                  document.getElementById('editContractManager2').value || null,
      meter_tampering:              _getRadioValue('edit_meter_tampering'),
      flood_hail_damage:            _getRadioValue('edit_flood_hail_damage'),
      malfunction:                  _getRadioValue('edit_malfunction'),
      parking_violation:            _getRadioValue('edit_parking_violation'),
      automobile_tax_unpaid:        _getRadioValue('edit_automobile_tax_unpaid'),
      qualified_invoice_registered: _getRadioValue('edit_qualified_invoice_registered'),
      invoice_registration_number:  document.getElementById('editInvoiceRegNumber')?.value || '',
      customer_furigana:            document.getElementById('editContractCustFurigana').value.trim() || null,
      customer_birth_date:          document.getElementById('editContractCustBirthDate').value || null,
      customer_license_number:      document.getElementById('editContractCustLicense').value.trim() || null,
    }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.href = '?tab=contract';
    else alert(d.message || '契約の更新に失敗しました');
  });
}

// ── 契約承認 ─────────────────────────────────────────────────────────────

function approveContract(action) {
  const reason = action === 'reject' ? prompt('差し戻し理由を入力してください') : '';
  if (action === 'reject' && !reason) return;
  apiFetch(`/sateiinfo/api/contracts/${CONTRACT_ID}/approve/`, {
    method: 'POST',
    body: JSON.stringify({ action, reason }),
  })
  .then(r => r.json())
  .then(d => {
    if (d.success) location.reload();
    else alert(d.message);
  });
}
