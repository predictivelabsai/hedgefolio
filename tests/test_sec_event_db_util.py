"""
Unit tests for SEC event database utilities.
Tests database operations and queries.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.sec_event_db_util import (
    insert_sec_event,
    insert_sec_event_intent,
    insert_amendment,
    insert_group_member,
    get_recent_events,
    get_events_by_ticker,
    get_events_by_filer,
    get_activist_events,
    get_amendment_history,
    get_event_statistics,
    get_top_filers,
    get_top_targets,
)


class TestInsertSecEvent(unittest.TestCase):
    """Test inserting SEC events."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.event_data = {
            'accession_number': '0000950123-24-001234',
            'filing_date': datetime.now().date(),
            'form_type': '13D',
            'cik': '0001234567',
            'filer_name': 'TEST ACTIVIST',
            'target_company_name': 'TEST COMPANY',
            'stake_percentage': 5.5,
        }
    
    def test_insert_valid_event(self):
        """Test inserting valid event."""
        # Mock the query to return None (no existing event)
        self.mock_session.query.return_value.filter.return_value.first.return_value = None
        
        result = insert_sec_event(self.mock_session, self.event_data)
        
        # Should call add and commit
        self.mock_session.add.assert_called_once()
        self.mock_session.commit.assert_called_once()
    
    def test_insert_duplicate_event(self):
        """Test handling duplicate event."""
        # Mock the query to return existing event
        existing_event = Mock()
        self.mock_session.query.return_value.filter.return_value.first.return_value = existing_event
        
        result = insert_sec_event(self.mock_session, self.event_data)
        
        # Should not call add for duplicate
        self.mock_session.add.assert_not_called()
    
    def test_insert_invalid_event(self):
        """Test inserting invalid event."""
        invalid_data = {
            'accession_number': 'INVALID',
        }
        
        result = insert_sec_event(self.mock_session, invalid_data)
        
        # Should return None for invalid data
        self.assertIsNone(result)


class TestInsertSecEventIntent(unittest.TestCase):
    """Test inserting event intent."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.intent_data = {
            'accession_number': '0000950123-24-001234',
            'intent_type': 'Activist',
            'purpose_description': 'Test purpose',
        }
    
    def test_insert_valid_intent(self):
        """Test inserting valid intent."""
        # Mock the event query
        mock_event = Mock()
        self.mock_session.query.return_value.filter.return_value.first.side_effect = [
            mock_event,  # Parent event exists
            None,  # No existing intent
        ]
        
        result = insert_sec_event_intent(self.mock_session, self.intent_data)
        
        self.mock_session.add.assert_called_once()


class TestGetRecentEvents(unittest.TestCase):
    """Test getting recent events."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
    
    def test_get_recent_events(self):
        """Test retrieving recent events."""
        # Mock the query chain
        mock_events = [Mock(), Mock()]
        self.mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_events
        
        result = get_recent_events(self.mock_session, days=30)
        
        self.assertEqual(len(result), 2)
    
    def test_get_recent_events_empty(self):
        """Test retrieving when no events exist."""
        self.mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        result = get_recent_events(self.mock_session, days=30)
        
        self.assertEqual(len(result), 0)


class TestGetEventsByTicker(unittest.TestCase):
    """Test getting events by ticker."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
    
    def test_get_events_by_ticker(self):
        """Test retrieving events by ticker."""
        mock_events = [Mock(), Mock()]
        self.mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_events
        
        result = get_events_by_ticker(self.mock_session, 'TSLA')
        
        self.assertEqual(len(result), 2)


class TestGetEventsByFiler(unittest.TestCase):
    """Test getting events by filer."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
    
    def test_get_events_by_filer(self):
        """Test retrieving events by filer."""
        mock_events = [Mock()]
        self.mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_events
        
        result = get_events_by_filer(self.mock_session, 'Activist Fund')
        
        self.assertEqual(len(result), 1)


class TestGetActivistEvents(unittest.TestCase):
    """Test getting activist events."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
    
    def test_get_activist_events(self):
        """Test retrieving activist events."""
        mock_event = Mock()
        mock_event.event_id = 1
        mock_event.accession_number = '0000950123-24-001234'
        mock_event.filing_date = datetime.now().date()
        mock_event.filer_name = 'Test'
        mock_event.target_company_name = 'Company'
        mock_event.target_ticker = 'TSLA'
        mock_event.stake_percentage = 5.5
        mock_event.shares_owned = 1000000
        mock_event.intent = Mock()
        mock_event.intent.intent_type = 'Activist'
        mock_event.intent.purpose_description = 'Test'
        
        self.mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_event]
        
        result = get_activist_events(self.mock_session, days=90)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['intent_type'], 'Activist')


class TestGetAmendmentHistory(unittest.TestCase):
    """Test getting amendment history."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
    
    def test_get_amendment_history(self):
        """Test retrieving amendment history."""
        mock_amendments = [Mock(), Mock()]
        self.mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_amendments
        
        result = get_amendment_history(self.mock_session, '0000950123-24-001234')
        
        self.assertEqual(len(result), 2)


class TestGetEventStatistics(unittest.TestCase):
    """Test getting event statistics."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
    
    def test_get_event_statistics(self):
        """Test retrieving event statistics."""
        # Mock the scalar returns
        self.mock_session.query.return_value.filter.return_value.scalar.side_effect = [
            100,  # total_events
            60,   # total_13d
            40,   # total_13g
            5.5,  # avg_stake
        ]
        
        result = get_event_statistics(self.mock_session, days=30)
        
        self.assertEqual(result['total_events'], 100)
        self.assertEqual(result['total_13d'], 60)
        self.assertEqual(result['total_13g'], 40)


class TestGetTopFilers(unittest.TestCase):
    """Test getting top filers."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
    
    def test_get_top_filers(self):
        """Test retrieving top filers."""
        mock_filer = Mock()
        mock_filer.filer_name = 'Test Activist'
        mock_filer.filing_count = 10
        mock_filer.unique_targets = 5
        mock_filer.avg_stake = 5.5
        mock_filer.latest_filing = datetime.now().date()
        
        self.mock_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_filer]
        
        result = get_top_filers(self.mock_session, limit=10)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['filing_count'], 10)


class TestGetTopTargets(unittest.TestCase):
    """Test getting top targets."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
    
    def test_get_top_targets(self):
        """Test retrieving top targets."""
        mock_target = Mock()
        mock_target.target_company_name = 'Test Company'
        mock_target.target_ticker = 'TSLA'
        mock_target.event_count = 5
        mock_target.unique_filers = 3
        mock_target.max_stake = 9.5
        
        self.mock_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_target]
        
        result = get_top_targets(self.mock_session, limit=10)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['event_count'], 5)


if __name__ == '__main__':
    unittest.main()
