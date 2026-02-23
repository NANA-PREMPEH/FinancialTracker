// Service Worker Registration
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then((reg) => {
        console.log('[PWA] Service Worker registered, scope:', reg.scope);
      })
      .catch((err) => {
        console.log('[PWA] Service Worker registration failed:', err);
      });
  });
}

// PWA Install Prompt
let deferredPrompt;

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;

  // Show install banner
  const banner = document.getElementById('pwaInstallBanner');
  if (banner) {
    banner.style.display = 'flex';
  }
});

function installApp() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') {
        console.log('[PWA] App installed');
      }
      deferredPrompt = null;
      const banner = document.getElementById('pwaInstallBanner');
      if (banner) {
        banner.style.display = 'none';
      }
    });
  }
}

function dismissInstallBanner() {
  const banner = document.getElementById('pwaInstallBanner');
  if (banner) {
    banner.style.display = 'none';
  }
  localStorage.setItem('pwaInstallDismissed', 'true');
}

// Don't show banner if already dismissed
window.addEventListener('DOMContentLoaded', () => {
  if (localStorage.getItem('pwaInstallDismissed') === 'true') {
    const banner = document.getElementById('pwaInstallBanner');
    if (banner) {
      banner.style.display = 'none';
    }
  }
});

// Detect when app is installed
window.addEventListener('appinstalled', () => {
  console.log('[PWA] App was installed');
  deferredPrompt = null;
  const banner = document.getElementById('pwaInstallBanner');
  if (banner) {
    banner.style.display = 'none';
  }
});
