"""
Database query utilities for Hedge Fund Index application.
Provides all data access through SQLAlchemy models.
"""

import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import func, desc, text
from sqlalchemy.orm import Session

from utils.db_util import (
    get_engine,
    get_session,
    Submission,
    CoverPage,
    SummaryPage,
    Signature,
    OtherManager,
    OtherManager2,
    InfoTable,
    CompanyTicker,
    User,
    DB_SCHEMA,
)

load_dotenv()


# ============================================================
# Session Management
# ============================================================

_engine = None
_SessionLocal = None


def _ensure_engine():
    """Create the shared engine + session factory once per process."""
    global _engine, _SessionLocal
    if _engine is None:
        _engine = get_engine()
        from sqlalchemy.orm import sessionmaker
        _SessionLocal = sessionmaker(bind=_engine)
    return _SessionLocal


def get_db_session() -> Session:
    """Return a fresh SQLAlchemy session.

    FastHTML serves requests concurrently across threads, so a singleton
    session is unsafe — any prior exception leaves the transaction aborted
    and poisons every subsequent query. We hand out a short-lived session
    per call and let the caller (or the garbage collector) close it.
    """
    factory = _ensure_engine()
    session = factory()
    # Belt-and-braces: if the session somehow inherits a failed transaction,
    # roll it back before the query starts.
    try:
        session.rollback()
    except Exception:
        pass
    return session


def close_session():
    """Disposed of automatically — kept for compatibility with old callers."""
    return None


# ============================================================
# Summary Statistics
# ============================================================

def get_summary_stats() -> Dict:
    """Get overall summary statistics."""
    session = get_db_session()
    
    # Total funds (unique filing managers)
    total_funds = session.query(func.count(func.distinct(CoverPage.filingmanager_name))).scalar() or 0
    
    # Total holdings
    total_holdings = session.query(func.count(InfoTable.infotable_sk)).scalar() or 0
    
    # Total AUM (sum of all values)
    total_aum = session.query(func.sum(InfoTable.value)).scalar() or 0
    
    # Unique securities
    unique_securities = session.query(func.count(func.distinct(InfoTable.name_of_issuer))).scalar() or 0
    
    # Convert Decimal to float for JSON serialization
    total_aum_float = float(total_aum) if total_aum else 0
    
    return {
        'total_funds': total_funds or 0,
        'total_holdings': total_holdings or 0,
        'total_aum': total_aum_float,
        'total_aum_billions': total_aum_float / 1e9,
        'unique_securities': unique_securities or 0
    }


# ============================================================
# Fund Queries
# ============================================================

def get_funds_list(limit: int = 1000) -> pd.DataFrame:
    """Get list of all funds with portfolio values."""
    session = get_db_session()
    
    query = text(f"""
        SELECT 
            c.filingmanager_name,
            c.accession_number,
            c.filingmanager_city,
            c.filingmanager_stateorcountry,
            s.table_value_total,
            s.table_entry_total
        FROM {DB_SCHEMA}.coverpage c
        LEFT JOIN {DB_SCHEMA}.summarypage s ON c.accession_number = s.accession_number
        ORDER BY s.table_value_total DESC NULLS LAST
        LIMIT :limit
    """)
    
    result = session.execute(query, {"limit": limit})
    df = pd.DataFrame(result.fetchall(), columns=[
        'FILINGMANAGER_NAME', 'ACCESSION_NUMBER', 'FILINGMANAGER_CITY', 
        'FILINGMANAGER_STATEORCOUNTRY', 'TABLEVALUETOTAL', 'TABLEENTRYTOTAL'
    ])
    return df


def get_fund_names() -> List[str]:
    """Get sorted list of unique fund names."""
    session = get_db_session()
    
    query = text(f"""
        SELECT DISTINCT filingmanager_name 
        FROM {DB_SCHEMA}.coverpage 
        WHERE filingmanager_name IS NOT NULL 
        ORDER BY filingmanager_name
    """)
    
    result = session.execute(query)
    return [row[0] for row in result.fetchall()]


