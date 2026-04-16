"""
LLM Provider Factory - Supports multiple LLM providers via OpenAI-compatible API.

Supported providers:
- XAI (Grok) - default
- OpenAI
- Anthropic (via OpenAI-compatible endpoints)
- Any OpenAI-compatible API

Configuration via .env:
    LLM_PROVIDER=xai|openai|anthropic|custom
    XAI_API_KEY=your_xai_key
    OPENAI_API_KEY=your_openai_key
    ANTHROPIC_API_KEY=your_anthropic_key
    CUSTOM_API_KEY=your_custom_key
    CUSTOM_API_BASE=https://your-api.com/v1
"""

import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    """Configuration for an LLM provider."""
    provider: str
    api_key: str
    base_url: Optional[str]
    default_model: str
    

# Provider configurations
PROVIDER_CONFIGS = {
    "xai": {
        "env_key": "XAI_API_KEY",
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-beta",
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "base_url": None,  # Uses default OpenAI URL
        "default_model": "gpt-3.5-turbo",
    },
    "anthropic": {
        "env_key": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-haiku-20240307",
    },
    "custom": {
        "env_key": "CUSTOM_API_KEY",
        "base_url": os.getenv("CUSTOM_API_BASE"),
        "default_model": os.getenv("CUSTOM_MODEL", "gpt-3.5-turbo"),
    },
}


def get_llm_config() -> Optional[LLMConfig]:
    """
    Get LLM configuration based on environment variables.
    
    Priority:
    1. LLM_PROVIDER env var (if set)
    2. First available API key (XAI -> OpenAI -> Anthropic -> Custom)
    
    Returns:
        LLMConfig or None if no provider configured
    """
    # Check if specific provider is requested
    requested_provider = os.getenv("LLM_PROVIDER", "").lower()
    
    if requested_provider and requested_provider in PROVIDER_CONFIGS:
        config = PROVIDER_CONFIGS[requested_provider]
        api_key = os.getenv(config["env_key"])
        if api_key:
            return LLMConfig(
                provider=requested_provider,
                api_key=api_key,
                base_url=config["base_url"],
                default_model=config["default_model"],
            )
    
    # Auto-detect: try providers in order of preference
    for provider, config in PROVIDER_CONFIGS.items():
        api_key = os.getenv(config["env_key"])
        if api_key:
            return LLMConfig(
                provider=provider,
                api_key=api_key,
                base_url=config["base_url"],
                default_model=config["default_model"],
            )
    
    return None


def get_llm_client():
    """
    Get an OpenAI-compatible client configured for the active provider.
    
    Returns:
        OpenAI client instance or None if not configured
    """
    config = get_llm_config()
    if not config:
        print("No LLM provider configured. Set XAI_API_KEY, OPENAI_API_KEY, or another provider in .env")
        return None
    
    try:
        from openai import OpenAI
        
        client_kwargs = {"api_key": config.api_key}
        if config.base_url:
            client_kwargs["base_url"] = config.base_url
        
        return OpenAI(**client_kwargs)
    except ImportError:
        print("OpenAI package not installed. Run: pip install openai")
        return None


def get_default_model() -> str:
    """Get the default model for the current provider."""
    config = get_llm_config()
    return config.default_model if config else "gpt-3.5-turbo"


def get_provider_name() -> str:
    """Get the name of the current LLM provider."""
    config = get_llm_config()
    return config.provider if config else "none"


