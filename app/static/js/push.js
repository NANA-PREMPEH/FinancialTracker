// Push notification subscription management
(function() {
  // Get VAPID public key from meta tag
  const vapidMeta = document.querySelector('meta[name="vapid-public-key"]');
  if (!vapidMeta || !('serviceWorker' in navigator) || !('PushManager' in window)) return;

  const VAPID_PUBLIC_KEY = vapidMeta.content;
  if (!VAPID_PUBLIC_KEY) return;

  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  async function subscribePush() {
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') return;

      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
      });

      await fetch('/push/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sub.toJSON())
      });

      console.log('[Push] Subscribed successfully');
    } catch (err) {
      console.log('[Push] Subscription failed:', err);
    }
  }

  // Auto-subscribe if notifications are already granted
  if (Notification.permission === 'granted') {
    subscribePush();
  }

  // Expose for manual triggering (e.g., from notification preferences page)
  window.subscribePush = subscribePush;
})();