def get_fund_data(fund_name: str) -> pd.DataFrame:
    """Get fund data by name."""
    session = get_db_session()
    
    query = text(f"""
        SELECT 
            c.accession_number,
            c.filingmanager_name,
            c.filingmanager_city,
            c.filingmanager_stateorcountry,
            c.report_type,
            s.table_value_total,
            s.table_entry_total
        FROM {DB_SCHEMA}.coverpage c
        LEFT JOIN {DB_SCHEMA}.summarypage s ON c.accession_number = s.accession_number
        WHERE c.filingmanager_name = :fund_name
    """)
    
    result = session.execute(query, {"fund_name": fund_name})
    df = pd.DataFrame(result.fetchall(), columns=[
        'ACCESSION_NUMBER', 'FILINGMANAGER_NAME', 'FILINGMANAGER_CITY',
        'FILINGMANAGER_STATEORCOUNTRY', 'REPORTTYPE', 'TABLEVALUETOTAL', 'TABLEENTRYTOTAL'
    ])
    return df


def search_funds(query: str, limit: int = 20) -> List[Dict]:
    """Search for funds by name (partial match)."""
    session = get_db_session()
    
    sql = text(f"""
        SELECT 
            c.filingmanager_name,
            c.accession_number,
            s.table_value_total,
            s.table_entry_total
        FROM {DB_SCHEMA}.coverpage c
        LEFT JOIN {DB_SCHEMA}.summarypage s ON c.accession_number = s.accession_number
        WHERE LOWER(c.filingmanager_name) LIKE LOWER(:query)
        ORDER BY s.table_value_total DESC NULLS LAST
        LIMIT :limit
    """)
    
    result = session.execute(sql, {"query": f"%{query}%", "limit": limit})
    
    return [
        {
            'name': row[0],
            'accession_number': row[1],
            'portfolio_value': row[2],
            'positions': row[3]
        }
        for row in result.fetchall()
    ]


def get_top_funds(top_n: int = 20) -> pd.DataFrame:
    """Get top funds by portfolio value."""
    session = get_db_session()
    
    query = text(f"""
        SELECT 
            c.filingmanager_name as "Fund Name",
            s.table_value_total as "Portfolio Value",
            s.table_entry_total as "Total Positions"
        FROM {DB_SCHEMA}.coverpage c
        JOIN {DB_SCHEMA}.summarypage s ON c.accession_number = s.accession_number
        WHERE s.table_value_total IS NOT NULL
        ORDER BY s.table_value_total DESC
        LIMIT :limit
    """)
    
    result = session.execute(query, {"limit": top_n})
    df = pd.DataFrame(result.fetchall(), columns=['Fund Name', 'Portfolio Value', 'Total Positions'])
    return df


# ============================================================
# Holdings Queries
# ============================================================

def get_fund_holdings(fund_name: str, limit: int = 50) -> pd.DataFrame:
    """Get holdings for a specific fund."""
    session = get_db_session()
    
    query = text(f"""
        SELECT 
            i.name_of_issuer as "NAMEOFISSUER",
            i.title_of_class as "TITLEOFCLASS",
            i.cusip as "CUSIP",
            i.value as "VALUE",
            i.ssh_prn_amt as "SSHPRNAMT",
            i.ssh_prn_amt_type as "SSHPRNAMTTYPE",
            i.put_call as "PUTCALL",
            i.investment_discretion as "INVESTMENTDISCRETION",
            i.voting_auth_sole as "VOTING_AUTH_SOLE",
            i.voting_auth_shared as "VOTING_AUTH_SHARED",
            i.voting_auth_none as "VOTING_AUTH_NONE",
            i.accession_number as "ACCESSION_NUMBER"
        FROM {DB_SCHEMA}.infotable i
        JOIN {DB_SCHEMA}.coverpage c ON i.accession_number = c.accession_number
        WHERE c.filingmanager_name = :fund_name
        ORDER BY i.value DESC
        LIMIT :limit
    """)
    
    result = session.execute(query, {"fund_name": fund_name, "limit": limit})
    df = pd.DataFrame(result.fetchall(), columns=[
        'NAMEOFISSUER', 'TITLEOFCLASS', 'CUSIP', 'VALUE', 'SSHPRNAMT', 
        'SSHPRNAMTTYPE', 'PUTCALL', 'INVESTMENTDISCRETION', 
        'VOTING_AUTH_SOLE', 'VOTING_AUTH_SHARED', 'VOTING_AUTH_NONE', 'ACCESSION_NUMBER'
    ])
    
    # Calculate portfolio percentage
    if not df.empty:
        total_value = df['VALUE'].sum()
        df['portfolio_pct'] = (df['VALUE'] / total_value) * 100 if total_value > 0 else 0
    
    return df


