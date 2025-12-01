#!/usr/bin/env python3
"""
Setup script for Hedge Fund Index data preparation.
This script reassembles the INFOTABLE.tsv from chunks and loads data into the database.
"""
import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_requirements():
    """Check if required packages are installed"""
    try:
        import pandas
        import numpy
        import sqlalchemy
        import psycopg2
        print("✓ Required packages are installed")
        return True
    except ImportError as e:
        print(f"✗ Missing required package: {e}")
        print("Please run: pip install -r requirements.txt")
        return False


def setup_data():
    """Setup data from chunks"""
    print("🔧 Setting up Hedge Fund Index data...")
    
    # Check if chunks exist
    chunks_dir = 'data/chunks'
    if not os.path.exists(chunks_dir):
        print(f"✗ Chunks directory not found: {chunks_dir}")
        print("Please ensure the repository was cloned correctly.")
        return False
    
    # Check if INFOTABLE.tsv already exists
    infotable_path = 'data/INFOTABLE.tsv'
    if os.path.exists(infotable_path):
        print("✓ INFOTABLE.tsv already exists")
        return True
    
    # Reassemble from chunks
    print("📦 Reassembling INFOTABLE.tsv from chunks...")
    try:
        from utils.reassemble_data import reassemble_infotable
        reassemble_infotable(chunks_dir, infotable_path)
        print("✓ INFOTABLE.tsv created successfully!")
        return True
    except Exception as e:
        print(f"✗ Error reassembling data: {e}")
        return False


def verify_data():
    """Verify that all required data files are present"""
    print("🔍 Verifying data files...")
    
    required_files = [
        'data/COVERPAGE.tsv',
        'data/SUBMISSION.tsv',
        'data/SUMMARYPAGE.tsv',
        'data/SIGNATURE.tsv',
        'data/OTHERMANAGER.tsv',
        'data/OTHERMANAGER2.tsv',
        'data/company_ticker.csv',
        'data/FORM13F_metadata.json'
    ]
    
    # Check for either INFOTABLE.tsv or chunks
    has_infotable = os.path.exists('data/INFOTABLE.tsv')
    has_chunks = os.path.exists('data/chunks') and len(os.listdir('data/chunks')) > 0
    
    if not has_infotable and not has_chunks:
        print("✗ Neither INFOTABLE.tsv nor chunks directory found!")
        return False
    
    if has_infotable:
        size_mb = os.path.getsize('data/INFOTABLE.tsv') / (1024 * 1024)
        print(f"✓ data/INFOTABLE.tsv ({size_mb:.1f} MB)")
    else:
        chunk_count = len([f for f in os.listdir('data/chunks') if f.startswith('INFOTABLE_chunk')])
        print(f"✓ data/chunks/ ({chunk_count} INFOTABLE chunks)")
    
    all_present = True
    for file_path in required_files:
        if os.path.exists(file_path):
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            print(f"✓ {file_path} ({size_mb:.2f} MB)")
        else:
            print(f"⚠ {file_path} - Missing (optional)")
    
    return True


def test_data_loading():
    """Test that data can be loaded successfully"""
    print("🧪 Testing data loading...")
    
    try:
        from utils.data_processor import SEC13FProcessor
        
        processor = SEC13FProcessor()
        stats = processor.get_summary_stats()
        
        print(f"✓ Data loaded successfully!")
        print(f"  📊 Total Funds: {stats['total_funds']:,}")
        print(f"  📈 Total Holdings: {stats['total_holdings']:,}")
        print(f"  💰 Total AUM: ${stats['total_aum_billions']:.1f}B")
        print(f"  🏢 Unique Securities: {stats['unique_securities']:,}")
        
        return True
        
    except Exception as e:
        print(f"⚠ Could not test data processor: {e}")
        return True  # Non-fatal, continue


