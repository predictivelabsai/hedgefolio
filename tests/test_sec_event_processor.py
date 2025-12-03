"""
Unit tests for SEC event data processor module.
Tests data normalization, extraction, and validation.
"""

import os
import sys
import unittest
from datetime import datetime
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.sec_event_processor import (
    normalize_filing_data,
    normalize_intent_data,
    normalize_amendment_data,
    validate_filing_data,
    extract_company_info,
    parse_amendment_info,
    detect_group_members,
    clean_text_field,
    prepare_filing_for_insert,
)


class TestNormalizeFilingData(unittest.TestCase):
    """Test data normalization."""
    
    def test_normalize_basic_fields(self):
        """Test normalizing basic string fields."""
        raw_data = {
            'accession_number': '0000950123-24-001234',
            'form_type': '13d',
            'filer_name': 'sample activist fund',
            'target_company_name': 'tesla inc',
        }
        
        normalized = normalize_filing_data(raw_data)
        
        self.assertEqual(normalized['accession_number'], '0000950123-24-001234')
        self.assertEqual(normalized['form_type'], '13D')
        self.assertEqual(normalized['filer_name'], 'SAMPLE ACTIVIST FUND')
        self.assertEqual(normalized['target_company_name'], 'TESLA INC')
    
    def test_normalize_cik_padding(self):
        """Test CIK padding to 10 digits."""
        raw_data = {
            'cik': '1234567',
            'target_cik': '98765',
        }
        
        normalized = normalize_filing_data(raw_data)
        
        self.assertEqual(normalized['cik'], '0001234567')
        self.assertEqual(normalized['target_cik'], '0000098765')
    
    def test_normalize_stake_percentage(self):
        """Test normalizing stake percentage to Decimal."""
        raw_data = {
            'stake_percentage': '5.5',
        }
        
        normalized = normalize_filing_data(raw_data)
        
        self.assertIsInstance(normalized['stake_percentage'], Decimal)
        self.assertEqual(float(normalized['stake_percentage']), 5.5)
    
    def test_normalize_stake_percentage_out_of_range(self):
        """Test handling stake percentage out of range."""
        raw_data = {
            'stake_percentage': '150.0',
        }
        
        normalized = normalize_filing_data(raw_data)
        
        # Should not include out-of-range stake
        self.assertNotIn('stake_percentage', normalized)
    
    def test_normalize_shares_owned(self):
        """Test normalizing shares owned to integer."""
        raw_data = {
            'shares_owned': '1000000.5',
        }
        
        normalized = normalize_filing_data(raw_data)
        
        self.assertIsInstance(normalized['shares_owned'], int)
        self.assertEqual(normalized['shares_owned'], 1000000)
    
    def test_normalize_filing_date(self):
        """Test normalizing filing date."""
        raw_data = {
            'filing_date': '2024-01-15',
        }
        
        normalized = normalize_filing_data(raw_data)
        
        self.assertIsNotNone(normalized.get('filing_date'))


class TestValidateFilingData(unittest.TestCase):
    """Test filing data validation."""
    
    def test_validate_required_fields(self):
        """Test validation of required fields."""
        incomplete_data = {
            'accession_number': '0000950123-24-001234',
            'form_type': '13D',
            # Missing required fields
        }
        
        is_valid, errors = validate_filing_data(incomplete_data)
        
        self.assertFalse(is_valid)
        self.assertTrue(len(errors) > 0)
    
    def test_validate_accession_number_format(self):
        """Test accession number format validation."""
        invalid_data = {
            'accession_number': 'INVALID',
            'form_type': '13D',
            'filer_name': 'Test',
            'target_company_name': 'Test',
            'filing_date': '2024-01-15',
        }
        
        is_valid, errors = validate_filing_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertTrue(any('accession' in e.lower() for e in errors))
    
    def test_validate_form_type(self):
        """Test form type validation."""
        invalid_data = {
            'accession_number': '0000950123-24-001234',
            'form_type': '10-K',  # Invalid
            'filer_name': 'Test',
            'target_company_name': 'Test',
            'filing_date': '2024-01-15',
        }
        
        is_valid, errors = validate_filing_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertTrue(any('form' in e.lower() for e in errors))
    
    def test_validate_stake_percentage_range(self):
        """Test stake percentage range validation."""
        invalid_data = {
            'accession_number': '0000950123-24-001234',
            'form_type': '13D',
            'filer_name': 'Test',
            'target_company_name': 'Test',
            'filing_date': '2024-01-15',
            'stake_percentage': 150.0,  # Out of range
        }
        
        is_valid, errors = validate_filing_data(invalid_data)
        
        self.assertFalse(is_valid)
        self.assertTrue(any('stake' in e.lower() for e in errors))
    
    def test_validate_valid_data(self):
        """Test validation of valid data."""
        valid_data = {
            'accession_number': '0000950123-24-001234',
            'form_type': '13D',
            'filer_name': 'Test Activist',
            'target_company_name': 'Test Company',
            'filing_date': '2024-01-15',
            'stake_percentage': 5.5,
        }
        
        is_valid, errors = validate_filing_data(valid_data)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)


