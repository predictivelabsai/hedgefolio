"""
SEC Events Tracker - 13D/13G Activist Filings Page
Displays recent activist and passive stake accumulation events from SEC EDGAR.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import logging

from utils.db_util import get_engine, get_session
from utils.sec_event_db_util import (
    get_recent_events,
    get_events_by_ticker,
    get_events_by_filer,
    get_activist_events,
    get_amendment_history,
    get_stake_timeline,
    get_event_statistics,
    get_top_filers,
    get_top_targets,
)

# Configure logging
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="SEC Events | Hedgefolio",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .event-card {
        background-color: #ffffff;
        padding: 15px;
        border-left: 4px solid #1f77b4;
        border-radius: 5px;
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db_session():
    """Get database session."""
    engine = get_engine()
    return get_session(engine)


@st.cache_data(ttl=3600)
def load_recent_events(days=30):
    """Load recent events with caching."""
    session = get_db_session()
    try:
        events = get_recent_events(session, days=days, limit=200)
        return events
    except Exception as e:
        logger.error(f"Error loading recent events: {e}")
        return []


@st.cache_data(ttl=3600)
def load_activist_events(days=90):
    """Load activist events with caching."""
    session = get_db_session()
    try:
        events = get_activist_events(session, days=days, limit=200)
        return events
    except Exception as e:
        logger.error(f"Error loading activist events: {e}")
        return []


@st.cache_data(ttl=3600)
def load_statistics(days=30):
    """Load event statistics."""
    session = get_db_session()
    try:
        stats = get_event_statistics(session, days=days)
        return stats
    except Exception as e:
        logger.error(f"Error loading statistics: {e}")
        return {}


@st.cache_data(ttl=3600)
def load_top_filers(limit=10):
    """Load top filers."""
    session = get_db_session()
    try:
        filers = get_top_filers(session, limit=limit)
        return filers
    except Exception as e:
        logger.error(f"Error loading top filers: {e}")
        return []


@st.cache_data(ttl=3600)
def load_top_targets(limit=10):
    """Load top targets."""
    session = get_db_session()
    try:
        targets = get_top_targets(session, limit=limit)
        return targets
    except Exception as e:
        logger.error(f"Error loading top targets: {e}")
        return []


def format_event_row(event):
    """Format event for display."""
    return {
        'Filing Date': event.filing_date,
        'Form': event.form_type,
        'Filer': event.filer_name,
        'Target': event.target_company_name,
        'Ticker': event.target_ticker or 'N/A',
        'Stake %': f"{float(event.stake_percentage):.2f}%" if event.stake_percentage else 'N/A',
        'Shares': f"{event.shares_owned:,}" if event.shares_owned else 'N/A',
        'Status': event.filing_status,
    }


def main():
    """Main page logic."""
    
    # Header
    st.title("📊 SEC Events Tracker")
    st.markdown("Track 13D/13G activist and passive stake accumulation filings from SEC EDGAR")
    
    # Sidebar - Search and Filter
    with st.sidebar:
        st.header("🔍 Search & Filter")
        
        search_type = st.radio(
            "Search by:",
            ["Recent Events", "Company", "Filer"],
            horizontal=False
        )
        
        if search_type == "Company":
            company_search = st.text_input("Enter company name or ticker...")
        elif search_type == "Filer":
            filer_search = st.text_input("Enter filer name...")
        
        date_range = st.slider(
            "Days to look back:",
            min_value=1,
            max_value=365,
            value=30,
            step=1
        )
        
        form_type_filter = st.multiselect(
            "Form Type:",
            ["13D", "13G"],
            default=["13D", "13G"]
        )
        
        min_stake = st.slider(
            "Minimum Stake %:",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=0.5
        )
    
    # Load data
    stats = load_statistics(days=date_range)
    recent_events = load_recent_events(days=date_range)
    activist_events = load_activist_events(days=date_range)
    top_filers = load_top_filers(limit=10)
    top_targets = load_top_targets(limit=10)
    
    # Key Metrics
    st.subheader("📈 Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Events (30d)",
            stats.get('total_events', 0),
            delta=None
        )
    
    with col2:
        st.metric(
            "13D Filings",
            stats.get('total_13d', 0),
            delta=None
        )
    
    with col3:
        st.metric(
            "13G Filings",
            stats.get('total_13g', 0),
            delta=None
        )
    
    with col4:
        avg_stake = stats.get('average_stake_percentage', 0)
        st.metric(
            "Avg Stake %",
            f"{avg_stake:.2f}%",
            delta=None
        )
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Recent Events",
        "🎯 Activist Campaigns",
        "💼 Passive Stakes",
        "🏆 Top Filers & Targets",
        "📖 About"
    ])
    
    # Tab 1: Recent Events
    with tab1:
        st.subheader("Recent 13D/13G Filings")
        
        if recent_events:
            # Convert to DataFrame
            events_data = []
            for event in recent_events:
                events_data.append(format_event_row(event))
            
            df_events = pd.DataFrame(events_data)
            
            # Apply filters
            if form_type_filter:
                df_events = df_events[df_events['Form'].isin(form_type_filter)]
            
            if min_stake > 0:
                df_events['Stake_Numeric'] = df_events['Stake %'].str.rstrip('%').astype(float)
                df_events = df_events[df_events['Stake_Numeric'] >= min_stake]
                df_events = df_events.drop('Stake_Numeric', axis=1)
            
            st.dataframe(
                df_events,
                use_container_width=True,
                hide_index=True,
                height=400
            )
            
            # Export button
            csv = df_events.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"sec_events_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No events found for the selected period.")
    
    # Tab 2: Activist Campaigns
    with tab2:
        st.subheader("13D Activist Campaigns")
        
        if activist_events:
            # Create DataFrame
            activist_data = []
            for event in activist_events:
                activist_data.append({
                    'Filing Date': event['filing_date'],
                    'Filer': event['filer_name'],
                    'Target': event['target_company_name'],
                    'Ticker': event['target_ticker'] or 'N/A',
                    'Stake %': f"{event['stake_percentage']:.2f}%" if event['stake_percentage'] else 'N/A',
                    'Intent': event['intent_type'] or 'N/A',
                    'Purpose': event['purpose'][:100] + '...' if event['purpose'] else 'N/A',
                })
            
            df_activist = pd.DataFrame(activist_data)
            
            st.dataframe(
                df_activist,
                use_container_width=True,
                hide_index=True,
                height=400
            )
            
            # Chart: Activist events over time
            st.subheader("Activist Activity Timeline")
            
            # Count events by date
            activist_timeline = pd.DataFrame(activist_data)
            activist_timeline['Filing Date'] = pd.to_datetime(activist_timeline['Filing Date'])
            daily_counts = activist_timeline.groupby(activist_timeline['Filing Date'].dt.date).size()
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=daily_counts.index,
                y=daily_counts.values,
                mode='lines+markers',
                name='13D Filings',
                line=dict(color='#1f77b4', width=2),
                marker=dict(size=8)
            ))
            
            fig.update_layout(
                title="13D Filings Over Time",
                xaxis_title="Date",
                yaxis_title="Number of Filings",
                hovermode='x unified',
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No activist campaigns found for the selected period.")
    
    # Tab 3: Passive Stakes
    with tab3:
        st.subheader("13G Passive Stakes")
        
        # Filter for 13G only
        passive_events = [e for e in recent_events if e.form_type == '13G']
        
        if passive_events:
            passive_data = []
            for event in passive_events:
                passive_data.append(format_event_row(event))
            
            df_passive = pd.DataFrame(passive_data)
            
            st.dataframe(
                df_passive,
                use_container_width=True,
                hide_index=True,
                height=400
            )
            
            # Stake distribution chart
            st.subheader("Stake Distribution")
            
            df_passive['Stake_Numeric'] = df_passive['Stake %'].str.rstrip('%').astype(float)
            
            fig = px.histogram(
                df_passive,
                x='Stake_Numeric',
                nbins=20,
                title='Distribution of Passive Stakes',
                labels={'Stake_Numeric': 'Stake %', 'count': 'Number of Filings'},
                color_discrete_sequence=['#2ca02c']
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No passive stakes found for the selected period.")
    
    # Tab 4: Top Filers & Targets
    with tab4:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🎯 Top Activist Filers")
            
            if top_filers:
                filer_data = []
                for filer in top_filers:
                    filer_data.append({
                        'Filer': filer['filer_name'],
                        'Filings': filer['filing_count'],
                        'Targets': filer['unique_targets'],
                        'Avg Stake %': f"{filer['average_stake']:.2f}%",
                        'Latest': filer['latest_filing'],
                    })
                
                df_filers = pd.DataFrame(filer_data)
                st.dataframe(df_filers, use_container_width=True, hide_index=True)
                
                # Chart
                fig = px.bar(
                    df_filers,
                    x='Filer',
                    y='Filings',
                    title='Top Filers by Number of Filings',
                    color='Filings',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No filer data available.")
        
        with col2:
            st.subheader("🏆 Most Targeted Companies")
            
            if top_targets:
                target_data = []
                for target in top_targets:
                    target_data.append({
                        'Company': target['company_name'],
                        'Ticker': target['ticker'] or 'N/A',
                        'Events': target['event_count'],
                        'Filers': target['unique_filers'],
                        'Max Stake %': f"{target['max_stake']:.2f}%",
                    })
                
                df_targets = pd.DataFrame(target_data)
                st.dataframe(df_targets, use_container_width=True, hide_index=True)
                
                # Chart
                fig = px.bar(
                    df_targets,
                    x='Company',
                    y='Events',
                    title='Most Targeted Companies',
                    color='Events',
                    color_continuous_scale='Reds'
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No target data available.")
    
    # Tab 5: About
    with tab5:
        st.subheader("About SEC Events Tracker")
        
        st.markdown("""
        ### 📊 Purpose
        This page tracks Schedule 13D and 13G SEC filings, which represent significant ownership changes
        and activist campaigns in publicly traded companies.
        
        ### 📋 What are 13D/13G Forms?
        
        **13D (Activist)**
        - Filed when someone acquires >5% ownership with intent to influence the company
        - Must disclose purpose, strategy, and plans
        - Filed within 10 days of crossing 5% threshold
        - Indicates activist or acquisition interest
        
        **13G (Passive)**
        - Filed when someone acquires >5% ownership passively
        - Simplified disclosure (no intent required)
        - Filed within 45 days of year-end or within 10 days if first crossed in Q1
        - Indicates passive institutional investment
        
        ### 🔍 How to Use This Page
        
        1. **Search & Filter**: Use the sidebar to filter by company, filer, or date range
        2. **Recent Events**: View all recent 13D/13G filings
        3. **Activist Campaigns**: Focus on 13D filings with activist intent
        4. **Passive Stakes**: View 13G passive investment filings
        5. **Top Filers & Targets**: See which activists are most active and which companies are most targeted
        
        ### 💡 Key Insights
        
        - **Activist Campaigns**: 13D filings often precede proxy fights, board seat demands, or strategic changes
        - **Stake Accumulation**: Amendment filings show how stakes change over time
        - **Intent Indicators**: Purpose and plans in 13D filings reveal activist strategy
        - **Passive vs Activist**: 13G filings indicate passive institutional investment
        
        ### 📚 Data Source
        All data is sourced from SEC EDGAR (Electronic Data Gathering, Order, and Retrieval system).
        
        ### ⚠️ Disclaimer
        This data is for informational purposes only. Always consult official SEC filings and conduct
        your own research before making investment decisions.
        """)


if __name__ == "__main__":
    main()
