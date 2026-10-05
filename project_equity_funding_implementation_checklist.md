# Project Transaction Equity Funding Checklist

Use this checklist to implement equity-funding choices while adding a project transaction at `/add`.

## Goal

Let a user record a project expense and explicitly identify whether it was funded by regular wallet cash, existing contributed capital, retained earnings, a new owner injection, a partner contribution, or opening capital. The implementation must link the project cost to equity funding without counting the same money twice.

## 1. Design and accounting rules

- [x] Keep a project expense separate from the source of its funding.
- [x] Treat existing contributed capital and retained earnings as allocations, not additional income.
- [x] Treat a new owner or partner contribution as an equity movement and wallet inflow before the expense is recorded.
- [x] Treat opening capital as the initial contributed balance and create a linked allocation without a duplicate wallet movement.
- [x] Preserve normal wallet-funded project expenses as the default behaviour.
- [x] Prevent an allocation from exceeding the available balance of its selected source.

## 2. Data model and migration

- [x] Add an optional link from `CapitalAllocation` to the originating expense/transaction record.
- [x] Add a migration for the new link and foreign key.
- [x] Keep historical allocations and expenses readable when no link exists.
- [x] Confirm one category equity pool remains the source for a same-category project.

## 3. Add Transaction user interface

- [x] Show Equity Funding only when the transaction is a project expense.
- [x] Add funding-source choices: regular wallet, contributed capital, retained earnings, new owner injection, partner contribution, and opening capital.
- [x] Show an equity category/pool selector derived from the selected project category.
- [x] Explain the accounting effect of the selected source.
- [x] Show available contributed and retained balances where applicable.
- [x] Require partner details for partner contributions.
- [x] Keep the controls hidden and inactive for non-project or income transactions.

## 4. Transaction creation rules

- [x] Preserve the existing expense and wallet logic for regular wallet funding.
- [x] Create a `CapitalAllocation` for contributed-capital funding.
- [x] Create a `CapitalAllocation` for retained-earnings funding.
- [x] Create an equity transaction and related journal entry for a new owner injection.
- [x] Create an equity transaction and related journal entry for a partner contribution.
- [x] Create or update opening capital only when the user explicitly selects opening capital.
- [x] Link every new allocation to the expense that triggered it.
- [x] Commit the expense, wallet change, and allocation atomically.
- [x] Roll back all related changes if validation or persistence fails.

## 5. Historical reconciliation

- [x] Add a reconciliation action for an existing project expense.
- [x] Allow linking it to existing contributed capital or retained earnings.
- [x] Allow setting it as opening capital only when appropriate.
- [x] Do not modify the original expense amount, payment history, or wallet transaction during allocation-only reconciliation.
- [x] Prevent duplicate reconciliations for the same expense.

## 6. Display and traceability

- [x] Show the funding source and linked expense in project capital-allocation history.
- [x] Show the linked project expense from the Equity Capital page.
- [x] Show funding details on the project expense where available.
- [x] Keep Total Equity unchanged when capital is allocated to a project.

## 7. Tests and verification

- [x] Test regular wallet-funded project expense behaviour remains unchanged.
- [x] Test contributed-capital and retained-earnings allocations with limits.
- [x] Test owner and partner contribution flows with wallet and journal updates.
- [x] Test opening-capital flow does not duplicate wallet cash.
- [x] Test cross-category and over-allocation rejection.
- [x] Test rollback behavior when a related write fails.
- [x] Test historical reconciliation and duplicate-prevention rules.
- [x] Run all relevant project, equity, transaction, and migration tests.

## Section 4 completion

New owner and partner capital now create an external `EquityTransaction`, post its matching journal entry, and are then linked to the project expense through a capital allocation. The wallet is increased by the incoming capital and reduced by the expense in the same database transaction. A persistence error rolls back all of those changes.

## Section 5 completion

The Equity Capital page now lists unreconciled expenses that are already linked to a project. Reconciliation creates one allocation for the full historical expense amount; it does not change the expense, wallet, or payment records. When cash is already present in transaction history, the Historical Contribution option records the equity source without moving the wallet again. A standalone Historical Owner Injection action also records and optionally allocates a later owner contribution without duplicating cash. Opening capital is allowed only for the category's first contributed-capital reconciliation, and the one-to-one expense link prevents duplicates.

## Section 6 completion

Allocation records now display their funding source and a link to the underlying expense. The Equity page, transaction history, and project detail page each expose that link. Allocations reduce only available capital; they never change Total Equity.

## Section 7 completion

The active equity and project test suites cover every funding option, allocation limits, cross-category validation, rollback, historical reconciliation, and traceability. The relevant suites pass with 18 tests, and the database is confirmed at migration head `c9e5f7a1b2d3`.

## Current implementation note

The `/add` page now follows **Project → Business category → optional project**. Choosing the general Project category reveals the business-category selector (for example Coconut or Electric Lunch Box); the project selector then contains only projects in that selected business category. The available funding choices currently cover regular wallet funding, contributed capital, retained earnings, and opening capital. Owner injection, partner contribution, historical reconciliation, display traceability, and dedicated end-to-end tests remain pending.
