document.getElementById('deleteModal').addEventListener('show.bs.modal', function (event) {
  const btn = event.relatedTarget;
  document.getElementById('deleteTargetName').textContent = btn.dataset.name;
  document.getElementById('deleteForm').action = btn.dataset.deleteUrl;
});
