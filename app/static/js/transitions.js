// Smooth page transitions using View Transitions API
(function() {
  if (!document.startViewTransition) return;

  document.addEventListener('click', function(e) {
    const link = e.target.closest('a:not([target]):not([download]):not([href^="#"]):not([href^="javascript"])');
    if (!link) return;
    if (link.hostname !== window.location.hostname) return;

    e.preventDefault();
    document.startViewTransition(function() {
      window.location.href = link.href;
    });
  });
})();
