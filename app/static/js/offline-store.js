// IndexedDB wrapper for offline transaction support
const OFFLINE_DB_NAME = 'fintracker-offline';
const OFFLINE_DB_VERSION = 1;

function openOfflineDB() {
  return new Promise(function(resolve, reject) {
    var request = indexedDB.open(OFFLINE_DB_NAME, OFFLINE_DB_VERSION);
    request.onerror = function() { reject(request.error); };
    request.onsuccess = function() { resolve(request.result); };
    request.onupgradeneeded = function(e) {
      var db = e.target.result;
      if (!db.objectStoreNames.contains('pendingTransactions')) {
        db.createObjectStore('pendingTransactions', { keyPath: 'id', autoIncrement: true });
      }
    };
  });
}

async function queueOfflineTransaction(formData) {
  var db = await openOfflineDB();
  var tx = db.transaction('pendingTransactions', 'readwrite');
  var store = tx.objectStore('pendingTransactions');
  var data = {};
  formData.forEach(function(value, key) { data[key] = value; });
  store.add({ data: data, timestamp: Date.now() });
}

async function getPendingCount() {
  try {
    var db = await openOfflineDB();
    var tx = db.transaction('pendingTransactions', 'readonly');
    var store = tx.objectStore('pendingTransactions');
    return new Promise(function(resolve) {
      var req = store.count();
      req.onsuccess = function() { resolve(req.result); };
      req.onerror = function() { resolve(0); };
    });
  } catch (e) {
    return 0;
  }
}

// Online/Offline detection
function updateOnlineStatus() {
  var banner = document.getElementById('offlineBanner');
  if (!banner) return;
  if (navigator.onLine) {
    banner.classList.remove('visible');
    // Try background sync when coming back online
    if ('serviceWorker' in navigator && 'SyncManager' in window) {
      navigator.serviceWorker.ready.then(function(reg) {
        reg.sync.register('sync-transactions');
      });
    }
  } else {
    banner.classList.add('visible');
  }
}

window.addEventListener('online', updateOnlineStatus);
window.addEventListener('offline', updateOnlineStatus);
window.addEventListener('DOMContentLoaded', updateOnlineStatus);