class LLMProvider:
    """
    High-level LLM provider interface.
    
    Usage:
        llm = LLMProvider()
        response = llm.complete("What is 2+2?")
        sector = llm.classify_sector("Apple Inc", "AAPL")
        ticker = llm.get_ticker("Microsoft Corporation")
    """
    
    def __init__(self):
        self.config = get_llm_config()
        self.client = get_llm_client()
        
        if self.config:
            print(f"LLM Provider initialized: {self.config.provider} (model: {self.config.default_model})")
    
    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self.client is not None
    
    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 100,
        temperature: float = 0.1,
    ) -> Optional[str]:
        """
        Send a completion request to the LLM.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            model: Model to use (defaults to provider's default)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
        
        Returns:
            Response text or None on error
        """
        if not self.client:
            return None
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=model or self.config.default_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"LLM completion error: {e}")
            return None
    
    def classify_sector(self, company_name: str, ticker: Optional[str] = None) -> Optional[str]:
        """
        Classify a company's sector using AI.
        
        Args:
            company_name: Company name
            ticker: Optional ticker symbol
        
        Returns:
            Sector name or None
        """
        prompt = f"""Given the company information below, provide the most likely sector/industry classification.
Return ONLY the sector name, nothing else.

Company: {company_name}
Ticker: {ticker if ticker else 'Not provided'}

Common sectors include: Technology, Healthcare, Financial Services, Consumer Cyclical, 
Consumer Defensive, Industrials, Energy, Basic Materials, Real Estate, Communication Services, 
Utilities, ETF.

Sector:"""
        
        response = self.complete(
            prompt=prompt,
            system_prompt="You are a financial analyst. Provide only the sector name, no additional text.",
            max_tokens=20,
            temperature=0.1,
        )
        
        if response and len(response) < 50 and not response.lower().startswith("i'm sorry"):
            return response
        return None
    
    def get_ticker(self, company_name: str) -> Optional[str]:
        """
        Get the ticker symbol for a company using AI.
        
        Args:
            company_name: Company name
        
        Returns:
            Ticker symbol or None
        """
        prompt = f"""Given the company name below, provide the most likely stock ticker symbol.
Return ONLY the ticker symbol, nothing else.

Company: {company_name}

Common ticker examples:
- Apple Inc -> AAPL
- Microsoft Corporation -> MSFT
- Tesla Inc -> TSLA
- JPMorgan Chase & Co -> JPM
- Goldman Sachs Group Inc -> GS
- Hess Corporation -> HES
- Advanced Micro Devices Inc -> AMD
- Marvell Technology Inc -> MRVL

Ticker:"""
        
        response = self.complete(
            prompt=prompt,
            system_prompt="You are a financial analyst. Provide only the ticker symbol, no additional text.",
            max_tokens=10,
            temperature=0.1,
        )
        
        if response:
            ticker = response.upper().strip()
            # Validate: should be alphanumeric and max 6 chars
            if len(ticker) <= 6 and ticker.replace(".", "").isalnum():
                return ticker
        return None
    
    def analyze_portfolio(self, holdings: List[Dict]) -> Optional[str]:
        """
        Generate AI analysis of a portfolio.
        
        Args:
            holdings: List of holdings with name, value, sector
        
        Returns:
            Analysis text or None
        """
        # Format holdings for the prompt
        holdings_text = "\n".join([
            f"- {h.get('name', 'Unknown')}: ${h.get('value', 0):,.0f} ({h.get('sector', 'Unknown')})"
            for h in holdings[:20]  # Limit to top 20
        ])
        
        prompt = f"""Analyze this hedge fund portfolio and provide key insights:

Top Holdings:
{holdings_text}

Provide a brief analysis (2-3 sentences) covering:
1. Sector concentration
2. Notable positions
3. Investment style indication"""
        
        return self.complete(
            prompt=prompt,
            system_prompt="You are a hedge fund analyst. Provide concise, professional analysis.",
            max_tokens=200,
            temperature=0.3,
        )


# Singleton instance for easy import
_llm_instance = None


def get_llm() -> LLMProvider:
    """Get the singleton LLM provider instance."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMProvider()
    return _llm_instance


# Convenience functions
def classify_sector(company_name: str, ticker: Optional[str] = None) -> Optional[str]:
    """Classify a company's sector using the default LLM provider."""
    return get_llm().classify_sector(company_name, ticker)


def get_ticker_from_llm(company_name: str) -> Optional[str]:
    """Get a ticker symbol using the default LLM provider."""
    return get_llm().get_ticker(company_name)


# Test
if __name__ == "__main__":
    print("Testing LLM Provider...")
    print(f"Provider: {get_provider_name()}")
    
    config = get_llm_config()
    if config:
        print(f"API Key: {config.api_key[:10]}...")
        print(f"Base URL: {config.base_url}")
        print(f"Model: {config.default_model}")
    
    llm = get_llm()
    if llm.is_available():
        print("\n--- Testing sector classification ---")
        sector = llm.classify_sector("Apple Inc", "AAPL")
        print(f"Apple Inc sector: {sector}")
        
        print("\n--- Testing ticker lookup ---")
        ticker = llm.get_ticker("Microsoft Corporation")
        print(f"Microsoft Corporation ticker: {ticker}")
        
        print("\n--- Testing general completion ---")
        response = llm.complete("What is the capital of France?", max_tokens=20)
        print(f"Response: {response}")
    else:
        print("LLM not available - check API keys in .env")


