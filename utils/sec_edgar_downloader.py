"""
SEC EDGAR downloader for 13D/13G filings.
Fetches and parses activist and passive stake accumulation filings from SEC EDGAR.
Uses SEC Full-Text Search API and RSS feeds to discover filings dynamically.
"""

import os
import re
import logging
import tempfile
import shutil
import time
import requests
import datetime as dt
from typing import Dict, List, Optional, Set
from pathlib import Path

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create logs directory if it doesn't exist
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

# Add file handler if not already added
if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
    handler = logging.FileHandler(log_dir / "sec_events.log")
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Email for SEC EDGAR User-Agent (required by SEC)
SEC_EMAIL = os.getenv("SEC_EMAIL", "hedgefolio@example.com")

# SEC EDGAR endpoints
SEC_EFTS_SEARCH = "https://efts.sec.gov/LATEST/search-index"
SEC_FULL_TEXT_SEARCH = "https://www.sec.gov/cgi-bin/srch-ia"
SEC_RSS_FILINGS = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar"


def get_headers():
    """Get headers for SEC EDGAR API requests."""
    return {
        "User-Agent": f"HedgeFolio {SEC_EMAIL}",
        "Accept": "application/json, text/html, application/xml",
        "Accept-Encoding": "gzip, deflate",
    }


def get_recent_filings_from_rss(form_types: List[str] = None, max_results: int = 100) -> List[Dict]:
    """
    Get recent filings from SEC RSS feeds.
    
    Args:
        form_types: List of form types to filter (e.g., ['SC 13D', 'SC 13G'])
        max_results: Maximum number of results to return
    
    Returns:
        List of filing metadata dictionaries with cik, accession_number, form_type, etc.
    """
    if form_types is None:
        form_types = ['SC 13D', 'SC 13G', 'SC 13D/A', 'SC 13G/A']
    
    filings = []
    
    for form_type in form_types:
        try:
            # SEC RSS feed URL for specific form type
            # This returns recent filings for the specified form type
            url = f"{SEC_RSS_FILINGS}?action=getcurrent&type={form_type.replace(' ', '%20')}&company=&dateb=&owner=include&count={max_results}&output=atom"
            
            logger.info(f"Fetching RSS feed for {form_type}")
            
            response = requests.get(url, headers=get_headers(), timeout=30)
            
            if response.status_code == 200:
                if HAS_FEEDPARSER:
                    feed = feedparser.parse(response.content)
                    
                    for entry in feed.entries:
                        try:
                            # Extract CIK from the link
                            # Link format: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001234567&...
                            cik_match = re.search(r'CIK=(\d+)', entry.get('link', ''))
                            if not cik_match:
                                # Try extracting from id field
                                cik_match = re.search(r'/data/(\d+)/', entry.get('id', ''))
                            
                            # Extract accession number
                            accession_match = re.search(r'(\d{10}-\d{2}-\d{6})', entry.get('id', '') + entry.get('link', ''))
                            
                            if cik_match:
                                filing = {
                                    'cik': cik_match.group(1).zfill(10),
                                    'accession_number': accession_match.group(1) if accession_match else None,
                                    'form_type': form_type,
                                    'title': entry.get('title', ''),
                                    'filed_date': entry.get('updated', ''),
                                    'link': entry.get('link', ''),
                                }
                                filings.append(filing)
                        except Exception as e:
                            logger.debug(f"Error parsing RSS entry: {e}")
                            continue
                else:
                    # Fallback: parse XML manually
                    cik_matches = re.findall(r'CIK=(\d+)', response.text)
                    accession_matches = re.findall(r'(\d{10}-\d{2}-\d{6})', response.text)
                    
                    for cik in set(cik_matches):
                        filing = {
                            'cik': cik.zfill(10),
                            'form_type': form_type,
                        }
                        filings.append(filing)
            
            time.sleep(0.2)  # Rate limiting
            
        except Exception as e:
            logger.warning(f"Error fetching RSS feed for {form_type}: {e}")
            continue
    
    logger.info(f"Found {len(filings)} filings from RSS feeds")
    return filings


