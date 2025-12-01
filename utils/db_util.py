"""
Database utilities for Form 13F SEC filings data.
Uses SQLAlchemy to manage connections and data loading.
"""

import os
from datetime import datetime
from typing import Optional
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    BigInteger,
    Date,
    Text,
    DateTime,
    ForeignKey,
    Index,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.schema import DDL

# Load environment variables
load_dotenv()

DB_URL = os.getenv("DB_URL")
DB_SCHEMA = os.getenv("DB_SCHEMA", "hedgefolio")

Base = declarative_base()


# ============================================================
# SQLAlchemy Models
# ============================================================

class Submission(Base):
    """Core submission info for each 13F filing."""
    __tablename__ = "submission"
    __table_args__ = {"schema": DB_SCHEMA}

    accession_number = Column(String(25), primary_key=True)
    filing_date = Column(Date, nullable=False)
    submission_type = Column(String(10), nullable=False)
    cik = Column(String(10), nullable=False, index=True)
    period_of_report = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    coverpage = relationship("CoverPage", back_populates="submission", uselist=False, cascade="all, delete-orphan")
    summarypage = relationship("SummaryPage", back_populates="submission", uselist=False, cascade="all, delete-orphan")
    signature = relationship("Signature", back_populates="submission", uselist=False, cascade="all, delete-orphan")
    othermanagers = relationship("OtherManager", back_populates="submission", cascade="all, delete-orphan")
    othermanagers2 = relationship("OtherManager2", back_populates="submission", cascade="all, delete-orphan")
    infotable_entries = relationship("InfoTable", back_populates="submission", cascade="all, delete-orphan")


class CoverPage(Base):
    """Cover page details including filing manager info."""
    __tablename__ = "coverpage"
    __table_args__ = {"schema": DB_SCHEMA}

    accession_number = Column(String(25), ForeignKey(f"{DB_SCHEMA}.submission.accession_number", ondelete="CASCADE"), primary_key=True)
    report_calendar_or_quarter = Column(Date, nullable=False, index=True)
    is_amendment = Column(String(1))
    amendment_no = Column(Integer)
    amendment_type = Column(String(20))
    conf_denied_expired = Column(String(1))
    date_denied_expired = Column(Date)
    date_reported = Column(Date)
    reason_for_nonconfidentiality = Column(String(40))
    filingmanager_name = Column(String(150), nullable=False, index=True)
    filingmanager_street1 = Column(String(40))
    filingmanager_street2 = Column(String(40))
    filingmanager_city = Column(String(30))
    filingmanager_stateorcountry = Column(String(2))
    filingmanager_zipcode = Column(String(10))
    report_type = Column(String(30), nullable=False)
    form13f_filenumber = Column(String(17))
    crd_number = Column(String(9))
    sec_filenumber = Column(String(17))
    provide_info_for_instruction5 = Column(String(1), nullable=False)
    additional_information = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    submission = relationship("Submission", back_populates="coverpage")


class SummaryPage(Base):
    """Summary statistics for each filing."""
    __tablename__ = "summarypage"
    __table_args__ = {"schema": DB_SCHEMA}

    accession_number = Column(String(25), ForeignKey(f"{DB_SCHEMA}.submission.accession_number", ondelete="CASCADE"), primary_key=True)
    other_included_managers_count = Column(Integer)
    table_entry_total = Column(Integer)
    table_value_total = Column(BigInteger, index=True)
    is_confidential_omitted = Column(String(1))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    submission = relationship("Submission", back_populates="summarypage")


class Signature(Base):
    """Signatory information for each filing."""
    __tablename__ = "signature"
    __table_args__ = {"schema": DB_SCHEMA}

    accession_number = Column(String(25), ForeignKey(f"{DB_SCHEMA}.submission.accession_number", ondelete="CASCADE"), primary_key=True)
    name = Column(String(150), nullable=False)
    title = Column(String(60), nullable=False)
    phone = Column(String(20))
    signature = Column(String(150), nullable=False)
    city = Column(String(30), nullable=False)
    stateorcountry = Column(String(2), nullable=False)
    signature_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    submission = relationship("Submission", back_populates="signature")


