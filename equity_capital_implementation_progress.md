# Equity Capital Implementation Progress (v2)

> Companion tracker for [Equity Capital Implementation Guide (v2)](equity_capital_implementation_guide%202.md).
>
> **Status:** Not started
> **Last updated:** 2026-10-04

## Scope

Implement category-level equity capital with project-level capital allocations while preserving these accounting rules:

```text
Total Equity = Contributed Capital + Retained Earnings

Contributed Capital = Initial Capital + Owner Injections
                    + Partner Contributions - Owner Drawings

Reinvestments and project allocations are internal earmarks.
They do not increase total equity or move wallet cash.
```

## Implementation Checklist

### 1. Data models and migration

- [x] Add `EquityCapital` model.
- [x] Add `EquityTransaction` model for external capital movements only.
- [x] Add `CapitalAllocation` model for project funding and reinvestment earmarks.
- [x] Add `Project` capital-allocation properties.
- [x] Add source-specific available-capital properties to `EquityCapital`.
- [x] Generate migration.
- [x] Review generated migration before applying it.
- [x] Apply migration in a development database.

**Done when:** one equity-capital record can exist per category, transactions and allocations are correctly related, and the migration succeeds on a copy of existing data.

### 2. Accounting calculations

- [x] Calculate contributed capital: initial + injections + partner contributions − drawings.
- [x] Calculate retained earnings from `ProjectCategory.current_profit`.
- [x] Calculate total equity without adding reinvestments a second time.
- [x] Calculate available contributed capital after capital-sourced allocations.
- [x] Calculate available retained earnings after retained-sourced allocations.
- [x] Calculate combined unallocated capital.
- [x] Calculate project-level allocated capital and utilisation.

**Done when:** a reinvestment changes allocation availability but leaves total equity unchanged.

### 3. Equity routes and validation

- [x] Create the `equity` blueprint and overview route.
- [x] Add initial-capital setup route.
- [x] Add external capital transaction route.
- [x] Add external transaction deletion route with wallet reversal.
- [x] Add capital-allocation route.
- [x] Add capital-allocation deletion route.
- [x] Validate transaction and allocation types.
- [x] Require a positive amount.
- [x] Require an owned wallet for external transactions.
- [x] Reject drawings larger than the selected wallet balance.
- [x] Require a project for `project_funding` allocations.
- [x] Reject allocations to a project outside the equity pool's category.
- [x] Reject allocations that exceed the selected source's available balance.

**Done when:** invalid requests cannot create cross-category, over-allocated, or unlinked cash records.

### 4. Wallet and accounting integration

- [x] Increase wallet balance for injections and partner contributions.
- [x] Decrease wallet balance for drawings.
- [x] Reverse wallet movement when an external transaction is deleted.
- [x] Keep wallet changes and equity records in one database transaction.
- [x] Confirm allocations and reinvestment earmarks do not change wallet balances.
- [x] Decide whether to enable automatic journal entries.
- [x] If enabled, create journal entries only for external transactions.

**Done when:** cash, equity records, and optional journal entries stay in sync after create and delete operations.

### 5. User interface

- [x] Create the Equity Capital overview page.
- [x] Add aggregate cards for contributed capital, retained earnings, total equity, allocated, and unallocated capital.
- [x] Add category-level equity breakdown cards.
- [x] Add initial-capital setup/edit modal.
- [x] Add external-capital transaction modal.
- [x] Add project-allocation modal filtered to the selected category's projects.
- [x] Add transaction history with deletion action.
- [x] Add allocation history with deletion action.
- [x] Add equity navigation link.
- [x] Add capital funding summary to project details.

**Done when:** users can understand each category's equity, source of capital, allocations, and remaining availability without inspecting the database.

### 6. Tests and verification

- [x] Test one equity pool per category.
- [x] Test contributed-capital calculations.
- [x] Test retained-earnings calculations.
- [x] Test that reinvestments do not double-count equity.
- [x] Test each external transaction type and its wallet impact.
- [x] Test deleting an external transaction reverses its wallet impact.
- [x] Test an allocation cannot exceed available contributed capital.
- [x] Test an allocation cannot exceed available retained earnings.
- [x] Test a project allocation must use the same category as its equity pool.
- [x] Test project capital utilisation.
- [x] Test templates load and routes enforce user ownership.
- [x] Run the full relevant test suite.

## Suggested Acceptance Scenario

Use this scenario after implementation:

