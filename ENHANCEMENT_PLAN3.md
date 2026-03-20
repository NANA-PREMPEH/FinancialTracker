# ENHANCEMENT PLAN 3: Bugs, Technical Debt & Extended Features

**Date:** March 18, 2026
**Scope:** 24 items covering bugs, critical fixes, API gaps, code quality, and extended features
**Project:** Flask + SQLAlchemy Financial Tracker (MySQL, Jinja2, Chart.js)

---

## Table of Contents

1. [Phase 1 — Critical Bugs & Fixes](#phase-1--critical-bugs--fixes)
2. [Phase 2 — API Gaps & Completions](#phase-2--api-gaps--completions)
3. [Phase 3 — Code Quality & Security](#phase-3--code-quality--security)
4. [Phase 4 — Stub Completions & Feature Extensions](#phase-4--stub-completions--feature-extensions)
5. [Phase 5 — Enhanced User Experience](#phase-5--enhanced-user-experience)

---

## Phase 1 — Critical Bugs & Fixes

### Enhancement #1: Fix API Summary Query Join Error
**Problem:** [`app/api/summary.py`](app/api/summary.py:72) line 72-79 has incorrect join syntax - joins Category but filters on Expense.user_id incorrectly. The query joins Category directly but should use Category relationship.

**Fix:**
```python
# Current (broken):
category_spending = db.session.query(
    Category.name, func.sum(Expense.amount)
).join(Category).filter(...)
# Should be:
category_spending = db.session.query(
    Category.name, func.sum(Expense.amount)
).join(Expense, Category.id == Expense.category_id).filter(...)
```

**Files:** `app/api/summary.py`

---

### Enhancement #2: Fix Calculator Avalanche Simulation Bug
**Problem:** [`app/routes_calculator.py`](app/routes_calculator.py:189) line 189 uses a lambda incorrectly: `debts.sort(key=lambda d: -d['rate'] if callable else 'balance')` - the `callable` check is wrong.

**Fix:** Remove the broken sort and use proper sorting logic for avalanche method (already duplicated correctly at lines 191-240).

**Files:** `app/routes_calculator.py`

---

### Enhancement #3: Add Global Error Handlers
**Problem:** No custom error pages for 400, 403, 404, 500 errors. Users see generic Werkzeug errors.

**Fix:** Add error handlers in `app/__init__.py`:
```python
@app.errorhandler(400)
def bad_request(e): return render_template('error.html', code=400), 400

@app.errorhandler(403)
def forbidden(e): return render_template('error.html', code=403), 403

@app.errorhandler(404)
def not_found(e): return render_template('error.html', code=404), 404

@app.errorhandler(500)
def server_error(e): return render_template('error.html', code=500), 500
```

Create `app/templates/error.html` with consistent styling.

**Files:** `app/__init__.py`, `app/templates/error.html` (new)

---

### Enhancement #4: Fix Currency Formatting Inconsistencies
**Problem:** Templates use different currency formats: `GH₵`, `GHS`, `$`, hardcoded symbols. No统一 formatting.

**Fix:**
- Create a Jinja2 filter `format_currency(amount, currency=None)` in `app/__init__.py`
- Default currency from user preferences or config
- Update all templates to use `{{ amount|format_currency() }}`

**Files:** `app/__init__.py`, all template files

---

### Enhancement #5: Add Missing Input Validation in API Endpoints
**Problem:** Some API endpoints lack proper input validation (e.g., negative amounts, invalid dates).

**Fix:** Add validation helper and apply to all create/update endpoints:
- Amounts must be positive numbers
- Dates must be valid ISO format
- Strings must not exceed max length
- Required fields must be present

**Files:** `app/api/__init__.py`, all API endpoint files

---

### Enhancement #6: Fix Template Max/Min Filter Issues
**Problem:** [`app/templates/metrics.html`](app/templates/metrics.html:111) line 111 uses `max` filter which may be undefined in Jinja.

**Fix:** Add custom Jinja2 filters or ensure `max` and `min` are available via Flask context processor:
```python
@app.context_processor
def utility_processor():
    return dict(max=max, min=min, enumerate=enumerate)
```

**Files:** `app/__init__.py`, affected template files

---

## Phase 2 — API Gaps & Completions

### Enhancement #7: Complete Budget CRUD API
**Problem:** [`app/api/budgets.py`](app/api/budgets.py) only has GET endpoint. Missing POST, PUT, DELETE.

**Fix:** Add:
- `POST /api/v1/budgets` — create budget
- `PUT /api/v1/budgets/<id>` — update budget  
- `DELETE /api/v1/budgets/<id>` — delete budget
- Proper validation, error handling, serialization

**Files:** `app/api/budgets.py`

---

### Enhancement #8: Add Recurring Transactions API
**Problem:** No API endpoints for recurring transactions (auto-created expenses/income).

**Fix:** Create `app/api/recurring.py`:
- `GET /api/v1/recurring` — list all recurring transactions
- `POST /api/v1/recurring` — create recurring transaction
- `GET /api/v1/recurring/<id>` — get single
- `PUT /api/v1/recurring/<id>` — update
- `DELETE /api/v1/recurring/<id>` — delete

**Files:** `app/api/recurring.py` (new), `app/api/__init__.py`

---

### Enhancement #9: Add Projects API
**Problem:** No API for project management.

**Fix:** Create `app/api/projects.py`:
- `GET /api/v1/projects` — list projects
- `POST /api/v1/projects` — create project
- `GET /api/v1/projects/<id>` — get project with items
- `PUT /api/v1/projects/<id>` — update project
- `DELETE /api/v1/projects/<id>` — delete project
- `POST /api/v1/projects/<id>/items` — add project item

**Files:** `app/api/projects.py` (new), `app/api/__init__.py`

---

### Enhancement #10: Add Wishlist API
**Problem:** No API for wishlist items.

**Fix:** Create `app/api/wishlist.py`:
- `GET /api/v1/wishlist` — list wishlist
- `POST /api/v1/wishlist` — add item
- `PUT /api/v1/wishlist/<id>` — update item
- `DELETE /api/v1/wishlist/<id>` — delete item

**Files:** `app/api/wishlist.py` (new), `app/api/__init__.py`

---

### Enhancement #11: Add Transaction Search API
**Problem:** No way to search transactions via API.

**Fix:** Add search endpoint in `app/api/transactions.py`:
```python
@api_bp.route('/transactions/search', methods=['GET'])
@require_api_key('read')
def search_transactions():
    # Query params: q (search term), category_id, wallet_id, 
    # start_date, end_date, transaction_type, min_amount, max_amount
```

**Files:** `app/api/transactions.py`

---

### Enhancement #12: Add Webhook Management API
**Problem:** No API to manage webhooks for automation.

**Fix:** Create `app/api/webhooks.py`:
- `GET /api/v1/webhooks` — list webhooks
- `POST /api/v1/webhooks` — create webhook
- `DELETE /api/v1/webhooks/<id>` — delete webhook

**Files:** `app/api/webhooks.py` (new), `app/api/__init__.py`

---

### Enhancement #13: Add Reports/Export API
**Problem:** No API for generating reports.

**Fix:** Create `app/api/reports.py`:
- `GET /api/v1/reports/summary` — financial summary
- `GET /api/v1/reports/cash-flow` — cash flow report
- `GET /api/v1/reports/budget-performance` — budget adherence
- Support date range parameters

**Files:** `app/api/reports.py` (new), `app/api/__init__.py`

---

## Phase 3 — Code Quality & Security

### Enhancement #14: Add Structured Logging
**Problem:** No centralized logging. Print statements scattered.

**Fix:** Configure logging in `app/__init__.py`:
```python
import logging
from logging.handlers import RotatingFileHandler
import os

if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/fintrack.log', maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
```

**Files:** `app/__init__.py`

---

### Enhancement #15: Add Request ID Tracking
**Problem:** Hard to trace requests across logs.

**Fix:** Add request ID middleware:
```python
from uuid import uuid4

@app.before_request
def add_request_id():
    g.request_id = request.headers.get('X-Request-ID') or str(uuid4())

@app.after_request
def add_request_id_header(response):
    response.headers['X-Request-ID'] = g.get('request_id', 'unknown')
    return response
```

**Files:** `app/__init__.py`

---

### Enhancement #16: Add API Rate Limiting per User
**Problem:** Current rate limiting is per API key, not per user.

**Fix:** Enhance rate limiting in `app/api/__init__.py`:
- Track requests per user_id + API key combination
- Add user-specific rate limits (configurable)
- Return proper 429 status with Retry-After header

**Files:** `app/api/__init__.py`

---

### Enhancement #17: Input Sanitization
**Problem:** Potential XSS in user inputs displayed without escaping.

**Fix:** 
- Enable Jinja2 autoescape globally
- Add CSRF protection for all forms (Flask-WTF)
- Sanitize user inputs in API responses
- Add Content Security Policy headers

**Files:** `app/__init__.py`, templates, forms

---

### Enhancement #18: Add Database Connection Pooling Health Check
**Problem:** No way to check database health.

**Fix:** Add health check endpoint:
```python
@app.route('/api/health')
def health_check():
    try:
        db.session.execute('SELECT 1')
        return jsonify({'status': 'healthy', 'db': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'db': str(e)}), 503
```

**Files:** `app/__init__.py` or new `app/routes_health.py`

---

## Phase 4 — Stub Completions & Feature Extensions

### Enhancement #19: Complete ROI Calculator
**Problem:** [`app/templates/calculator.html`](app/templates/calculator.html:116) ROI calculator inputs exist but no calculation logic.

**Fix:** Add ROI calculation logic in `app/routes_calculator.py`:
- Calculate return percentage: `(current - invested) / invested * 100`
- Annualized return: `((current / invested) ** (1/years) - 1) * 100`
- Link JavaScript to call `/calculator/compute` endpoint

**Files:** `app/routes_calculator.py`, `app/templates/calculator.html`

---

### Enhancement #20: Enhance Tax Center Export
**Problem:** Tax export is basic, lacks bracket breakdown.

**Fix:** Enhance tax calculation with:
- Ghana GRA bracket visualization
- Deduction category breakdown
- Tax liability projection
- Export to PDF with professional formatting

**Files:** `app/routes_advanced.py`, `app/templates/tax_center.html`

---

### Enhancement #21: Add Budget Rollover Feature
**Problem:** Budgets reset each period, no rollover of unused amounts.

**Fix:** Add budget rollover logic:
- Option to enable rollover per budget
- Carry unused budget to next period
- Track rollover history
- Add UI toggle in budget forms

**Files:** `app/models.py`, `app/routes_budgets.py`, `app/templates/budgets.html`

---

### Enhancement #22: Complete Shared Wallet Activity Feed
**Problem:** Shared wallets lack activity tracking.

**Fix:** Add `WalletActivity` model and endpoint:
- Track all actions on shared wallets
- Show who made changes
- Display in wallet detail view
- Include timestamp and action type

**Files:** `app/models.py`, `app/routes_shared_wallets.py`, `app/templates/wallets.html`

---

## Phase 5 — Enhanced User Experience

### Enhancement #23: Add Dashboard Widget Customization
**Problem:** Fixed dashboard layout, users can't customize.

**Fix:** Add widget system:
- Store user preferences for visible widgets
- Allow drag-and-drop reordering
- Add/remove widgets dynamically
- Persist preferences in database

**Files:** `app/models.py`, `app/routes.py`, `app/templates/dashboard.html`

---

### Enhancement #24: Add Scheduled Report Emails
**Problem:** No automated report delivery.

**Fix:** Implement scheduled reports:
- Add `ScheduledReport` model: user_id, report_type, frequency, recipients
- Background scheduler (APScheduler) to generate and send
- Support daily, weekly, monthly frequencies
- Include PDF attachment option

**Files:** `app/models.py`, `app/routes_newsletter.py`, new scheduler setup in `app/__init__.py`

---

## Implementation Order

| Priority | Enhancements | Rationale |
|----------|-------------|-----------|
| **P0 — Do First** | #1, #2, #3, #6 | Critical bugs causing errors |
| **P1 — Security** | #14, #15, #17 | Logging, tracking, sanitization |
| **P2 — API Completion** | #7, #8, #9, #10, #11, #12, #13 | Fill major API gaps |
| **P3 — Quality** | #4, #5, #16, #18 | Code consistency and reliability |
| **P4 — Features** | #19, #20, #21, #22, #23, #24 | User-facing enhancements |

---

## Estimated File Impact

| Category | New Files | Modified Files |
|----------|-----------|----------------|
| Route files | 4 | 8 |
| Template files | 2 | 15 |
| API files | 7 | 3 |
| Config/Main files | 1 | 2 |
| Model changes | 0 | 2 |
| **Total** | **14** | **30** |

---

## Notes

- All API additions follow RESTful conventions
- New endpoints require authentication via API key or JWT
- Rate limiting applies to all `/api/v1/*` routes
- Error responses follow consistent JSON format: `{"error": "message"}`
- All new features should have corresponding test coverage
- Consider backwards compatibility for API v1 (use versioning for breaking changes)