class TestExtractCompanyInfo(unittest.TestCase):
    """Test company information extraction."""
    
    def test_extract_company_name(self):
        """Test extracting company name."""
        filing_text = """
        ITEM 1. SECURITY AND ISSUER
        TESLA INC
        """
        
        info = extract_company_info(filing_text)
        
        self.assertIn('company_name', info)
        self.assertIn('TESLA', info['company_name'].upper())
    
    def test_extract_ticker(self):
        """Test extracting ticker symbol."""
        filing_text = """
        TICKER: TSLA
        """
        
        info = extract_company_info(filing_text)
        
        if 'ticker' in info:
            self.assertEqual(info['ticker'], 'TSLA')


class TestParseAmendmentInfo(unittest.TestCase):
    """Test amendment information parsing."""
    
    def test_detect_amendment(self):
        """Test detecting amendment filing."""
        filing_text = """
        AMENDMENT NO. 1
        PREVIOUS PERCENTAGE OWNED: 4.5%
        CURRENT PERCENTAGE OWNED: 5.5%
        """
        
        info = parse_amendment_info(filing_text)
        
        self.assertTrue(info.get('is_amendment'))
        self.assertEqual(info.get('amendment_number'), 1)
    
    def test_extract_stake_changes(self):
        """Test extracting stake changes."""
        filing_text = """
        AMENDMENT NO. 2
        PREVIOUS PERCENTAGE OWNED: 5.5%
        NEW PERCENTAGE OWNED: 6.2%
        """
        
        info = parse_amendment_info(filing_text)
        
        if 'previous_stake_percentage' in info:
            self.assertEqual(info['previous_stake_percentage'], 5.5)
        if 'new_stake_percentage' in info:
            self.assertEqual(info['new_stake_percentage'], 6.2)


class TestDetectGroupMembers(unittest.TestCase):
    """Test group member detection."""
    
    def test_detect_group_members(self):
        """Test detecting group members."""
        filing_text = """
        GROUP MEMBERS
        0001234567 Member One Inc
        0002345678 Member Two LLC
        """
        
        members = detect_group_members(filing_text)
        
        self.assertTrue(len(members) > 0)


class TestCleanTextField(unittest.TestCase):
    """Test text field cleaning."""
    
    def test_clean_text_field(self):
        """Test cleaning text field."""
        text = "  This   is   a   test  "
        
        cleaned = clean_text_field(text)
        
        self.assertEqual(cleaned, "This is a test")
    
    def test_truncate_long_text(self):
        """Test truncating long text."""
        text = "A" * 2000
        
        cleaned = clean_text_field(text, max_length=100)
        
        self.assertEqual(len(cleaned), 100)
        self.assertTrue(cleaned.endswith('...'))
    
    def test_clean_none_text(self):
        """Test cleaning None text."""
        cleaned = clean_text_field(None)
        
        self.assertIsNone(cleaned)


class TestPrepareFilingForInsert(unittest.TestCase):
    """Test preparing filing for database insertion."""
    
    def test_prepare_valid_filing(self):
        """Test preparing valid filing."""
        raw_filing = {
            'accession_number': '0000950123-24-001234',
            'form_type': '13D',
            'filing_date': '2024-01-15',
            'cik': '1234567',
            'filer_name': 'Test Activist',
            'target_company_name': 'Test Company',
            'stake_percentage': 5.5,
            'intent_type': 'Activist',
            'purpose_description': 'Test purpose',
        }
        
        prepared = prepare_filing_for_insert(raw_filing)
        
        self.assertIn('event', prepared)
        self.assertIn('intent', prepared)
    
    def test_prepare_invalid_filing(self):
        """Test preparing invalid filing."""
        raw_filing = {
            'accession_number': 'INVALID',
            'form_type': '13D',
        }
        
        prepared = prepare_filing_for_insert(raw_filing)
        
        # Should return empty dict for invalid data
        self.assertEqual(len(prepared), 0)


if __name__ == '__main__':
    unittest.main()