def get_recent_filings_from_search(days: int = 30, max_results: int = 200) -> List[Dict]:
    """
    Get recent 13D/13G filings using SEC EDGAR Full-Text Search.
    
    Args:
        days: Number of days to look back
        max_results: Maximum number of results
    
    Returns:
        List of filing metadata dictionaries
    """
    filings = []
    
    # Calculate date range
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=days)
    
    # SEC EDGAR search URL - this searches the filing index
    # Using the company search with form type filter
    form_types = ['SC%2013D', 'SC%2013G']  # URL encoded
    
    for form_type in form_types:
        try:
            url = f"{SEC_RSS_FILINGS}?action=getcurrent&type={form_type}&company=&dateb=&owner=include&count={max_results}&start=0&output=atom"
            
            logger.info(f"Searching for recent {form_type} filings")
            
            response = requests.get(url, headers=get_headers(), timeout=30)
            
            if response.status_code == 200:
                # Parse the Atom feed response
                # Extract filing info from the response
                entries = re.findall(
                    r'<entry>.*?<id>([^<]+)</id>.*?<title[^>]*>([^<]+)</title>.*?<updated>([^<]+)</updated>.*?</entry>',
                    response.text,
                    re.DOTALL
                )
                
                for entry_id, title, updated in entries:
                    try:
                        # Extract CIK and accession from the entry
                        cik_match = re.search(r'/data/(\d+)/', entry_id)
                        accession_match = re.search(r'(\d{10}-\d{2}-\d{6})', entry_id)
                        
                        if cik_match:
                            filing = {
                                'cik': cik_match.group(1).zfill(10),
                                'accession_number': accession_match.group(1) if accession_match else None,
                                'form_type': form_type.replace('%20', ' '),
                                'title': title.strip(),
                                'filed_date': updated[:10] if updated else None,
                            }
                            filings.append(filing)
                    except Exception as e:
                        logger.debug(f"Error parsing entry: {e}")
                        continue
            
            time.sleep(0.2)
            
        except Exception as e:
            logger.warning(f"Error searching for {form_type}: {e}")
            continue
    
    logger.info(f"Found {len(filings)} filings from search")
    return filings


def get_filings_from_daily_index(days: int = 7) -> List[Dict]:
    """
    Get filings from SEC EDGAR daily index files.
    
    Args:
        days: Number of days to look back
    
    Returns:
        List of filing metadata dictionaries
    """
    filings = []
    
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=days)
    
    current_date = start_date
    while current_date <= end_date:
        try:
            # Determine quarter
            quarter = (current_date.month - 1) // 3 + 1
            year = current_date.year
            
            # Daily index URL
            # Format: https://www.sec.gov/Archives/edgar/daily-index/2024/QTR4/form.20241203.idx
            date_str = current_date.strftime("%Y%m%d")
            url = f"{SEC_ARCHIVES}/daily-index/{year}/QTR{quarter}/form.{date_str}.idx"
            
            logger.debug(f"Fetching daily index for {date_str}")
            
            response = requests.get(url, headers=get_headers(), timeout=30)
            
            if response.status_code == 200:
                # Parse the fixed-width index file
                lines = response.text.split('\n')
                
                # Skip header lines (usually first 10 lines)
                for line in lines[10:]:
                    if not line.strip():
                        continue
                    
                    # Check if this is a 13D or 13G filing
                    if 'SC 13D' in line or 'SC 13G' in line or '13-D' in line or '13-G' in line:
                        try:
                            # Parse the fixed-width format
                            # Format: Form Type | Company Name | CIK | Date Filed | Filename
                            parts = line.split()
                            if len(parts) >= 4:
                                # Extract form type (first 1-2 parts)
                                form_type = parts[0]
                                if parts[1] in ['13D', '13G', '13D/A', '13G/A']:
                                    form_type = f"{parts[0]} {parts[1]}"
                                
                                # Find CIK (10-digit number)
                                cik_match = re.search(r'\b(\d{10})\b', line)
                                # Find accession number
                                accession_match = re.search(r'(\d{10}-\d{2}-\d{6})', line)
                                
                                if cik_match:
                                    filing = {
                                        'cik': cik_match.group(1),
                                        'accession_number': accession_match.group(1) if accession_match else None,
                                        'form_type': '13D' if '13D' in form_type else '13G',
                                        'filed_date': current_date.strftime('%Y-%m-%d'),
                                    }
                                    filings.append(filing)
                        except Exception as e:
                            logger.debug(f"Error parsing index line: {e}")
                            continue
            
            time.sleep(0.1)  # Rate limiting
            
        except Exception as e:
            logger.debug(f"No index for {current_date}: {e}")
        
        current_date += dt.timedelta(days=1)
    
    logger.info(f"Found {len(filings)} filings from daily index")
    return filings


