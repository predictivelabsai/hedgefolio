# Hedgefolio

**Invest like a hedge fund manager.** Monitor the portfolios of the world's top hedge funds through SEC 13F filings analysis.

## Overview

Hedgefolio is a comprehensive hedge fund analysis platform built with Streamlit and PostgreSQL. It processes SEC 13F filings to provide insights into institutional investment patterns, allowing retail investors to see what the smart money is buying and selling.

## Features

### 📊 Fund Analysis (Home Page)
- **Portfolio Treemaps**: Interactive visualization of fund holdings by sector
- **Real-time Price Data**: 1-month price changes from Yahoo Finance
- **Sector Analysis**: Portfolio breakdown by industry
- **Top Holdings**: Detailed position information with values and percentages

### 🔍 Holdings Explorer
- **Security Search**: Find which funds hold specific stocks
- **Cross-Fund Analysis**: Compare positions across multiple funds
- **Aggregated Data**: Total value and share counts across all holders

### 📈 Market Insights
- **Popular Securities**: Most widely held stocks across all funds
- **Fund Concentration**: Market share distribution among top funds
- **Market Statistics**: Value distribution and security type breakdown

### 📖 About Hedgefolio
- **SEC 13F Methodology**: Understanding the data source
- **Filing Schedule**: Quarterly deadlines and data freshness
- **How to Use**: Investment research workflow guide

### 📬 Email Subscriptions
- **Sidebar Signup**: Subscribe to portfolio update notifications
- **Postmark Integration**: Transactional email delivery

## Technology Stack

- **Frontend**: Streamlit
- **Database**: PostgreSQL (with SQLAlchemy ORM)
- **Data Processing**: Pandas, NumPy
- **Visualizations**: Plotly
- **Market Data**: Yahoo Finance API
- **Email**: Postmark SDK
- **Data Source**: SEC EDGAR 13F filings

## Installation

### Prerequisites
- Python 3.11+
- PostgreSQL database
- pip package manager

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-repo/hedgefolio.git
   cd hedgefolio
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or: .venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   
   Create a `.env` file in the project root:
   ```bash
   # Database
   DB_URL=postgresql://user:password@host:port/database
   DB_SCHEMA=hedgefolio
   
   # Email (Postmark)
   POSTMARK_API_KEY=your_postmark_api_key
   POSTMARK_FROM_EMAIL=noreply@yourdomain.com
   
   # Optional: AI features
   OPENAI_API_KEY=your_openai_api_key
   ```

5. **Initialize the database and load data**
   ```bash
   python tasks/setup_data.py
   ```

6. **Run the application**
   ```bash
   streamlit run Home.py
   ```

7. **Access the application**
   - Open your browser to `http://localhost:8501`

## Data Management Tasks

### `tasks/setup_data.py` - Initial Setup & Full Data Load

Use this script for initial setup or to reload all data:

```bash
# Full setup: reassemble chunks, check duplicates, load to DB, verify
python tasks/setup_data.py
```

**What it does:**
1. ✅ Checks required packages are installed
2. 📦 Reassembles INFOTABLE.tsv from chunks (if needed)
3. 🔍 Verifies all data files are present
4. 🗄️ Creates database schema and tables
5. 📤 Loads all data into the database
6. ✓ Verifies database integrity

### `tasks/data_sync.py` - Data Synchronization

Use this script for ongoing data maintenance:

```bash
# Full sync (download, load, verify)
python tasks/data_sync.py

# Only verify database integrity
python tasks/data_sync.py --verify

# Only load existing data files to database
python tasks/data_sync.py --load-only

# Clean up data files after verifying DB (removes TSV files)
python tasks/data_sync.py --cleanup
```

**Available options:**
| Option | Description |
|--------|-------------|
| `--download-only` | Only download new SEC data |
| `--load-only` | Only load existing data to database |
| `--verify` | Only verify database integrity |
| `--cleanup` | Clean up data files after DB verification |

### Scheduling Daily Updates

To run data sync daily, add a cron job:

```bash
# Edit crontab
crontab -e

# Add this line to run at 6 AM daily
0 6 * * * cd /path/to/hedgefolio && .venv/bin/python tasks/data_sync.py >> /var/log/hedgefolio-sync.log 2>&1
```

## Database Schema

The application uses PostgreSQL with the following main tables:

| Table | Description |
|-------|-------------|
| `submission` | Core filing metadata |
| `coverpage` | Filing manager information |
| `summarypage` | Portfolio summary statistics |
| `infotable` | Individual holdings (860K+ records) |
| `signature` | Filing signatories |
| `othermanager` | Co-managers on filings |
| `company_ticker` | Ticker symbol mappings |
| `users` | Email subscribers |

## SEC 13F Filing Schedule

13F filings are due **45 days after quarter end**:

| Quarter | Period | Filing Deadline |
|---------|--------|-----------------|
| Q1 | Jan-Mar | May 15 |
| Q2 | Apr-Jun | August 14 |
| Q3 | Jul-Sep | November 14 |
| Q4 | Oct-Dec | February 14 |

**Note:** Data is a snapshot from the quarter-end date and may be 6-8 weeks old when filed.

## Project Structure

```
hedgefolio/
├── Home.py                    # Main Streamlit application
├── pages/
│   ├── 1_🔍_Holdings_Explorer.py
│   ├── 2_📊_Market_Insights.py
│   └── 3_📖_About_Hedgefolio.py
├── utils/
│   ├── db_util.py            # SQLAlchemy models & data loading
│   ├── db_queries.py         # Database query functions
│   ├── email_util.py         # Postmark email integration
│   ├── yf_util.py            # Yahoo Finance utilities
│   └── ticker_mapping.py     # Company-to-ticker mapping
├── tasks/
│   ├── setup_data.py         # Initial data setup
│   └── data_sync.py          # Ongoing data synchronization
├── sql/
│   └── schema.sql            # Database schema
├── data/
│   ├── company_ticker.csv    # Ticker mappings
│   └── FORM13F_metadata.json # SEC schema documentation
├── requirements.txt
├── .env                      # Environment variables (not committed)
└── README.md
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DB_URL` | Yes | PostgreSQL connection string |
| `DB_SCHEMA` | Yes | Database schema name (default: hedgefolio) |
| `POSTMARK_API_KEY` | No | Postmark API key for email |
| `POSTMARK_FROM_EMAIL` | No | Sender email address |
| `OPENAI_API_KEY` | No | OpenAI key for AI features |

## Deployment

### Streamlit Cloud

1. Push code to GitHub
2. Connect repository to [Streamlit Cloud](https://share.streamlit.io/)
3. Add environment variables in Streamlit Cloud dashboard
4. Deploy

### Docker (Coming Soon)

Docker support planned for future release.

## Data Sources

- **Primary**: SEC EDGAR 13F filings
- **Market Data**: Yahoo Finance API
- **Sector Classification**: Yahoo Finance + OpenAI

## Disclaimer

This is not investment advice. Hedgefolio provides information for educational and research purposes only. Past performance does not guarantee future results. Always conduct your own research and consult a financial advisor before making investment decisions.

## License

MIT License - See LICENSE file for details.
