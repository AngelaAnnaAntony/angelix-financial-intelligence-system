# ANGELIX – Financial Intelligence System

Angelix is an AI-powered financial intelligence and analytics platform developed using Flask and PostgreSQL.

The system allows individuals and organizations to upload financial documents, extract financial information, review extracted data, manage transactions, generate financial statements, analyze financial performance, calculate financial health indicators, perform forecasting, obtain AI-assisted financial insights, and generate professional PDF reports.

---

## Key Features

### Authentication and Security
- User registration and login
- Logout
- Password reset workflow
- Session-based authentication
- JWT support
- CSRF protection
- Password hashing
- Role-based application controls
- Secure file handling
- Audit and system logging

### Financial Data Management
- Manual transaction creation
- Transaction listing and management
- Income, Expense, Asset, Liability and Equity classifications
- Organization-based data isolation
- Accounting ML classification

### Document Processing
Supported document formats include:

- PDF
- CSV
- XLSX
- XLS
- PNG
- JPG
- JPEG

The document-processing workflow supports:

- PDF text extraction
- OCR processing
- Image preprocessing
- Financial entity extraction
- Extraction candidate generation
- Human review and correction
- Statement classification
- Financial statement line-item storage

### Financial Statements
Angelix supports financial statement workflows including:

- Profit and Loss / Income Statement
- Balance Sheet
- Cash Flow Statement
- Trial Balance
- Other supported statement types

Statement line items are classified according to their statement context.

For example, a Profit and Loss statement uses:

- Income
- Expense
- Calculated

while a Balance Sheet uses:

- Asset
- Liability
- Equity

Calculated statement values are stored as statement line items and are not incorrectly converted into transactions.

### Financial Analytics
The analytics module provides:

- Revenue
- Expenses
- Net Profit
- Profit Margin
- Transaction statistics
- Category breakdowns
- Financial ratios
- Financial trends
- Balance Sheet analysis
- Accounting equation validation

### Financial Health Score

Angelix calculates a deterministic Financial Health Score using financial data available in the system.

The score includes components such as:

- Profitability
- Expense Control
- Asset/Liability Coverage
- Leverage
- Balance Sheet Strength

The deterministic calculation remains the numerical source of truth.

### Financial Forecasting

Angelix provides financial forecasting based on available historical financial data.

Forecast outputs include:

- Expected revenue
- Expected expenses
- Expected profit

### AI Financial Intelligence

Angelix integrates configurable AI assistance through OpenRouter.

AI functionality can provide:

- Financial analysis
- Financial insights
- Recommendations
- Financial outlook
- Context-aware financial assistance

AI is used to explain and interpret supplied financial information.

Deterministic financial calculations remain the source of truth for numerical financial values.

Use an available free OpenRouter model when configuring the application. No API key is hard-coded into the source code.

### Reports

Angelix provides PDF reporting using ReportLab.

Financial analysis reports can include:

- Financial KPIs
- Revenue and expense analysis
- Category breakdowns
- Financial ratios
- Balance Sheet information
- Financial Health Score
- Forecasting results
- AI financial analysis
- AI recommendations
- Data quality information

Financial statements can also be generated where applicable and where existing structured statements are not already available for the selected period.

---

# Technology Stack

## Backend
- Python 3.12
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-Login
- Flask-JWT-Extended
- Flask-WTF
- Flask-Bcrypt

## Database
- PostgreSQL
- SQLAlchemy
- Alembic / Flask-Migrate

## Data Processing
- Pandas
- OpenPyXL
- xlrd

## OCR and Document Processing
- PyMuPDF
- Pillow
- Tesseract OCR
- EasyOCR

## Machine Learning
- Scikit-learn
- Joblib
- Supervised accounting classification models

## AI
- OpenRouter API

## Reporting
- ReportLab

## Frontend
- HTML
- CSS
- Vanilla JavaScript
- Chart-based financial visualizations

## Production
- Gunicorn
- Docker
- Docker Compose

---

# Project Structure

```text
angelix/
│
├── app/
│   ├── ai/
│   ├── analytics/
│   ├── config/
│   ├── models/
│   ├── ocr/
│   ├── reports/
│   ├── routes/
│   ├── services/
│   │   └── ml/
│   ├── static/
│   ├── templates/
│   └── utils/
│
├── ANGELIX_Supervised_Accounting_ML/
│   ├── data/
│   ├── models/
│   ├── scripts/
│   ├── src/
│   └── tests/
│
├── docs/
├── instance/
│   └── ml_models/
├── migrations/
├── scripts/
├── tests/
├── uploads/
├── generated_reports/
├── logs/
│
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
├── requirements.txt
├── run.py
└── wsgi.py