// Touch gesture handling for mobile sidebar
(function() {
  let touchStartX = 0;
  let touchStartY = 0;
  let touchEndX = 0;
  let touchEndY = 0;
  const SWIPE_THRESHOLD = 70;
  const EDGE_ZONE = 30;

  document.addEventListener('touchstart', function(e) {
    touchStartX = e.changedTouches[0].screenX;
    touchStartY = e.changedTouches[0].screenY;
  }, { passive: true });

  document.addEventListener('touchend', function(e) {
    touchEndX = e.changedTouches[0].screenX;
    touchEndY = e.changedTouches[0].screenY;

    const diffX = touchEndX - touchStartX;
    const diffY = Math.abs(touchEndY - touchStartY);

    // Only handle horizontal swipes (not vertical scrolling)
    if (diffY > Math.abs(diffX)) return;

    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;

    // Swipe right from left edge to open sidebar
    if (diffX > SWIPE_THRESHOLD && touchStartX < EDGE_ZONE) {
      if (!sidebar.classList.contains('open')) {
        if (typeof toggleSidebar === 'function') toggleSidebar();
      }
    }

    // Swipe left to close sidebar
    if (diffX < -SWIPE_THRESHOLD && sidebar.classList.contains('open')) {
      if (typeof toggleSidebar === 'function') toggleSidebar();
    }
  }, { passive: true });
})();