def get_holdings_by_accession(accession_numbers: List[str], limit: int = 1000) -> pd.DataFrame:
    """Get holdings for specific accession numbers."""
    session = get_db_session()
    
    if not accession_numbers:
        return pd.DataFrame()
    
    # Create placeholders for the IN clause
    placeholders = ', '.join([f':acc_{i}' for i in range(len(accession_numbers))])
    params = {f'acc_{i}': acc for i, acc in enumerate(accession_numbers)}
    params['limit'] = limit
    
    query = text(f"""
        SELECT 
            i.name_of_issuer as "NAMEOFISSUER",
            i.title_of_class as "TITLEOFCLASS",
            i.cusip as "CUSIP",
            i.value as "VALUE",
            i.ssh_prn_amt as "SSHPRNAMT",
            i.ssh_prn_amt_type as "SSHPRNAMTTYPE",
            i.put_call as "PUTCALL",
            i.investment_discretion as "INVESTMENTDISCRETION",
            i.accession_number as "ACCESSION_NUMBER"
        FROM {DB_SCHEMA}.infotable i
        WHERE i.accession_number IN ({placeholders})
        ORDER BY i.value DESC
        LIMIT :limit
    """)
    
    result = session.execute(query, params)
    df = pd.DataFrame(result.fetchall(), columns=[
        'NAMEOFISSUER', 'TITLEOFCLASS', 'CUSIP', 'VALUE', 'SSHPRNAMT', 
        'SSHPRNAMTTYPE', 'PUTCALL', 'INVESTMENTDISCRETION', 'ACCESSION_NUMBER'
    ])
    return df


def get_all_holdings_df(limit: int = 100000) -> pd.DataFrame:
    """Get all holdings as a DataFrame (for compatibility with legacy code)."""
    session = get_db_session()
    
    query = text(f"""
        SELECT 
            i.name_of_issuer as "NAMEOFISSUER",
            i.title_of_class as "TITLEOFCLASS",
            i.cusip as "CUSIP",
            i.value as "VALUE",
            i.ssh_prn_amt as "SSHPRNAMT",
            i.ssh_prn_amt_type as "SSHPRNAMTTYPE",
            i.put_call as "PUTCALL",
            i.investment_discretion as "INVESTMENTDISCRETION",
            i.accession_number as "ACCESSION_NUMBER"
        FROM {DB_SCHEMA}.infotable i
        LIMIT :limit
    """)
    
    result = session.execute(query, {"limit": limit})
    df = pd.DataFrame(result.fetchall(), columns=[
        'NAMEOFISSUER', 'TITLEOFCLASS', 'CUSIP', 'VALUE', 'SSHPRNAMT', 
        'SSHPRNAMTTYPE', 'PUTCALL', 'INVESTMENTDISCRETION', 'ACCESSION_NUMBER'
    ])
    return df


# ============================================================
# Security Queries
# ============================================================