def download_recent_filings(days: int = 30, limit_per_cik: int = 5) -> List[Dict]:
    """
    Download all 13D/13G filings from the past N days.
    Discovers filings dynamically using RSS feeds and daily index.
    
    Args:
        days: Number of days to look back
        limit_per_cik: Max filings to download per CIK
    
    Returns:
        List of parsed filing dictionaries
    """
    from sec_edgar_downloader import Downloader
    
    filings = []
    discovered_filings = []
    
    # Calculate date range
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=days)
    
    logger.info(f"Downloading 13D/13G filings from {start_date} to {end_date}")
    
    # Method 1: Get filings from RSS feeds (most recent)
    logger.info("Discovering filings from RSS feeds...")
    rss_filings = get_recent_filings_from_rss(max_results=100)
    discovered_filings.extend(rss_filings)
    
    # Method 2: Get filings from daily index (more comprehensive)
    logger.info("Discovering filings from daily index...")
    index_filings = get_filings_from_daily_index(days=min(days, 30))  # Limit to 30 days for index
    discovered_filings.extend(index_filings)
    
    # Method 3: Search for recent filings
    logger.info("Discovering filings from search...")
    search_filings = get_recent_filings_from_search(days=days)
    discovered_filings.extend(search_filings)
    
    # Deduplicate by CIK
    seen_ciks = set()
    unique_filings = []
    for f in discovered_filings:
        cik = f.get('cik')
        if cik and cik not in seen_ciks:
            seen_ciks.add(cik)
            unique_filings.append(f)
    
    logger.info(f"Discovered {len(unique_filings)} unique filers with recent 13D/13G filings")
    
    if not unique_filings:
        logger.warning("No filings discovered. SEC may be rate limiting.")
        return []
    
    # Create a temporary directory for downloads
    temp_dir = tempfile.mkdtemp(prefix="sec_edgar_")
    
    try:
        # Initialize the downloader
        dl = Downloader("HedgeFolio", SEC_EMAIL, temp_dir)
        
        # Download filings for each discovered CIK
        for filing_info in unique_filings:
            cik = filing_info.get('cik')
            if not cik:
                continue
            
            # Determine form type
            form_type_raw = filing_info.get('form_type', 'SC 13D')
            is_13d = '13D' in form_type_raw.upper()
            form_type = "SC 13D" if is_13d else "SC 13G"
            
            try:
                # Download filings for this CIK
                count = dl.get(
                    form_type,
                    cik,
                    after=start_date.strftime("%Y-%m-%d"),
                    before=end_date.strftime("%Y-%m-%d"),
                    include_amends=True,
                    download_details=True,
                    limit=limit_per_cik,
                )
                
                if count > 0:
                    logger.info(f"Downloaded {count} {form_type} filings for CIK {cik}")
                
                # Rate limiting
                time.sleep(0.15)
                
            except Exception as e:
                logger.debug(f"Error downloading for CIK {cik}: {e}")
                continue
        
        # Parse all downloaded filings
        filings = parse_downloaded_filings(temp_dir)
        
        # Filter by date range
        filings = [
            f for f in filings 
            if f.get('filing_date') and f.get('filing_date') >= start_date.strftime("%Y-%m-%d")
        ]
        
        logger.info(f"Downloaded and parsed {len(filings)} 13D/13G filings")
        
    except Exception as e:
        logger.error(f"Error in download_recent_filings: {e}")
    
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Error cleaning up temp directory: {e}")
    
    return filings


def parse_downloaded_filings(download_dir: str) -> List[Dict]:
    """
    Parse all downloaded filings from a directory.
    
    Args:
        download_dir: Directory containing downloaded filings
    
    Returns:
        List of parsed filing dictionaries
    """
    filings = []
    download_path = Path(download_dir)
    
    # The sec-edgar-downloader creates a structure like:
    # download_dir/sec-edgar-filings/[CIK]/[FORM_TYPE]/[ACCESSION]/
    filings_dir = download_path / "sec-edgar-filings"
    
    if not filings_dir.exists():
        logger.warning(f"No filings directory found at {filings_dir}")
        return filings
    
    # Walk through all downloaded filings
    for cik_dir in filings_dir.iterdir():
        if not cik_dir.is_dir():
            continue
            
        for form_dir in cik_dir.iterdir():
            if not form_dir.is_dir():
                continue
                
            form_type = form_dir.name
            
            for accession_dir in form_dir.iterdir():
                if not accession_dir.is_dir():
                    continue
                
                try:
                    filing_data = parse_filing_directory(accession_dir, form_type)
                    if filing_data:
                        filings.append(filing_data)
                except Exception as e:
                    logger.warning(f"Error parsing filing {accession_dir}: {e}")
                    continue
    
    return filings


