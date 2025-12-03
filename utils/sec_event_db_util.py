"""
Database utilities for SEC 13D/13G events.
Handles insertion, querying, and management of event data.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from models.sec_event_models import (
    SecEvent,
    SecEventIntent,
    SecEventAmendment,
    SecEventGroupMember,
)
from utils.sec_event_processor import validate_filing_data

logger = logging.getLogger(__name__)


def insert_sec_event(session: Session, event_data: Dict) -> Optional[SecEvent]:
    """
    Insert a new 13D/13G event into database.
    
    Args:
        session (Session): SQLAlchemy session
        event_data (Dict): Normalized event data
    
    Returns:
        Optional[SecEvent]: Inserted SecEvent object or None on failure
    """
    try:
        # Validate data
        is_valid, errors = validate_filing_data(event_data)
        if not is_valid:
            logger.warning(f"Validation failed: {errors}")
            return None
        
        # Check for duplicate
        existing = session.query(SecEvent).filter(
            SecEvent.accession_number == event_data.get('accession_number')
        ).first()
        
        if existing:
            logger.info(f"Event already exists: {event_data.get('accession_number')}")
            return existing
        
        # Create new event
        event = SecEvent(
            accession_number=event_data.get('accession_number'),
            filing_date=event_data.get('filing_date'),
            form_type=event_data.get('form_type'),
            cik=event_data.get('cik'),
            filer_name=event_data.get('filer_name'),
            filer_address=event_data.get('filer_address'),
            target_cik=event_data.get('target_cik'),
            target_company_name=event_data.get('target_company_name'),
            target_ticker=event_data.get('target_ticker'),
            stake_percentage=event_data.get('stake_percentage'),
            shares_owned=event_data.get('shares_owned'),
            shares_outstanding=event_data.get('shares_outstanding'),
            filing_status=event_data.get('filing_status', 'Initial'),
            amendment_number=event_data.get('amendment_number'),
            is_amendment=event_data.get('is_amendment', False),
        )
        
        session.add(event)
        session.commit()
        
        logger.info(f"Inserted event: {event.accession_number}")
        return event
    
    except Exception as e:
        logger.error(f"Error inserting event: {e}")
        session.rollback()
        return None


def insert_sec_event_intent(session: Session, intent_data: Dict) -> Optional[SecEventIntent]:
    """
    Insert activist intent information (13D only).
    
    Args:
        session (Session): SQLAlchemy session
        intent_data (Dict): Intent data with accession_number
    
    Returns:
        Optional[SecEventIntent]: Inserted SecEventIntent object or None
    """
    try:
        # Check if event exists
        event = session.query(SecEvent).filter(
            SecEvent.accession_number == intent_data.get('accession_number')
        ).first()
        
        if not event:
            logger.warning(f"Parent event not found: {intent_data.get('accession_number')}")
            return None
        
        # Check if intent already exists
        existing = session.query(SecEventIntent).filter(
            SecEventIntent.accession_number == intent_data.get('accession_number')
        ).first()
        
        if existing:
            logger.info(f"Intent already exists: {intent_data.get('accession_number')}")
            return existing
        
        # Create intent
        intent = SecEventIntent(
            accession_number=intent_data.get('accession_number'),
            intent_type=intent_data.get('intent_type'),
            purpose_description=intent_data.get('purpose_description'),
            plans_or_proposals=intent_data.get('plans_or_proposals'),
            background_of_filer=intent_data.get('background_of_filer'),
        )
        
        session.add(intent)
        session.commit()
        
        logger.info(f"Inserted intent: {intent.accession_number}")
        return intent
    
    except Exception as e:
        logger.error(f"Error inserting intent: {e}")
        session.rollback()
        return None


def insert_amendment(session: Session, amendment_data: Dict) -> Optional[SecEventAmendment]:
    """
    Insert amendment record.
    
    Args:
        session (Session): SQLAlchemy session
        amendment_data (Dict): Amendment data
    
    Returns:
        Optional[SecEventAmendment]: Inserted SecEventAmendment object or None
    """
    try:
        # Verify parent event exists
        parent = session.query(SecEvent).filter(
            SecEvent.accession_number == amendment_data.get('parent_accession_number')
        ).first()
        
        if not parent:
            logger.warning(f"Parent event not found: {amendment_data.get('parent_accession_number')}")
            return None
        
        # Check for duplicate
        existing = session.query(SecEventAmendment).filter(
            SecEventAmendment.amendment_accession_number == amendment_data.get('amendment_accession_number')
        ).first()
        
        if existing:
            logger.info(f"Amendment already exists: {amendment_data.get('amendment_accession_number')}")
            return existing
        
        # Create amendment
        amendment = SecEventAmendment(
            parent_accession_number=amendment_data.get('parent_accession_number'),
            amendment_accession_number=amendment_data.get('amendment_accession_number'),
            amendment_date=amendment_data.get('amendment_date'),
            amendment_number=amendment_data.get('amendment_number'),
            amendment_description=amendment_data.get('amendment_description'),
            previous_stake_percentage=amendment_data.get('previous_stake_percentage'),
            new_stake_percentage=amendment_data.get('new_stake_percentage'),
            previous_shares=amendment_data.get('previous_shares'),
            new_shares=amendment_data.get('new_shares'),
        )
        
        session.add(amendment)
        session.commit()
        
        logger.info(f"Inserted amendment: {amendment.amendment_accession_number}")
        return amendment
    
    except Exception as e:
        logger.error(f"Error inserting amendment: {e}")
        session.rollback()
        return None


def insert_group_member(session: Session, member_data: Dict) -> Optional[SecEventGroupMember]:
    """
    Insert group member record.
    
    Args:
        session (Session): SQLAlchemy session
        member_data (Dict): Member data with accession_number
    
    Returns:
        Optional[SecEventGroupMember]: Inserted SecEventGroupMember object or None
    """
    try:
        # Verify event exists
        event = session.query(SecEvent).filter(
            SecEvent.accession_number == member_data.get('accession_number')
        ).first()
        
        if not event:
            logger.warning(f"Event not found: {member_data.get('accession_number')}")
            return None
        
        # Create group member
        member = SecEventGroupMember(
            accession_number=member_data.get('accession_number'),
            member_name=member_data.get('member_name'),
            member_cik=member_data.get('member_cik'),
            member_address=member_data.get('member_address'),
            member_relationship=member_data.get('member_relationship'),
        )
        
        session.add(member)
        session.commit()
        
        logger.info(f"Inserted group member: {member.member_name}")
        return member
    
    except Exception as e:
        logger.error(f"Error inserting group member: {e}")
        session.rollback()
        return None


def get_recent_events(session: Session, days: int = 30, limit: int = 100) -> List[SecEvent]:
    """
    Get recent 13D/13G events.
    
    Args:
        session (Session): SQLAlchemy session
        days (int): Number of days to look back
        limit (int): Maximum results to return
    
    Returns:
        List[SecEvent]: List of SecEvent objects
    """
    try:
        cutoff_date = datetime.now().date() - timedelta(days=days)
        
        events = session.query(SecEvent).filter(
            SecEvent.filing_date >= cutoff_date
        ).order_by(
            desc(SecEvent.filing_date)
        ).limit(limit).all()
        
        logger.info(f"Retrieved {len(events)} recent events from last {days} days")
        return events
    
    except Exception as e:
        logger.error(f"Error retrieving recent events: {e}")
        session.rollback()
        return []


def get_events_by_ticker(session: Session, ticker: str, limit: int = 50) -> List[SecEvent]:
    """
    Get events for a specific ticker.
    
    Args:
        session (Session): SQLAlchemy session
        ticker (str): Stock ticker symbol
        limit (int): Maximum results
    
    Returns:
        List[SecEvent]: List of SecEvent objects
    """
    try:
        events = session.query(SecEvent).filter(
            SecEvent.target_ticker == ticker.upper()
        ).order_by(
            desc(SecEvent.filing_date)
        ).limit(limit).all()
        
        logger.info(f"Retrieved {len(events)} events for ticker {ticker}")
        return events
    
    except Exception as e:
        logger.error(f"Error retrieving events by ticker: {e}")
        session.rollback()
        return []


def get_events_by_filer(session: Session, filer_name: str, limit: int = 50) -> List[SecEvent]:
    """
    Get events filed by a specific filer.
    
    Args:
        session (Session): SQLAlchemy session
        filer_name (str): Filer name (partial match)
        limit (int): Maximum results
    
    Returns:
        List[SecEvent]: List of SecEvent objects
    """
    try:
        events = session.query(SecEvent).filter(
            SecEvent.filer_name.ilike(f"%{filer_name}%")
        ).order_by(
            desc(SecEvent.filing_date)
        ).limit(limit).all()
        
        logger.info(f"Retrieved {len(events)} events for filer {filer_name}")
        return events
    
    except Exception as e:
        logger.error(f"Error retrieving events by filer: {e}")
        session.rollback()
        return []


def get_activist_events(session: Session, days: int = 90, limit: int = 50) -> List[Dict]:
    """
    Get 13D activist events with intent information.
    
    Args:
        session (Session): SQLAlchemy session
        days (int): Days to look back
        limit (int): Maximum results
    
    Returns:
        List[Dict]: List of events with intent data
    """
    try:
        cutoff_date = datetime.now().date() - timedelta(days=days)
        
        events = session.query(SecEvent).filter(
            and_(
                SecEvent.form_type == '13D',
                SecEvent.filing_date >= cutoff_date
            )
        ).order_by(
            desc(SecEvent.filing_date)
        ).limit(limit).all()
        
        # Convert to dicts with intent info
        result = []
        for event in events:
            event_dict = {
                'event_id': event.event_id,
                'accession_number': event.accession_number,
                'filing_date': event.filing_date,
                'filer_name': event.filer_name,
                'target_company_name': event.target_company_name,
                'target_ticker': event.target_ticker,
                'stake_percentage': float(event.stake_percentage) if event.stake_percentage else None,
                'shares_owned': event.shares_owned,
                'intent_type': event.intent.intent_type if event.intent else None,
                'purpose': event.intent.purpose_description if event.intent else None,
            }
            result.append(event_dict)
        
        logger.info(f"Retrieved {len(result)} activist events from last {days} days")
        return result
    
    except Exception as e:
        logger.error(f"Error retrieving activist events: {e}")
        session.rollback()
        return []


def get_amendment_history(session: Session, parent_accession: str) -> List[SecEventAmendment]:
    """
    Get amendment history for a filing.
    
    Args:
        session (Session): SQLAlchemy session
        parent_accession (str): Parent accession number
    
    Returns:
        List[SecEventAmendment]: List of amendments ordered by date
    """
    try:
        amendments = session.query(SecEventAmendment).filter(
            SecEventAmendment.parent_accession_number == parent_accession
        ).order_by(
            SecEventAmendment.amendment_date
        ).all()
        
        logger.info(f"Retrieved {len(amendments)} amendments for {parent_accession}")
        return amendments
    
    except Exception as e:
        logger.error(f"Error retrieving amendment history: {e}")
        session.rollback()
        return []


def get_stake_timeline(
    session: Session,
    target_company: str,
    filer_name: str
) -> List[Dict]:
    """
    Get timeline of stake changes for a filer/company pair.
    
    Args:
        session (Session): SQLAlchemy session
        target_company (str): Target company name
        filer_name (str): Filer name
    
    Returns:
        List[Dict]: List of events and amendments ordered chronologically
    """
    try:
        # Get initial filing
        initial_event = session.query(SecEvent).filter(
            and_(
                SecEvent.target_company_name.ilike(f"%{target_company}%"),
                SecEvent.filer_name.ilike(f"%{filer_name}%"),
                SecEvent.is_amendment == False
            )
        ).first()
        
        if not initial_event:
            logger.warning(f"No initial event found for {target_company} / {filer_name}")
            return []
        
        timeline = []
        
        # Add initial event
        timeline.append({
            'date': initial_event.filing_date,
            'accession_number': initial_event.accession_number,
            'event_type': 'Initial',
            'stake_percentage': float(initial_event.stake_percentage) if initial_event.stake_percentage else None,
            'shares': initial_event.shares_owned,
        })
        
        # Get amendments
        amendments = get_amendment_history(session, initial_event.accession_number)
        for amendment in amendments:
            timeline.append({
                'date': amendment.amendment_date,
                'accession_number': amendment.amendment_accession_number,
                'event_type': 'Amendment',
                'amendment_number': amendment.amendment_number,
                'previous_stake': float(amendment.previous_stake_percentage) if amendment.previous_stake_percentage else None,
                'new_stake': float(amendment.new_stake_percentage) if amendment.new_stake_percentage else None,
                'previous_shares': amendment.previous_shares,
                'new_shares': amendment.new_shares,
            })
        
        # Sort by date
        timeline.sort(key=lambda x: x['date'])
        
        logger.info(f"Retrieved timeline with {len(timeline)} events")
        return timeline
    
    except Exception as e:
        logger.error(f"Error retrieving stake timeline: {e}")
        session.rollback()
        return []


def update_event_status(session: Session, accession_number: str, status: str) -> Optional[SecEvent]:
    """
    Update filing status.
    
    Args:
        session (Session): SQLAlchemy session
        accession_number (str): Accession number
        status (str): New status
    
    Returns:
        Optional[SecEvent]: Updated SecEvent object or None
    """
    try:
        event = session.query(SecEvent).filter(
            SecEvent.accession_number == accession_number
        ).first()
        
        if not event:
            logger.warning(f"Event not found: {accession_number}")
            return None
        
        event.filing_status = status
        event.updated_at = datetime.utcnow()
        session.commit()
        
        logger.info(f"Updated status for {accession_number} to {status}")
        return event
    
    except Exception as e:
        logger.error(f"Error updating event status: {e}")
        session.rollback()
        return None


def get_event_statistics(session: Session, days: int = 30) -> Dict:
    """
    Get statistics about recent events.
    
    Args:
        session (Session): SQLAlchemy session
        days (int): Days to look back
    
    Returns:
        Dict: Statistics dictionary
    """
    try:
        cutoff_date = datetime.now().date() - timedelta(days=days)
        
        total_events = session.query(func.count(SecEvent.event_id)).filter(
            SecEvent.filing_date >= cutoff_date
        ).scalar()
        
        total_13d = session.query(func.count(SecEvent.event_id)).filter(
            and_(
                SecEvent.form_type == '13D',
                SecEvent.filing_date >= cutoff_date
            )
        ).scalar()
        
        total_13g = session.query(func.count(SecEvent.event_id)).filter(
            and_(
                SecEvent.form_type == '13G',
                SecEvent.filing_date >= cutoff_date
            )
        ).scalar()
        
        avg_stake = session.query(func.avg(SecEvent.stake_percentage)).filter(
            SecEvent.filing_date >= cutoff_date
        ).scalar()
        
        stats = {
            'total_events': total_events or 0,
            'total_13d': total_13d or 0,
            'total_13g': total_13g or 0,
            'average_stake_percentage': float(avg_stake) if avg_stake else 0,
            'period_days': days,
        }
        
        logger.info(f"Event statistics: {stats}")
        return stats
    
    except Exception as e:
        logger.error(f"Error retrieving event statistics: {e}")
        session.rollback()
        return {}


def get_top_filers(session: Session, limit: int = 10) -> List[Dict]:
    """
    Get top activist filers by number of filings.
    
    Args:
        session (Session): SQLAlchemy session
        limit (int): Number of filers to return
    
    Returns:
        List[Dict]: List of top filers with statistics
    """
    try:
        filers = session.query(
            SecEvent.filer_name,
            func.count(SecEvent.event_id).label('filing_count'),
            func.count(func.distinct(SecEvent.target_company_name)).label('unique_targets'),
            func.avg(SecEvent.stake_percentage).label('avg_stake'),
            func.max(SecEvent.filing_date).label('latest_filing'),
        ).filter(
            SecEvent.form_type == '13D'
        ).group_by(
            SecEvent.filer_name
        ).order_by(
            desc('filing_count')
        ).limit(limit).all()
        
        result = []
        for filer in filers:
            result.append({
                'filer_name': filer.filer_name,
                'filing_count': filer.filing_count,
                'unique_targets': filer.unique_targets,
                'average_stake': float(filer.avg_stake) if filer.avg_stake else 0,
                'latest_filing': filer.latest_filing,
            })
        
        logger.info(f"Retrieved top {len(result)} filers")
        return result
    
    except Exception as e:
        logger.error(f"Error retrieving top filers: {e}")
        session.rollback()
        return []


def get_top_targets(session: Session, limit: int = 10) -> List[Dict]:
    """
    Get most targeted companies by activists.
    
    Args:
        session (Session): SQLAlchemy session
        limit (int): Number of targets to return
    
    Returns:
        List[Dict]: List of most targeted companies
    """
    try:
        targets = session.query(
            SecEvent.target_company_name,
            SecEvent.target_ticker,
            func.count(SecEvent.event_id).label('event_count'),
            func.count(func.distinct(SecEvent.filer_name)).label('unique_filers'),
            func.max(SecEvent.stake_percentage).label('max_stake'),
        ).filter(
            SecEvent.form_type == '13D'
        ).group_by(
            SecEvent.target_company_name,
            SecEvent.target_ticker
        ).order_by(
            desc('event_count')
        ).limit(limit).all()
        
        result = []
        for target in targets:
            result.append({
                'company_name': target.target_company_name,
                'ticker': target.target_ticker,
                'event_count': target.event_count,
                'unique_filers': target.unique_filers,
                'max_stake': float(target.max_stake) if target.max_stake else 0,
            })
        
        logger.info(f"Retrieved top {len(result)} targets")
        return result
    
    except Exception as e:
        logger.error(f"Error retrieving top targets: {e}")
        session.rollback()
        return []
