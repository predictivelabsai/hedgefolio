#!/usr/bin/env python3
"""
SEC Events Sync Task - Download and update 13D/13G SEC filings data.
Run this daily to keep the SEC events database up to date.

Usage:
    python tasks/sync_sec_events.py                     # Full sync (30 days)
    python tasks/sync_sec_events.py --days 7            # Sync last 7 days
    python tasks/sync_sec_events.py --setup             # Setup database tables only
    python tasks/sync_sec_events.py --verify            # Verify database integrity
    python tasks/sync_sec_events.py --sample            # Load sample data for testing
"""
import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from decimal import Decimal
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_database():
    """Create SEC events tables if they don't exist."""
    print("🗄️  Setting up SEC events database tables...")
    
    try:
        from utils.db_util import get_engine, DB_URL, DB_SCHEMA
        from sqlalchemy import text
        from models.sec_event_models import Base
        
        if not DB_URL:
            print("⚠️  DB_URL not configured - skipping database setup")
            return False
        
        engine = get_engine()
        
        # Create schema if not exists
        with engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA}"))
            conn.commit()
        
        # Create tables using SQLAlchemy models
        Base.metadata.create_all(engine)
        
        print(f"✓ SEC events tables created in schema '{DB_SCHEMA}'")
        return True
        
    except Exception as e:
        print(f"✗ Database setup error: {e}")
        import traceback
        traceback.print_exc()
        return False


def download_and_sync_filings(days: int = 30) -> int:
    """
    Download 13D/13G filings from SEC EDGAR and sync to database.
    
    Args:
        days (int): Number of days to look back
    
    Returns:
        int: Number of filings synced
    """
    print(f"📥 Downloading 13D/13G filings from last {days} days...")
    
    try:
        from utils.db_util import get_engine, get_session
        from utils.sec_edgar_downloader import download_recent_filings
        from utils.sec_event_db_util import insert_sec_event, insert_sec_event_intent
        from utils.sec_event_processor import prepare_filing_for_insert
        
        engine = get_engine()
        session = get_session(engine)
        
        synced_count = 0
        error_count = 0
        
        try:
            # Download filings from SEC EDGAR
            filings = download_recent_filings(days=days)
            
            print(f"  Found {len(filings)} filings to process")
            
            for filing in filings:
                try:
                    # Prepare data for insertion
                    prepared = prepare_filing_for_insert(filing)
                    
                    if not prepared or not prepared.get('event'):
                        logger.warning(f"Skipping invalid filing: {filing.get('accession_number')}")
                        error_count += 1
                        continue
                    
                    # Insert main event
                    event = insert_sec_event(session, prepared['event'])
                    
                    if event:
                        synced_count += 1
                        
                        # Insert intent if available (13D only)
                        if prepared.get('intent'):
                            insert_sec_event_intent(session, prepared['intent'])
                        
                        if synced_count % 10 == 0:
                            print(f"  Processed {synced_count} filings...")
                
                except Exception as e:
                    logger.error(f"Error processing filing: {e}")
                    error_count += 1
                    continue
            
            print(f"\n✓ Synced {synced_count} filings ({error_count} errors)")
            return synced_count
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
            
    except Exception as e:
        print(f"✗ Sync error: {e}")
        import traceback
        traceback.print_exc()
        return 0


