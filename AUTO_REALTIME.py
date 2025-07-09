import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from datetime import datetime, time as dt_time
import pytz
import threading
from streamlit_autorefresh import st_autorefresh

# Initialize session state
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = {}
if 'last_update' not in st.session_state:
    st.session_state.last_update = {}
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 60  # Default to 60 seconds
if 'last_refresh_time' not in st.session_state:
    st.session_state.last_refresh_time = time.time()
if 'refresh_count' not in st.session_state:
    st.session_state.refresh_count = 0

# Custom functions
def get_stock_data(symbol, interval, period='1d'):
    try:
        # Adjust period for 1d interval to ensure enough data for candlestick charts
        period = '1mo' if interval == '1d' else period
        stock = yf.Ticker(symbol)
        df = stock.history(period=period, interval=interval)
        if df.empty or len(df) < 2:
            st.error(f"No sufficient data for {symbol} with interval {interval}")
            return None
        current_price = df['Close'].iloc[-1]
        previous_price = df['Close'].iloc[-2]
        current_volume = df['Volume'].iloc[-1]
        previous_volume = df['Volume'].iloc[-2]
        timestamp = df.index[-1]
        local_tz = pytz.timezone('America/New_York')
        timestamp_local = timestamp.tz_convert(local_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
        change_pct = ((current_price - previous_price) / previous_price) * 100
        volume_change_pct = ((current_volume - previous_volume) / previous_volume) * 100 if previous_volume > 0 else 0
        return {
            'data': df,
            'price': current_price,
            'volume': current_volume,
            'open': df['Open'].iloc[-1],
            'high': df['High'].iloc[-1],
            'low': df['Low'].iloc[-1],
            'change_pct': change_pct,
            'volume_change_pct': volume_change_pct,
            'timestamp': timestamp_local
        }
    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {str(e)}")
        return None

def get_volume_trend_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        # Fetch 1-minute data for the last trading day
        df = stock.history(period='1d', interval='1m')
        if df.empty or len(df) < 2:
            st.error(f"No intraday data for {symbol}")
            return None
        # Filter for market hours (9:30 AM to 4:00 PM EDT)
        local_tz = pytz.timezone('America/New_York')
        df = df.tz_convert(local_tz)
        market_open = dt_time(9, 30)  # 9:30 AM
        market_close = dt_time(16, 0)  # 4:00 PM
        df = df.between_time(market_open, market_close)
        if df.empty:
            st.error(f"No data for {symbol} during market hours (9:30 AM–4:00 PM EDT)")
            return None
        return df
    except Exception as e:
        st.error(f"Error fetching intraday data for {symbol}: {str(e)}")
        return None

def create_candlestick_chart(df, symbol, interval):
    if df is not None and not df.empty:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=('Candlestick', 'Volume'), row_heights=[0.7, 0.3])
        
        fig.add_trace(go.Candlestick(x=df.index,
                                    open=df['Open'],
                                    high=df['High'],
                                    low=df['Low'],
                                    close=df['Close'],
                                    name=symbol),
                     row=1, col=1)
        
        colors = ['green' if df['Volume'].iloc[i] >= df['Volume'].iloc[max(0, i-1)] else 'red' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color=colors), row=2, col=1)
        
        fig.update_layout(
            title=f"{symbol} Candlestick Chart ({interval})",
            yaxis_title="Price",
            yaxis2_title="Volume",
            xaxis_title="Time",
            xaxis_rangeslider_visible=False,
            template="plotly_white"
        )
        return fig
    return None

def create_volume_trend_chart(df, symbol):
    if df is not None and not df.empty and len(df) >= 2:
        volume_data = df['Volume']
        labels = volume_data.index.strftime('%H:%M')  # Show only time (e.g., 09:30, 10:00)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=labels,
            y=volume_data,
            mode='lines+markers',
            name='Volume',
            line=dict(color='#2196F3', width=2),
            fill='tozeroy',
            fillcolor='rgba(33, 150, 243, 0.2)'
        ))
        
        fig.update_layout(
            title=f"Volume Trend for {symbol} (Market Hours: 9:30 AM–4:00 PM EDT)",
            xaxis_title="Time (EDT)",
            yaxis_title="Volume",
            template="plotly_white",
            showlegend=True
        )
        return fig
    return None

