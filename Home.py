"""
Hedge Fund Index - Main Application
Fund Analysis with Portfolio Treemap
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os

# Disable file watching to prevent inotify issues on Streamlit Cloud
os.environ['STREAMLIT_SERVER_FILE_WATCHER_TYPE'] = 'none'
os.environ['STREAMLIT_SERVER_RUN_ON_SAVE'] = 'false'

from dotenv import load_dotenv
load_dotenv()

# Import database utilities
from utils.db_queries import (
    get_summary_stats,
    get_fund_names,
    get_fund_data,
    get_fund_holdings,
    get_top_funds,
    check_database_connection,
    subscribe_user,
    get_subscriber_count,
)
from utils.yf_util import get_stock_info_batch, extract_ticker_from_cusip
from utils.email_util import validate_email, send_welcome_email, POSTMARK_API_KEY

# Page configuration
st.set_page_config(
    page_title="Hedgefolio",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


def create_heatmap(holdings_df, fund_name=None):
    """Create a treemap heatmap of portfolio holdings with price changes and sectors"""
    try:
        if holdings_df.empty or len(holdings_df) < 1:
            st.info("Not enough holdings data to create heatmap (minimum 1 holding required)")
            return None
        
        # Take top 20 holdings for better visualization
        top_holdings = holdings_df.head(20).copy()
        
        # Ensure we have the required columns
        if 'portfolio_pct' not in top_holdings.columns:
            st.error("Portfolio percentage data not available")
            return None
        
        # Extract tickers from company names
        top_holdings['ticker'] = top_holdings['NAMEOFISSUER'].apply(extract_ticker_from_cusip)
        
        # Show ticker discovery progress
        total_companies = len(top_holdings)
        found_tickers = len([t for t in top_holdings['ticker'] if t])
        st.info(f"📊 Ticker Discovery: {found_tickers}/{total_companies} companies have ticker symbols")
        
        # Get stock information for available tickers
        available_tickers = [ticker for ticker in top_holdings['ticker'] if ticker]
        
        if available_tickers:
            ticker_to_company = dict(zip(top_holdings['ticker'], top_holdings['NAMEOFISSUER']))
            
            with st.spinner(f"Fetching stock price changes and sector data for {len(available_tickers)} companies..."):
                stock_info = get_stock_info_batch(available_tickers, ticker_to_company)
            
            top_holdings['price_change'] = top_holdings['ticker'].apply(
                lambda x: stock_info.get(x, {}).get('price_change') if x else None
            )
            top_holdings['sector'] = top_holdings['ticker'].apply(
                lambda x: stock_info.get(x, {}).get('sector') if x else "Unknown"
            )
        else:
            top_holdings['price_change'] = None
            top_holdings['sector'] = "Unknown"
        
        # Use price change for color
        if top_holdings['price_change'].notna().any():
            price_changes = top_holdings['price_change'].fillna(0)
            max_change = max(abs(price_changes.min()), abs(price_changes.max()))
            if max_change > 0:
                top_holdings['color_value'] = price_changes / max_change
            else:
                top_holdings['color_value'] = 0
        else:
            np.random.seed(42)
            top_holdings['color_value'] = np.random.uniform(0, 1, len(top_holdings))
        
        # Create labels
        top_holdings['label'] = top_holdings.apply(
            lambda row: f"{row['NAMEOFISSUER']}<br>{row['ticker'] or 'N/A'}<br>{row['portfolio_pct']:.1f}%", 
            axis=1
        )
        
        treemap_data = top_holdings.copy()
        treemap_data['sector'] = treemap_data['sector'].fillna('Unknown').astype(str)
        treemap_data['color_value'] = pd.to_numeric(treemap_data['color_value'], errors='coerce').fillna(0)
        treemap_data['portfolio_pct'] = pd.to_numeric(treemap_data['portfolio_pct'], errors='coerce').fillna(0)
        
        treemap_title = f'Portfolio Holdings by Sector (Top 20) - {fund_name}' if fund_name else 'Portfolio Holdings by Sector (Top 20)'
        
        fig = px.treemap(
            treemap_data,
            path=['sector', 'label'],
            values='portfolio_pct',
            color='color_value',
            color_continuous_scale='RdYlGn',
            title=treemap_title,
            hover_data=['VALUE', 'portfolio_pct', 'SSHPRNAMT', 'price_change', 'ticker']
        )
        
        fig.update_layout(
            height=700,
            font_size=11,
            title_font_size=16,
            margin=dict(t=50, l=25, r=25, b=25),
            coloraxis_showscale=True,
            coloraxis_colorbar=dict(
                title="Price Change %",
                thickness=15,
                len=0.5
            )
        )
        
        fig.update_traces(
            textfont_size=9,
            textposition="middle center",
            texttemplate="%{label}"
        )
        
        return fig
        
    except Exception as e:
        st.error(f"Error creating heatmap: {str(e)}")
        return None


def render_sidebar():
    """Render sidebar with email signup."""
    with st.sidebar:
        st.header("📬 Stay Updated")
        st.write("Get notified about hedge fund portfolio changes and market insights.")
        
        # Email signup form
        with st.form(key="email_signup_form", clear_on_submit=True):
            email = st.text_input(
                "Email address",
                placeholder="you@example.com",
                label_visibility="collapsed"
            )
            submit = st.form_submit_button("Subscribe", use_container_width=True)
            
            if submit:
                if not email:
                    st.error("Please enter your email address.")
                elif not validate_email(email):
                    st.error("Please enter a valid email address.")
                else:
                    # Subscribe user
                    result = subscribe_user(email)
                    
                    if result["success"]:
                        st.success(f"✅ {result['message']}")
                        
                        # Send welcome email if new subscriber and Postmark is configured
                        if result["is_new"] and POSTMARK_API_KEY:
                            try:
                                send_welcome_email(email)
                            except Exception:
                                pass  # Silently fail if email sending fails
                    else:
                        st.error(result["message"])
        
        st.divider()
        
        # Subscriber count
        try:
            count = get_subscriber_count()
            if count > 0:
                st.caption(f"👥 {count:,} subscribers")
        except Exception:
            pass
        
        st.divider()
        
        # Navigation info
        st.subheader("🧭 Navigation")
        st.write("**🔍 Holdings Explorer**")
        st.caption("Search securities across all funds")
        st.write("**📊 Market Insights**")
        st.caption("View popular securities & trends")


def main():
    # Render sidebar
    render_sidebar()
    
    # Hero section
    st.title("📊 Hedgefolio")
    st.markdown("""
    ### *Invest like a hedge fund manager*
    
    Monitor the portfolios of the world's top hedge funds. Get daily notifications 
    when institutional investors make moves. See what the smart money is buying and selling.
    """)
    
    st.divider()
    
    # Check database connection
    if not check_database_connection():
        st.error("❌ Database connection failed. Please check your configuration.")
        st.info("Make sure DB_URL is set in your .env file and the database is accessible.")
        return
    
    # Get summary stats
    try:
        stats = get_summary_stats()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return
    
    # Display key metrics
    st.subheader("📈 Market Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Funds", f"{stats['total_funds']:,}")
    with col2:
        st.metric("Total Holdings", f"{stats['total_holdings']:,}")
    with col3:
        st.metric("Total AUM", f"${stats['total_aum_billions']:.1f}B")
    with col4:
        st.metric("Unique Securities", f"{stats['unique_securities']:,}")
    
    st.divider()
    
    # Fund selection
    funds_list = get_fund_names()
    
    if not funds_list:
        st.warning("No funds found in database.")
        return
    
    # Find Bridgewater as default
    default_index = 0
    for i, fund in enumerate(funds_list):
        if "BRIDGEWATER" in fund.upper() and "ASSOCIATES" in fund.upper():
            default_index = i
            break
    
    selected_fund = st.selectbox(
        "🏢 Select a fund to analyze:",
        funds_list,
        index=default_index
    )
    
    if selected_fund:
        # Get fund data
        fund_data = get_fund_data(selected_fund)
        
        if not fund_data.empty:
            # Display fund metrics
            col1, col2, col3 = st.columns(3)
            
            portfolio_value = fund_data['TABLEVALUETOTAL'].sum() if 'TABLEVALUETOTAL' in fund_data.columns else 0
            total_positions = fund_data['TABLEENTRYTOTAL'].sum() if 'TABLEENTRYTOTAL' in fund_data.columns else 0
            
            # Get holdings for unique securities count
            holdings = get_fund_holdings(selected_fund, limit=10000)
            unique_securities = holdings['NAMEOFISSUER'].nunique() if not holdings.empty else 0
            
            with col1:
                if portfolio_value and portfolio_value > 0:
                    st.metric("Portfolio Value", f"${portfolio_value/1e6:.1f}M")
                else:
                    st.metric("Portfolio Value", "N/A")
            with col2:
                st.metric("Total Positions", f"{int(total_positions):,}" if total_positions else "N/A")
            with col3:
                st.metric("Unique Securities", f"{unique_securities:,}")
            
            # TREEMAP FIRST - Main visualization
            if not holdings.empty:
                st.subheader("🗺️ Portfolio Heatmap by Sector")
                st.write("Portfolio Holdings Treemap with 1-Month Price Changes (Top 20)")
                
                # Prepare holdings data
                top_holdings = holdings.groupby(['NAMEOFISSUER', 'TITLEOFCLASS']).agg({
                    'VALUE': 'sum',
                    'SSHPRNAMT': 'sum',
                    'PUTCALL': 'first',
                    'CUSIP': 'first'
                }).reset_index()
                
                total_value = top_holdings['VALUE'].sum()
                top_holdings['portfolio_pct'] = (top_holdings['VALUE'] / total_value) * 100 if total_value > 0 else 0
                top_holdings = top_holdings.sort_values('VALUE', ascending=False)
                
                heatmap_fig = create_heatmap(top_holdings, selected_fund)
                if heatmap_fig:
                    st.plotly_chart(
                        heatmap_fig, 
                        use_container_width=True,
                        config={
                            'displayModeBar': True,
                            'displaylogo': False,
                            'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d']
                        }
                    )
                    
                    st.markdown("""
                    **Color Legend:**
                    - 🔴 **Red**: Negative price change (stock declined)
                    - 🟡 **Yellow**: Neutral price change
                    - 🟢 **Green**: Positive price change (stock gained)
                    """)
                
                st.divider()
                
                # Top holdings table
                st.subheader("🔝 Top Holdings")
                
                display_holdings = top_holdings.head(50).copy()
                display_holdings['VALUE'] = display_holdings['VALUE'].apply(lambda x: f"${x/1e6:.1f}M")
                display_holdings['SSHPRNAMT'] = display_holdings['SSHPRNAMT'].apply(lambda x: f"{x:,.0f}")
                display_holdings['portfolio_pct'] = display_holdings['portfolio_pct'].apply(lambda x: f"{x:.2f}%")
                
                display_holdings = display_holdings[['NAMEOFISSUER', 'TITLEOFCLASS', 'VALUE', 'SSHPRNAMT', 'portfolio_pct']]
                display_holdings.columns = ['Security', 'Type', 'Value', 'Shares', 'Portfolio %']
                
                st.dataframe(display_holdings, use_container_width=True)
            else:
                st.warning("No holdings data found for this fund.")
        else:
            st.error("Fund data not found.")
    


if __name__ == "__main__":
    main()