def setup_database():
    """Create database schema and tables"""
    print("🗄️  Setting up database...")
    
    try:
        from utils.db_util import get_engine, create_tables, DB_URL, DB_SCHEMA
        
        if not DB_URL:
            print("⚠ DB_URL not configured in .env - skipping database setup")
            return True
        
        print(f"  Schema: {DB_SCHEMA}")
        print(f"  URL: {DB_URL[:50]}...")
        
        engine = get_engine()
        
        # Test connection
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Database connection successful")
        
        # Create tables
        create_tables(engine)
        print("✓ Database tables created")
        
        return True
        
    except Exception as e:
        print(f"✗ Database setup error: {e}")
        return False


def load_data_to_db():
    """Load all data files into the database"""
    print("📤 Loading data into database...")
    
    try:
        from utils.db_util import (
            get_engine, get_session, DB_URL,
            load_submission_data,
            load_coverpage_data,
            load_summarypage_data,
            load_signature_data,
            load_othermanager_data,
            load_othermanager2_data,
            load_infotable_data,
            load_company_ticker_data,
        )
        
        if not DB_URL:
            print("⚠ DB_URL not configured - skipping data load")
            return True
        
        engine = get_engine()
        session = get_session(engine)
        data_dir = "data"
        
        try:
            # Load data in order (respecting foreign key constraints)
            print("\n  Loading submission data...")
            load_submission_data(data_dir, session)
            
            print("  Loading coverpage data...")
            load_coverpage_data(data_dir, session)
            
            print("  Loading summarypage data...")
            load_summarypage_data(data_dir, session)
            
            print("  Loading signature data...")
            load_signature_data(data_dir, session)
            
            print("  Loading othermanager data...")
            load_othermanager_data(data_dir, session)
            
            print("  Loading othermanager2 data...")
            load_othermanager2_data(data_dir, session)
            
            print("  Loading infotable data (this may take a while)...")
            load_infotable_data(data_dir, session)
            
            print("  Loading company_ticker data...")
            load_company_ticker_data(data_dir, session)
            
            print("\n✓ All data loaded successfully!")
            return True
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
            
    except Exception as e:
        print(f"✗ Data loading error: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_database():
    """Verify data was loaded correctly into the database"""
    print("🔍 Verifying database...")
    
    try:
        from utils.db_util import get_engine, get_session, DB_URL, DB_SCHEMA
        from sqlalchemy import text
        
        if not DB_URL:
            print("⚠ DB_URL not configured - skipping verification")
            return True
        
        engine = get_engine()
        
        with engine.connect() as conn:
            # Count records in each table
            tables = [
                'submission', 'coverpage', 'summarypage', 'signature',
                'othermanager', 'othermanager2', 'infotable', 'company_ticker'
            ]
            
            print("\n  Table record counts:")
            for table in tables:
                try:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {DB_SCHEMA}.{table}"))
                    count = result.scalar()
                    print(f"    {table}: {count:,} records")
                except Exception as e:
                    print(f"    {table}: error - {e}")
        
        print("\n✓ Database verification complete!")
        return True
        
    except Exception as e:
        print(f"✗ Verification error: {e}")
        return False


def main():
    """Main setup function"""
    print("🚀 Hedge Fund Index Data Setup")
    print("=" * 50)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Setup data files
    if not setup_data():
        sys.exit(1)
    
    # Verify data files
    if not verify_data():
        sys.exit(1)
    
    # Test data loading (optional)
    test_data_loading()
    
    # Setup database
    if not setup_database():
        sys.exit(1)
    
    # Load data into database
    if not load_data_to_db():
        sys.exit(1)
    
    # Verify database
    if not verify_database():
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("🎉 Setup completed successfully!")
    print("\nYou can now run the application with:")
    print("  streamlit run Home.py")
    print("\nOr query the database directly:")
    print("  python -c \"from utils.db_util import get_session, InfoTable; s = get_session(); print(s.query(InfoTable).limit(5).all())\"")


if __name__ == "__main__":
    main()