def create_portfolio_chart(symbols, changes):
    if symbols and changes and all(isinstance(c, (int, float)) for c in changes):
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=symbols,
            y=changes,
            marker_color=['#4CAF50' if c >= 0 else '#F44336' for c in changes],
            marker_line_color=['#388E3C' if c >= 0 else '#D32F2F' for c in changes],
            marker_line_width=1
        ))
        
        fig.update_layout(
            title="Portfolio Performance",
            xaxis_title="Stocks",
            yaxis_title="Percentage Change (%)",
            template="plotly_white",
            showlegend=False,
            yaxis=dict(zeroline=True, zerolinecolor='black', zerolinewidth=1)
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
        local_tz = pytz.timezone('America/New_York')
        current_time = datetime.now(local_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
        clock_placeholder.markdown(f"<div style='position: absolute; top: 10px; right: 10px; font-size: 16px; font-weight: bold;'>Clock: {current_time}</div>", unsafe_allow_html=True)
        time.sleep(1)

# Start clock in a separate thread
clock_placeholder = st.empty()
threading.Thread(target=display_clock, daemon=True).start()

# Title and description
st.title("📈 Real-Time Stock Monitoring Dashboard")
st.markdown("Track multiple stocks with interactive candlestick charts and real-time updates")

# Auto-refresh logic (before sidebar to ensure timestamp updates)
if st.session_state.auto_refresh:
    # Convert interval to milliseconds (60 seconds = 60000 ms)
    refresh_count = st_autorefresh(interval=st.session_state.refresh_interval * 1000, key="stockrefresh")
    if refresh_count > 0:  # Skip first run to avoid immediate refresh
        with st.spinner("🔄 Auto-refreshing stock data..."):
            any_data_updated = False
            for symbol in list(st.session_state.watchlist.keys()):
                data = get_stock_data(symbol, st.session_state.watchlist[symbol]['interval'])
                if data is not None:
                    st.session_state.watchlist[symbol]['data'] = data['data']
                    st.session_state.watchlist[symbol]['last_update'] = data['timestamp']
                    st.session_state.watchlist[symbol]['price'] = data['price']
                    st.session_state.watchlist[symbol]['volume'] = data['volume']
                    st.session_state.watchlist[symbol]['open'] = data['open']
                    st.session_state.watchlist[symbol]['high'] = data['high']
                    st.session_state.watchlist[symbol]['low'] = data['low']
                    st.session_state.watchlist[symbol]['change_pct'] = data['change_pct']
                    st.session_state.watchlist[symbol]['volume_change_pct'] = data['volume_change_pct']
                    any_data_updated = True
            st.session_state.last_refresh_time = time.time()  # Update timestamp every refresh
            if any_data_updated:
                st.session_state.refresh_count += 1
            else:
                st.warning("Auto-refresh failed: No data updated for any stock")

# Sidebar for controls
with st.sidebar:
    st.header("⚙️ Controls")
    
    symbol_input = st.text_input(
        "Enter Stock Symbol (e.g., ASML)",
        placeholder="e.g., ASML",
        help="Enter a valid stock symbol"
    )
    
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
        index=2,
        help="Each candle represents this time period"
    )
    
    refresh_interval = st.number_input(
        "Auto-Refresh Interval (seconds)",
        min_value=10,
        max_value=3600,
        value=st.session_state.refresh_interval,
        step=10,
        help="Set the interval for auto-refresh in seconds"
    )
    st.session_state.refresh_interval = refresh_interval
    
    auto_refresh = st.toggle(
        "Enable Auto-Refresh",
        value=st.session_state.auto_refresh,
        help="Toggle to enable/disable automatic data refresh"
    )
    st.session_state.auto_refresh = auto_refresh
    
    if st.button("📊 Add to Watchlist", type="primary"):
        if symbol_input:
            symbol = symbol_input.upper().strip()
            if symbol:
                data = get_stock_data(symbol, selected_interval)
                if data is not None:
                    st.session_state.watchlist[symbol] = {
                        'data': data['data'],
                        'interval': selected_interval,
                        'last_update': data['timestamp'],
                        'price': data['price'],
                        'volume': data['volume'],
                        'open': data['open'],
                        'high': data['high'],
                        'low': data['low'],
                        'change_pct': data['change_pct'],
                        'volume_change_pct': data['volume_change_pct']
                    }
                    st.success(f"✅ Added {symbol} to watchlist!")
                    st.rerun()
                else:
                    st.error("❌ Failed to fetch data for this symbol")
            else:
                st.error("❌ Invalid stock symbol")
        else:
            st.error("❌ Please enter a stock symbol")

    if st.button("🔄 Refresh All", key="refresh_all"):
        with st.spinner("🔄 Refreshing stock data..."):
            for symbol in list(st.session_state.watchlist.keys()):
                data = get_stock_data(symbol, st.session_state.watchlist[symbol]['interval'])
                if data is not None:
                    st.session_state.watchlist[symbol]['data'] = data['data']
                    st.session_state.watchlist[symbol]['last_update'] = data['timestamp']
                    st.session_state.watchlist[symbol]['price'] = data['price']
                    st.session_state.watchlist[symbol]['volume'] = data['volume']
                    st.session_state.watchlist[symbol]['open'] = data['open']
                    st.session_state.watchlist[symbol]['high'] = data['high']
                    st.session_state.watchlist[symbol]['low'] = data['low']
                    st.session_state.watchlist[symbol]['change_pct'] = data['change_pct']
                    st.session_state.watchlist[symbol]['volume_change_pct'] = data['volume_change_pct']
            st.session_state.last_refresh_time = time.time()
            st.session_state.refresh_count += 1
        st.success("✅ All stocks refreshed!")
        st.rerun()

    if st.button("🗑️ Clear All Stocks", type="secondary"):
        st.session_state.watchlist = {}
        st.success("✅ All stocks cleared!")
        st.rerun()
    
    # Refresh Status
    st.subheader("🔄 Refresh Status")
    st.markdown(f"**Auto-Refresh Enabled:** {'Yes' if st.session_state.auto_refresh else 'No'}")
    st.markdown(f"**Last Refresh:** {datetime.fromtimestamp(st.session_state.last_refresh_time).astimezone(pytz.timezone('America/New_York')).strftime('%Y-%m-%d %H:%M:%S %Z') if st.session_state.last_refresh_time else 'N/A'}")
    st.markdown(f"**Refresh Count:** {st.session_state.refresh_count}")

    # Volume Trend Selection
    st.subheader("📈 Volume Trend")
    selected_volume_stock = st.selectbox(
        "Select Stock for Volume Trend",
        options=list(st.session_state.watchlist.keys()) if st.session_state.watchlist else ["No stocks available"],
        help="Select a stock to view its volume trend (9:30 AM–4:00 PM EDT)"
    )

# Main content area
if not st.session_state.watchlist:
    st.info("📝 Add stocks to your watchlist using the sidebar to get started!")
else:
    for symbol, stock_info in st.session_state.watchlist.items():
        with st.container():
            st.subheader(f"📊 {symbol}")
            
            st.markdown(f"**Last Updated:** {stock_info['last_update']}")
            
            st.markdown(f"""
                <div style="position: relative; min-height: 60px;">
                    <div style="position: absolute; top: 0; right: 0; text-align: right;">
                        <div style="font-size: 18px; font-weight: bold; color: {'green' if stock_info['change_pct'] >= 0 else 'red'};">Current Price: ${stock_info['price']:.2f}</div>
                        <div style="font-size: 16px; font-weight: bold; color: {'green' if stock_info['change_pct'] >= 0 else 'red'};">Change: {stock_info['change_pct']:+.2f}%</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            st.metric("📈 Open", f"${stock_info['open']:.2f}")
            st.metric("📊 High", f"${stock_info['high']:.2f}")
            st.metric("📉 Low", f"${stock_info['low']:.2f}")
            st.markdown(f"""
                <div style="font-size: 16px; font-weight: bold; color: {'green' if stock_info['volume_change_pct'] >= 0 else 'red'};">
                    📦 Volume: {int(stock_info['volume']):,}
                </div>
            """, unsafe_allow_html=True)
            
            fig = create_candlestick_chart(stock_info['data'], symbol, stock_info['interval'])
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No data available for chart")
            
            st.divider()

# Portfolio Performance Overview
if st.session_state.watchlist:
    st.subheader("📊 Portfolio Performance Overview")
    st.markdown("Percentage change for all stocks in the watchlist")
    
    symbols = list(st.session_state.watchlist.keys())
    changes = [st.session_state.watchlist[symbol]['change_pct'] for symbol in symbols]
    
    fig = create_portfolio_chart(symbols, changes)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No valid data available for portfolio performance chart")

# Volume Trend Analysis
if st.session_state.watchlist and selected_volume_stock in st.session_state.watchlist:
    st.subheader(f"📈 Volume Trend for {selected_volume_stock}")
    st.markdown("Volume from 9:30 AM to 4:00 PM EDT")
    
    df = get_volume_trend_data(selected_volume_stock)
    fig = create_volume_trend_chart(df, selected_volume_stock)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Not enough data for volume trend chart (9:30 AM–4:00 PM EDT)")

# Footer
st.markdown("---")
st.markdown("🔍 **Data provided by Yahoo Finance** | 📊 **Real-Time Stock Monitoring Dashboard**")
