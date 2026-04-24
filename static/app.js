document.addEventListener('DOMContentLoaded', () => {
  const openers = document.querySelectorAll('[data-open-modal]');
  const closers = document.querySelectorAll('[data-close-modal]');

  openers.forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = document.getElementById(btn.dataset.openModal);
      if (modal) modal.classList.add('open');
    });
  });

  closers.forEach(btn => {
    btn.addEventListener('click', () => {
      btn.closest('.modal')?.classList.remove('open');
    });
  });

  document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', e => {
      if (e.target === modal) modal.classList.remove('open');
    });
  });
});