def parse_filing_directory(filing_dir: Path, form_type: str) -> Optional[Dict]:
    """
    Parse a single filing from its downloaded directory.
    
    Args:
        filing_dir: Path to the filing directory
        form_type: Form type (SC 13D, SC 13G, etc.)
    
    Returns:
        Parsed filing data or None
    """
    # Find the main filing document
    txt_files = list(filing_dir.glob("*.txt"))
    
    if not txt_files:
        logger.warning(f"No .txt files found in {filing_dir}")
        return None
    
    # Prefer full-submission.txt or primary-document.txt
    filing_path = None
    for txt_file in txt_files:
        if "full-submission" in txt_file.name.lower():
            filing_path = txt_file
            break
        elif "primary-document" in txt_file.name.lower():
            filing_path = txt_file
    
    if not filing_path:
        filing_path = txt_files[0]
    
    try:
        with open(filing_path, 'r', encoding='utf-8', errors='ignore') as f:
            filing_text = f.read()
    except Exception as e:
        logger.error(f"Error reading {filing_path}: {e}")
        return None
    
    # Extract accession number from directory name
    accession_number = filing_dir.name
    
    # Determine if it's 13D or 13G
    is_13d = '13D' in form_type.upper() or '13-D' in form_type.upper()
    simple_form_type = '13D' if is_13d else '13G'
    
    # Build data dictionary
    data = {
        'accession_number': accession_number,
        'form_type': simple_form_type,
    }
    
    # Extract filing date
    filing_date_match = re.search(r'FILED AS OF DATE:\s*(\d{8})', filing_text)
    if filing_date_match:
        date_str = filing_date_match.group(1)
        data['filing_date'] = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
    else:
        date_match = re.search(r'DATE AS OF CHANGE:\s*(\d{8})', filing_text)
        if date_match:
            date_str = date_match.group(1)
            data['filing_date'] = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
    
    # Extract CIK (filer) - look for FILED BY section first
    filed_by_section = re.search(r'FILED BY:.*?CENTRAL INDEX KEY:\s*(\d+)', filing_text, re.DOTALL)
    if filed_by_section:
        data['cik'] = filed_by_section.group(1).zfill(10)
    else:
        cik_match = re.search(r'CENTRAL INDEX KEY:\s*(\d+)', filing_text)
        if cik_match:
            data['cik'] = cik_match.group(1).zfill(10)
    
    # Extract filer name - look for FILED BY section
    filed_by_name = re.search(r'FILED BY:.*?COMPANY CONFORMED NAME:\s*(.+?)(?:\n|$)', filing_text, re.DOTALL)
    if filed_by_name:
        data['filer_name'] = filed_by_name.group(1).strip()
    else:
        filer_name_match = re.search(r'COMPANY CONFORMED NAME:\s*(.+?)(?:\n|$)', filing_text)
        if filer_name_match:
            data['filer_name'] = filer_name_match.group(1).strip()
    
    # Extract target company info - multiple methods
    target_company = None
    
    # Method 1: SUBJECT COMPANY section
    subject_section = re.search(
        r'SUBJECT COMPANY:.*?COMPANY CONFORMED NAME:\s*(.+?)(?:\n|$)',
        filing_text,
        re.DOTALL | re.IGNORECASE
    )
    if subject_section:
        target_company = subject_section.group(1).strip()
    
    # Method 2: Look for ISSUER pattern
    if not target_company:
        issuer_match = re.search(
            r'ISSUER:.*?COMPANY CONFORMED NAME:\s*(.+?)(?:\n|$)',
            filing_text,
            re.DOTALL | re.IGNORECASE
        )
        if issuer_match:
            target_company = issuer_match.group(1).strip()
    
    # Method 3: Look for "Name of Issuer" in Item 1
    if not target_company:
        item1_patterns = [
            r'(?:NAME OF ISSUER|SECURITY AND ISSUER)[:\s]*\n*\s*([A-Z][A-Za-z0-9\s\.,&\'\-]+?)(?:\n|\(|Common|Class)',
            r'ITEM\s*1[.\s]*.*?(?:NAME OF ISSUER|SECURITY AND ISSUER)[:\s]*([A-Z][A-Za-z0-9\s\.,&\'\-]+?)(?:\n|\()',
            r'Item\s*1[^:]*:\s*([A-Z][A-Za-z0-9\s\.,&\'\-]+)',
        ]
        for pattern in item1_patterns:
            match = re.search(pattern, filing_text, re.IGNORECASE | re.DOTALL)
            if match:
                target_text = match.group(1).strip()
                target_text = re.sub(r'\s+', ' ', target_text)
                target_text = target_text.split('\n')[0][:200]
                if len(target_text) >= 3:
                    target_company = target_text
                    break
    
    # Method 4: Look for CUSIP label and extract company before it
    if not target_company:
        cusip_match = re.search(
            r'([A-Z][A-Za-z0-9\s\.,&\'\-]{5,50})\s*(?:CUSIP|Common Stock)',
            filing_text[:5000],
            re.IGNORECASE
        )
        if cusip_match:
            target_company = cusip_match.group(1).strip()
    
    if target_company:
        data['target_company_name'] = target_company
    
    # Try to extract ticker
    ticker_match = re.search(
        r'(?:TICKER SYMBOL|Trading Symbol|Stock Symbol)[:\s]*([A-Z]{1,5})',
        filing_text,
        re.IGNORECASE
    )
    if ticker_match:
        data['target_ticker'] = ticker_match.group(1).upper()
    
    # Extract stake information
    stake_info = extract_stake_info(filing_text)
    data.update(stake_info)
    
    # Extract intent information (13D only)
    if is_13d:
        intent_info = extract_intent_info(filing_text)
        data.update(intent_info)
    
    # Check if this is an amendment
    is_amendment = '/A' in form_type or 'AMENDMENT' in filing_text.upper()[:500]
    data['is_amendment'] = is_amendment
    data['filing_status'] = 'Amendment' if is_amendment else 'Initial'
    
    # Validate required fields
    if not data.get('filer_name') or not data.get('target_company_name'):
        logger.warning(f"Missing required fields for {accession_number}")
        if not data.get('target_company_name') and data.get('filer_name'):
            data['target_company_name'] = 'UNKNOWN COMPANY'
    
    return data


