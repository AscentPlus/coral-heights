document.addEventListener('DOMContentLoaded', () => {
  const printBtn = document.getElementById('btn-print-receipt');
  if (printBtn) {
    printBtn.addEventListener('click', () => {
      window.print();
    });
  }
});
