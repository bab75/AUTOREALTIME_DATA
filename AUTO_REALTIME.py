import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import time
from datetime import datetime
import pytz
import threading  # Added missing import

# Initialize session state
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = {}
if 'last_update' not in st.session_state:
    st.session_state.last_update = {}
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 60

# Custom functions (replace with your utils if different)
def get_stock_data(symbol, interval, period='1d'):
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period=period, interval=interval)
        if df.empty:
            st.error(f"No data available for {symbol} with interval {interval}")
            return None
        current_price = df['Close'].iloc[-1]
        volume = df['Volume'].iloc[-1]
        timestamp = df.index[-1]
        local_tz = datetime.now().astimezone().tzinfo
        timestamp_local = timestamp.tz_convert(local_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
        return {'data': df, 'price': current_price, 'volume': volume, 'timestamp': timestamp_local}
    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {str(e)}")
        return None

def create_candlestick_chart(df, symbol, interval):
    if df is not None and not df.empty:
        fig = go.Figure(data=[go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name=symbol
        )])
        fig.update_layout(
            title=f"{symbol} Candlestick Chart ({interval})",
            xaxis_title="Time",
            yaxis_title="Price",
            xaxis_rangeslider_visible=False
        )
        return fig
    return None

# Configure page
st.set_page_config(
    page_title="Real-Time Stock Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Real-time clock
def display_clock():
    while True:
        current_time = datetime.now().astimezone(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d %H:%M:%S %Z')
        st.markdown(f"<div style='position: absolute; top: 10px; right: 10px; font-size: 16px; font-weight: bold;'>Clock: {current_time}</div>", unsafe_allow_html=True)
        time.sleep(1)  # Update every second
threading.Thread(target=display_clock, daemon=True).start()

# Title and description
st.title("📈 Real-Time Stock Monitoring Dashboard")
st.markdown("Track multiple stocks with interactive candlestick charts and real-time updates")

# Sidebar for controls
with st.sidebar:
    st.header("⚙️ Controls")
    
    # Stock symbol input
    symbol_input = st.text_input(
        "Enter Stock Symbol (e.g., ASML)",
        placeholder="e.g., ASML",
        help="Enter a valid stock symbol"
    )
    
    # Time interval selection
    interval_options = {
        "1m": "1 Minute", "2m": "2 Minutes", "5m": "5 Minutes",
        "15m": "15 Minutes", "30m": "30 Minutes", "60m": "60 Minutes",
        "90m": "90 Minutes", "1h": "1 Hour", "1d": "1 Day",
        "5d": "5 Days", "1wk": "1 Week", "1mo": "1 Month"
    }
    selected_interval = st.selectbox(
        "Select Chart Time Interval",
        options=list(interval_options.keys()),
        format_func=lambda x: interval_options[x],
        index=2,  # Default to 5m
        help="Each candle represents this time period"
    )
    
    # Submit button
    if st.button("📊 Add to Watchlist", type="primary"):
        if symbol_input:
            symbol = symbol_input.upper().strip()
            if symbol:  # Basic validation
                data = get_stock_data(symbol, selected_interval)
                if data is not None:
                    st.session_state.watchlist[symbol] = {
                        'data': data['data'],
                        'interval': selected_interval,
                        'last_update': data['timestamp'],
                        'price': data['price'],
                        'volume': data['volume']
                    }
                    st.success(f"✅ Added {symbol} to watchlist!")
                    st.rerun()
                else:
                    st.error("❌ Failed to fetch data for this symbol")
            else:
                st.error("❌ Invalid stock symbol")
        else:
            st.error("❌ Please enter a stock symbol")

    # Auto-refresh button
    if st.button("🔄 Refresh All", key="refresh_all"):
        st.session_state.auto_refresh = True
        with st.spinner("🔄 Refreshing stock data..."):
            for symbol in list(st.session_state.watchlist.keys()):
                data = get_stock_data(symbol, st.session_state.watchlist[symbol]['interval'])
                if data is not None:
                    st.session_state.watchlist[symbol]['data'] = data['data']
                    st.session_state.watchlist[symbol]['last_update'] = data['timestamp']
                    st.session_state.watchlist[symbol]['price'] = data['price']
                    st.session_state.watchlist[symbol]['volume'] = data['volume']
            st.success("✅ All stocks refreshed!")
        st.rerun()

    # Clear all button
    if st.button("🗑️ Clear All Stocks", type="secondary"):
        st.session_state.watchlist = {}
        st.success("✅ All stocks cleared!")
        st.rerun()

# Main content area
if not st.session_state.watchlist:
    st.info("📝 Add stocks to your watchlist using the sidebar to get started!")
else:
    for symbol, stock_info in st.session_state.watchlist.items():
        with st.container():
            st.subheader(f"📊 {symbol}")
            
            # Stock information and chart
            col1, col2 = st.columns([1, 3])
            
            with col1:
                # Display timestamp
                st.markdown(f"**Last Updated:** {stock_info['last_update']}")
                
                # Custom HTML for price and volume layout
                st.markdown(f"""
                    <div style="position: relative; min-height: 60px;">
                        <div style="position: absolute; top: 0; right: 0; text-align: right;">
                            <div style="font-size: 18px; font-weight: bold;">Current Price: ${stock_info['price']:.2f}</div>
                            <div style="font-size: 16px; font-weight: bold;">Volume: {stock_info['volume']:,}</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Remove and refresh buttons
                if st.button(f"❌ Remove {symbol}", key=f"remove_{symbol}"):
                    del st.session_state.watchlist[symbol]
                    st.success(f"✅ {symbol} removed from watchlist!")
                    st.rerun()
            
            with col2:
                fig = create_candlestick_chart(stock_info['data'], symbol, stock_info['interval'])
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No data available for chart")
            
            st.divider()

# Footer
st.markdown("---")
st.markdown("🔍 **Data provided by Yahoo Finance** | 📊 **Real-Time Stock Monitoring Dashboard**")
