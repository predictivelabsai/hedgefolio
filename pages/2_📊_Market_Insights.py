"""
Market Insights Page - Popular Securities and Market Trends
Uses database for all data access.
"""
import streamlit as st
import pandas as pd
import plotly.express as px

from utils.db_queries import (
    get_summary_stats,
    get_popular_securities,
    get_fund_concentration,
    get_security_type_distribution,
    get_value_statistics,
    check_database_connection,
)

st.set_page_config(page_title="Market Insights | Hedgefolio", page_icon="📊", layout="wide")


def main():
    st.title("📊 Market Insights")
    
    # Documentation
    with st.expander("📖 How to Use This Page", expanded=False):
        st.markdown("""
        ## 🎯 Purpose
        Get a bird's-eye view of the hedge fund market including popular securities and fund concentration.
        
        ## 📊 Sections
        
        ### 1. **Market Overview**
        Key metrics across all funds.
        
        ### 2. **Most Popular Securities**
        Securities held by the most funds with highest total value.
        
        ### 3. **Fund Concentration**
        Largest funds by portfolio value.
        
        ### 4. **Market Statistics**
        Distribution of security types and position sizes.
        
        ## 💡 Interpretation
        - **High Fund Count** = Crowded trade
        - **Large Total Value** = Significant institutional interest
        - **Concentrated** = Few funds control most assets
        """)
    
    # Check database
    if not check_database_connection():
        st.error("❌ Database connection failed.")
        return
    
    # Market overview
    st.subheader("🌍 Market Overview")
    
    try:
        stats = get_summary_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Funds", f"{stats['total_funds']:,}")
        with col2:
            st.metric("Total Holdings", f"{stats['total_holdings']:,}")
        with col3:
            st.metric("Total AUM", f"${stats['total_aum']/1e12:.2f}T")
        with col4:
            st.metric("Unique Securities", f"{stats['unique_securities']:,}")
    except Exception as e:
        st.error(f"Error loading stats: {e}")
        return
    
    # Most popular securities
    st.subheader("🔥 Most Popular Securities")
    
    try:
        popular_securities = get_popular_securities(30)
        
        if not popular_securities.empty:
            display_popular = popular_securities.copy()
            display_popular['Total Value'] = display_popular['Total Value'].apply(lambda x: f"${x/1e9:.1f}B")
            display_popular['Total Shares'] = display_popular['Total Shares'].apply(lambda x: f"{x/1e6:.1f}M")
            
            st.dataframe(display_popular, use_container_width=True)
            
            # Bar chart
            st.subheader("📈 Top Securities by Total Value")
            
            top_10 = popular_securities.head(10)
            fig_bar = px.bar(
                top_10,
                x='Total Value',
                y='Security',
                orientation='h',
                title="Top 10 Securities by Total Value Across All Funds",
                labels={'Total Value': 'Total Value ($)', 'Security': 'Security Name'}
            )
            fig_bar.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_bar, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading popular securities: {e}")
    
    # Fund concentration
    st.subheader("🏛️ Fund Concentration")
    
    try:
        fund_concentration = get_fund_concentration(15)
        
        if not fund_concentration.empty:
            display_concentration = fund_concentration.copy()
            display_concentration.columns = ['Fund Name', 'Portfolio Value', 'Total Positions']
            display_concentration['Portfolio Value'] = display_concentration['Portfolio Value'].apply(
                lambda x: f"${x/1e9:.1f}B" if pd.notna(x) else "N/A"
            )
            display_concentration['Total Positions'] = display_concentration['Total Positions'].apply(
                lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
            )
            
            st.dataframe(display_concentration, use_container_width=True)
            
            # Pie chart
            st.subheader("🥧 Market Share Distribution")
            
            top_funds_pie = fund_concentration.head(10).copy()
            if not top_funds_pie.empty and top_funds_pie['TABLEVALUETOTAL'].sum() > 0:
                fig_pie = px.pie(
                    top_funds_pie,
                    values='TABLEVALUETOTAL',
                    names='FILINGMANAGER_NAME',
                    title="Top 10 Funds by Portfolio Value"
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(height=500)
                st.plotly_chart(fig_pie, use_container_width=True)
    except Exception as e:
        st.error(f"Error loading fund concentration: {e}")
    
    # Market statistics
    st.subheader("📈 Market Statistics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Security Type Distribution:**")
        try:
            security_types = get_security_type_distribution()
            if not security_types.empty:
                st.bar_chart(security_types.set_index('Type')['Count'])
        except Exception as e:
            st.warning(f"Could not load security types: {e}")
    
    with col2:
        st.write("**Value Distribution:**")
        try:
            value_stats = get_value_statistics()
            st.write(f"- Mean Position: ${value_stats['mean']/1e6:.1f}M")
            st.write(f"- Median Position: ${value_stats['50%']/1e6:.1f}M")
            st.write(f"- Max Position: ${value_stats['max']/1e9:.1f}B")
            st.write(f"- Total Positions: {value_stats['count']:,}")
        except Exception as e:
            st.warning(f"Could not load value stats: {e}")


if __name__ == "__main__":
    main()

