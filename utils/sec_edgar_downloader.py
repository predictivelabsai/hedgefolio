"""
SEC EDGAR downloader for 13D/13G filings.
Fetches and parses activist and passive stake accumulation filings from SEC EDGAR.
"""

import requests
import pandas as pd
import io
import datetime as dt
import re
import logging
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create logs directory if it doesn't exist
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

# Add file handler
handler = logging.FileHandler(log_dir / "sec_events.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# SEC EDGAR constants
SEC_EDGAR_BASE_URL = "https://www.sec.gov/Archives/edgar"
SEC_EDGAR_DAILY_INDEX = "https://www.sec.gov/Archives/edgar/daily-index"
USER_AGENT = "HedgeFolio (kaljuvee@gmail.com)"
RATE_LIMIT_DELAY = 0.1  # seconds between requests


def download_daily_index(date: str = None) -> pd.DataFrame:
    """
    Download SEC EDGAR daily index for 13D/13G filings.
    
    Args:
        date (str, optional): Date in YYYYMMDD format. Defaults to today.
    
    Returns:
        pd.DataFrame: DataFrame with columns: cik, company, form, filed, path
    
    Raises:
        Exception: If download fails after retries
    """
    if date is None:
        date = dt.date.today().strftime("%Y%m%d")
    
    url = f"{SEC_EDGAR_DAILY_INDEX}/form.{date}.idx"
    headers = {"User-Agent": USER_AGENT}
    
    logger.info(f"Downloading SEC EDGAR index for {date}")
    
    # Retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse the fixed-width format
            lines = response.text.splitlines()
            
            # Skip header lines (first 10 lines are metadata)
            data_lines = lines[10:]
            
            if not data_lines:
                logger.warning(f"No data found in index for {date}")
                return pd.DataFrame()
            
            # Parse fixed-width format
            # Columns: CIK (12), Company Name (60), Form Type (12), Date Filed (12), Filename (40+)
            cols = ["cik", "company", "form", "filed", "path"]
            
            try:
                df = pd.read_fwf(
                    io.StringIO("\n".join(data_lines)),
                    widths=[12, 60, 12, 12, 40],
                    header=None,
                    names=cols
                )
                
                # Clean up whitespace
                df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
                
                logger.info(f"Downloaded {len(df)} filings from {date}")
                return df
                
            except Exception as parse_error:
                logger.error(f"Error parsing index: {parse_error}")
                # Try alternative parsing
                return pd.DataFrame()
        
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to download index after {max_retries} attempts")
                raise
    
    return pd.DataFrame()


def filter_13d_13g_filings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter index for 13D and 13G forms only.
    
    Args:
        df (pd.DataFrame): Raw index DataFrame
    
    Returns:
        pd.DataFrame: Filtered DataFrame with only 13D/13G rows
    """
    if df.empty:
        return df
    
    # Filter for 13D and 13G forms
    mask = df['form'].str.contains('13-D|13-G', case=False, na=False)
    filtered = df[mask].copy()
    
    logger.info(f"Filtered {len(filtered)} 13D/13G filings from {len(df)} total")
    return filtered


def parse_13d_filing(accession_number: str) -> Dict:
    """
    Download and parse a 13D filing.
    
    Args:
        accession_number (str): SEC accession number
    
    Returns:
        Dict: Dictionary with extracted data
    """
    try:
        # Convert accession number to path format
        # Format: 0000950123-24-001234 -> 0000950123-24-001234.txt
        path = accession_number.replace("-", "")
        filing_url = f"{SEC_EDGAR_BASE_URL}/{path[:10]}/{path[10:16]}/{accession_number}.txt"
        
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(filing_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        filing_text = response.text
        
        # Extract key information
        data = {
            'accession_number': accession_number,
            'form_type': '13D',
            'filing_text': filing_text,
        }
        
        # Extract filing date
        filing_date_match = re.search(r'FILED AS OF DATE:\s*(\d{8})', filing_text)
        if filing_date_match:
            date_str = filing_date_match.group(1)
            data['filing_date'] = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
        
        # Extract filer information
        filer_match = re.search(r'CENTRAL INDEX KEY:\s*(\d+)', filing_text)
        if filer_match:
            data['cik'] = filer_match.group(1).zfill(10)
        
        # Extract filer name
        filer_name_match = re.search(r'COMPANY CONFORMED NAME:\s*(.+?)(?:\n|$)', filing_text)
        if filer_name_match:
            data['filer_name'] = filer_name_match.group(1).strip()
        
        # Extract target company info
        target_match = re.search(r'SECURITY AND ISSUER:\s*(.+?)(?:\n|$)', filing_text)
        if target_match:
            data['target_company_name'] = target_match.group(1).strip()
        
        # Extract stake information
        stake_info = extract_stake_info(filing_text)
        data.update(stake_info)
        
        # Extract intent information
        intent_info = extract_intent_info(filing_text)
        data.update(intent_info)
        
        # Detect group members
        group_members = detect_group_members(filing_text)
        if group_members:
            data['group_members'] = group_members
        
        logger.info(f"Parsed 13D filing: {accession_number}")
        return data
    
    except Exception as e:
        logger.error(f"Error parsing 13D filing {accession_number}: {e}")
        return {}


def parse_13g_filing(accession_number: str) -> Dict:
    """
    Download and parse a 13G filing.
    
    Args:
        accession_number (str): SEC accession number
    
    Returns:
        Dict: Dictionary with extracted data
    """
    try:
        # Convert accession number to path format
        path = accession_number.replace("-", "")
        filing_url = f"{SEC_EDGAR_BASE_URL}/{path[:10]}/{path[10:16]}/{accession_number}.txt"
        
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(filing_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        filing_text = response.text
        
        # Extract key information
        data = {
            'accession_number': accession_number,
            'form_type': '13G',
            'filing_text': filing_text,
        }
        
        # Extract filing date
        filing_date_match = re.search(r'FILED AS OF DATE:\s*(\d{8})', filing_text)
        if filing_date_match:
            date_str = filing_date_match.group(1)
            data['filing_date'] = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
        
        # Extract filer information
        filer_match = re.search(r'CENTRAL INDEX KEY:\s*(\d+)', filing_text)
        if filer_match:
            data['cik'] = filer_match.group(1).zfill(10)
        
        # Extract filer name
        filer_name_match = re.search(r'COMPANY CONFORMED NAME:\s*(.+?)(?:\n|$)', filing_text)
        if filer_name_match:
            data['filer_name'] = filer_name_match.group(1).strip()
        
        # Extract target company info
        target_match = re.search(r'SECURITY AND ISSUER:\s*(.+?)(?:\n|$)', filing_text)
        if target_match:
            data['target_company_name'] = target_match.group(1).strip()
        
        # Extract stake information
        stake_info = extract_stake_info(filing_text)
        data.update(stake_info)
        
        # Detect group members
        group_members = detect_group_members(filing_text)
        if group_members:
            data['group_members'] = group_members
        
        logger.info(f"Parsed 13G filing: {accession_number}")
        return data
    
    except Exception as e:
        logger.error(f"Error parsing 13G filing {accession_number}: {e}")
        return {}


def extract_stake_info(filing_text: str) -> Dict:
    """
    Extract stake percentage and share counts from filing text.
    
    Args:
        filing_text (str): Raw filing text
    
    Returns:
        Dict: Dictionary with stake_percentage, shares_owned, shares_outstanding
    """
    data = {}
    
    try:
        # Extract stake percentage
        stake_match = re.search(
            r'(?:PERCENT OF CLASS|Percentage of class|% of class).*?:\s*(\d+\.?\d*)',
            filing_text,
            re.IGNORECASE
        )
        if stake_match:
            data['stake_percentage'] = float(stake_match.group(1))
        
        # Extract shares owned
        shares_match = re.search(
            r'(?:Amount of beneficial ownership|shares owned).*?:\s*(\d+(?:,\d{3})*)',
            filing_text,
            re.IGNORECASE
        )
        if shares_match:
            shares_str = shares_match.group(1).replace(',', '')
            data['shares_owned'] = int(shares_str)
        
        # Extract shares outstanding
        outstanding_match = re.search(
            r'(?:shares outstanding|total shares).*?:\s*(\d+(?:,\d{3})*)',
            filing_text,
            re.IGNORECASE
        )
        if outstanding_match:
            outstanding_str = outstanding_match.group(1).replace(',', '')
            data['shares_outstanding'] = int(outstanding_str)
    
    except Exception as e:
        logger.warning(f"Error extracting stake info: {e}")
    
    return data


def extract_intent_info(filing_text: str) -> Dict:
    """
    Extract activist intent and strategy from 13D filing.
    
    Args:
        filing_text (str): Raw filing text
    
    Returns:
        Dict: Dictionary with intent_type, purpose, plans, background
    """
    data = {}
    
    try:
        # Extract purpose of transaction (Item 4)
        purpose_match = re.search(
            r'ITEM 4.*?PURPOSE OF TRANSACTION.*?:?\s*(.+?)(?:ITEM \d|$)',
            filing_text,
            re.IGNORECASE | re.DOTALL
        )
        if purpose_match:
            data['purpose_description'] = purpose_match.group(1).strip()[:1000]
        
        # Extract plans or proposals (Item 6)
        plans_match = re.search(
            r'ITEM 6.*?PLANS OR PROPOSALS.*?:?\s*(.+?)(?:ITEM \d|$)',
            filing_text,
            re.IGNORECASE | re.DOTALL
        )
        if plans_match:
            data['plans_or_proposals'] = plans_match.group(1).strip()[:1000]
        
        # Extract background (Item 2)
        background_match = re.search(
            r'ITEM 2.*?IDENTITY AND BACKGROUND.*?:?\s*(.+?)(?:ITEM \d|$)',
            filing_text,
            re.IGNORECASE | re.DOTALL
        )
        if background_match:
            data['background_of_filer'] = background_match.group(1).strip()[:500]
        
        # Determine intent type based on content
        intent_type = "Other"
        if "acquisition" in filing_text.lower() or "merger" in filing_text.lower():
            intent_type = "M&A"
        elif "activist" in filing_text.lower() or "board" in filing_text.lower():
            intent_type = "Activist"
        elif "passive" in filing_text.lower() or "investment" in filing_text.lower():
            intent_type = "Passive"
        
        data['intent_type'] = intent_type
    
    except Exception as e:
        logger.warning(f"Error extracting intent info: {e}")
    
    return data


def detect_group_members(filing_text: str) -> List[Dict]:
    """
    Detect group members for group filings.
    
    Args:
        filing_text (str): Raw filing text
    
    Returns:
        List[Dict]: List of group members with name, cik, address
    """
    members = []
    
    try:
        # Look for "GROUP MEMBERS" or similar sections
        group_section = re.search(
            r'GROUP MEMBERS.*?:?\s*(.+?)(?:ITEM \d|$)',
            filing_text,
            re.IGNORECASE | re.DOTALL
        )
        
        if group_section:
            group_text = group_section.group(1)
            
            # Extract member names and CIKs
            member_matches = re.finditer(
                r'(\d+)\s+(.+?)(?=\d+\s+|$)',
                group_text
            )
            
            for match in member_matches:
                member = {
                    'member_cik': match.group(1).zfill(10),
                    'member_name': match.group(2).strip()
                }
                members.append(member)
    
    except Exception as e:
        logger.warning(f"Error detecting group members: {e}")
    
    return members


def download_recent_filings(days: int = 30) -> List[Dict]:
    """
    Download all 13D/13G filings from the past N days.
    
    Args:
        days (int): Number of days to look back
    
    Returns:
        List[Dict]: List of parsed filing dictionaries
    """
    filings = []
    
    # Generate date range
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=days)
    
    current_date = start_date
    
    logger.info(f"Downloading 13D/13G filings from {start_date} to {end_date}")
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        
        try:
            # Download daily index
            df = download_daily_index(date_str)
            
            if df.empty:
                current_date += dt.timedelta(days=1)
                continue
            
            # Filter for 13D/13G
            filtered = filter_13d_13g_filings(df)
            
            if filtered.empty:
                current_date += dt.timedelta(days=1)
                continue
            
            # Parse each filing
            for idx, row in filtered.iterrows():
                accession = row['path'].split('/')[-1].replace('.txt', '')
                
                try:
                    if '13-D' in row['form']:
                        filing = parse_13d_filing(accession)
                    else:
                        filing = parse_13g_filing(accession)
                    
                    if filing:
                        filings.append(filing)
                
                except Exception as e:
                    logger.warning(f"Error parsing {accession}: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Error processing {date_str}: {e}")
        
        current_date += dt.timedelta(days=1)
    
    logger.info(f"Downloaded {len(filings)} 13D/13G filings")
    return filings


def get_filings_by_company(company_name: str, days: int = 365) -> List[Dict]:
    """
    Get all 13D/13G filings for a specific company.
    
    Args:
        company_name (str): Target company name
        days (int): Number of days to look back
    
    Returns:
        List[Dict]: List of filings for the company
    """
    all_filings = download_recent_filings(days)
    
    # Filter by company name
    company_filings = [
        f for f in all_filings
        if company_name.lower() in f.get('target_company_name', '').lower()
    ]
    
    logger.info(f"Found {len(company_filings)} filings for {company_name}")
    return company_filings


def get_filings_by_filer(filer_name: str, days: int = 365) -> List[Dict]:
    """
    Get all 13D/13G filings by a specific filer.
    
    Args:
        filer_name (str): Filer name
        days (int): Number of days to look back
    
    Returns:
        List[Dict]: List of filings by the filer
    """
    all_filings = download_recent_filings(days)
    
    # Filter by filer name
    filer_filings = [
        f for f in all_filings
        if filer_name.lower() in f.get('filer_name', '').lower()
    ]
    
    logger.info(f"Found {len(filer_filings)} filings by {filer_name}")
    return filer_filings