| Event | Amount | Expected result |
|---|---:|---|
| Initial capital | GHS 10,000 | Contributed capital = GHS 10,000 |
| Owner injection | GHS 2,000 | Contributed capital = GHS 12,000; wallet increases |
| Category retained earnings | GHS 3,000 | Total equity = GHS 15,000 |
| Allocate contributed capital to Project 62 | GHS 4,000 | Total equity unchanged; contributed availability = GHS 8,000 |
| Earmark retained earnings | GHS 1,000 | Total equity unchanged; retained availability = GHS 2,000 |
| Owner drawing | GHS 500 | Contributed capital = GHS 11,500; wallet decreases |

## Progress Log

| Date | Area | Status | Notes |
|---|---|---|---|
| 2026-10-04 | Planning | Complete | Version 2 guide reviewed and safeguards added. |
| 2026-10-04 | Database migration | Complete | Fresh local development schema rebuilt and verified. A production-like data rehearsal remains required before deployment. |
| 2026-10-04 | User Interface | Complete | Polished `/equity/` overview page with executive hero dashboard, glassmorphic metric cards, progress indicators, educational guide, and modern modal dialogs. |
| 2026-10-04 | Automated Testing | Complete | 11/11 equity tests and project regression tests passing. |

## Implementation Notes

- Use the version 2 guide as the source of truth for accounting behavior.
- Initial capital may be historical and therefore may not have a wallet movement.
- Do not represent initial capital, injections, partner contributions, drawings, or reinvestments as project income.
- Gross and net project profit remain operational metrics; equity capital is a funding and ownership metric.

---

## Complete v2 Feature Traceability Checklist

This section is the implementation source-of-truth checklist. Every item in the Equity Capital Implementation Guide (v2) must be completed, verified, or explicitly marked as deferred.

### A. EquityCapital model — Complete

- [x] Create the `EquityCapital` table and SQLAlchemy model.
- [x] Add primary key `id`.
- [x] Add required `user_id` foreign key.
- [x] Add required `category_id` foreign key.
- [x] Enforce one equity pool per category with a unique `category_id` constraint.
- [x] Add `initial_capital`, defaulting to zero.
- [x] Add optional `initial_capital_date`.
- [x] Add optional `business_name` alias.
- [x] Add optional `notes`.
- [x] Add `created_at` and automatically updated `updated_at` timestamps.
- [x] Add the one-to-one `ProjectCategory` relationship.
- [x] Add transaction relationship with descending transaction-date ordering and cascade deletion.
- [x] Add allocation relationship with descending allocation-date ordering and cascade deletion.
- [x] Add user relationship with cascade deletion.
- [x] Implement `total_additional_injections`.
- [x] Implement `total_partner_contributions`.
- [x] Implement `total_drawings`.
- [x] Implement `contributed_capital`.
- [x] Implement live `retained_earnings` from `ProjectCategory.current_profit`.
- [x] Implement `total_allocated_to_projects`.
- [x] Implement `total_reinvestment_earmarks`.
- [x] Implement `total_allocated`.
- [x] Implement `allocated_from_contributions`.
- [x] Implement `allocated_from_retained_earnings`.
- [x] Implement `available_contributed_capital`.
- [x] Implement `available_retained_earnings`.
- [x] Implement `unallocated_capital`.
- [x] Implement `total_equity` as contributed capital plus retained earnings only.
- [x] Confirm reinvestments never increase `total_equity`.

### B. EquityTransaction model — Complete

- [x] Create the `EquityTransaction` table and model.
- [x] Add primary key, user foreign key, and required equity-capital foreign key.
- [x] Restrict supported transaction types to `injection`, `partner_contribution`, and `drawing`.
- [x] Do not include `reinvestment` as an equity transaction type.
- [x] Add positive `amount` and transaction `date` fields.
- [x] Add optional `description`, `partner_name`, and `notes` fields.
- [x] Add wallet foreign key (required by the wallet-posting safeguard).
- [x] Add optional `journal_entry_id` foreign key.
- [x] Add wallet, journal-entry, and user relationships.
- [x] Implement `is_inflow` for injections and partner contributions only.

### C. CapitalAllocation model — Complete

- [x] Create the `CapitalAllocation` table and model.
- [x] Add primary key, user foreign key, and required equity-capital foreign key.
- [x] Restrict allocation types to `project_funding` and `reinvestment`.
- [x] Add positive `amount`, `date`, `description`, `notes`, and creation timestamp fields.
- [x] Add optional `project_id` foreign key.
- [x] Require `project_id` for `project_funding` at route-validation level.
- [x] Allow a project-less `reinvestment` as a general earmark.
- [x] Add `funding_source` and restrict it to `capital` or `retained`.
- [x] Add project and user relationships.
- [x] Confirm allocations are internal memo records, not revenue, expenses, or equity additions.