def search_securities(query: str, limit: int = 100) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Search for securities by name and return matching holdings and funds."""
    session = get_db_session()
    
    # Get matching holdings aggregated by security
    security_query = text(f"""
        SELECT 
            i.name_of_issuer as "Security",
            i.title_of_class as "Type",
            SUM(i.value) as "Total Value",
            SUM(i.ssh_prn_amt) as "Total Shares",
            COUNT(DISTINCT i.accession_number) as "Fund Count"
        FROM {DB_SCHEMA}.infotable i
        WHERE LOWER(i.name_of_issuer) LIKE LOWER(:query)
        GROUP BY i.name_of_issuer, i.title_of_class
        ORDER BY SUM(i.value) DESC
        LIMIT :limit
    """)
    
    result = session.execute(security_query, {"query": f"%{query}%", "limit": limit})
    security_df = pd.DataFrame(result.fetchall(), columns=[
        'Security', 'Type', 'Total Value', 'Total Shares', 'Fund Count'
    ])
    
    if security_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    # Get funds holding these securities
    fund_query = text(f"""
        SELECT 
            c.filingmanager_name as "Fund Name",
            SUM(i.value) as "Position Value",
            SUM(i.ssh_prn_amt) as "Shares Held"
        FROM {DB_SCHEMA}.infotable i
        JOIN {DB_SCHEMA}.coverpage c ON i.accession_number = c.accession_number
        WHERE LOWER(i.name_of_issuer) LIKE LOWER(:query)
        GROUP BY c.filingmanager_name
        ORDER BY SUM(i.value) DESC
        LIMIT :limit
    """)
    
    result = session.execute(fund_query, {"query": f"%{query}%", "limit": limit})
    fund_df = pd.DataFrame(result.fetchall(), columns=[
        'Fund Name', 'Position Value', 'Shares Held'
    ])
    
    return security_df, fund_df


def get_popular_securities(top_n: int = 50) -> pd.DataFrame:
    """Get most popular securities by total value and fund count."""
    session = get_db_session()
    
    query = text(f"""
        SELECT 
            i.name_of_issuer as "Security",
            i.title_of_class as "Type",
            SUM(i.value) as "Total Value",
            SUM(i.ssh_prn_amt) as "Total Shares",
            COUNT(DISTINCT i.accession_number) as "Fund Count"
        FROM {DB_SCHEMA}.infotable i
        GROUP BY i.name_of_issuer, i.title_of_class
        ORDER BY SUM(i.value) DESC
        LIMIT :limit
    """)
    
    result = session.execute(query, {"limit": top_n})
    df = pd.DataFrame(result.fetchall(), columns=[
        'Security', 'Type', 'Total Value', 'Total Shares', 'Fund Count'
    ])
    return df


def get_holdings_by_cusip(cusip: str) -> pd.DataFrame:
    """Get all holdings for a specific CUSIP."""
    session = get_db_session()
    
    query = text(f"""
        SELECT 
            i.name_of_issuer,
            i.title_of_class,
            i.cusip,
            i.value,
            i.ssh_prn_amt,
            c.filingmanager_name
        FROM {DB_SCHEMA}.infotable i
        JOIN {DB_SCHEMA}.coverpage c ON i.accession_number = c.accession_number
        WHERE i.cusip = :cusip
        ORDER BY i.value DESC
    """)
    
    result = session.execute(query, {"cusip": cusip})
    df = pd.DataFrame(result.fetchall(), columns=[
        'name_of_issuer', 'title_of_class', 'cusip', 'value', 'ssh_prn_amt', 'filingmanager_name'
    ])
    return df


# ============================================================
# Market Statistics
# ============================================================

def get_security_type_distribution() -> pd.DataFrame:
    """Get distribution of security types."""
    session = get_db_session()
    
    query = text(f"""
        SELECT 
            title_of_class as "Type",
            COUNT(*) as "Count"
        FROM {DB_SCHEMA}.infotable
        GROUP BY title_of_class
        ORDER BY COUNT(*) DESC
        LIMIT 20
    """)
    
    result = session.execute(query)
    df = pd.DataFrame(result.fetchall(), columns=['Type', 'Count'])
    return df


def get_value_statistics() -> Dict:
    """Get value distribution statistics."""
    session = get_db_session()
    
    query = text(f"""
        SELECT 
            AVG(value) as mean_value,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value) as median_value,
            MAX(value) as max_value,
            MIN(value) as min_value,
            COUNT(*) as total_positions
        FROM {DB_SCHEMA}.infotable
    """)
    
    result = session.execute(query)
    row = result.fetchone()
    
    return {
        'mean': row[0] or 0,
        '50%': row[1] or 0,
        'max': row[2] or 0,
        'min': row[3] or 0,
        'count': row[4] or 0
    }


def get_fund_concentration(top_n: int = 20) -> pd.DataFrame:
    """Get fund concentration metrics."""
    session = get_db_session()
    
    query = text(f"""
        SELECT 
            c.filingmanager_name as "FILINGMANAGER_NAME",
            s.table_value_total as "TABLEVALUETOTAL",
            s.table_entry_total as "TABLEENTRYTOTAL"
        FROM {DB_SCHEMA}.coverpage c
        JOIN {DB_SCHEMA}.summarypage s ON c.accession_number = s.accession_number
        WHERE s.table_value_total IS NOT NULL
        ORDER BY s.table_value_total DESC
        LIMIT :limit
    """)
    
    result = session.execute(query, {"limit": top_n})
    df = pd.DataFrame(result.fetchall(), columns=[
        'FILINGMANAGER_NAME', 'TABLEVALUETOTAL', 'TABLEENTRYTOTAL'
    ])
    return df


# ============================================================
# Ticker Mapping
# ============================================================

def get_ticker_for_company(company_name: str) -> Optional[str]:
    """Get ticker symbol for a company name."""
    session = get_db_session()
    
    query = text(f"""
        SELECT ticker 
        FROM {DB_SCHEMA}.company_ticker 
        WHERE UPPER(company_name) = UPPER(:name)
        LIMIT 1
    """)
    
    result = session.execute(query, {"name": company_name})
    row = result.fetchone()
    return row[0] if row else None


def get_company_tickers() -> pd.DataFrame:
    """Get all company ticker mappings."""
    session = get_db_session()
    
    query = text(f"""
        SELECT company_name, ticker, sector, source, last_updated
        FROM {DB_SCHEMA}.company_ticker
        ORDER BY company_name
    """)
    
    result = session.execute(query)
    df = pd.DataFrame(result.fetchall(), columns=[
        'company_name', 'ticker', 'sector', 'source', 'last_updated'
    ])
    return df


def add_ticker_mapping(company_name: str, ticker: str, sector: str = None, source: str = 'manual'):
    """Add a new ticker mapping."""
    session = get_db_session()
    
    query = text(f"""
        INSERT INTO {DB_SCHEMA}.company_ticker (company_name, ticker, sector, source, last_updated)
        VALUES (:company_name, :ticker, :sector, :source, CURRENT_DATE)
        ON CONFLICT (company_name, ticker) DO UPDATE SET
            sector = EXCLUDED.sector,
            source = EXCLUDED.source,
            last_updated = CURRENT_DATE
    """)
    
    session.execute(query, {
        "company_name": company_name,
        "ticker": ticker,
        "sector": sector,
        "source": source
    })
    session.commit()


# ============================================================
# Data Quality
# ============================================================

def get_data_quality_stats() -> Dict:
    """Get data quality statistics."""
    session = get_db_session()
    
    # Count records in each table
    tables = {
        'submission': Submission,
        'coverpage': CoverPage,
        'summarypage': SummaryPage,
        'signature': Signature,
        'othermanager': OtherManager,
        'othermanager2': OtherManager2,
        'infotable': InfoTable,
        'company_ticker': CompanyTicker
    }
    
    counts = {}
    for name, model in tables.items():
        try:
            count = session.query(func.count()).select_from(model).scalar()
            counts[name] = count or 0
        except Exception:
            counts[name] = 0
    
    return counts


def check_database_connection() -> bool:
    """Check if database connection is working."""
    try:
        session = get_db_session()
        session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ============================================================
# User Management
# ============================================================

def subscribe_user(email: str) -> Dict:
    """
    Subscribe a user to email updates.
    
    Returns:
        Dict with 'success', 'message', and 'is_new' keys
    """
    session = get_db_session()
    
    try:
        # Check if user already exists
        existing = session.query(User).filter(User.email == email.lower().strip()).first()
        
        if existing:
            if existing.subscription_status == "active":
                return {
                    "success": True,
                    "message": "You're already subscribed!",
                    "is_new": False
                }
            else:
                # Resubscribe
                existing.subscription_status = "active"
                existing.updated_at = datetime.utcnow()
                session.commit()
                return {
                    "success": True,
                    "message": "Welcome back! You've been resubscribed.",
                    "is_new": False
                }
        
        # Create new user
        new_user = User(
            email=email.lower().strip(),
            subscription_status="active"
        )
        session.add(new_user)
        session.commit()
        
        return {
            "success": True,
            "message": "Thanks for subscribing!",
            "is_new": True
        }
        
    except Exception as e:
        session.rollback()
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "is_new": False
        }


def unsubscribe_user(email: str) -> Dict:
    """Unsubscribe a user from email updates."""
    session = get_db_session()
    
    try:
        user = session.query(User).filter(User.email == email.lower().strip()).first()
        
        if not user:
            return {
                "success": False,
                "message": "Email not found in our records."
            }
        
        user.subscription_status = "unsubscribed"
        user.updated_at = datetime.utcnow()
        session.commit()
        
        return {
            "success": True,
            "message": "You've been unsubscribed."
        }
        
    except Exception as e:
        session.rollback()
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


def get_active_subscribers() -> List[str]:
    """Get list of active subscriber emails."""
    session = get_db_session()
    
    users = session.query(User.email).filter(
        User.subscription_status == "active"
    ).all()
    
    return [user.email for user in users]


def get_subscriber_count() -> int:
    """Get count of active subscribers."""
    session = get_db_session()
    
    return session.query(func.count(User.id)).filter(
        User.subscription_status == "active"
    ).scalar() or 0


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user details by email."""
    session = get_db_session()
    
    user = session.query(User).filter(User.email == email.lower().strip()).first()
    
    if not user:
        return None
    
    return {
        "id": user.id,
        "email": user.email,
        "subscription_status": user.subscription_status,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }

