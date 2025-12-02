"""
SEC event data processor for normalization and validation.
Cleans and prepares extracted filing data for database insertion.
"""

import re
import logging
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


def normalize_filing_data(raw_data: Dict) -> Dict:
    """
    Normalize and clean extracted filing data.
    
    Args:
        raw_data (Dict): Raw extracted data from downloader
    
    Returns:
        Dict: Normalized dictionary ready for database insertion
    """
    normalized = {}
    
    try:
        # String fields - trim and uppercase where appropriate
        normalized['accession_number'] = raw_data.get('accession_number', '').strip()
        normalized['form_type'] = raw_data.get('form_type', '').strip().upper()
        normalized['cik'] = str(raw_data.get('cik', '')).strip().zfill(10)
        normalized['filer_name'] = raw_data.get('filer_name', '').strip().upper()
        normalized['filer_address'] = raw_data.get('filer_address', '').strip() if raw_data.get('filer_address') else None
        
        # Target company info
        normalized['target_cik'] = str(raw_data.get('target_cik', '')).strip().zfill(10) if raw_data.get('target_cik') else None
        normalized['target_company_name'] = raw_data.get('target_company_name', '').strip().upper()
        normalized['target_ticker'] = raw_data.get('target_ticker', '').strip().upper() if raw_data.get('target_ticker') else None
        
        # Filing dates
        filing_date = raw_data.get('filing_date')
        if filing_date:
            if isinstance(filing_date, str):
                # Parse date string
                for fmt in ['%Y-%m-%d', '%Y%m%d', '%m/%d/%Y']:
                    try:
                        normalized['filing_date'] = datetime.strptime(filing_date, fmt).date()
                        break
                    except ValueError:
                        continue
            else:
                normalized['filing_date'] = filing_date
        
        # Numeric fields
        if raw_data.get('stake_percentage') is not None:
            try:
                stake = float(raw_data.get('stake_percentage'))
                if 0 <= stake <= 100:
                    normalized['stake_percentage'] = Decimal(str(round(stake, 2)))
            except (ValueError, TypeError):
                logger.warning(f"Invalid stake percentage: {raw_data.get('stake_percentage')}")
        
        if raw_data.get('shares_owned') is not None:
            try:
                normalized['shares_owned'] = int(float(raw_data.get('shares_owned')))
            except (ValueError, TypeError):
                logger.warning(f"Invalid shares owned: {raw_data.get('shares_owned')}")
        
        if raw_data.get('shares_outstanding') is not None:
            try:
                normalized['shares_outstanding'] = int(float(raw_data.get('shares_outstanding')))
            except (ValueError, TypeError):
                logger.warning(f"Invalid shares outstanding: {raw_data.get('shares_outstanding')}")
        
        # Status fields
        normalized['filing_status'] = raw_data.get('filing_status', 'Initial').strip()
        normalized['amendment_number'] = raw_data.get('amendment_number')
        normalized['is_amendment'] = raw_data.get('is_amendment', False)
        
        logger.debug(f"Normalized filing: {normalized.get('accession_number')}")
        return normalized
    
    except Exception as e:
        logger.error(f"Error normalizing filing data: {e}")
        return {}


def normalize_intent_data(raw_data: Dict) -> Dict:
    """
    Normalize intent information.
    
    Args:
        raw_data (Dict): Raw intent data
    
    Returns:
        Dict: Normalized intent data
    """
    normalized = {}
    
    try:
        normalized['accession_number'] = raw_data.get('accession_number', '').strip()
        normalized['intent_type'] = raw_data.get('intent_type', 'Other').strip()
        normalized['purpose_description'] = raw_data.get('purpose_description', '').strip() if raw_data.get('purpose_description') else None
        normalized['plans_or_proposals'] = raw_data.get('plans_or_proposals', '').strip() if raw_data.get('plans_or_proposals') else None
        normalized['background_of_filer'] = raw_data.get('background_of_filer', '').strip() if raw_data.get('background_of_filer') else None
        
        return normalized
    
    except Exception as e:
        logger.error(f"Error normalizing intent data: {e}")
        return {}


def normalize_amendment_data(raw_data: Dict) -> Dict:
    """
    Normalize amendment information.
    
    Args:
        raw_data (Dict): Raw amendment data
    
    Returns:
        Dict: Normalized amendment data
    """
    normalized = {}
    
    try:
        normalized['parent_accession_number'] = raw_data.get('parent_accession_number', '').strip()
        normalized['amendment_accession_number'] = raw_data.get('amendment_accession_number', '').strip()
        
        # Amendment date
        amendment_date = raw_data.get('amendment_date')
        if amendment_date:
            if isinstance(amendment_date, str):
                for fmt in ['%Y-%m-%d', '%Y%m%d', '%m/%d/%Y']:
                    try:
                        normalized['amendment_date'] = datetime.strptime(amendment_date, fmt).date()
                        break
                    except ValueError:
                        continue
            else:
                normalized['amendment_date'] = amendment_date
        
        normalized['amendment_number'] = raw_data.get('amendment_number')
        normalized['amendment_description'] = raw_data.get('amendment_description', '').strip() if raw_data.get('amendment_description') else None
        
        # Numeric fields
        if raw_data.get('previous_stake_percentage') is not None:
            try:
                stake = float(raw_data.get('previous_stake_percentage'))
                if 0 <= stake <= 100:
                    normalized['previous_stake_percentage'] = Decimal(str(round(stake, 2)))
            except (ValueError, TypeError):
                pass
        
        if raw_data.get('new_stake_percentage') is not None:
            try:
                stake = float(raw_data.get('new_stake_percentage'))
                if 0 <= stake <= 100:
                    normalized['new_stake_percentage'] = Decimal(str(round(stake, 2)))
            except (ValueError, TypeError):
                pass
        
        if raw_data.get('previous_shares') is not None:
            try:
                normalized['previous_shares'] = int(float(raw_data.get('previous_shares')))
            except (ValueError, TypeError):
                pass
        
        if raw_data.get('new_shares') is not None:
            try:
                normalized['new_shares'] = int(float(raw_data.get('new_shares')))
            except (ValueError, TypeError):
                pass
        
        return normalized
    
    except Exception as e:
        logger.error(f"Error normalizing amendment data: {e}")
        return {}


def validate_filing_data(data: Dict) -> Tuple[bool, List[str]]:
    """
    Validate filing data before database insertion.
    
    Args:
        data (Dict): Filing data to validate
    
    Returns:
        Tuple[bool, List[str]]: (is_valid, list_of_errors)
    """
    errors = []
    
    # Check required fields
    required_fields = [
        'accession_number',
        'filing_date',
        'form_type',
        'filer_name',
        'target_company_name'
    ]
    
    for field in required_fields:
        if not data.get(field):
            errors.append(f"Missing required field: {field}")
    
    # Validate accession number format
    accession = data.get('accession_number', '')
    if accession and not re.match(r'^\d{10}-\d{2}-\d{6}$', accession):
        errors.append(f"Invalid accession number format: {accession}")
    
    # Validate form type
    form_type = data.get('form_type', '')
    if form_type and form_type not in ['13D', '13G']:
        errors.append(f"Invalid form type: {form_type}")
    
    # Validate stake percentage
    if data.get('stake_percentage') is not None:
        try:
            stake = float(data.get('stake_percentage'))
            if not (0 <= stake <= 100):
                errors.append(f"Stake percentage out of range: {stake}")
        except (ValueError, TypeError):
            errors.append(f"Invalid stake percentage: {data.get('stake_percentage')}")
    
    # Validate filing date
    filing_date = data.get('filing_date')
    if filing_date:
        try:
            if isinstance(filing_date, str):
                datetime.strptime(filing_date, '%Y-%m-%d')
        except ValueError:
            errors.append(f"Invalid filing date format: {filing_date}")
    
    # Validate CIK format
    cik = data.get('cik', '')
    if cik and not re.match(r'^\d{10}$', str(cik)):
        errors.append(f"Invalid CIK format: {cik}")
    
    is_valid = len(errors) == 0
    
    if not is_valid:
        logger.warning(f"Validation errors for {accession}: {errors}")
    
    return is_valid, errors


def extract_company_info(filing_text: str) -> Dict:
    """
    Extract target company information from filing text.
    
    Args:
        filing_text (str): Raw filing text
    
    Returns:
        Dict: Dictionary with company_name, cik, ticker
    """
    company_info = {}
    
    try:
        # Extract company name from Item 1
        company_match = re.search(
            r'ITEM 1.*?SECURITY AND ISSUER.*?:?\s*(.+?)(?:\n|$)',
            filing_text,
            re.IGNORECASE
        )
        if company_match:
            company_info['company_name'] = company_match.group(1).strip()
        
        # Try to extract ticker
        ticker_match = re.search(
            r'(?:TICKER|Symbol).*?:?\s*([A-Z]{1,5})',
            filing_text,
            re.IGNORECASE
        )
        if ticker_match:
            company_info['ticker'] = ticker_match.group(1).strip()
        
        # Extract CIK
        cik_match = re.search(
            r'(?:TARGET|ISSUER).*?CIK.*?:?\s*(\d+)',
            filing_text,
            re.IGNORECASE
        )
        if cik_match:
            company_info['cik'] = cik_match.group(1).zfill(10)
    
    except Exception as e:
        logger.warning(f"Error extracting company info: {e}")
    
    return company_info


def parse_amendment_info(filing_text: str) -> Dict:
    """
    Parse amendment details from 13D/13G filing.
    
    Args:
        filing_text (str): Raw filing text
    
    Returns:
        Dict: Dictionary with amendment information
    """
    amendment_info = {}
    
    try:
        # Check if this is an amendment
        if 'AMENDMENT' in filing_text.upper():
            amendment_info['is_amendment'] = True
            
            # Extract amendment number
            amend_match = re.search(
                r'AMENDMENT NO\.?\s*:?\s*(\d+)',
                filing_text,
                re.IGNORECASE
            )
            if amend_match:
                amendment_info['amendment_number'] = int(amend_match.group(1))
            
            # Extract previous stake
            prev_stake_match = re.search(
                r'PREVIOUS PERCENTAGE OWNED.*?:?\s*(\d+\.?\d*)',
                filing_text,
                re.IGNORECASE
            )
            if prev_stake_match:
                amendment_info['previous_stake_percentage'] = float(prev_stake_match.group(1))
            
            # Extract new stake
            new_stake_match = re.search(
                r'(?:NEW|CURRENT) PERCENTAGE OWNED.*?:?\s*(\d+\.?\d*)',
                filing_text,
                re.IGNORECASE
            )
            if new_stake_match:
                amendment_info['new_stake_percentage'] = float(new_stake_match.group(1))
    
    except Exception as e:
        logger.warning(f"Error parsing amendment info: {e}")
    
    return amendment_info


def detect_group_members(filing_text: str) -> List[Dict]:
    """
    Detect group members for group filings.
    
    Args:
        filing_text (str): Raw filing text
    
    Returns:
        List[Dict]: List of group members
    """
    members = []
    
    try:
        # Look for group members section
        if 'GROUP MEMBERS' in filing_text.upper():
            # Extract section
            group_section = re.search(
                r'GROUP MEMBERS.*?:?\s*(.+?)(?:ITEM \d|$)',
                filing_text,
                re.IGNORECASE | re.DOTALL
            )
            
            if group_section:
                group_text = group_section.group(1)
                
                # Extract member information
                member_lines = group_text.split('\n')
                for line in member_lines:
                    line = line.strip()
                    if line and len(line) > 5:
                        # Try to extract CIK and name
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                cik = int(parts[0])
                                name = ' '.join(parts[1:])
                                members.append({
                                    'member_cik': str(cik).zfill(10),
                                    'member_name': name
                                })
                            except ValueError:
                                pass
    
    except Exception as e:
        logger.warning(f"Error detecting group members: {e}")
    
    return members


def clean_text_field(text: str, max_length: int = 1000) -> Optional[str]:
    """
    Clean and truncate text field.
    
    Args:
        text (str): Text to clean
        max_length (int): Maximum length
    
    Returns:
        Optional[str]: Cleaned text or None
    """
    if not text:
        return None
    
    # Remove extra whitespace
    cleaned = ' '.join(text.split())
    
    # Truncate if needed
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length - 3] + '...'
    
    return cleaned if cleaned else None


def prepare_filing_for_insert(raw_filing: Dict) -> Dict:
    """
    Prepare complete filing data for database insertion.
    
    Args:
        raw_filing (Dict): Raw filing data from downloader
    
    Returns:
        Dict: Prepared filing data with all normalized fields
    """
    prepared = {}
    
    try:
        # Normalize main filing data
        normalized = normalize_filing_data(raw_filing)
        prepared['event'] = normalized
        
        # Validate
        is_valid, errors = validate_filing_data(normalized)
        if not is_valid:
            logger.warning(f"Validation errors: {errors}")
            return {}
        
        # Prepare intent data if 13D
        if normalized.get('form_type') == '13D':
            intent_data = {
                'accession_number': normalized.get('accession_number'),
                'intent_type': raw_filing.get('intent_type'),
                'purpose_description': clean_text_field(raw_filing.get('purpose_description')),
                'plans_or_proposals': clean_text_field(raw_filing.get('plans_or_proposals')),
                'background_of_filer': clean_text_field(raw_filing.get('background_of_filer')),
            }
            normalized_intent = normalize_intent_data(intent_data)
            if normalized_intent.get('accession_number'):
                prepared['intent'] = normalized_intent
        
        # Prepare group members if present
        if raw_filing.get('group_members'):
            prepared['group_members'] = [
                {
                    'accession_number': normalized.get('accession_number'),
                    'member_name': member.get('member_name', '').strip(),
                    'member_cik': member.get('member_cik', '').strip(),
                }
                for member in raw_filing.get('group_members', [])
                if member.get('member_name')
            ]
        
        return prepared
    
    except Exception as e:
        logger.error(f"Error preparing filing for insert: {e}")
        return {}
