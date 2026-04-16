"""
AI utilities for sector classification and ticker symbol lookup.
Uses the llm_provider factory to support multiple LLM backends (XAI, OpenAI, etc.)

Note: This module maintains backward compatibility with the original OpenAI-specific
function names, but now uses the configurable LLM provider under the hood.
"""

from typing import Optional
from dotenv import load_dotenv

# Import from llm_provider
from utils.llm_provider import (
    get_llm,
    classify_sector as _classify_sector,
    get_ticker_from_llm as _get_ticker,
    get_provider_name,
)

load_dotenv()


def get_sector_from_openai(company_name: str, ticker: Optional[str] = None) -> Optional[str]:
    """
    Use AI to determine the most likely sector for a company.
    
    Note: Despite the name, this now uses the configured LLM provider
    (XAI by default, or OpenAI if configured).
    
    Args:
        company_name (str): The name of the company
        ticker (Optional[str]): The ticker symbol if available
    
    Returns:
        Optional[str]: The sector name or None if error
    """
    return _classify_sector(company_name, ticker)


def get_ticker_from_openai(company_name: str) -> Optional[str]:
    """
    Use AI to determine the most likely ticker symbol for a company.
    
    Note: Despite the name, this now uses the configured LLM provider
    (XAI by default, or OpenAI if configured).
    
    Args:
        company_name (str): The name of the company
    
    Returns:
        Optional[str]: The ticker symbol or None if error
    """
    return _get_ticker(company_name)


def get_ticker_with_fallback(company_name: str, use_cache: bool = True) -> Optional[str]:
    """
    Get ticker symbol with caching to avoid repeated API calls.
    
    Args:
        company_name (str): The name of the company
        use_cache (bool): Whether to use cached results
    
    Returns:
        Optional[str]: The ticker symbol or None if error
    """
    # Simple in-memory cache
    if not hasattr(get_ticker_with_fallback, 'cache'):
        get_ticker_with_fallback.cache = {}
    
    # Create cache key
    cache_key = f"ticker_{company_name}"
    
    # Check cache first
    if use_cache and cache_key in get_ticker_with_fallback.cache:
        return get_ticker_with_fallback.cache[cache_key]
    
    # Get ticker from LLM
    ticker = _get_ticker(company_name)
    
    # Cache the result
    if ticker:
        get_ticker_with_fallback.cache[cache_key] = ticker
    
    return ticker


def get_sector_with_fallback(company_name: str, ticker: Optional[str] = None, use_cache: bool = True) -> Optional[str]:
    """
    Get sector information with caching to avoid repeated API calls.
    
    Args:
        company_name (str): The name of the company
        ticker (Optional[str]): The ticker symbol if available
        use_cache (bool): Whether to use cached results
    
    Returns:
        Optional[str]: The sector name or None if error
    """
    # Simple in-memory cache
    if not hasattr(get_sector_with_fallback, 'cache'):
        get_sector_with_fallback.cache = {}
    
    # Create cache key
    cache_key = f"{company_name}_{ticker}" if ticker else company_name
    
    # Check cache first
    if use_cache and cache_key in get_sector_with_fallback.cache:
        return get_sector_with_fallback.cache[cache_key]
    
    # Get sector from LLM
    sector = _classify_sector(company_name, ticker)
    
    # Cache the result
    if sector:
        get_sector_with_fallback.cache[cache_key] = sector
    
    return sector


def get_current_provider() -> str:
    """Get the name of the current LLM provider being used."""
    return get_provider_name()


def is_llm_available() -> bool:
    """Check if an LLM provider is available."""
    return get_llm().is_available()


# Test
if __name__ == "__main__":
    print(f"Current LLM Provider: {get_current_provider()}")
    print(f"LLM Available: {is_llm_available()}")
    
    if is_llm_available():
        # Test sector classification
        print("\nTesting sector classification:")
        sector = get_sector_from_openai("Apple Inc", "AAPL")
        print(f"  Apple Inc: {sector}")
        
        sector = get_sector_from_openai("JPMorgan Chase & Co", "JPM")
        print(f"  JPMorgan Chase: {sector}")
        
        # Test ticker lookup
        print("\nTesting ticker lookup:")
        ticker = get_ticker_from_openai("Microsoft Corporation")
        print(f"  Microsoft Corporation: {ticker}")
        
        ticker = get_ticker_from_openai("Tesla Inc")
        print(f"  Tesla Inc: {ticker}")
    else:
        print("\nNo LLM configured. Set XAI_API_KEY or OPENAI_API_KEY in .env")
