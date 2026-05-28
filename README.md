# Financial Tracker - Spendee Inspired Budget App

A comprehensive personal finance management application inspired by Spendee, built with Flask and SQLAlchemy. Track expenses, manage budgets, analyze spending patterns, and take control of your finances.

![Python Version](https://img.shields.io/badge/python-3.12.4-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.1.2-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ Features

### Core Transaction Features
- 💰 **Transaction Types**: Track Expenses, Income, and Transfers
- 🎨 **Visual Category Icons**: 11 pre-defined categories with emoji icons
- 📝 **Notes & Tags**: Add detailed notes and comma-separated labels
- 📎 **Receipt Upload**: Attach photos of receipts to transactions
- 📅 **Quick Date Selection**: "Today" and "Yesterday" buttons for fast entry

### Advanced Spendee Features
- 💼 **Multi-Wallet Management**: Cash, Bank, Mobile Money, Crypto, E-Wallet accounts
- 🔢 **Account Number Tracking**: Capture account numbers for Bank and Mobile Money wallets
- 🎯 **Budget Tracking**: Set spending limits per category with visual progress bars
- 🔄 **Recurring Transactions**: Automate bills with full Edit/Delete capabilities
- 📊 **Analytics & Charts**: Interactive pie and line charts with Chart.js
- ✏️ **Custom Categories**: Create personalized expense categories
- 🔍 **Advanced Search & Filters**: Filter by category, wallet, type, date range
- 📤 **CSV Export**: Download transaction data for external analysis
- 💱 **Multi-Currency Support**: Manage wallets in different currencies (GHS, USD, EUR, GBP)

## 🚀 Quick Start

### Prerequisites
- Python 3.12.4 or higher
- pip (Python package installer)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd TestingAntigravity
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment**
   - Windows:
     ```bash
     .venv\Scripts\activate
     ```
   - macOS/Linux:
     ```bash
     source .venv/bin/activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application**
   ```bash
   python run.py
   ```

6. **Access the app**
   Open your browser and navigate to: `http://127.0.0.1:5001`

## 📁 Project Structure

```
TestingAntigravity/
├── app/
│   ├── __init__.py           # App factory
│   ├── models.py             # Database models
│   ├── routes.py             # Application routes
│   ├── static/
│   │   ├── style.css         # Premium UI styles
│   │   └── receipts/         # Uploaded receipt images
│   └── templates/
│       ├── base.html         # Base template
│       ├── dashboard.html    # Main dashboard
│       ├── add_expense.html  # Add transaction form
│       ├── edit_expense.html # Edit transaction form
│       ├── all_expenses.html # All transactions with filters
│       ├── wallets.html      # Wallet management
│       ├── budgets.html      # Budget tracking
│       ├── recurring.html    # Recurring transactions
│       ├── analytics.html    # Charts and insights
│       ├── categories.html   # Category management
│       └── reports.html      # Financial reports
├── run.py                    # Application entry point
├── seed_data.py              # Sample data generator
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## 💡 Usage Guide

### Managing Wallets
1. Navigate to **Wallets** in the menu
2. Click **+ Add Wallet**
3. Enter wallet details (name, balance, currency, type)
4. Wallets automatically update balances with transactions

### Setting Budgets
1. Go to **Budgets**
2. Click **+ Add Budget**
3. Select category, amount, and period (weekly/monthly/yearly)
4. Monitor progress with visual indicators

### Adding Transactions
1. Click **Add Transaction**
2. Select transaction type (Expense/Income/Transfer)
3. Fill in amount, description, category, and wallet
4. Optionally add notes, tags, and receipt photo
5. Use quick date buttons or select custom date

### Creating Recurring Transactions
1. Navigate to **Recurring**
2. Click **+ Add Recurring**
3. Set up transaction details and frequency
4. System tracks next due date automatically

### Analyzing Spending
1. Visit **Analytics** for visual insights
2. View pie chart for category breakdown
3. Check line chart for monthly trends
4. Review detailed tables for exact amounts

### Exporting Data
1. Go to **All Transactions**
2. Apply filters if needed
3. Click **📥 Export CSV**
4. Open in Excel, Google Sheets, etc.

## 🗄️ Database Models

- **Wallet**: Multi-account management with currency support
- **Category**: Expense categories with custom icons
- **Expense**: Transactions with full details
- **Budget**: Category-specific spending limits
- **RecurringTransaction**: Automated scheduled transactions
- **ExchangeRate**: Currency conversion rates (ready for future use)

## 🎨 Design Features

- Modern, premium UI with Inter font
- Gradient cards and glassmorphic header
- Responsive layout
- Color-coded budget alerts
- Interactive charts with Chart.js
- Accessible design with high contrast

## 📊 Reports

Generate financial reports for:
- **Weekly**: Last 7 days
- **Monthly**: Current month
- **Quarterly**: Last 90 days
- **Yearly**: Current year

All reports show category-wise breakdowns with totals.

## 🔧 Technologies Used

- **Backend**: Flask 3.1.2, SQLAlchemy 2.0.44
- **Database**: SQLite
- **Frontend**: HTML5, CSS3, JavaScript
- **Charts**: Chart.js (via CDN)
- **Data Export**: Pandas 2.3.3
- **PDF Generation**: ReportLab 4.4.5 (ready)
- **Image Processing**: Pillow 12.0.0

## 📝 Sample Data

To populate the database with sample data for testing:

```bash
python seed_data.py
```

This creates sample transactions across different categories and dates.

## 🚧 Future Enhancements

- Real-time currency conversion API integration
- PDF export with embedded charts
- Mobile responsive improvements
- Bank account synchronization
- Shared wallet collaboration features
- Budget rollover functionality
- Savings goals tracking
- Bill payment reminders

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- Inspired by [Spendee](https://www.spendee.com/) budget tracking app
- Built with Flask and modern web technologies
- Icons from emoji sets

## 📧 Contact

For questions or feedback, please open an issue on GitHub.

---

**Made with ❤️ for better financial management**
