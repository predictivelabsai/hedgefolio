"""
About Hedgefolio - Methodology and Data Sources
"""
import streamlit as st

st.set_page_config(page_title="About | Hedgefolio", page_icon="📖", layout="wide")


def main():
    st.title("📖 About Hedgefolio")
    
    st.markdown("""
    ## Invest Like a Hedge Fund Manager
    
    Hedgefolio provides retail investors with insights into the portfolios of the world's 
    largest and most successful hedge funds. By analyzing SEC 13F filings, we help you 
    understand what the smart money is buying and selling.
    """)
    
    st.divider()
    
    # What is SEC Form 13F
    st.header("📋 What is SEC Form 13F?")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        **Form 13F** is a quarterly report required by the U.S. Securities and Exchange Commission (SEC) 
        that must be filed by institutional investment managers who manage **$100 million or more** 
        in qualifying assets.
        
        ### Who Must File?
        - Hedge funds
        - Mutual funds
        - Pension funds
        - Insurance companies
        - Bank trust departments
        - Investment advisors
        
        ### What's Reported?
        - **Equity holdings** (stocks)
        - **Convertible bonds**
        - **Stock options** (puts and calls)
        - **ETFs** (Exchange-Traded Funds)
        - **American Depositary Receipts (ADRs)**
        
        The filing includes the name of the security, CUSIP number, number of shares held, 
        and the market value of each position.
        """)
    
    with col2:
        st.info("""
        **💡 Key Insight**
        
        13F filings give you a window into the 
        investment strategies of the world's 
        most sophisticated investors.
        
        While you can't copy their trades in 
        real-time, you can learn from their 
        long-term investment decisions.
        """)
    
    st.divider()
    
    # Filing Schedule
    st.header("📅 Filing Schedule & Data Freshness")
    
    st.markdown("""
    ### Quarterly Filing Deadlines
    
    13F filings are due **within 45 days** after the end of each calendar quarter:
    """)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Q1 (Jan-Mar)", "May 15")
        st.caption("Holdings as of March 31")
    
    with col2:
        st.metric("Q2 (Apr-Jun)", "August 14")
        st.caption("Holdings as of June 30")
    
    with col3:
        st.metric("Q3 (Jul-Sep)", "November 14")
        st.caption("Holdings as of September 30")
    
    with col4:
        st.metric("Q4 (Oct-Dec)", "February 14")
        st.caption("Holdings as of December 31")
    
    st.warning("""
    **⚠️ Important Timing Note**
    
    Because filings are due 45 days after quarter-end, the data represents a **snapshot in time** 
    that may be 6-8 weeks old by the time it's publicly available. Large funds may have already 
    adjusted their positions since the filing date.
    """)
    
    st.divider()
    
    # Our Methodology
    st.header("🔬 Our Methodology")
    
    st.markdown("""
    ### Data Collection
    
    We collect and process 13F filings directly from the SEC's EDGAR database. Our data pipeline:
    
    1. **Downloads** the latest quarterly bulk 13F data from SEC EDGAR
    2. **Parses** the filing data including holdings, manager information, and signatures
    3. **Enriches** with real-time stock data from Yahoo Finance (prices, sectors)
    4. **Stores** in a PostgreSQL database for fast querying
    5. **Updates** daily to capture amendments and late filings
    
    ### Data Processing
    
    | Data Type | Source | Update Frequency |
    |-----------|--------|------------------|
    | Holdings Data | SEC EDGAR 13F Filings | Quarterly + Daily amendments |
    | Stock Prices | Yahoo Finance | Real-time |
    | Sector Classification | Yahoo Finance + AI | On-demand |
    | Ticker Mapping | Manual + Yahoo Finance | Continuous |
    
    ### Limitations
    
    - **Delay**: Data is 45+ days old at time of filing
    - **Long positions only**: 13F doesn't require disclosure of short positions
    - **No bond details**: Most fixed income positions are excluded
    - **Threshold**: Only managers with $100M+ must file
    - **Amendments**: Funds may file amendments that update previous filings
    """)
    
    st.divider()
    
    # How to Use Hedgefolio
    st.header("🎯 How to Use Hedgefolio")
    
    st.markdown("""
    ### Investment Research Workflow
    
    **1. Discover Top Funds** 📈
    - Browse the main page to see portfolio treemaps of major hedge funds
    - Compare portfolio allocations across different investment styles
    
    **2. Search for Securities** 🔍
    - Use Holdings Explorer to find which funds own specific stocks
    - Identify "crowded trades" where many funds hold the same positions
    
    **3. Track Market Trends** 📊
    - View Market Insights to see the most popular securities
    - Understand institutional sentiment for specific sectors
    
    **4. Get Notified** 📬
    - Subscribe to email updates to receive notifications when new filings are available
    - Stay informed about major portfolio changes from top funds
    """)
    
    st.divider()
    
    # Data Coverage
    st.header("📊 Data Coverage")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### What's Included
        - ✅ All 13F-HR (Holdings Report) filings
        - ✅ 13F-HR/A (Amended Holdings Reports)
        - ✅ Manager information and signatures
        - ✅ Individual position details
        - ✅ Voting authority information
        """)
    
    with col2:
        st.markdown("""
        ### What's NOT Included
        - ❌ Real-time trading data
        - ❌ Short positions
        - ❌ Private company holdings
        - ❌ Most fixed income positions
        - ❌ Positions under $200,000
        """)
    
    st.divider()
    
    # Legal Disclaimer
    st.header("⚖️ Disclaimer")
    
    st.markdown("""
    **This is not investment advice.** Hedgefolio provides information for educational and 
    research purposes only. Past performance of hedge funds does not guarantee future results.
    
    - The data presented may contain errors or be outdated
    - Investment decisions should not be based solely on 13F filings
    - Hedge fund positions may have changed since the filing date
    - Always conduct your own research and consult a financial advisor
    
    SEC 13F data is public information provided by the U.S. Securities and Exchange Commission.
    """)
    
    st.divider()
    
    # Contact
    st.header("📧 Contact")
    
    st.markdown("""
    Questions or feedback? We'd love to hear from you.
    
    Subscribe to our mailing list using the sidebar to receive updates and new features.
    """)


if __name__ == "__main__":
    main()