def extract_stake_info(filing_text: str) -> Dict:
    """Extract stake percentage and share counts from filing text."""
    data = {}
    
    try:
        # Extract stake percentage
        stake_patterns = [
            r'(?:PERCENT OF CLASS|Percentage of class|% of class|PERCENT OF CLASS REPRESENTED).*?[:\s]+(\d+\.?\d*)\s*%?',
            r'Item\s*(?:11|13).*?(\d+\.?\d*)\s*%',
            r'(?:aggregate percentage|beneficial ownership).*?(\d+\.?\d*)\s*%',
        ]
        
        for pattern in stake_patterns:
            stake_match = re.search(pattern, filing_text, re.IGNORECASE | re.DOTALL)
            if stake_match:
                try:
                    stake = float(stake_match.group(1))
                    if 0 < stake <= 100:
                        data['stake_percentage'] = stake
                        break
                except ValueError:
                    continue
        
        # Extract shares owned
        shares_patterns = [
            r'(?:Amount of beneficial ownership|shares beneficially owned|aggregate amount beneficially owned).*?[:\s]+(\d{1,3}(?:,\d{3})*|\d+)',
            r'Item\s*(?:9|11).*?(\d{1,3}(?:,\d{3})*|\d+)\s*shares',
        ]
        
        for pattern in shares_patterns:
            shares_match = re.search(pattern, filing_text, re.IGNORECASE | re.DOTALL)
            if shares_match:
                try:
                    shares_str = shares_match.group(1).replace(',', '')
                    shares = int(shares_str)
                    if shares > 0:
                        data['shares_owned'] = shares
                        break
                except ValueError:
                    continue
        
        # Extract shares outstanding
        outstanding_patterns = [
            r'(?:shares outstanding|total shares|number of shares outstanding).*?[:\s]+(\d{1,3}(?:,\d{3})*|\d+)',
        ]
        
        for pattern in outstanding_patterns:
            outstanding_match = re.search(pattern, filing_text, re.IGNORECASE | re.DOTALL)
            if outstanding_match:
                try:
                    outstanding_str = outstanding_match.group(1).replace(',', '')
                    outstanding = int(outstanding_str)
                    if outstanding > 0:
                        data['shares_outstanding'] = outstanding
                        break
                except ValueError:
                    continue
    
    except Exception as e:
        logger.warning(f"Error extracting stake info: {e}")
    
    return data


