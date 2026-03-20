# ENHANCEMENT PLAN 2: Advanced Features & Technical Debt

This document outlines the second phase of enhancements for the Financial Tracker project, focusing on completing advanced module stubs, fixing technical bugs, and standardizing the user experience across new blueprints.

## 1. Bugs & Critical Fixes

### 1.1 Template Errors
- [ ] **Metrics Undefined Error**: Fix `UndefinedError: 'max' is undefined` in `metrics.html` line 111. Ensure common Python functions like `max` and `min` are available in the Jinja environment or handled via template filters.
- [ ] **SMC Placeholder**: Update `smc.html` to display the actual list of contracts and payment modals. Currently, it only shows a "No contracts" placeholder.

### 1.2 Data Synchronization
- [ ] **Notification Persistence**: Sync `session['notification_prefs']` with the `User.push_prefs` database field. Currently, settings modified in `routes_settings.py` do not persist across database sessions.
- [ ] **Asset Currency Matching**: Ensure `FixedAsset` totals in `fixed_assets.html` respect the default system currency or provide auto-conversion for assets held in different currencies.

## 2. Stub & Placeholder Completions

### 2.1 Advanced Logic
- [ ] **Actual ML Training**: Implement a proper simulation or integration for `run_ml_training` in `routes_advanced.py`. Replace simple flash messages with a background task (or simulated progress) that calculates actual spending trends or anomaly detection.
- [ ] **Automation Logs**: Move `session['automation_logs']` to a dedicated database table (e.g., `AutomationLog`) to provide a persistent audit trail for rules.

### 2.2 User Interface (Modals)
- [ ] **Fixed Assets Edit**: Implement the `edit_asset` modal in `fixed_assets.html` and link it to the existing POST route in `routes_fixed_assets.py`.
- [ ] **Construction & Global Finance Edit**: Add missing edit modals to `construction.html` and `global_finance.html` to match the backend routes in `routes_domain.py`.

## 3. Incomplete Implementations

### 3.1 Export Services
- [ ] **Dashboard Exports**: Implement full CSV, Excel, and PDF export functionality for the main Dashboard totals. Currently, buttons on the dashboard are UI-only.
- [ ] **Tax Summary Export**: Enhance the Tax Center PDF export to include a breakdown of bracket-wise calculations for better transparency.

### 3.2 Security & Audit
- [ ] **Advanced Audit Filters**: Add filtering capabilities (by date, user, or event type) to the Security Audit Log in `routes_security.py`.
- [ ] **Suspicious Activity Thresholds**: Allow users to configure "Suspicious Activity" thresholds (e.g., transaction amount limit) in their Security settings.

## 4. API Layer Expansion

### 4.1 Cross-Module Integration
- [ ] **Project-Asset Linkage**: Allow linking `ProjectItem` payments to `FixedAsset` acquisition costs for better capital expenditure tracking.
- [ ] **Goal-Automation Trigger**: Add a new automation trigger `goal_completed` to the `automation_engine.py` to allow notifications or webhooks when a savings goal is met.

## 5. Code Quality & Configuration

### 5.1 Route Standardization
- [ ] **Final Blueprint Migration**: Move remaining core routes (Categories, Historical Data, Currency Conversion) from `routes.py` into dedicated blueprints to eliminate the monolithic `main` blueprint.
- [ ] **Unified Modal JavaScript**: Extract repeated modal handling logic (open/close/reset) into a shared `static/js/modals.js` file.

### 5.2 Documentation & Config
- [ ] **Automation Condition Guide**: Add an in-app "Help" overlay for the Automation engine to explain available fields and syntax for conditions.
- [ ] **Environment Validation**: Enhance `config.py` to validate required environment variables (like `MAIL_SERVER` or `SECRET_KEY`) at startup.