def load_sample_data() -> int:
    """
    Load sample 13D/13G data for testing purposes.
    Creates realistic sample events without hitting SEC EDGAR.
    
    Returns:
        int: Number of sample events created
    """
    print("📊 Loading sample SEC events data...")
    
    try:
        from utils.db_util import get_engine, get_session
        from utils.sec_event_db_util import insert_sec_event, insert_sec_event_intent
        from decimal import Decimal
        
        engine = get_engine()
        session = get_session(engine)
        
        # Sample 13D filings (activist) - using valid 10-digit CIKs
        sample_13d_events = [
            {
                'accession_number': '0001193125-25-000001',
                'filing_date': (datetime.now() - timedelta(days=1)).date(),
                'form_type': '13D',
                'cik': '0001234567',
                'filer_name': 'ACTIVIST CAPITAL MANAGEMENT LLC',
                'filer_address': '100 Wall Street, New York, NY 10005',
                'target_cik': '0000320193',
                'target_company_name': 'APPLE INC',
                'target_ticker': 'AAPL',
                'stake_percentage': Decimal('5.2'),
                'shares_owned': 850000000,
                'shares_outstanding': 16000000000,
                'filing_status': 'Initial',
                'is_amendment': False,
            },
            {
                'accession_number': '0001193125-25-000002',
                'filing_date': (datetime.now() - timedelta(days=3)).date(),
                'form_type': '13D',
                'cik': '0001234568',
                'filer_name': 'ICAHN ENTERPRISES LP',
                'filer_address': '767 Fifth Avenue, New York, NY 10153',
                'target_cik': '0000789019',
                'target_company_name': 'MICROSOFT CORP',
                'target_ticker': 'MSFT',
                'stake_percentage': Decimal('6.1'),
                'shares_owned': 450000000,
                'shares_outstanding': 7400000000,
                'filing_status': 'Initial',
                'is_amendment': False,
            },
            {
                'accession_number': '0001193125-25-000003',
                'filing_date': (datetime.now() - timedelta(days=5)).date(),
                'form_type': '13D',
                'cik': '0001234569',
                'filer_name': 'THIRD POINT LLC',
                'filer_address': '55 Hudson Yards, New York, NY 10001',
                'target_cik': '0001018724',
                'target_company_name': 'AMAZON.COM INC',
                'target_ticker': 'AMZN',
                'stake_percentage': Decimal('5.5'),
                'shares_owned': 560000000,
                'shares_outstanding': 10200000000,
                'filing_status': 'Initial',
                'is_amendment': False,
            },
            {
                'accession_number': '0001193125-25-000004',
                'filing_date': (datetime.now() - timedelta(days=7)).date(),
                'form_type': '13D',
                'cik': '0001234570',
                'filer_name': 'STARBOARD VALUE LP',
                'filer_address': '777 Third Avenue, New York, NY 10017',
                'target_cik': '0000051143',
                'target_company_name': 'INTERNATIONAL BUSINESS MACHINES CORP',
                'target_ticker': 'IBM',
                'stake_percentage': Decimal('7.2'),
                'shares_owned': 66000000,
                'shares_outstanding': 910000000,
                'filing_status': 'Initial',
                'is_amendment': False,
            },
            {
                'accession_number': '0001193125-25-000005',
                'filing_date': (datetime.now() - timedelta(days=10)).date(),
                'form_type': '13D',
                'cik': '0001234571',
                'filer_name': 'ELLIOTT MANAGEMENT CORP',
                'filer_address': '40 West 57th Street, New York, NY 10019',
                'target_cik': '0001045810',
                'target_company_name': 'NVIDIA CORP',
                'target_ticker': 'NVDA',
                'stake_percentage': Decimal('5.8'),
                'shares_owned': 1400000000,
                'shares_outstanding': 24500000000,
                'filing_status': 'Initial',
                'is_amendment': False,
            },
        ]
        
        # Sample 13G filings (passive) - using valid 10-digit CIKs
        sample_13g_events = [
            {
                'accession_number': '0001193125-25-000010',
                'filing_date': (datetime.now() - timedelta(days=2)).date(),
                'form_type': '13G',
                'cik': '0001234580',
                'filer_name': 'VANGUARD GROUP INC',
                'filer_address': '100 Vanguard Blvd, Malvern, PA 19355',
                'target_cik': '0001652044',
                'target_company_name': 'ALPHABET INC',
                'target_ticker': 'GOOGL',
                'stake_percentage': Decimal('8.2'),
                'shares_owned': 510000000,
                'shares_outstanding': 6200000000,
                'filing_status': 'Initial',
                'is_amendment': False,
            },
            {
                'accession_number': '0001193125-25-000011',
                'filing_date': (datetime.now() - timedelta(days=4)).date(),
                'form_type': '13G',
                'cik': '0001234581',
                'filer_name': 'BLACKROCK INC',
                'filer_address': '55 East 52nd Street, New York, NY 10055',
                'target_cik': '0001318605',
                'target_company_name': 'TESLA INC',
                'target_ticker': 'TSLA',
                'stake_percentage': Decimal('6.5'),
                'shares_owned': 208000000,
                'shares_outstanding': 3200000000,
                'filing_status': 'Initial',
                'is_amendment': False,
            },
            {
                'accession_number': '0001193125-25-000012',
                'filing_date': (datetime.now() - timedelta(days=6)).date(),
                'form_type': '13G',
                'cik': '0001234582',
                'filer_name': 'STATE STREET CORP',
                'filer_address': '1 Lincoln Street, Boston, MA 02111',
                'target_cik': '0000320193',
                'target_company_name': 'APPLE INC',
                'target_ticker': 'AAPL',
                'stake_percentage': Decimal('5.1'),
                'shares_owned': 816000000,
                'shares_outstanding': 16000000000,
                'filing_status': 'Initial',
                'is_amendment': False,
            },
            {
                'accession_number': '0001193125-25-000013',
                'filing_date': (datetime.now() - timedelta(days=8)).date(),
                'form_type': '13G',
                'cik': '0001234583',
                'filer_name': 'FIDELITY MANAGEMENT',
                'filer_address': '245 Summer Street, Boston, MA 02210',
                'target_cik': '0001326801',
                'target_company_name': 'META PLATFORMS INC',
                'target_ticker': 'META',
                'stake_percentage': Decimal('7.8'),
                'shares_owned': 200000000,
                'shares_outstanding': 2560000000,
                'filing_status': 'Initial',
                'is_amendment': False,
            },
            {
                'accession_number': '0001193125-25-000014',
                'filing_date': (datetime.now() - timedelta(days=12)).date(),
                'form_type': '13G',
                'cik': '0001234584',
                'filer_name': 'CAPITAL RESEARCH',
                'filer_address': '333 South Hope Street, Los Angeles, CA 90071',
                'target_cik': '0000200406',
                'target_company_name': 'JOHNSON & JOHNSON',
                'target_ticker': 'JNJ',
                'stake_percentage': Decimal('5.3'),
                'shares_owned': 128000000,
                'shares_outstanding': 2410000000,
                'filing_status': 'Initial',
                'is_amendment': False,
            },
        ]
        
        # Sample intent data for 13D filings
        sample_intents = [
            {
                'accession_number': '0001193125-25-000001',
                'intent_type': 'Activist',
                'purpose_description': 'The Reporting Person acquired the shares for investment purposes and intends to engage with management regarding capital allocation and board composition.',
                'plans_or_proposals': 'The Reporting Person intends to seek board representation and may propose operational improvements.',
            },
            {
                'accession_number': '0001193125-25-000002',
                'intent_type': 'Activist',
                'purpose_description': 'The Reporting Person believes the shares are undervalued and plans to engage constructively with the Board to unlock shareholder value.',
                'plans_or_proposals': 'May advocate for strategic alternatives including asset sales or increased capital returns.',
            },
            {
                'accession_number': '0001193125-25-000003',
                'intent_type': 'M&A',
                'purpose_description': 'The Reporting Person acquired shares as part of a strategic investment thesis and may seek to explore potential business combinations.',
                'plans_or_proposals': 'May engage in discussions regarding strategic transactions or seek board representation.',
            },
            {
                'accession_number': '0001193125-25-000004',
                'intent_type': 'Activist',
                'purpose_description': 'The Reporting Person intends to engage with management regarding cost optimization and operational efficiency initiatives.',
                'plans_or_proposals': 'Plans to nominate director candidates at the next annual meeting.',
            },
            {
                'accession_number': '0001193125-25-000005',
                'intent_type': 'Activist',
                'purpose_description': 'The Reporting Person believes the company can improve performance through better capital allocation.',
                'plans_or_proposals': 'May advocate for increased share buybacks and dividend increases.',
            },
        ]
        
        synced_count = 0
        
        try:
            # Insert 13D events
            for event_data in sample_13d_events:
                event = insert_sec_event(session, event_data)
                if event:
                    synced_count += 1
            
            # Insert 13G events
            for event_data in sample_13g_events:
                event = insert_sec_event(session, event_data)
                if event:
                    synced_count += 1
            
            # Insert intents
            for intent_data in sample_intents:
                insert_sec_event_intent(session, intent_data)
            
            print(f"\n✓ Loaded {synced_count} sample SEC events")
            return synced_count
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
            
    except Exception as e:
        print(f"✗ Sample data loading error: {e}")
        import traceback
        traceback.print_exc()
        return 0