def extract_intent_info(filing_text: str) -> Dict:
    """Extract activist intent and strategy from 13D filing."""
    data = {}
    
    try:
        # Extract purpose of transaction (Item 4)
        purpose_match = re.search(
            r'ITEM\s*4[.\s]*(?:PURPOSE OF TRANSACTION|PURPOSE OF THE TRANSACTION)?.*?[:.]?\s*(.+?)(?=ITEM\s*5|$)',
            filing_text,
            re.IGNORECASE | re.DOTALL
        )
        if purpose_match:
            purpose_text = purpose_match.group(1).strip()
            purpose_text = re.sub(r'\s+', ' ', purpose_text)[:1000]
            if len(purpose_text) > 20:
                data['purpose_description'] = purpose_text
        
        # Extract plans or proposals (Item 6)
        plans_match = re.search(
            r'ITEM\s*6[.\s]*(?:CONTRACTS|ARRANGEMENTS)?.*?[:.]?\s*(.+?)(?=ITEM\s*7|$)',
            filing_text,
            re.IGNORECASE | re.DOTALL
        )
        if plans_match:
            plans_text = plans_match.group(1).strip()
            plans_text = re.sub(r'\s+', ' ', plans_text)[:1000]
            if len(plans_text) > 20:
                data['plans_or_proposals'] = plans_text
        
        # Extract background (Item 2)
        background_match = re.search(
            r'ITEM\s*2[.\s]*(?:IDENTITY AND BACKGROUND)?.*?[:.]?\s*(.+?)(?=ITEM\s*3|$)',
            filing_text,
            re.IGNORECASE | re.DOTALL
        )
        if background_match:
            background_text = background_match.group(1).strip()
            background_text = re.sub(r'\s+', ' ', background_text)[:500]
            if len(background_text) > 20:
                data['background_of_filer'] = background_text
        
        # Determine intent type
        intent_type = "Other"
        filing_lower = filing_text.lower()
        
        if any(term in filing_lower for term in ['acquisition', 'merger', 'tender offer', 'going private']):
            intent_type = "M&A"
        elif any(term in filing_lower for term in ['activist', 'board representation', 'proxy', 'nominate director']):
            intent_type = "Activist"
        elif any(term in filing_lower for term in ['passive', 'investment purposes', 'ordinary course']):
            intent_type = "Passive"
        elif any(term in filing_lower for term in ['influence', 'change', 'strategic alternatives']):
            intent_type = "Activist"
        
        data['intent_type'] = intent_type
    
    except Exception as e:
        logger.warning(f"Error extracting intent info: {e}")
    
    return data


def download_filing_by_cik(cik: str, form_type: str = "SC 13D", limit: int = 10, days: int = 365) -> List[Dict]:
    """Download filings for a specific CIK."""
    from sec_edgar_downloader import Downloader
    
    filings = []
    temp_dir = tempfile.mkdtemp(prefix="sec_edgar_")
    
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=days)
    
    try:
        dl = Downloader("HedgeFolio", SEC_EMAIL, temp_dir)
        
        count = dl.get(
            form_type,
            cik,
            limit=limit,
            after=start_date.strftime("%Y-%m-%d"),
            before=end_date.strftime("%Y-%m-%d"),
            include_amends=True,
            download_details=True,
        )
        
        logger.info(f"Downloaded {count} {form_type} filings for CIK {cik}")
        
        filings = parse_downloaded_filings(temp_dir)
        
    except Exception as e:
        logger.error(f"Error downloading filings for CIK {cik}: {e}")
    
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Error cleaning up temp directory: {e}")
    
    return filings


def get_filings_by_company(company_name: str, days: int = 365) -> List[Dict]:
    """Get all 13D/13G filings for a specific company."""
    all_filings = download_recent_filings(days)
    
    company_filings = [
        f for f in all_filings
        if company_name.lower() in f.get('target_company_name', '').lower()
    ]
    
    logger.info(f"Found {len(company_filings)} filings for {company_name}")
    return company_filings


def get_filings_by_filer(filer_name: str, days: int = 365) -> List[Dict]:
    """Get all 13D/13G filings by a specific filer."""
    all_filings = download_recent_filings(days)
    
    filer_filings = [
        f for f in all_filings
        if filer_name.lower() in f.get('filer_name', '').lower()
    ]
    
    logger.info(f"Found {len(filer_filings)} filings by {filer_name}")
    return filer_filings
