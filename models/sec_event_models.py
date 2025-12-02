"""
SQLAlchemy models for 13D/13G SEC events.
Represents activist and passive stake accumulation filings.
"""

import os
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    Date,
    Text,
    Boolean,
    Numeric,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base

# Get schema from environment
DB_SCHEMA = os.getenv("DB_SCHEMA", "hedgefolio")

Base = declarative_base()


class SecEvent(Base):
    """Core 13D/13G event data - activist and passive stake accumulation filings."""
    
    __tablename__ = "sec_event"
    __table_args__ = (
        Index("idx_sec_event_filing_date", "filing_date"),
        Index("idx_sec_event_form_type", "form_type"),
        Index("idx_sec_event_filer_name", "filer_name"),
        Index("idx_sec_event_target_company", "target_company_name"),
        Index("idx_sec_event_target_ticker", "target_ticker"),
        Index("idx_sec_event_filing_date_form_type", "filing_date", "form_type"),
        {"schema": DB_SCHEMA}
    )
    
    event_id = Column(Integer, primary_key=True, autoincrement=True)
    accession_number = Column(String(25), unique=True, nullable=False)
    filing_date = Column(Date, nullable=False, index=True)
    form_type = Column(String(10), nullable=False, index=True)  # '13D' or '13G'
    cik = Column(String(10), nullable=False)
    filer_name = Column(String(200), nullable=False, index=True)
    filer_address = Column(Text)
    target_cik = Column(String(10))
    target_company_name = Column(String(200), nullable=False, index=True)
    target_ticker = Column(String(20), index=True)
    stake_percentage = Column(Numeric(5, 2))
    shares_owned = Column(BigInteger)
    shares_outstanding = Column(BigInteger)
    filing_status = Column(String(20))  # 'Initial', 'Amendment'
    amendment_number = Column(Integer)
    is_amendment = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    intent = relationship(
        "SecEventIntent",
        back_populates="event",
        uselist=False,
        cascade="all, delete-orphan"
    )
    amendments = relationship(
        "SecEventAmendment",
        back_populates="parent_event",
        cascade="all, delete-orphan"
    )
    group_members = relationship(
        "SecEventGroupMember",
        back_populates="event",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return (
            f"<SecEvent(accession={self.accession_number}, "
            f"form={self.form_type}, filer={self.filer_name}, "
            f"target={self.target_company_name})>"
        )


class SecEventIntent(Base):
    """13D activist intent and strategy information."""
    
    __tablename__ = "sec_event_intent"
    __table_args__ = (
        Index("idx_sec_event_intent_accession", "accession_number"),
        {"schema": DB_SCHEMA}
    )
    
    intent_id = Column(Integer, primary_key=True, autoincrement=True)
    accession_number = Column(
        String(25),
        ForeignKey(f"{DB_SCHEMA}.sec_event.accession_number", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    intent_type = Column(String(50))  # 'Activist', 'M&A', 'Passive', 'Other'
    purpose_description = Column(Text)
    plans_or_proposals = Column(Text)
    background_of_filer = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    event = relationship("SecEvent", back_populates="intent")
    
    def __repr__(self):
        return (
            f"<SecEventIntent(accession={self.accession_number}, "
            f"intent_type={self.intent_type})>"
        )


class SecEventAmendment(Base):
    """Amendment history for 13D/13G filings."""
    
    __tablename__ = "sec_event_amendment"
    __table_args__ = (
        Index("idx_sec_event_amendment_parent", "parent_accession_number"),
        Index("idx_sec_event_amendment_date", "amendment_date"),
        Index("idx_sec_event_amendment_parent_date", "parent_accession_number", "amendment_date"),
        {"schema": DB_SCHEMA}
    )
    
    amendment_id = Column(Integer, primary_key=True, autoincrement=True)
    parent_accession_number = Column(
        String(25),
        ForeignKey(f"{DB_SCHEMA}.sec_event.accession_number", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    amendment_accession_number = Column(String(25), unique=True, nullable=False)
    amendment_date = Column(Date, nullable=False, index=True)
    amendment_number = Column(Integer)
    amendment_description = Column(Text)
    previous_stake_percentage = Column(Numeric(5, 2))
    new_stake_percentage = Column(Numeric(5, 2))
    previous_shares = Column(BigInteger)
    new_shares = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    parent_event = relationship("SecEvent", back_populates="amendments")
    
    def __repr__(self):
        return (
            f"<SecEventAmendment(parent={self.parent_accession_number}, "
            f"amendment={self.amendment_number})>"
        )


class SecEventGroupMember(Base):
    """Group members for group 13D/13G filings."""
    
    __tablename__ = "sec_event_group_member"
    __table_args__ = (
        Index("idx_sec_event_group_member_accession", "accession_number"),
        {"schema": DB_SCHEMA}
    )
    
    member_id = Column(Integer, primary_key=True, autoincrement=True)
    accession_number = Column(
        String(25),
        ForeignKey(f"{DB_SCHEMA}.sec_event.accession_number", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    member_name = Column(String(200), nullable=False)
    member_cik = Column(String(10))
    member_address = Column(Text)
    member_relationship = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    event = relationship("SecEvent", back_populates="group_members")
    
    def __repr__(self):
        return (
            f"<SecEventGroupMember(accession={self.accession_number}, "
            f"member={self.member_name})>"
        )