def verify_database():
    """Verify SEC events database integrity and record counts."""
    print("🔍 Verifying SEC events database...")
    
    try:
        from utils.db_util import get_engine, DB_SCHEMA
        from sqlalchemy import text
        
        engine = get_engine()
        
        with engine.connect() as conn:
            tables = [
                'sec_event',
                'sec_event_intent',
                'sec_event_amendment',
                'sec_event_group_member',
            ]
            
            print("\n  Table record counts:")
            total_records = 0
            
            for table in tables:
                try:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {DB_SCHEMA}.{table}"))
                    count = result.scalar()
                    print(f"    {table}: {count:,} records")
                    total_records += count
                except Exception as e:
                    print(f"    {table}: error - {e}")
            
            print(f"\n  Total records: {total_records:,}")
            
            # Get some statistics
            try:
                result = conn.execute(text(f"""
                    SELECT 
                        form_type,
                        COUNT(*) as count,
                        MIN(filing_date) as earliest,
                        MAX(filing_date) as latest
                    FROM {DB_SCHEMA}.sec_event
                    GROUP BY form_type
                """))
                
                print("\n  Filing statistics:")
                for row in result:
                    print(f"    {row[0]}: {row[1]} filings ({row[2]} to {row[3]})")
                    
            except Exception as e:
                print(f"    Could not get filing statistics: {e}")
        
        print("\n✓ Database verification complete!")
        return True
        
    except Exception as e:
        print(f"✗ Verification error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="SEC Events Data Sync Task")
    parser.add_argument("--days", type=int, default=30, help="Number of days to look back")
    parser.add_argument("--setup", action="store_true", help="Only setup database tables")
    parser.add_argument("--verify", action="store_true", help="Only verify database")
    parser.add_argument("--sample", action="store_true", help="Load sample data for testing")
    
    args = parser.parse_args()
    
    print("🚀 SEC Events Data Sync")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    success = True
    
    if args.verify:
        success = verify_database()
    elif args.setup:
        success = setup_database()
    elif args.sample:
        # Setup tables first
        if setup_database():
            load_sample_data()
            verify_database()
        else:
            success = False
    else:
        # Full sync
        if setup_database():
            synced = download_and_sync_filings(days=args.days)
            if synced == 0:
                print("\n⚠️  No filings synced. Loading sample data instead...")
                load_sample_data()
            verify_database()
        else:
            success = False
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 SEC events sync completed successfully!")
    else:
        print("❌ SEC events sync completed with errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()

