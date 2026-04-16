#!/usr/bin/env python3
"""
Data Sync Task - Download and update SEC 13F data
Run this daily to keep the database up to date.

Usage:
    python tasks/data_sync.py                    # Full sync
    python tasks/data_sync.py --download-only    # Only download new data
    python tasks/data_sync.py --load-only        # Only load existing data to DB
    python tasks/data_sync.py --verify           # Verify database integrity
"""
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def download_sec_data():
    """Download latest SEC 13F data from SEC EDGAR."""
    print("📥 Downloading SEC 13F data...")
    
    # TODO: Implement SEC EDGAR API download
    # The SEC provides bulk data downloads at:
    # https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets
    
    print("⚠️  Automatic download not yet implemented.")
    print("   Please manually download data from:")
    print("   https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets")
    print("   And place the files in the data/ directory.")
    
    return False


def reassemble_chunks():
    """Reassemble INFOTABLE.tsv from chunks if needed."""
    print("📦 Checking for chunk reassembly...")
    
    data_dir = Path("data")
    chunks_dir = data_dir / "chunks"
    infotable_path = data_dir / "INFOTABLE.tsv"
    
    if infotable_path.exists():
        print("✓ INFOTABLE.tsv already exists")
        return True
    
    if not chunks_dir.exists():
        print("⚠️  No chunks directory found")
        return True  # Not an error, just no chunks
    
    chunk_files = sorted(chunks_dir.glob("INFOTABLE_chunk_*.tsv"))
    if not chunk_files:
        print("⚠️  No chunk files found")
        return True
    
    print(f"  Reassembling from {len(chunk_files)} chunks...")
    
    try:
        from utils.reassemble_data import reassemble_infotable
        reassemble_infotable(str(chunks_dir), str(infotable_path))
        print("✓ INFOTABLE.tsv created successfully")
        return True
    except Exception as e:
        print(f"✗ Error reassembling: {e}")
        return False


def check_duplicates():
    """Check for and report duplicate records in data files."""
    print("🔍 Checking for duplicate records...")
    
    import pandas as pd
    
    data_dir = Path("data")
    
    # Check SUBMISSION duplicates
    submission_path = data_dir / "SUBMISSION.tsv"
    if submission_path.exists():
        df = pd.read_csv(submission_path, sep='\t', dtype=str)
        dups = df.duplicated(subset=['ACCESSION_NUMBER']).sum()
        print(f"  SUBMISSION.tsv: {dups} duplicates")
    
    # Check COVERPAGE duplicates
    coverpage_path = data_dir / "COVERPAGE.tsv"
    if coverpage_path.exists():
        df = pd.read_csv(coverpage_path, sep='\t', dtype=str)
        dups = df.duplicated(subset=['ACCESSION_NUMBER']).sum()
        print(f"  COVERPAGE.tsv: {dups} duplicates")
    
    # Check OTHERMANAGER2 duplicates (known to have some)
    othermanager2_path = data_dir / "OTHERMANAGER2.tsv"
    if othermanager2_path.exists():
        df = pd.read_csv(othermanager2_path, sep='\t', dtype=str)
        dups = df.duplicated(subset=['ACCESSION_NUMBER', 'SEQUENCENUMBER']).sum()
        print(f"  OTHERMANAGER2.tsv: {dups} duplicates")
    
    print("✓ Duplicate check complete")
    return True


def load_to_database():
    """Load all data files into the database."""
    print("📤 Loading data into database...")
    
    try:
        from utils.db_util import (
            get_engine, get_session, create_tables,
            load_submission_data,
            load_coverpage_data,
            load_summarypage_data,
            load_signature_data,
            load_othermanager_data,
            load_othermanager2_data,
            load_infotable_data,
            load_company_ticker_data,
            DB_URL, DB_SCHEMA
        )
        
        if not DB_URL:
            print("⚠️  DB_URL not configured - skipping database load")
            return True
        
        print(f"  Schema: {DB_SCHEMA}")
        
        engine = get_engine()
        session = get_session(engine)
        data_dir = "data"
        
        # Create tables if needed
        create_tables(engine)
        
        try:
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
            print(f"✗ Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            session.close()
            
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def verify_database():
    """Verify database integrity and record counts."""
    print("🔍 Verifying database...")
    
    try:
        from utils.db_util import get_engine, DB_SCHEMA
        from sqlalchemy import text
        
        engine = get_engine()
        
        with engine.connect() as conn:
            tables = [
                'submission', 'coverpage', 'summarypage', 'signature',
                'othermanager', 'othermanager2', 'infotable', 'company_ticker'
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
        
        print("\n✓ Database verification complete!")
        return True
        
    except Exception as e:
        print(f"✗ Verification error: {e}")
        return False


def cleanup_data_files():
    """Clean up data files after successful database load."""
    print("🧹 Cleaning up data files...")
    
    data_dir = Path("data")
    
    # Files to keep (metadata and ticker mappings)
    keep_files = {
        'FORM13F_metadata.json',
        'FORM13F_readme.htm',
        'company_ticker.csv'
    }
    
    # Files to remove
    remove_patterns = ['*.tsv']
    
    removed_count = 0
    for pattern in remove_patterns:
        for file in data_dir.glob(pattern):
            if file.name not in keep_files:
                print(f"  Removing: {file.name}")
                file.unlink()
                removed_count += 1
    
    # Remove chunks directory
    chunks_dir = data_dir / "chunks"
    if chunks_dir.exists():
        import shutil
        print("  Removing: chunks/")
        shutil.rmtree(chunks_dir)
        removed_count += 1
    
    print(f"✓ Removed {removed_count} files/directories")
    return True


def main():
    parser = argparse.ArgumentParser(description="SEC 13F Data Sync Task")
    parser.add_argument("--download-only", action="store_true", help="Only download new data")
    parser.add_argument("--load-only", action="store_true", help="Only load existing data to DB")
    parser.add_argument("--verify", action="store_true", help="Only verify database")
    parser.add_argument("--cleanup", action="store_true", help="Clean up data files after DB load")
    
    args = parser.parse_args()
    
    print("🚀 SEC 13F Data Sync")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    success = True
    
    if args.verify:
        success = verify_database()
    elif args.download_only:
        success = download_sec_data()
    elif args.load_only:
        success = reassemble_chunks() and load_to_database()
    elif args.cleanup:
        # Verify first, then cleanup
        if verify_database():
            response = input("\nAre you sure you want to remove data files? (yes/no): ")
            if response.lower() == 'yes':
                success = cleanup_data_files()
            else:
                print("Cleanup cancelled.")
        else:
            print("Database verification failed. Not cleaning up.")
            success = False
    else:
        # Full sync
        success = (
            reassemble_chunks() and
            check_duplicates() and
            load_to_database() and
            verify_database()
        )
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Data sync completed successfully!")
    else:
        print("❌ Data sync completed with errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()


