// Lightweight receipt lightbox viewer
function openLightbox(src) {
  const overlay = document.createElement('div');
  overlay.className = 'lightbox-overlay';
  overlay.innerHTML =
    '<div class="lightbox-content">' +
    '<button class="lightbox-close" onclick="this.closest(\'.lightbox-overlay\').remove()" aria-label="Close">&times;</button>' +
    '<img src="' + src + '" alt="Receipt">' +
    '</div>';

  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) overlay.remove();
  });

  document.addEventListener('keydown', function handler(e) {
    if (e.key === 'Escape') {
      overlay.remove();
      document.removeEventListener('keydown', handler);
    }
  });

  document.body.appendChild(overlay);
}
