# FinancialTracker — Bug Report

Generated: 2026-04-01

Total bugs found: **51** across backend Python, HTML templates, JavaScript, service worker, tests, and configuration.

---

## Table of Contents

- [Critical (7)](#critical)
- [High (13)](#high)
- [Medium (18)](#medium)
- [Low (13)](#low)

---

## Critical

### BUG-01: Hardcoded Secret Key Fallback
- **File:** `app/config.py:5`
- **Code:** `SECRET_KEY = os.environ.get('SECRET_KEY', 'fintracker-secret-key-2026')`
- **Issue:** If the `SECRET_KEY` environment variable is unset, the app uses a predictable hardcoded secret key. Attackers can forge session cookies and impersonate any user.
- **Fix:** Remove the fallback or require the env var at startup. Generate a random key for development.

### BUG-02: Hardcoded Database Credentials
- **File:** `app/config.py:13`
- **Code:** `SQLALCHEMY_DATABASE_URI = _database_url or 'mysql+pymysql://root:root@localhost/fintrackdb'`
- **Issue:** Default fallback contains hardcoded `root:root` MySQL credentials. If deployed without setting `DATABASE_URL`, the app connects with root privileges.
- **Fix:** Remove the fallback or raise an error if `DATABASE_URL` is not set.

### BUG-03: Open Redirect in Login
- **File:** `app/auth.py:50-51`
- **Code:** `next_page = request.args.get('next'); return redirect(next_page or url_for('main.dashboard'))`
- **Issue:** The `next` parameter is not validated against relative paths. An attacker can craft `/login?next=https://evil.com` to redirect users after login to a malicious site.
- **Fix:** Use `url_has_allowed_host_and_scheme(next_page)` or validate that `next_page` starts with `/` and doesn't start with `//`.

### BUG-04: Missing CSRF Tokens in All Auth Forms
- **Files:** `auth/login.html:47`, `auth/register.html:47`, `auth/reset_password.html:47`, `auth/request_reset.html:51`, `auth/reset_with_token.html:47`, `auth/verify_email.html:54`
- **Code:** `<form method="POST" class="auth-form">` (no CSRF token anywhere)
- **Issue:** All authentication forms submit via POST without CSRF tokens. If Flask-WTF CSRFProtect is enabled, all form submissions will fail (400). If not enabled, the app is vulnerable to cross-site request forgery attacks.
- **Fix:** Add `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` to every POST form.

### BUG-05: Undefined `authenticated_client` in Test
- **File:** `tests/test_auth.py:145`
- **Code:** `def test_verify_2fa_get(self, client): response = authenticated_client.get('/auth/verify_2fa')`
- **Issue:** Function parameter is `client` but body references `authenticated_client`, which is undefined. Raises `NameError` at test time.
- **Fix:** Change parameter name to `authenticated_client` or use `client` consistently.

### BUG-06: `app.db` Does Not Exist in Flask-SQLAlchemy
- **File:** `tests/conftest.py:116-117, 134-135, 156-157`
- **Code:** `app.db.session.add(wallet)`
- **Issue:** Flask-SQLAlchemy does not attach `db` to the `app` object. The correct reference is the module-level `db` instance. Raises `AttributeError` in fixtures `test_wallet`, `test_category`, `test_expense`.
- **Fix:** Replace `app.db` with the imported `db` instance.

### BUG-07: `init_db()` Called Without Required Argument
- **File:** `seed_data.py:12`
- **Code:** `init_db()`
- **Issue:** `init_db` in `run.py:7` is defined as `def init_db(app):`, requiring an `app` argument. Calling it without arguments raises `TypeError`.
- **Fix:** Pass the Flask app instance: `init_db(app)`.

---

## High

### BUG-08: `Category` Model Has No `type` Attribute
- **File:** `app/routes_advanced.py:268`
- **Code:** `category = Category(user_id=current_user.id, name=category_name, type='expense')`
- **Issue:** The `Category` model has no `type` column. This raises `TypeError: 'type' is an invalid keyword argument for Category` at runtime.
- **Fix:** Remove the `type` parameter or add the column to the model if it's intended.

### BUG-09: `Goal` Model Has No `status` Attribute
- **File:** `app/routes_settings.py:161`
- **Code:** `'status': g.status`
- **Issue:** The `Goal` model has no `status` attribute (it uses `is_completed`). Raises `AttributeError` during data export.
- **Fix:** Change to `'status': 'completed' if g.is_completed else 'active'`.

### BUG-10: Tax Deduction Creates Expense Without `wallet_id`
- **File:** `app/routes_advanced.py:272-279`
- **Code:** `expense = Expense(...)` — no `wallet_id` provided, but the model has `nullable=False` on `wallet_id`.
- **Issue:** Raises `IntegrityError` if the database enforces NOT NULL on `wallet_id`.
- **Fix:** Either add a `wallet_id` parameter or make the column nullable.

### BUG-11: Incomplete Account Deletion Leaves Orphaned Data
- **File:** `app/routes_settings.py:103-106`
- **Code:** Only deletes `SecurityEvent, AuditLog, Budget, Goal, Investment, Creditor, Expense, Category, Wallet`
- **Issue:** Missing ~25+ models including `RecurringTransaction, FinancialSummary, WishlistItem, Debtor, InsurancePolicy, NetWorthSnapshot, FixedAsset, Project, PushSubscription, etc.` Causes foreign key constraint errors on databases with FK enforcement.
- **Fix:** Add all user-owned models to the deletion cascade, or configure `ondelete='CASCADE'` at the model level.

### BUG-12: File Upload Allows Arbitrary Extensions
- **File:** `app/routes_expenses.py:55-59`
- **Code:** `filename = secure_filename(file.filename); filepath = os.path.join('app', 'static', 'receipts', filename); file.save(filepath)`
- **Issue:** `secure_filename` strips directory traversal but doesn't validate file extension. Users can upload `.html`, `.svg`, or other dangerous file types that get served statically.
- **Fix:** Whitelist allowed extensions (e.g., `.jpg`, `.png`, `.pdf`).

### BUG-13: XSS in Lightbox — `src` Injected into innerHTML
- **File:** `app/static/js/lightbox.js:8`
- **Code:** `'<img src="' + src + '" alt="Receipt">'`
- **Issue:** The `src` parameter is directly interpolated into innerHTML without sanitization. A crafted URL like `" onerror="alert(document.cookie)` executes arbitrary JavaScript. Stored XSS vector.
- **Fix:** Use `element.setAttribute('src', src)` instead of string concatenation with innerHTML.

### BUG-14: `|safe` Filter on JSON Data in Script Tags
- **File:** `cash_flow.html:269`
- **Code:** `const monthlyData = {{ monthly_data|tojson|safe }};`
- **Issue:** The `|safe` filter disables HTML escaping. If JSON data contains `</script>`, it can break out of the script context and enable XSS.
- **Fix:** Remove `|safe` — use `{{ monthly_data|tojson }}` alone (Flask's `tojson` already produces safe output).

### BUG-15: `|safe` Filter on Chart Data in investments.html
- **File:** `investments.html:557-561`
- **Code:** `const allocationLabels = JSON.parse('{{ allocation_labels | safe }}');`
- **Issue:** Using `|safe` on backend data injected into a JS string context. If data contains single quotes or special characters, it breaks the JavaScript or enables XSS.
- **Fix:** Use `{{ allocation_labels|tojson }}` and remove `JSON.parse()`.

### BUG-16: Privacy Toggle Double-Inverts on Page Load
- **File:** `dashboard.html:304-309`
- **Code:** `if (isPrivacyMode) { togglePrivacy(); }`
- **Issue:** `togglePrivacy()` is a toggle — it flips the state. When `isPrivacyMode` is `true`, calling it sets it to `false` and shows amounts. The amounts end up visible despite the user having enabled privacy mode.
- **Fix:** Apply privacy styling directly without calling the toggle function: add the CSS class to blur amounts without flipping the boolean.

### BUG-17: Race Condition in Live-Search (No Request Cancellation)
- **File:** `app/static/js/live-search.js:20-34`
- **Code:** `fetch(form.action + '?' + params.toString()).then(...)` (no AbortController)
- **Issue:** Rapid typing fires multiple concurrent requests that can complete out of order. Stale results overwrite fresh ones in the DOM.
- **Fix:** Use `AbortController` to cancel previous requests before starting new ones.

### BUG-18: No Error Handling in Offline Transaction Queue
- **File:** `app/static/js/offline-store.js:19-26`
- **Code:** `async function queueOfflineTransaction(formData) { var db = await openOfflineDB(); ... store.add(...); }`
- **Issue:** No try/catch. If `openOfflineDB()` rejects or the transaction fails, the error is an unhandled promise rejection. `store.add()` result is never awaited.
- **Fix:** Wrap in try/catch and await the transaction completion.

### BUG-19: Service Worker Push Handler Crashes on Non-JSON Data
- **File:** `app/static/sw.js:101`
- **Code:** `const data = event.data ? event.data.json() : { ... };`
- **Issue:** If `event.data` contains non-JSON content (plain text), `.json()` throws `SyntaxError`, causing the push notification to silently fail.
- **Fix:** Wrap in try/catch or use `event.data.text()` with a fallback.

### BUG-20: Hidden Delete Form Without CSRF Token
- **File:** `edit_expense.html:163`
- **Code:** `<form id="deleteExpenseForm" method="POST" action="..." style="display: none;"></form>`
- **Issue:** Hidden delete form has no CSRF token. Combined with any XSS vulnerability, this enables forced deletion of expenses.
- **Fix:** Add CSRF token to the form.

### BUG-21: Fetch POST Requests Missing CSRF Tokens
- **Files:** `dashboard.html:327-330`, `goals.html:690-692`, `project_details.html:458-462`, `backup.html:450-456,515-522,562-568`
- **Code:** `fetch('/goals/tasks/${taskId}/toggle', { method: 'POST', headers: { 'Accept': 'application/json' } })`
- **Issue:** POST requests via fetch don't include CSRF tokens. If CSRF protection is enforced server-side, these requests will all fail with 400 errors.
- **Fix:** Include `X-CSRFToken` header with the CSRF token value from a meta tag or cookie.

---

## Medium

### BUG-22: `login_user` Receives String Instead of Boolean for `remember`
- **File:** `app/auth.py:45`
- **Code:** `login_user(user, remember=request.form.get('remember'))`
- **Issue:** `request.form.get('remember')` returns the string `'on'` or `None`. Flask-Login expects a boolean. The non-empty string is truthy, so `remember` is always True when the checkbox is checked, but this is a type correctness bug.
- **Fix:** Change to `remember=bool(request.form.get('remember'))`.

### BUG-23: Open Redirect via `_safe_return_url` — `//evil.com` Bypass
- **File:** `app/routes_creditors.py:10-13`
- **Code:** `if next_url and next_url.startswith('/'): return next_url`
- **Issue:** `//evil.com` starts with `/` and would redirect to an external site (browsers treat `//` as protocol-relative URL).
- **Fix:** Also check `not next_url.startswith('//')`.

### BUG-24: Missing Input Validation on Form Amount Fields
- **Files:** `routes_expenses.py:35`, `routes_recurring.py:24,30`, `routes_goals.py:134`, `routes_projects.py:118,154,179,229`, `routes_wishlist.py:26,49`, `routes_commitments.py:35,54`, `routes_fixed_assets.py:30-31,34`, `routes_accounting.py:51,53-55`
- **Code:** `amount = float(request.form.get('amount', 0))`
- **Issue:** No try/except around `float()` or `int()` conversions. Non-numeric input causes an unhandled `ValueError` → 500 error.
- **Fix:** Wrap in try/except with a user-friendly error flash.

### BUG-25: `end_date` Unassigned for Invalid Budget Period
- **File:** `app/routes_budgets.py:58-74`
- **Code:** The if/elif chain only handles `weekly`, `monthly`, `yearly`. If `period` is something else, `end_date` is never assigned.
- **Issue:** Raises `UnboundLocalError` when creating the `Budget` object with an invalid period value.
- **Fix:** Add a default `else` clause that sets a reasonable `end_date` or rejects the form input.

### BUG-26: Cash Flow Missing Income from Extra Payments
- **File:** `app/routes_cashflow.py:96-97`
- **Code:** `actual_expenses += m_extra_debt_exp` but `m_extra_debtor_inc` and `m_extra_contract_inc` are never added to `actual_income`.
- **Issue:** Debtor/contract income is computed but not included in income totals, causing incorrect cash flow calculations.
- **Fix:** Add `actual_income += m_extra_debtor_inc + m_extra_contract_inc`.

### BUG-27: `get_exchange_rate` Silently Returns 1.0 on Failure
- **File:** `app/utils.py:46`
- **Code:** `return 1.0`
- **Issue:** If the API call fails and no cached rate exists, returns `1.0` — treating all currencies as equal. Could cause major financial miscalculations (e.g., 1 USD = 1 GHS instead of ~12 GHS).
- **Fix:** Raise an exception or return `None` and handle it at the call site.

### BUG-28: Flash Category `'danger'` vs `'error'` Inconsistency
- **File:** `app/routes_investments.py:128,156,203,251,307,361`
- **Code:** `flash(f'Error adding investment: {str(e)}', 'danger')`
- **Issue:** The rest of the application uses `'error'` as the flash category. Templates that only check for `'error'` won't display these messages.
- **Fix:** Change `'danger'` to `'error'` to be consistent.

### BUG-29: Race Condition on Wallet Balance Updates
- **Files:** `routes_expenses.py:158-160`, `routes_wallets.py:236-237`, `routes_creditors.py:348`, `routes_debtors.py:432`
- **Code:** `wallet.balance -= converted_amount`
- **Issue:** Read-modify-write without row-level locking. Two concurrent requests can both read the same balance and both subtract, leading to incorrect totals.
- **Fix:** Use `SELECT ... FOR UPDATE` or SQLAlchemy `with_for_update()`.

### BUG-30: Wishlist Item Referenced After Deletion
- **File:** `app/routes_wishlist.py:97-100`
- **Code:** `db.session.delete(item); db.session.commit(); flash(f"Executed '{item.name}'! ...")`
- **Issue:** After deletion and commit, the object's attributes may be expired/cleared by SQLAlchemy, causing `DetachedInstanceError` or empty string in the flash message.
- **Fix:** Capture `item.name` in a variable before deleting.

### BUG-31: Debt Payment Expense Deletion Doesn't Restore Creditor Amount
- **File:** `app/routes_creditors.py:348,359-368`
- **Code:** Wallet balance is refunded on expense deletion, but `DebtPayment` record and creditor amount are not reversed.
- **Issue:** Deleting a debt payment expense double-counts the refund. The creditor's owed amount is not restored.
- **Fix:** In `delete_expense`, check if it's a debt payment and reverse the creditor adjustment.

### BUG-32: Currency Select Shows Duplicate GHS Options
- **File:** `add_expense.html:56-59`
- **Code:** `<option value="GHS">GHS</option>` followed by `{% for code, name in currencies.items() %}` which also includes GHS.
- **Issue:** The dropdown has duplicate GHS entries.
- **Fix:** Remove the hardcoded GHS option or filter it from the loop.

### BUG-33: Hardcoded URL Paths in JavaScript (Multiple Templates)
- **Files:** `budgets.html:122`, `goals.html:649,655,677,711,735`, `creditors.html:453,460`, `debtors.html:676,703,718,729`, `recurring.html:146`, `project_details.html:498`
- **Code:** `form.action = '/budgets/delete/${budgetToDelete}';`
- **Issue:** Hardcoded URL paths instead of using `url_for()`. Breaks if the app is deployed under a subpath or URL structure changes.
- **Fix:** Use `url_for()` in data attributes or inject URL prefixes via template variables.

### BUG-34: Fragile URL Matching in Service Worker Notification Click
- **File:** `app/static/sw.js:128`
- **Code:** `if (client.url.includes(urlToOpen) && 'focus' in client) {`
- **Issue:** `String.includes()` does substring matching. `urlToOpen = '/add'` matches `/add_expense`, `/address`, etc. Could focus the wrong tab.
- **Fix:** Use exact URL comparison or `new URL()` parsing.

### BUG-35: 2FA Disable Uses `prompt()` for Password Entry
- **File:** `security.html:144`
- **Code:** `onclick="const pw=prompt('Enter password to disable 2FA:');..."`
- **Issue:** `prompt()` displays the password in plain text. Should use a proper modal with a masked password input.
- **Fix:** Create a modal dialog with `<input type="password">`.

### BUG-36: No Client-Side Password Confirmation Validation
- **Files:** `auth/register.html:69,77`, `auth/reset_password.html:61,69`, `auth/reset_with_token.html:53,61`, `settings.html:249,254`
- **Issue:** Password and confirm_password fields have no JavaScript validation. Users must wait for a server round-trip to discover mismatched passwords.
- **Fix:** Add a JS check on form submit that compares the two fields.

### BUG-37: Lightbox Keydown Listener Memory Leak
- **File:** `app/static/js/lightbox.js:15-20`
- **Code:** The `keydown` listener is only removed when Escape is pressed. If the lightbox is closed via the close button or overlay click, the listener is never removed.
- **Issue:** Repeated open/close cycles accumulate orphaned event listeners.
- **Fix:** Store the handler reference and remove it on all close paths.

### BUG-38: Stale Search Results on JSON Parse Failure
- **File:** `app/static/js/live-search.js:21`
- **Code:** `.then(function(r) { return r.json(); })`
- **Issue:** If the server returns a non-JSON response (e.g., 500 HTML error page), `r.json()` throws. The catch block only logs the error — the user sees no feedback.
- **Fix:** Check `Content-Type` header or wrap in try/catch with user-visible error message.

### BUG-39: Unpinned Dependencies in requirements.txt
- **File:** `requirements.txt:25-28`
- **Code:** `python-dotenv`, `PyJWT`, `pandas`, `psycopg2-binary` (no version pins)
- **Issue:** Builds are non-reproducible. A new major version could introduce breaking changes.
- **Fix:** Pin all dependency versions with `==` or `>=X.Y,<Z`.

---

## Low

### BUG-40: Duplicate Database Query on Dashboard Load
- **File:** `app/routes.py:271-272`
- **Code:** `Category.query.filter_by(name='Money Lent', user_id=current_user.id).first()` — same query already at line 142.
- **Issue:** Unnecessary duplicate query on every dashboard load.
- **Fix:** Reuse the result from line 142.

### BUG-41: Unused Variables / Dead Code in Dashboard
- **File:** `app/routes.py:158-179`
- **Code:** `oldest_expense`, `oldest_hist`, `hist_date` are computed but overridden by `oldest_date = dashboard_start_date`.
- **Issue:** Wasted DB queries for results that are never used.
- **Fix:** Remove the dead code.

### BUG-42: `print()` Statements in Production Code
- **Files:** `app/routes_expenses.py:69`, `app/utils.py:40,91`
- **Code:** `print(f"Converting {input_amount}...")`, `print(f"Error fetching rate...")`
- **Issue:** Debug print statements pollute stdout in production. Should use `app.logger`.
- **Fix:** Replace `print()` with `app.logger.debug()` / `app.logger.error()`.

### BUG-43: Typo in Error Message — "fo" Instead of "for"
- **File:** `app/utils.py:40`
- **Code:** `print(f"Error fetching rate fo {from_currency}: {e}")`
- **Issue:** Typo "fo" → "for".
- **Fix:** Correct the typo.

### BUG-44: `__import__('datetime')` Anti-Pattern
- **File:** `app/routes_advanced.py:535,571`
- **Code:** `six_months_ago = now - __import__('datetime').timedelta(days=180)`
- **Issue:** Using `__import__` inline instead of importing `timedelta` at the top. Works but is unnecessarily convoluted and hard to maintain.
- **Fix:** Add `from datetime import timedelta` at the top of the file.

### BUG-45: Unused `CACHE_NAME` Constant in Service Worker
- **File:** `app/static/sw.js:2`
- **Code:** `const CACHE_NAME = 'fintracker-v1';`
- **Issue:** Defined but never referenced. Only `STATIC_CACHE` and `DYNAMIC_CACHE` are used. Dead code that could cause confusion.
- **Fix:** Remove the unused constant.

### BUG-46: Service Worker Never Cleans Old Dynamic Caches
- **File:** `app/static/sw.js:26-37`
- **Code:** The activate handler only deletes caches that are neither `STATIC_CACHE` nor `DYNAMIC_CACHE`. Old `DYNAMIC_CACHE` versions are never cleaned.
- **Issue:** Unbounded storage growth over time.
- **Fix:** Add version suffix to `DYNAMIC_CACHE` name and delete old versions.

### BUG-47: Sync Silently Discards Permanently Failed Transactions
- **File:** `app/static/sw.js:156-168`
- **Code:** Failed transactions remain in IndexedDB with no retry limit, backoff, or user notification.
- **Issue:** Transactions that always fail (e.g., invalid data) accumulate indefinitely.
- **Fix:** Add a retry counter and notify the user after N failures.

### BUG-48: API Key Displayed in Flash Message
- **File:** `app/routes_api_keys.py:36`
- **Code:** `flash(f'API Key created. Save this key now (shown only once): {raw_key}', 'success')`
- **Issue:** Secrets in flash messages appear in HTML, can be captured by browser extensions or XSS, and may be logged in server access logs.
- **Fix:** Render the key in a dedicated one-time view rather than a flash message.

### BUG-49: Notification Count Query on Every Request
- **File:** `app/routes_notifications.py:81-87`
- **Code:** `@notifications_bp.app_context_processor` runs `Notification.query.filter_by(...).count()` on every template render for authenticated users.
- **Issue:** Adds a database query to every single page load. Performance overhead.
- **Fix:** Cache the count or use a lazy-loaded property.

### BUG-50: Inconsistent Currency Formatting Across Templates
- **Files:** `dashboard.html:53` uses `GHS`, `goals.html:45` uses `GH₵`, `investments.html:38` uses `GH&#8373;`
- **Issue:** Three different representations of the Ghana Cedi symbol. Creates visual inconsistency.
- **Fix:** Standardize to a single representation via a shared template filter or macro.

### BUG-51: Analytics Table colspan Mismatch in Empty State
- **File:** `analytics.html:139`
- **Code:** `<td colspan="4">No historical data available.</td>` but the table has 5 columns.
- **Issue:** Misaligned empty row — only spans 4 of 5 columns.
- **Fix:** Change to `colspan="5"`.

---

## Summary by Severity

| Severity | Count | Description |
|----------|-------|-------------|
| **Critical** | 7 | Security keys exposed, auth bypass, test infrastructure broken |
| **High** | 13 | XSS, model attribute errors, missing CSRF, data integrity |
| **Medium** | 18 | Open redirects, input validation, race conditions, logic errors |
| **Low** | 13 | Performance, dead code, typos, inconsistencies |
| **Total** | **51** | |

## Recommended Priority Fixes

1. **BUG-01, BUG-02**: Rotate secrets and remove hardcoded fallbacks immediately
2. **BUG-03**: Fix open redirect in login — actively exploitable
3. **BUG-04, BUG-20, BUG-21**: Add CSRF protection to all forms and fetch requests
4. **BUG-08, BUG-09, BUG-10**: Fix model attribute errors — these cause 500 errors on use
5. **BUG-13, BUG-14, BUG-15**: Fix XSS vulnerabilities in templates and JS
6. **BUG-16**: Fix privacy toggle — currently non-functional
7. **BUG-11**: Fix incomplete account deletion — causes database integrity errors
