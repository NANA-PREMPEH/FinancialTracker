// Debounced live search for the expenses/transactions page
(function() {
  var debounceTimer;

  function liveSearch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function() {
      var form = document.getElementById('filterForm');
      if (!form) return;

      var params = new URLSearchParams(new FormData(form));
      params.set('ajax', '1');

      var tbody = document.getElementById('expenseTableBody');
      var countEl = document.getElementById('resultCount');
      if (tbody) {
        tbody.style.opacity = '0.5';
      }

      fetch(form.action + '?' + params.toString())
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (tbody && data.html) {
            tbody.innerHTML = data.html;
            tbody.style.opacity = '1';
          }
          if (countEl && data.count !== undefined) {
            countEl.textContent = data.count + ' transaction(s)';
          }
        })
        .catch(function(err) {
          console.error('Live search error:', err);
          if (tbody) tbody.style.opacity = '1';
        });
    }, 300);
  }

  // Expose globally
  window.liveSearch = liveSearch;
})();