### D. Project capital metrics — Complete

- [x] Add `Project.total_capital_allocated`.
- [x] Add `Project.capital_from_contributions`.
- [x] Add `Project.capital_from_retained`.
- [x] Add `Project.capital_utilization` based on paid expenses and allocated capital.
- [x] Return zero utilisation rather than divide by zero when no capital is allocated.
- [x] Confirm existing gross-profit and net-profit calculations remain separate from capital funding.

### E. Database migration and data compatibility

- [x] Generate a migration for all three new tables.
- [x] Confirm all foreign keys point to the correct table names.
- [x] Confirm the category uniqueness constraint is created.
- [x] Review migration downgrade behavior.
- [x] Build and verify a fresh local development schema from the current models.
- [ ] Apply the migration to a copy of production-like data before deployment.
- [x] Confirm the current models can read projects, categories, wallets, and equity tables on the fresh schema.
- [x] Document deployment backup and rollback steps below.

#### Deployment backup and rollback

1. Back up the target database before upgrading, for example: `mysqldump -u <user> -p <database> > pre_equity_backup.sql`.
2. Run `flask db upgrade` only after rehearsing the full migration chain against a copy of production-like data.
3. Verify the three equity tables, their foreign keys, and the one-pool-per-category uniqueness constraint after deployment.
4. If deployment must be reverted, restore the pre-upgrade backup. The migration downgrade drops all three new equity tables and therefore intentionally discards their data.
5. The local `db.metadata.create_all()` bootstrap used for this empty development database is **not** a migration strategy for an existing database and must not be used in production.

### F. Equity overview route

- [x] Create and register the `equity` blueprint at `/equity`.
- [x] Require authentication for all equity routes.
- [x] Load or seed the current user's project categories.
- [x] Ensure every category has exactly one `EquityCapital` record when the overview opens.
- [x] Commit newly created equity records safely.
- [x] Load only current-user wallets.
- [x] Load only current-user projects for allocation controls.
- [x] Calculate totals for initial capital, injections, partner contributions, drawings, contributed capital, retained earnings, total equity, allocated capital, and unallocated capital.
- [x] Pass transaction and allocation type choices to the template.

### G. Initial-capital setup route

- [x] Authorize the category against the current user.
- [x] Find or create the category's equity record.
- [x] Save initial capital amount.
- [x] Parse and save an optional initial-capital date.
- [x] Save optional business name and notes.
- [x] Roll back and show a useful error if saving fails.
- [x] Treat historical initial capital as an opening balance without mandatory wallet movement.

### H. External transaction routes

- [x] Validate external transaction type.
- [x] Validate an amount greater than zero.
- [x] Parse a supplied date or default to the current date.
- [x] Accept description, partner name, and notes.
- [x] Require a wallet owned by the current user.
- [x] Reject a missing or foreign wallet.
- [x] Reject a drawing that exceeds the selected wallet balance.
- [x] Persist the wallet link on the transaction.
- [x] Increase wallet balance for injection and partner contribution.
- [x] Decrease wallet balance for drawing.
- [x] Save wallet and equity transaction atomically.
- [x] Delete only an equity transaction owned by the current user.
- [x] Reverse the original wallet movement before deleting a transaction.
- [x] Roll back both wallet and equity changes if any operation fails.

### I. Allocation routes and safeguards

- [x] Validate allocation type.
- [x] Validate an amount greater than zero.
- [x] Parse a supplied date or default to the current date.
- [x] Validate `funding_source` as `capital` or `retained`.
- [x] Require a project for `project_funding`.
- [x] Confirm the selected project belongs to the current user.
- [x] Confirm the selected project belongs to the same category as the equity pool.
- [x] Reject a cross-category project allocation.
- [x] Reject an allocation that exceeds available contributed capital when source is `capital`.
- [x] Reject an allocation that exceeds available retained earnings when source is `retained`.
- [x] Preserve optional general reinvestment earmarks without a project.
- [x] Do not change a wallet balance for an allocation.
- [x] Do not create a journal entry for an allocation.
- [x] Delete only an allocation owned by the current user.
- [x] Confirm deleting an allocation restores only its available allocation balance, not wallet cash or total equity.

### J. Equity Capital page

