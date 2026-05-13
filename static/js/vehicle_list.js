/**
 * vehicle_list.js — 車両一覧画面
 */

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