class OtherManager(Base):
    """Other managers included in the filing."""
    __tablename__ = "othermanager"
    __table_args__ = {"schema": DB_SCHEMA}

    accession_number = Column(String(25), ForeignKey(f"{DB_SCHEMA}.submission.accession_number", ondelete="CASCADE"), primary_key=True)
    othermanager_sk = Column(BigInteger, primary_key=True)
    cik = Column(String(10), index=True)
    form13f_filenumber = Column(String(17))
    crd_number = Column(String(9))
    sec_filenumber = Column(String(17))
    name = Column(String(150), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    submission = relationship("Submission", back_populates="othermanagers")


class OtherManager2(Base):
    """Additional other managers with sequence numbers."""
    __tablename__ = "othermanager2"
    __table_args__ = {"schema": DB_SCHEMA}

    accession_number = Column(String(25), ForeignKey(f"{DB_SCHEMA}.submission.accession_number", ondelete="CASCADE"), primary_key=True)
    sequence_number = Column(Integer, primary_key=True)
    cik = Column(String(10), index=True)
    form13f_filenumber = Column(String(17))
    crd_number = Column(String(9))
    sec_filenumber = Column(String(17))
    name = Column(String(150), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    submission = relationship("Submission", back_populates="othermanagers2")


class InfoTable(Base):
    """Holdings data - securities positions."""
    __tablename__ = "infotable"
    __table_args__ = (
        Index("idx_infotable_cusip", "cusip"),
        Index("idx_infotable_name_of_issuer", "name_of_issuer"),
        Index("idx_infotable_value", "value"),
        {"schema": DB_SCHEMA}
    )

    accession_number = Column(String(25), ForeignKey(f"{DB_SCHEMA}.submission.accession_number", ondelete="CASCADE"), primary_key=True)
    infotable_sk = Column(BigInteger, primary_key=True)
    name_of_issuer = Column(String(200), nullable=False)
    title_of_class = Column(String(150), nullable=False)
    cusip = Column(String(9), nullable=False)
    figi = Column(String(12))
    value = Column(BigInteger, nullable=False)
    ssh_prn_amt = Column(BigInteger, nullable=False)
    ssh_prn_amt_type = Column(String(10), nullable=False)
    put_call = Column(String(10))
    investment_discretion = Column(String(10), nullable=False)
    other_manager = Column(String(100))
    voting_auth_sole = Column(BigInteger, nullable=False)
    voting_auth_shared = Column(BigInteger, nullable=False)
    voting_auth_none = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    submission = relationship("Submission", back_populates="infotable_entries")


class CompanyTicker(Base):
    """Mapping of company names to ticker symbols."""
    __tablename__ = "company_ticker"
    __table_args__ = (
        Index("idx_company_ticker_ticker", "ticker"),
        Index("idx_company_ticker_sector", "sector"),
        {"schema": DB_SCHEMA}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(200), nullable=False)
    ticker = Column(String(20), nullable=False)
    sector = Column(String(100))
    source = Column(String(50))
    last_updated = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    """User signups for email notifications."""
    __tablename__ = "users"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    subscription_status = Column(String(20), nullable=False, default="active")  # active, unsubscribed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================
# Database Engine and Session Management
# ============================================================

def get_engine(echo: bool = False):
    """Create SQLAlchemy engine with the configured database URL."""
    if not DB_URL:
        raise ValueError("DB_URL environment variable is not set")
    return create_engine(DB_URL, echo=echo)


def get_session(engine=None) -> Session:
    """Create a new database session."""
    if engine is None:
        engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def create_schema(engine=None):
    """Create the database schema if it doesn't exist."""
    if engine is None:
        engine = get_engine()
    
    with engine.connect() as conn:
        conn.execute(DDL(f"CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA}"))
        conn.commit()


def create_tables(engine=None):
    """Create all tables defined in the models."""
    if engine is None:
        engine = get_engine()
    
    create_schema(engine)
    Base.metadata.create_all(engine)
    print(f"Tables created in schema '{DB_SCHEMA}'")


def drop_tables(engine=None):
    """Drop all tables (use with caution!)."""
    if engine is None:
        engine = get_engine()
    
    Base.metadata.drop_all(engine)
    print(f"Tables dropped from schema '{DB_SCHEMA}'")


# ============================================================
# Data Loading Utilities
# ============================================================

def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date strings in various formats."""
    if pd.isna(date_str) or not date_str:
        return None
    
    date_str = str(date_str).strip()
    
    # Try different date formats
    formats = [
        "%d-%b-%Y",  # DD-MON-YYYY (e.g., 31-DEC-2024)
        "%Y-%m-%d",  # YYYY-MM-DD
        "%m/%d/%Y",  # MM/DD/YYYY
        "%d-%m-%Y",  # DD-MM-YYYY
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    return None


def safe_int(value) -> Optional[int]:
    """Safely convert value to integer."""
    if pd.isna(value) or value == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def safe_str(value) -> Optional[str]:
    """Safely convert value to string."""
    if pd.isna(value) or value == "":
        return None
    return str(value).strip()


def load_submission_data(data_dir: str, session: Session, batch_size: int = 1000):
    """Load SUBMISSION.tsv data into the database."""
    filepath = Path(data_dir) / "SUBMISSION.tsv"
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
    
    print(f"Loading {filepath}...")
    df = pd.read_csv(filepath, sep="\t", dtype=str)
    
    records = []
    for _, row in df.iterrows():
        records.append({
            "accession_number": row["ACCESSION_NUMBER"],
            "filing_date": parse_date(row["FILING_DATE"]),
            "submission_type": row["SUBMISSIONTYPE"],
            "cik": row["CIK"],
            "period_of_report": parse_date(row["PERIODOFREPORT"]),
        })
        
        if len(records) >= batch_size:
            _upsert_batch(session, Submission, records)
            records = []
    
    if records:
        _upsert_batch(session, Submission, records)
    
    session.commit()
    print(f"Loaded {len(df)} submission records")


def load_coverpage_data(data_dir: str, session: Session, batch_size: int = 1000):
    """Load COVERPAGE.tsv data into the database."""
    filepath = Path(data_dir) / "COVERPAGE.tsv"
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
    
    print(f"Loading {filepath}...")
    df = pd.read_csv(filepath, sep="\t", dtype=str)
    
    records = []
    for _, row in df.iterrows():
        records.append({
            "accession_number": row["ACCESSION_NUMBER"],
            "report_calendar_or_quarter": parse_date(row["REPORTCALENDARORQUARTER"]),
            "is_amendment": safe_str(row.get("ISAMENDMENT")),
            "amendment_no": safe_int(row.get("AMENDMENTNO")),
            "amendment_type": safe_str(row.get("AMENDMENTTYPE")),
            "conf_denied_expired": safe_str(row.get("CONFDENIEDEXPIRED")),
            "date_denied_expired": parse_date(row.get("DATEDENIEDEXPIRED", "")),
            "date_reported": parse_date(row.get("DATEREPORTED", "")),
            "reason_for_nonconfidentiality": safe_str(row.get("REASONFORNONCONFIDENTIALITY")),
            "filingmanager_name": row["FILINGMANAGER_NAME"],
            "filingmanager_street1": safe_str(row.get("FILINGMANAGER_STREET1")),
            "filingmanager_street2": safe_str(row.get("FILINGMANAGER_STREET2")),
            "filingmanager_city": safe_str(row.get("FILINGMANAGER_CITY")),
            "filingmanager_stateorcountry": safe_str(row.get("FILINGMANAGER_STATEORCOUNTRY")),
            "filingmanager_zipcode": safe_str(row.get("FILINGMANAGER_ZIPCODE")),
            "report_type": row["REPORTTYPE"],
            "form13f_filenumber": safe_str(row.get("FORM13FFILENUMBER")),
            "crd_number": safe_str(row.get("CRDNUMBER")),
            "sec_filenumber": safe_str(row.get("SECFILENUMBER")),
            "provide_info_for_instruction5": row["PROVIDEINFOFORINSTRUCTION5"],
            "additional_information": safe_str(row.get("ADDITIONALINFORMATION")),
        })
        
        if len(records) >= batch_size:
            _upsert_batch(session, CoverPage, records)
            records = []
    
    if records:
        _upsert_batch(session, CoverPage, records)
    
    session.commit()
    print(f"Loaded {len(df)} coverpage records")


def load_summarypage_data(data_dir: str, session: Session, batch_size: int = 1000):
    """Load SUMMARYPAGE.tsv data into the database."""
    filepath = Path(data_dir) / "SUMMARYPAGE.tsv"
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
    
    print(f"Loading {filepath}...")
    df = pd.read_csv(filepath, sep="\t", dtype=str)
    
    records = []
    for _, row in df.iterrows():
        records.append({
            "accession_number": row["ACCESSION_NUMBER"],
            "other_included_managers_count": safe_int(row.get("OTHERINCLUDEDMANAGERSCOUNT")),
            "table_entry_total": safe_int(row.get("TABLEENTRYTOTAL")),
            "table_value_total": safe_int(row.get("TABLEVALUETOTAL")),
            "is_confidential_omitted": safe_str(row.get("ISCONFIDENTIALOMITTED")),
        })
        
        if len(records) >= batch_size:
            _upsert_batch(session, SummaryPage, records)
            records = []
    
    if records:
        _upsert_batch(session, SummaryPage, records)
    
    session.commit()
    print(f"Loaded {len(df)} summarypage records")


def load_signature_data(data_dir: str, session: Session, batch_size: int = 1000):
    """Load SIGNATURE.tsv data into the database."""
    filepath = Path(data_dir) / "SIGNATURE.tsv"
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
    
    print(f"Loading {filepath}...")
    df = pd.read_csv(filepath, sep="\t", dtype=str)
    
    records = []
    for _, row in df.iterrows():
        records.append({
            "accession_number": row["ACCESSION_NUMBER"],
            "name": row["NAME"],
            "title": row["TITLE"],
            "phone": safe_str(row.get("PHONE")),
            "signature": row["SIGNATURE"],
            "city": row["CITY"],
            "stateorcountry": row["STATEORCOUNTRY"],
            "signature_date": parse_date(row["SIGNATUREDATE"]),
        })
        
        if len(records) >= batch_size:
            _upsert_batch(session, Signature, records)
            records = []
    
    if records:
        _upsert_batch(session, Signature, records)
    
    session.commit()
    print(f"Loaded {len(df)} signature records")


def load_othermanager_data(data_dir: str, session: Session, batch_size: int = 1000):
    """Load OTHERMANAGER.tsv data into the database."""
    filepath = Path(data_dir) / "OTHERMANAGER.tsv"
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
    
    print(f"Loading {filepath}...")
    df = pd.read_csv(filepath, sep="\t", dtype=str)
    
    records = []
    for _, row in df.iterrows():
        records.append({
            "accession_number": row["ACCESSION_NUMBER"],
            "othermanager_sk": safe_int(row["OTHERMANAGER_SK"]),
            "cik": safe_str(row.get("CIK")),
            "form13f_filenumber": safe_str(row.get("FORM13FFILENUMBER")),
            "crd_number": safe_str(row.get("CRDNUMBER")),
            "sec_filenumber": safe_str(row.get("SECFILENUMBER")),
            "name": row["NAME"],
        })
        
        if len(records) >= batch_size:
            _upsert_batch(session, OtherManager, records)
            records = []
    
    if records:
        _upsert_batch(session, OtherManager, records)
    
    session.commit()
    print(f"Loaded {len(df)} othermanager records")


def load_othermanager2_data(data_dir: str, session: Session, batch_size: int = 1000):
    """Load OTHERMANAGER2.tsv data into the database."""
    filepath = Path(data_dir) / "OTHERMANAGER2.tsv"
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
    
    print(f"Loading {filepath}...")
    df = pd.read_csv(filepath, sep="\t", dtype=str)
    
    records = []
    for _, row in df.iterrows():
        records.append({
            "accession_number": row["ACCESSION_NUMBER"],
            "sequence_number": safe_int(row["SEQUENCENUMBER"]),
            "cik": safe_str(row.get("CIK")),
            "form13f_filenumber": safe_str(row.get("FORM13FFILENUMBER")),
            "crd_number": safe_str(row.get("CRDNUMBER")),
            "sec_filenumber": safe_str(row.get("SECFILENUMBER")),
            "name": row["NAME"],
        })
        
        if len(records) >= batch_size:
            _upsert_batch(session, OtherManager2, records)
            records = []
    
    if records:
        _upsert_batch(session, OtherManager2, records)
    
    session.commit()
    print(f"Loaded {len(df)} othermanager2 records")


def load_infotable_data(data_dir: str, session: Session, batch_size: int = 5000):
    """Load INFOTABLE data from chunks directory into the database."""
    chunks_dir = Path(data_dir) / "chunks"
    if not chunks_dir.exists():
        print(f"Chunks directory not found: {chunks_dir}")
        return
    
    chunk_files = sorted(chunks_dir.glob("INFOTABLE_chunk_*.tsv"))
    if not chunk_files:
        print("No INFOTABLE chunk files found")
        return
    
    total_records = 0
    for chunk_file in chunk_files:
        print(f"Loading {chunk_file}...")
        df = pd.read_csv(chunk_file, sep="\t", dtype=str)
        
        records = []
        for _, row in df.iterrows():
            records.append({
                "accession_number": row["ACCESSION_NUMBER"],
                "infotable_sk": safe_int(row["INFOTABLE_SK"]),
                "name_of_issuer": row["NAMEOFISSUER"],
                "title_of_class": row["TITLEOFCLASS"],
                "cusip": row["CUSIP"],
                "figi": safe_str(row.get("FIGI")),
                "value": safe_int(row["VALUE"]),
                "ssh_prn_amt": safe_int(row["SSHPRNAMT"]),
                "ssh_prn_amt_type": row["SSHPRNAMTTYPE"],
                "put_call": safe_str(row.get("PUTCALL")),
                "investment_discretion": row["INVESTMENTDISCRETION"],
                "other_manager": safe_str(row.get("OTHERMANAGER")),
                "voting_auth_sole": safe_int(row["VOTING_AUTH_SOLE"]),
                "voting_auth_shared": safe_int(row["VOTING_AUTH_SHARED"]),
                "voting_auth_none": safe_int(row["VOTING_AUTH_NONE"]),
            })
            
            if len(records) >= batch_size:
                _upsert_batch(session, InfoTable, records)
                records = []
        
        if records:
            _upsert_batch(session, InfoTable, records)
        
        session.commit()
        total_records += len(df)
        print(f"  Loaded {len(df)} records from {chunk_file.name}")
    
    print(f"Total infotable records loaded: {total_records}")


def load_company_ticker_data(data_dir: str, session: Session, batch_size: int = 1000):
    """Load company_ticker.csv data into the database."""
    filepath = Path(data_dir) / "company_ticker.csv"
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
    
    print(f"Loading {filepath}...")
    df = pd.read_csv(filepath, dtype=str)
    
    records = []
    for _, row in df.iterrows():
        records.append({
            "company_name": row["company_name"],
            "ticker": row["ticker"],
            "sector": safe_str(row.get("sector")),
            "source": safe_str(row.get("source")),
            "last_updated": parse_date(row.get("last_updated", "")),
        })
        
        if len(records) >= batch_size:
            _insert_batch(session, CompanyTicker, records)
            records = []
    
    if records:
        _insert_batch(session, CompanyTicker, records)
    
    session.commit()
    print(f"Loaded {len(df)} company_ticker records")


def _upsert_batch(session: Session, model, records: list):
    """Insert or update a batch of records using PostgreSQL's ON CONFLICT."""
    if not records:
        return
    
    # Get primary key columns
    pk_columns = [col.name for col in model.__table__.primary_key.columns]
    
    # Deduplicate records within the batch (keep last occurrence)
    # This prevents "ON CONFLICT DO UPDATE command cannot affect row a second time" error
    seen = {}
    for record in records:
        pk_key = tuple(record.get(col) for col in pk_columns)
        seen[pk_key] = record
    deduped_records = list(seen.values())
    
    stmt = insert(model.__table__).values(deduped_records)
    
    # Create update dict excluding primary key columns
    update_dict = {
        col.name: stmt.excluded[col.name]
        for col in model.__table__.columns
        if col.name not in pk_columns and col.name not in ["created_at"]
    }
    
    stmt = stmt.on_conflict_do_update(
        index_elements=pk_columns,
        set_=update_dict
    )
    
    session.execute(stmt)


def _insert_batch(session: Session, model, records: list):
    """Insert a batch of records, ignoring conflicts."""
    if not records:
        return
    
    stmt = insert(model.__table__).values(records)
    stmt = stmt.on_conflict_do_nothing()
    session.execute(stmt)


def load_all_data(data_dir: str = "data"):
    """Load all Form 13F data from TSV files into the database."""
    engine = get_engine()
    session = get_session(engine)
    
    try:
        # Create schema and tables
        create_tables(engine)
        
        # Load data in correct order (respecting foreign key constraints)
        print("\n=== Loading Form 13F Data ===\n")
        
        load_submission_data(data_dir, session)
        load_coverpage_data(data_dir, session)
        load_summarypage_data(data_dir, session)
        load_signature_data(data_dir, session)
        load_othermanager_data(data_dir, session)
        load_othermanager2_data(data_dir, session)
        load_infotable_data(data_dir, session)
        load_company_ticker_data(data_dir, session)
        
        print("\n=== Data loading complete ===\n")
        
    except Exception as e:
        session.rollback()
        print(f"Error loading data: {e}")
        raise
    finally:
        session.close()


# ============================================================
# Query Utilities
# ============================================================

def get_filing_by_accession(session: Session, accession_number: str) -> Optional[Submission]:
    """Get a filing by its accession number with all related data."""
    return session.query(Submission).filter(
        Submission.accession_number == accession_number
    ).first()


def get_filings_by_manager(session: Session, manager_name: str, limit: int = 100):
    """Get filings by manager name (partial match)."""
    return session.query(Submission).join(CoverPage).filter(
        CoverPage.filingmanager_name.ilike(f"%{manager_name}%")
    ).limit(limit).all()


def get_holdings_by_cusip(session: Session, cusip: str):
    """Get all holdings for a specific CUSIP."""
    return session.query(InfoTable).filter(
        InfoTable.cusip == cusip
    ).all()


def get_holdings_by_issuer(session: Session, issuer_name: str, limit: int = 1000):
    """Get holdings by issuer name (partial match)."""
    return session.query(InfoTable).filter(
        InfoTable.name_of_issuer.ilike(f"%{issuer_name}%")
    ).limit(limit).all()


def get_top_holdings(session: Session, accession_number: str, limit: int = 20):
    """Get top holdings by value for a specific filing."""
    return session.query(InfoTable).filter(
        InfoTable.accession_number == accession_number
    ).order_by(InfoTable.value.desc()).limit(limit).all()


# ============================================================
# CLI Entry Point
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Form 13F Database Utility")
    parser.add_argument("--action", choices=["create", "drop", "load", "load-all"], 
                        default="load-all", help="Action to perform")
    parser.add_argument("--data-dir", default="data", help="Directory containing data files")
    parser.add_argument("--echo", action="store_true", help="Echo SQL statements")
    
    args = parser.parse_args()
    
    engine = get_engine(echo=args.echo)
    
    if args.action == "create":
        create_tables(engine)
    elif args.action == "drop":
        response = input("Are you sure you want to drop all tables? (yes/no): ")
        if response.lower() == "yes":
            drop_tables(engine)
    elif args.action in ["load", "load-all"]:
        load_all_data(args.data_dir)

