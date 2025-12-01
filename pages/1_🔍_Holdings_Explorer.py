"""
Holdings Explorer Page - Search Securities Across All Funds
Uses database for all data access.
"""
import streamlit as st
import pandas as pd

from utils.db_queries import (
    get_summary_stats,
    search_securities,
    check_database_connection,
)

st.set_page_config(page_title="Holdings Explorer | Hedgefolio", page_icon="🔍", layout="wide")


def main():
    st.title("🔍 Holdings Explorer")
    
    # Documentation
    with st.expander("📖 How to Use This Page", expanded=False):
        st.markdown("""
        ## 🎯 Purpose
        Search and analyze specific securities across all hedge fund holdings.
        
        ## 🔍 How to Use
        
        ### 1. **Search for Securities**
        - Enter a company name or ticker symbol
        - Use partial names (e.g., "NVIDIA" or "Apple")
        - Search is case-insensitive
        
        ### 2. **Interpret Results**
        
        **Security Summary:**
        - **Total Value**: Combined value across all funds
        - **Total Shares**: Total shares held
        - **Fund Count**: Number of funds holding this security
        
        **Fund Holdings:**
        - **Position Value**: Value of each fund's position
        - **Shares Held**: Shares held by each fund
        
        ## 💡 Search Tips
        - Try company names: "APPLE", "NVIDIA", "TESLA"
        - Use partial matches: "MICRO" finds "MICROSOFT"
        """)
    
    # Check database
    if not check_database_connection():
        st.error("❌ Database connection failed.")
        return
    
    # Initialize session state
    if 'search_query' not in st.session_state:
        st.session_state.search_query = ""
    
    # Search interface
    query = st.text_input(
        "Search for securities:",
        value=st.session_state.search_query,
        placeholder="e.g., NVIDIA, Apple, Tesla",
        help="Enter a company name or ticker symbol"
    )
    
    if query != st.session_state.search_query:
        st.session_state.search_query = query
    
    if query:
        with st.spinner("Searching..."):
            security_results, fund_results = search_securities(query)
        
        if not security_results.empty:
            st.subheader(f"📊 Search Results for '{query}'")
            
            # Format security results
            display_securities = security_results.copy()
            display_securities['Total Value'] = display_securities['Total Value'].apply(lambda x: f"${x:,.0f}")
            display_securities['Total Shares'] = display_securities['Total Shares'].apply(lambda x: f"{x:,.0f}")
            
            st.dataframe(display_securities, use_container_width=True)
            
            if not fund_results.empty:
                st.subheader("🏢 Funds Holding This Security")
                
                # Format fund results
                display_funds = fund_results.copy()
                display_funds['Position Value'] = display_funds['Position Value'].apply(lambda x: f"${x:,.0f}")
                display_funds['Shares Held'] = display_funds['Shares Held'].apply(lambda x: f"{x:,.0f}")
                
                st.dataframe(display_funds, use_container_width=True)
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Funds Holding", len(fund_results))
                
                with col2:
                    total_value = fund_results['Position Value'].sum()
                    st.metric("Total Position Value", f"${total_value/1e9:.2f}B")
                
                with col3:
                    avg_position = fund_results['Position Value'].mean()
                    st.metric("Average Position", f"${avg_position/1e6:.1f}M")
        else:
            st.warning(f"No securities found matching '{query}'.")
    else:
        st.info("Enter a search term to find securities across all fund holdings.")
        
        # Example searches
        st.subheader("💡 Example Searches")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Search NVIDIA"):
                st.session_state.search_query = "NVIDIA"
                st.rerun()
        
        with col2:
            if st.button("Search Apple"):
                st.session_state.search_query = "APPLE"
                st.rerun()
        
        with col3:
            if st.button("Search Tesla"):
                st.session_state.search_query = "TESLA"
                st.rerun()


if __name__ == "__main__":
    main()

