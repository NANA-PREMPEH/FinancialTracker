# FinancialTracker Enhancement Plan

**Date:** March 10, 2026 --
**Scope:** 22 enhancements covering critical fixes, stub completions, API gaps, and code quality
**Project:** Flask + SQLAlchemy Financial Tracker (MySQL, Jinja2, Chart.js)

---

## Table of Contents

1. [Phase 1 — Critical Fixes](#phase-1--critical-fixes)
2. [Phase 2 — Stub & Placeholder Completions](#phase-2--stub--placeholder-completions)
3. [Phase 3 — Incomplete Implementations](#phase-3--incomplete-implementations)
4. [Phase 4 — API Layer Expansion](#phase-4--api-layer-expansion)
5. [Phase 5 — Code Quality & Configuration](#phase-5--code-quality--configuration)

---

## Phase 1 — Critical Fixes

### Enhancement #1: Fix Budget Planning Template Reference
**Problem:** `routes_budget_planning.py` line 41 manually aliases `b.limit = b.amount` to work around the template using `b.limit`. This is fragile — if the alias is ever missed, the page 500s.
**Fix:**
- Update `budget_planning.html` template to use `b.amount` directly instead of `b.limit`
- Remove the `b.limit = b.amount` alias hack from `routes_budget_planning.py`
- Add `b.remaining` computed property: `b.amount - b.spent`

**Files:** `app/routes_budget_planning.py`, `app/templates/budget_planning.html`

---

### Enhancement #2: Fix Duplicate Backref Definitions on Models
**Problem:** Several models define TWO `user` relationships with different backrefs, e.g.:
```python
# PasswordResetToken has BOTH:
user = db.relationship('User', backref=db.backref('reset_tokens', ...))
user = db.relationship('User', backref=db.backref('_user_passwordresettokens', ...))
```
This causes SQLAlchemy warnings and potential conflicts. Affected models:
- `PasswordResetToken` (lines 893 + 898)
- `EmailVerificationToken` (lines 911 + 916)
- `PushSubscription` (lines 929 + 931)

**Fix:**
- Remove the duplicate `_user_*` prefixed relationships from these 3 models
- Keep only the readable backref names (`reset_tokens`, `verification_tokens`, `push_subscriptions`)

**Files:** `app/models.py`

---

## Phase 2 — Stub & Placeholder Completions

### Enhancement #3: Complete AI Insights Page
**Current State:** `routes_ai_insights.py` (159 lines) has rule-based insights only — spending trends, savings rate, budget alerts, debt ratio, unusual transactions.
**Enhancement:**
- Add **spending forecast** — project next month's expenses per category using 3-month rolling average
- Add **top recommendations** — prioritized action items (e.g., "Reduce Food spending by 15% to meet budget", "Pay off highest-interest creditor first")
- Add **weekly spending heatmap** data — show which days of the week the user spends most
- Add **income stability score** — measure variance in monthly income over last 6 months
- Add **financial health score** — composite metric combining savings rate, debt ratio, budget adherence, and goal progress

**Files:** `app/routes_ai_insights.py`, `app/templates/ai_insights.html`

---

### Enhancement #4: Build Full Calculator Module
**Current State:** `routes_calculator.py` is 10 lines — just renders an empty template.
**Enhancement — Add 5 financial calculators:**
1. **Loan Amortization** — monthly payment, total interest, amortization schedule (inputs: principal, rate, term)
2. **Compound Interest** — future value with optional monthly contributions
3. **Savings Goal** — how much to save monthly to reach a target by a deadline
4. **Debt Payoff** — snowball vs. avalanche comparison using user's actual creditors
5. **Net Worth Projection** — project net worth growth based on current savings rate

All calculations done server-side in Python. Each calculator returns results + a breakdown table.

**Files:** `app/routes_calculator.py`, `app/templates/calculator.html`

---

### Enhancement #5: Expand Tax Center
**Current State:** Tax-related models exist but route implementation is minimal/missing.
**Enhancement:**
- Add `/tax-center` route with dashboard showing: taxable income, deductions, estimated tax liability
- Add deduction tracking: input deductible expenses (charity, education, health insurance)
- Add **tax bracket calculator** for Ghana's GRA income tax brackets
- Add annual tax summary export (PDF via ReportLab)

**Files:** `app/routes_advanced.py` (or new `routes_tax.py`), `app/templates/tax_center.html`

---

### Enhancement #6: Build Metrics Dashboard
**Current State:** No metrics dashboard exists despite being referenced.
**Enhancement:**
- Create `/metrics` route with key financial KPIs:
  - Monthly burn rate, runway (balance / avg monthly expenses)
  - Expense-to-income ratio over time (line chart)
  - Category distribution trends (stacked area chart)
  - Budget adherence rate (% of budgets stayed within limit)
  - Debt-to-asset ratio over time
  - Goal completion rate
- All data returned as JSON-compatible for Chart.js rendering

**Files:** `app/routes_advanced.py`, `app/templates/metrics.html`

---

### Enhancement #7: Complete Newsletter System
**Current State:** `routes_newsletter.py` (53 lines) generates a basic report but has no email delivery, scheduling, or download.
**Enhancement:**
- Add **PDF generation** of the monthly financial report using ReportLab
- Add **download as PDF** endpoint (`/newsletter/download`)
- Add **email delivery** — send the report to the user's email via Flask-Mail
- Add **newsletter preferences** — choose frequency (weekly/monthly) and sections to include
- Improve report content: add charts summary, goal progress, debt status, and spending trends

**Files:** `app/routes_newsletter.py`, `app/templates/newsletter.html`, `app/templates/newsletter_report.html`

---

### Enhancement #8: Expand Security Events Route
**Current State:** `routes_security.py` (41 lines) shows events/audit logs and a security score. Missing active session management, login history details, and security recommendations.
**Enhancement:**
- Add **active sessions list** — show login sessions with IP, user-agent, last activity
- Add **login history** with geolocation context (IP-based city/country from request headers)
- Add **security recommendations** — dynamic checklist (enable 2FA, verify email, change password regularly, review API keys)
- Add **export security logs** as CSV
- Add **suspicious activity alerts** — flag logins from new IPs or devices

**Files:** `app/routes_security.py`, `app/templates/security.html`

---

### Enhancement #9: Expand Settings Route
**Current State:** `routes_settings.py` (46 lines) handles profile update and password change only.
**Enhancement:**
- Add **notification preferences** — toggle email/push notifications per event type (budget alerts, goal reminders, login alerts)
- Add **data export** — download all user data as JSON or CSV (GDPR-style)
- Add **account deletion** — with confirmation and data purge
- Add **currency preferences** — set default currency with live conversion display
- Add **connected accounts** — show/disconnect OAuth providers

**Files:** `app/routes_settings.py`, `app/templates/settings.html`

---

### Enhancement #10: Expand Banking Template & Features
**Current State:** `routes_banking.py` (117 lines) has reconciliation and CSV import. The template is minimal.
**Enhancement:**
- Add **Excel import** support (`.xlsx` via openpyxl) alongside existing CSV
- Add **smart categorization** during import — match descriptions to existing categories using keyword matching
- Add **reconciliation history chart** — show balance discrepancy trends over time
- Add **duplicate transaction detection** — flag imported transactions that match existing ones (same amount, date, description)
- Improve the template with proper tables, filters, and reconciliation status badges

**Files:** `app/routes_banking.py`, `app/templates/banking.html`

---

## Phase 3 — Incomplete Implementations

### Enhancement #11: Build Automation Rule Execution Engine
**Current State:** `routes_automation.py` (83 lines) stores rules in DB but never executes them. No trigger-to-action pipeline exists.
**Enhancement:**
- Create `app/automation_engine.py` with:
  - `execute_rules(trigger_type, context)` — query active rules matching trigger, evaluate conditions, run actions
  - Condition evaluator: parse simple conditions like `amount > 500`, `category == 'Food'`
  - Action handlers:
    - `send_notification` — create in-app Notification + optional push via `send_push_to_user()`
    - `add_tags` — append tags to the triggering transaction
    - `auto_categorize` — reassign category based on rule params
    - `call_webhook` — POST to the configured WebhookEndpoint with event payload
- Hook `execute_rules()` into transaction creation/edit in `routes.py`
- Add execution log to track which rules fired and their results

**Files:** `app/automation_engine.py` (new), `app/routes.py`, `app/routes_automation.py`, `app/models.py` (add `AutomationLog` model)

---

### Enhancement #12: Complete Push Notification Integration
**Current State:** `routes_push.py` (98 lines) has subscribe/unsubscribe and `send_push_to_user()` utility. But nothing triggers push notifications.
**Enhancement:**
- Hook push notifications into key events:
  - Budget exceeded (>90% and >100%)
  - Goal milestone reached
  - Recurring transaction processed
  - Large unusual transaction detected
  - Creditor payment due date approaching (3 days before)
- Add `/push/test` endpoint for users to send a test notification to themselves
- Add push notification preferences (which events to receive)

**Files:** `app/routes_push.py`, `app/routes.py`, `app/routes_goals.py`, `app/routes_cashflow.py`

---

### Enhancement #13: Implement Shared Wallet Logic
**Current State:** `Wallet` model has `is_shared` field but no sharing mechanism.
**Enhancement:**
- Add `WalletShare` model: `wallet_id`, `shared_with_user_id`, `permission` (view/contribute/manage), `accepted`
- Add routes:
  - `POST /wallets/<id>/share` — invite user by email
  - `POST /wallets/invites/<id>/accept` — accept share invite
  - `POST /wallets/invites/<id>/decline` — decline
  - `GET /wallets/shared` — list wallets shared with current user
- Shared wallet transactions visible to all members
- Activity feed for shared wallets

**Files:** `app/models.py`, `app/routes.py` (wallet section), `app/templates/wallets.html`

---

### Enhancement #14: Implement ExchangeRate Usage
**Current State:** `ExchangeRate` model exists in models.py, `utils.py` has `get_exchange_rate()`, but conversion is hardcoded or unused.
**Enhancement:**
- Update `get_exchange_rate()` to query the `ExchangeRate` table first, fall back to a free API
- Add `/settings/exchange-rates` management page — manually set or auto-fetch rates
- Display converted amounts on dashboard/reports when user has multi-currency wallets
- Add currency conversion in transaction views (show equivalent in default currency)

**Files:** `app/utils.py`, `app/routes_settings.py`, `app/routes.py`, `app/templates/settings.html`

---

### Enhancement #15: Flesh Out Fixed Assets, Construction, Global Finance Templates
**Current State:** Routes are complete with full CRUD. Templates are minimal stubs (~1-2KB each).
**Enhancement for each:**

**Fixed Assets (`fixed_assets.html`):**
- Summary cards: total purchase value, current value, total depreciation
- Asset table with sort/filter by category, condition
- Depreciation schedule chart (line chart showing value over time)
- Add edit modal for inline editing

**Construction Works (`construction.html`):**
- Project cards with progress bars (spent/budget %)
- Status badges (planning, in_progress, completed, on_hold)
- Timeline view of project milestones
- Budget vs. actual spending comparison chart

**Global Finance (`global_finance.html`):**
- Entity cards grouped by type (Business, Partnership, Shareholding)
- Ownership pie chart
- Total portfolio value summary
- Edit/delete modals

**Files:** `app/templates/fixed_assets.html`, `app/templates/construction.html`, `app/templates/global_finance.html`, `app/templates/smc.html`

---

## Phase 4 — API Layer Expansion

### Enhancement #16: Add Auth Endpoints to REST API
**Current State:** API uses `X-API-Key` header auth only. No endpoints to authenticate or manage sessions programmatically.
**Enhancement:**
- `POST /api/v1/auth/login` — email+password login, returns JWT token
- `POST /api/v1/auth/register` — create account via API
- `POST /api/v1/auth/refresh` — refresh JWT token
- `GET /api/v1/auth/me` — get current user profile
- Support both API key and JWT Bearer token authentication
- Add JWT utility functions using `PyJWT` (already available via Authlib)

**Files:** `app/api/__init__.py`, `app/api/auth.py` (new)

---

### Enhancement #17: Add Missing API Endpoints
**Current State:** API has: transactions, wallets, categories, budgets, goals, summary. Missing many entities.
**Enhancement — Add CRUD API endpoints for:**
- `app/api/creditors.py` — `/api/v1/creditors` (list, create, get, update, delete) + `/api/v1/creditors/<id>/payments`
- `app/api/debtors.py` — `/api/v1/debtors` (same pattern) + `/api/v1/debtors/<id>/payments`
- `app/api/commitments.py` — `/api/v1/commitments` (CRUD)
- `app/api/investments.py` — `/api/v1/investments` (CRUD) + dividends sub-resource
- `app/api/insurance.py` — `/api/v1/insurance-policies` (CRUD)
- `app/api/pensions.py` — `/api/v1/pension-schemes` (CRUD)
- `app/api/fixed_assets.py` — `/api/v1/fixed-assets` (CRUD)

All endpoints follow existing patterns: API key auth, pagination via `paginate_query()`, JSON responses.

**Files:** `app/api/` (7 new files), `app/api/__init__.py` (register new modules)

---

### Enhancement #18: Add Rate Limiting & Bulk Operations
**Current State:** No rate limiting. No bulk create/update/delete.
**Enhancement:**
- **Rate limiting:** Add in-memory rate limiter (token bucket) as middleware on `/api/v1/*`
  - Default: 100 requests/minute per API key
  - Return `429 Too Many Requests` with `Retry-After` header
  - Track in `g.api_key_id` context
- **Bulk operations:**
  - `POST /api/v1/transactions/bulk` — create up to 100 transactions in one call
  - `DELETE /api/v1/transactions/bulk` — delete multiple by IDs
  - `POST /api/v1/categories/bulk` — bulk create categories
- Add `X-RateLimit-Remaining` and `X-RateLimit-Limit` response headers

**Files:** `app/api/__init__.py`, `app/api/transactions.py`, `app/api/categories.py`

---

## Phase 5 — Code Quality & Configuration

### Enhancement #19: Split Main `routes.py` (2,674 lines)
**Current State:** Single monolithic `routes.py` handles: dashboard, expenses, wallets, budgets, recurring transactions, projects, wishlist, creditors, debtors, categories, CSV export, analytics, and more.
**Enhancement — Extract into focused blueprints:**
- `routes_expenses.py` — add/edit/delete expenses, receipt uploads
- `routes_wallets.py` — wallet CRUD, transfers
- `routes_budgets.py` — budget CRUD (distinct from budget_planning)
- `routes_recurring.py` — recurring transaction management
- `routes_projects.py` — project/project-item management
- `routes_wishlist.py` — wishlist CRUD
- `routes_analytics.py` — charts, reports, CSV export
- `routes.py` — keep only dashboard route

All extracted blueprints registered as `main` blueprint sub-routes (use same URL prefix) to avoid breaking existing URLs.

**Files:** `app/routes.py` (reduce to ~200 lines), 7 new route files, `app/__init__.py`

---

### Enhancement #20: Environment-Based Configuration
**Current State:** `__init__.py` line 15 has hardcoded DB URI: `'mysql+pymysql://root:root@localhost/fintrackdb'`
**Enhancement:**
- Create `app/config.py` with environment classes:
  ```
  class Config (base — from env vars)
  class DevelopmentConfig(Config)
  class ProductionConfig(Config)
  class TestingConfig(Config) — uses SQLite in-memory
  ```
- Load config based on `FLASK_ENV` environment variable
- Move all hardcoded values to `.env` file (with `.env.example` template)
- Add `python-dotenv` for `.env` loading
- Update `__init__.py` to use `app.config.from_object()`

**Files:** `app/config.py` (new), `app/__init__.py`, `.env.example` (new)

---

### Enhancement #21: Add Unit & Integration Tests
**Current State:** Only `test_broken_routes.py` and `test_parity_routes.py` exist — basic route smoke tests.
**Enhancement:**
- Create `tests/` directory structure:
  ```
  tests/
    conftest.py          — Flask test client, test DB setup (SQLite in-memory)
    test_models.py       — Model creation, relationships, constraints
    test_auth.py         — Login, register, password reset, 2FA
    test_dashboard.py    — Dashboard loads, correct totals
    test_expenses.py     — CRUD operations, validation
    test_wallets.py      — CRUD, transfers, balance updates
    test_budgets.py      — Budget creation, spending tracking
    test_api.py          — API key auth, CRUD via REST endpoints
    test_calculator.py   — Calculator output validation
    test_automation.py   — Rule execution engine
  ```
- Use `pytest` + `pytest-flask`
- Test DB uses SQLite in-memory (from TestingConfig in #20)
- Minimum 80% coverage on critical paths

**Files:** `tests/` directory (10 new files), `Pipfile` (add pytest, pytest-flask)

---

### Enhancement #22: Clean Up Root Fix/Audit Scripts
**Current State:** Root directory contains one-off maintenance scripts:
- `fix_liabilities.py`, `fix_routes.py`, `fix_db.py`
- `audit_liabilities.py`, `audit_v2.py`

These suggest recurring data integrity issues.
**Enhancement:**
- Review each script to identify what data issues they fix
- Create `app/management/` directory with proper CLI commands:
  - `flask db-audit` — check for orphaned records, missing FKs, balance inconsistencies
  - `flask db-fix` — apply safe auto-fixes with confirmation prompts
  - `flask db-report` — generate integrity report
- Register as Flask CLI commands via `app.cli.add_command()`
- Delete the root-level `fix_*.py` and `audit_*.py` scripts after migrating their logic
- Add proper logging for all data fixes

**Files:** `app/management/` (new directory), `app/__init__.py`, delete 5 root scripts

---

## Implementation Order

| Priority | Enhancements | Rationale |
|----------|-------------|-----------|
| **P0 — Do First** | #1, #2 | Critical bugs causing errors |
| **P1 — Foundation** | #20, #19 | Config & code structure needed before other work |
| **P2 — Core Features** | #3, #4, #5, #6, #7, #11 | Complete the most user-visible stub features |
| **P3 — Integrations** | #8, #9, #10, #12, #13, #14 | Fill out incomplete implementations |
| **P4 — API** | #16, #17, #18 | Expand API layer |
| **P5 — Quality** | #15, #21, #22 | Templates, tests, cleanup |

---

## Estimated File Impact

| Category | New Files | Modified Files |
|----------|-----------|----------------|
| Route files | 8 | 12 |
| Template files | 5 | 10 |
| API files | 8 | 2 |
| Config/Test files | 13 | 2 |
| Model changes | 0 | 1 |
| Utility files | 2 | 1 |
| **Total** | **36** | **28** |

---

## Notes

- All new routes require `@login_required` decorator
- All DB queries must filter by `current_user.id` for data isolation
- New API endpoints follow existing pattern: API key auth via `require_api_key()`, pagination via `paginate_query()`
- Templates follow existing glassmorphic CSS design system
- No external service dependencies added (all calculations server-side)
- Database migrations via `flask db migrate` after model changes
