/**
 * customer_detail.js — 顧客詳細画面の JS
 * 依存: app.js (getCsrf, showToast), Bootstrap 5
 * テンプレート側インライン宣言が必要な変数: CUSTOMER_ID
 */

function saveCustomer() {
  const taxableRaw = document.getElementById('custTaxable').value;
  const payload = {
    name:                        document.getElementById('custName').value.trim(),
    furigana:                    document.getElementById('custFurigana').value.trim(),
    phone_number:                document.getElementById('custPhone').value.trim(),
    email:                       document.getElementById('custEmail').value.trim(),
    postal_code:                 document.getElementById('custPostal').value.trim(),
    address:                     document.getElementById('custAddress').value.trim(),
    birth_date:                  document.getElementById('custBirthDate').value,
    age:                         document.getElementById('custAge').value,
    gender:                      document.getElementById('custGender').value,
    occupation:                  document.getElementById('custOccupation').value.trim(),
    license_number:              document.getElementById('custLicense').value.trim(),
    family_structure:            document.getElementById('custFamily').value.trim(),
    is_taxable_business:         taxableRaw === '' ? null : taxableRaw === 'true',
    invoice_registration_number: document.getElementById('custInvoiceNum').value.trim(),
  };

  apiFetch(`/sateiinfo/api/customers/${CUSTOMER_ID}/update/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      showToast('顧客情報を更新しました');
      bootstrap.Modal.getInstance(document.getElementById('editCustomerModal')).hide();
      document.getElementById('dispName').textContent       = payload.name || '-';
      document.getElementById('dispFurigana').textContent   = payload.furigana || '-';
      document.getElementById('dispPhone').textContent      = payload.phone_number || '-';
      document.getElementById('dispEmail').textContent      = payload.email || '-';
      document.getElementById('dispPostal').textContent     = payload.postal_code || '-';
      document.getElementById('dispAddress').textContent    = payload.address || '-';
      document.getElementById('dispBirthDate').textContent  = payload.birth_date || '-';
      document.getElementById('dispAge').textContent        = payload.age ? payload.age + '歳' : '-';
      document.getElementById('dispGender').textContent     = payload.gender || '-';
      document.getElementById('dispOccupation').textContent = payload.occupation || '-';
      document.getElementById('dispLicense').textContent    = payload.license_number || '-';
      document.getElementById('dispFamily').textContent     = payload.family_structure || '-';
      document.getElementById('dispTaxable').textContent    =
        payload.is_taxable_business === null ? '-' : payload.is_taxable_business ? 'はい' : 'いいえ';
      document.getElementById('dispInvoiceNum').textContent = payload.invoice_registration_number || '-';
    } else {
      showToast(data.message || '更新に失敗しました', '', 'danger');
    }
  })
  .catch(() => showToast('通信エラーが発生しました', '', 'danger'));
}

function saveBankAccount() {
  const payload = {
    bank_name:      document.getElementById('bankName').value.trim(),
    branch_name:    document.getElementById('bankBranch').value.trim(),
    account_type:   document.getElementById('bankType').value,
    account_number: document.getElementById('bankNumber').value.trim(),
    account_holder: document.getElementById('bankHolder').value.trim(),
    is_primary:     document.getElementById('bankIsPrimary').checked,
  };
  if (!payload.bank_name || !payload.account_number || !payload.account_holder) {
    showToast('銀行名・口座番号・名義は必須です', '', 'danger');
    return;
  }
  apiFetch(`/sateiinfo/api/customers/${CUSTOMER_ID}/save-bank-account/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      showToast('口座情報を保存しました');
      bootstrap.Modal.getInstance(document.getElementById('addBankModal')).hide();
      location.reload();
    } else {
      showToast(data.message || '保存に失敗しました', '', 'danger');
    }
  })
  .catch(() => showToast('通信エラーが発生しました', '', 'danger'));
}

function deleteBankAccount(accountId, btn) {
  if (!confirm('この口座情報を削除しますか？')) return;
  apiFetch(`/sateiinfo/api/customers/${CUSTOMER_ID}/bank-accounts/${accountId}/delete/`, {
    method: 'POST',
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      showToast('口座情報を削除しました');
      btn.closest('tr').remove();
    } else {
      showToast(data.message || '削除に失敗しました', '', 'danger');
    }
  })
  .catch(() => showToast('通信エラーが発生しました', '', 'danger'));
}