- [x] Create `equity_capital.html` using the existing application visual style.
- [x] Add page header, title, description, and Equity Capital navigation context.
- [x] Show aggregate Initial Capital card.
- [x] Show aggregate Additional Injections card.
- [x] Show aggregate Partner Contributions card.
- [x] Show aggregate Owner Drawings card.
- [x] Show aggregate Contributed Capital card.
- [x] Show aggregate Retained Earnings card.
- [x] Show highlighted Total Equity card.
- [x] Show aggregate Allocated and Unallocated capital values.
- [x] Render one equity card for each category.
- [x] Show category name or business-name alias.
- [x] Show category total equity with positive/negative visual treatment.
- [x] Show each category's initial capital, injections, partner contributions, drawings, contributed capital, and retained earnings.
- [x] Show allocation progress bar capped at 100% visually.
- [x] Show allocated and available amounts beside the allocation bar.
- [x] Show capital-allocation history including amount, target project/general reinvestment, source, date, and deletion action.
- [x] Show external-capital movement history including signed amount, description/type, partner name when applicable, date, and deletion action.
- [x] Show empty states when a category has no transactions or allocations.

### K. Equity page forms and interactions

- [x] Add initial-capital setup/edit modal.
- [x] Include initial capital, date, business name, and notes fields in that modal.
- [x] Add external-capital transaction modal.
- [x] Include type, amount, date, description, partner name, wallet, and notes fields.
- [x] Show partner-name input only for a partner contribution.
- [x] Add allocation modal.
- [x] Include type, amount, date, project, funding source, description, and notes fields.
- [x] Filter project choices to the active equity category.
- [x] Make the project control required only for project funding.
- [x] Refresh Lucide icons after dynamic modal content is displayed, if needed by the page implementation.

### L. Navigation and project detail display

- [x] Register the equity blueprint in `app/__init__.py`.
- [x] Add the Equity Capital navigation link in `base.html`.
- [x] Use an appropriate landmark/equity icon and active-state treatment.
- [x] Add optional Capital Funding section to `project_details.html`.
- [x] Show total capital allocated to the project.
- [x] Show amount from contributed capital.
- [x] Show amount from retained earnings.
- [x] Show capital-utilisation percentage and capped progress bar.
- [x] Hide the project capital section cleanly when no allocations exist.

### M. Optional double-entry accounting integration

- [x] Decide whether automatic journal entries are enabled for this release.
- [x] Find or create suitable Cash/Asset and Equity accounts safely.
- [x] For an inflow, debit Cash and credit Equity.
- [x] For a drawing, debit Equity and credit Cash.
- [x] Update account balances consistently with the journal entry.
- [x] Link the journal entry to the equity transaction.
- [x] Create journal entry, wallet update, and equity transaction in one database transaction.
- [x] Define journal-entry reversal when an external equity transaction is deleted.
- [x] Confirm allocations never create journal entries.

### N. End-to-end verification

- [x] Create a category equity pool with GHS 10,000 historical initial capital.
- [x] Add a GHS 2,000 owner injection and verify wallet increase.
- [x] Add a GHS 3,000 category retained-profit position and verify total equity is GHS 15,000.
- [x] Allocate GHS 4,000 from contributed capital to a same-category project.
- [x] Verify total equity remains GHS 15,000 after that allocation.
- [x] Earmark GHS 1,000 of retained earnings for reinvestment.
- [x] Verify total equity remains GHS 15,000 after the earmark.
- [x] Verify contributed and retained availability reduce independently.
- [x] Attempt an over-allocation from each source and verify rejection.
- [x] Attempt a cross-category allocation and verify rejection.
- [x] Record a GHS 500 drawing and verify wallet and contributed capital decrease.
- [x] Delete that drawing and verify the wallet and equity values reverse.
- [x] Verify all pages, templates, migrations, and relevant automated tests pass.

#### Completed local run — 2026-10-04

The isolated `E2E Equity Verification 20261004165818-b5951a` scenario was run through the authenticated local routes. It confirmed GHS 15,000 total equity after the GHS 10,000 opening capital, GHS 2,000 injection, and GHS 3,000 retained profit; verified independent GHS 8,000 contributed and GHS 2,000 retained availability after allocations; rejected both over-allocations and a cross-category allocation; and reversed the GHS 500 drawing back to GHS 2,000 wallet cash and GHS 15,000 total equity. Both affected pages returned HTTP 200, the database reported Alembic head `b8e4f1c2d3a6`, and the relevant test suite passed 13 tests.
