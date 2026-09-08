# Project Category & Category Profit Feature Checklist

This checklist tracks the requirements and verification tasks for introducing **Project Categories**, **Category-Level Operational Expenses & Item Names**, **Editable Operational Expenses**, and **Dedicated Category Profit Pages**.

---

## 1. Database & Models
- [x] Create `ProjectCategory` model (`id`, `user_id`, `name`, `description`, `created_at`)
- [x] Create `ProjectCategoryExpense` model for operational/additional expenses (`id`, `user_id`, `category_id`, `amount`, `expense_name`, `notes`, `date`, `wallet_id`, `created_at`)
- [x] Add `category_id` foreign key and relationship to `Project` model
- [x] Implement auto-seeding of default categories (`Coconut`, `Electric Lunch Box`, `Cloth`) for users who have no categories
- [x] Update backup import/export in `app/routes_backup.py` to include project categories and category expenses
- [x] Ensure database table creation/migration script safely creates new tables and adds `category_id` column to `project`

---

## 2. Project Creation & Edit Pages (`/projects/add` & `/projects/edit/<id>`)
- [x] Add **Project Category** dropdown in `add_project.html` with default options (`Coconut`, `Electric Lunch Box`, `Cloth`)
- [x] Add dynamic **"+ Add New Category"** modal / quick-add tool on `add_project.html` to create categories on the fly via AJAX and instantly select the new category
- [x] Add Project Category dropdown and quick-add modal to `edit_project.html`
- [x] Update `add_project` and `edit_project` backend routes in `app/routes_projects.py` to process and persist `category_id`
- [x] Create API route (`/projects/categories/create`) to handle AJAX category creation

---

## 3. Projects Overview & Profit Tracking (`/projects`)
- [x] Add **Category Profit & Performance Summary** section on `projects.html`:
  - [x] Display card / widget for each project category (e.g., Coconut, Electric Lunch Box, Cloth)
  - [x] Calculate & display **Current Profit** for each category: `(Paid Project Income) - (Paid Project Item Expenses + Category Operational Expenses)`
  - [x] Display category revenue, item costs, and additional operational costs breakdown
  - [x] Show count of active and total projects under each category
- [x] Add Category Badges on individual project cards so users can easily see each project's category
- [x] Add Category filter tabs to filter project cards by category (All, Coconut, Electric Lunch Box, Cloth, etc.)

---

## 4. Category Operational / Additional Expenses (Actual Item Names & Editing)
- [x] Add **"+ Add Category Expense"** button and modal on `/projects` page:
  - [x] Select Category (Coconut, Electric Lunch Box, Cloth, etc.)
  - [x] Expense Name / Item Title (e.g. Shipping logistics, Packaging boxes, Marketing)
  - [x] Amount
  - [x] Date
  - [x] Optional Source Wallet
- [x] **Display actual item names** for operational expenses in category cards & expense ledger
- [x] **Editable Operational Expenses**:
  - [x] Add Edit button & modal (`#editExpenseModal`) to update expense name, amount, date, wallet, and notes
  - [x] Backend route `/projects/categories/expenses/<id>/edit` to persist updates and recalculate profit in real time
- [x] Add **Category Expenses History / Management** ledger modal on `/projects` to view, edit, and delete operational expenses
- [x] Backend route `/projects/categories/expenses/<id>/delete`

---

## 5. Dedicated Category Projects & Profit Page (`/projects/category/<id>`)
- [x] Create route `@main.route('/projects/category/<int:category_id>')` (`category_projects`)
- [x] Create template `category_projects.html`:
  - [x] Display list of **Current Profits against each project name** under the category
  - [x] Display category total revenue, project item costs, operational expenses, and net category profit
  - [x] Display itemized operational expenses with instant Add, Edit, and Delete actions
- [x] Update "View Projects" button on category cards in `/projects` to navigate directly to `/projects/category/<id>`

---

## 6. Verification & Testing
- [x] Verify visiting `http://127.0.0.1:5001/projects/add` renders the category dropdown with `Coconut`, `Electric Lunch Box`, and `Cloth`
- [x] Verify adding a custom category dynamically updates the dropdown immediately without page refresh
- [x] Verify saving a project with a category associates it correctly
- [x] Verify visiting `http://127.0.0.1:5001/projects#category-breakdown` displays actual operational expense item names
- [x] Verify editing an operational expense updates its item name and amount and recalculates profit
- [x] Verify clicking "View Projects" opens `/projects/category/<id>` with the list of current profits per project name
