import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import time
from datetime import datetime, timedelta
import pytz

# Initialize session state
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []
if 'last_update' not in st.session_state:
    st.session_state.last_update = time.time()
if 'selected_interval' not in st.session_state:
    st.session_state.selected_interval = '1m'
if 'input_key' not in st.session_state:
    st.session_state.input_key = 0
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = False
if 'last_timer_check' not in st.session_state:
    st.session_state.last_timer_check = time.time()

# Define interval options
interval_options = {'1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600}

# Custom CSS for styling
st.markdown("""
<style>
.progress-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin: 15px 0;
    background: rgba(255, 255, 255, 0.8);
    padding: 15px;
    border-radius: 10px;
}
.progress-text {
    font-size: 20px;
    font-weight: bold;
    color: #000000;
    margin-top: 10px;
}
.progress-interval {
    font-size: 16px;
    color: #000000;
    font-weight: bold;
    margin-top: 10px;
}
body {
    background: linear-gradient(135deg, #e6f3ff, #ffffff);
}
.system-time, .stock-timestamp {
    font-size: 16px;
    color: #000000;
    font-weight: bold;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# Function to get stock data
def get_stock_data(symbol, interval, period='1d'):
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period=period, interval=interval)
        if df.empty:
            return None, None
        current_price = df['Close'][-1] if not df.empty else None
        volume = df['Volume'][-1] if not df.empty else None
        low_price = df['Low'].min() if not df.empty else None
        high_price = df['High'].max() if not df.empty else None
        timestamp = df.index[-1]
        local_tz = datetime.now().astimezone().tzinfo
        timestamp_local = timestamp.tz_convert(local_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
        return df, {
            'price': current_price,
            'volume': volume,
            'low': low_price,
            'high': high_price,
            'timestamp': timestamp_local
        }
    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {str(e)}")
        return None, None

# Function to create candlestick chart
def create_candlestick_chart(df, symbol):
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
            title=f"{symbol} Candlestick Chart",
            xaxis_title="Time",
            yaxis_title="Price",
            xaxis_rangeslider_visible=False
        )
        return fig
    return None

# Sidebar for input and timer
st.sidebar.header("Stock Watchlist")
symbol_input = st.sidebar.text_input("Enter Stock Symbol (e.g., AAPL)", "", key=f"symbol_input_{st.session_state.input_key}").upper()
interval = st.sidebar.selectbox("Select Interval", options=list(interval_options.keys()), index=0, key=f"interval_select_{st.session_state.input_key}")
if st.sidebar.button("Add to Watchlist"):
    if symbol_input:
        if symbol_input not in st.session_state.watchlist:
            st.session_state.watchlist.append(symbol_input)
            st.session_state.selected_interval = interval
            st.session_state.input_key += 1
            st.session_state.last_update = time.time()
            st.session_state.last_timer_check = time.time()
            st.rerun()
        else:
            st.sidebar.warning(f"{symbol_input} is already in the watchlist!")
    else:
        st.sidebar.error("Please enter a valid stock symbol.")

# Timer logic in sidebar
if st.session_state.watchlist:
    current_time = time.time()
    elapsed = current_time - st.session_state.last_timer_check
    refresh_interval = interval_options[st.session_state.selected_interval]
    progress_value = min(elapsed / refresh_interval, 1.0)
    time_remaining = max(0, refresh_interval - elapsed)

    with st.sidebar:
        st.markdown(f"""
        <div class="progress-container">
            <div class="progress-interval">Refresh Interval: {st.session_state.selected_interval}</div>
            <div class="progress-text">Time until next refresh: {int(time_remaining)}s</div>
        </div>
        """, unsafe_allow_html=True)
        st.progress(progress_value)

        if progress_value >= 1.0 or st.session_state.get('manual_refresh', False):
            st.session_state.refresh_trigger = True
            st.session_state.last_update = current_time
            st.session_state.last_timer_check = current_time
            st.session_state.pop('manual_refresh', None)
            st.rerun()

        if st.button("🔄 Refresh Now"):
            st.session_state['manual_refresh'] = True
            st.rerun()

# Main app
st.title("Stock Market Watchlist")

# Display current system time
current_system_time = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
st.markdown(f"<div class='system-time'>System Time: {current_system_time}</div>", unsafe_allow_html=True)

# Display watchlist
if st.session_state.watchlist:
    st.subheader("Watchlist")
    for symbol in st.session_state.watchlist:
        st.write(f"- {symbol}")

    # Refresh data if triggered
    if st.session_state.refresh_trigger:
        with st.spinner("Fetching stock data..."):
            for i, symbol in enumerate(st.session_state.watchlist):
                st.subheader(f"Stock: {symbol}")
                data_placeholder = st.empty()
                with data_placeholder.container():
                    df, info = get_stock_data(symbol, st.session_state.selected_interval)
                    if df is not None and info:
                        st.markdown(f"<div class='stock-timestamp'>Last Updated: {info['timestamp']}</div>", unsafe_allow_html=True)
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Current Price", f"${info['price']:.2f}")
                        with col2:
                            st.metric("Low Price", f"${info['low']:.2f}")
                        with col3:
                            st.metric("High Price", f"${info['high']:.2f}")
                        with col4:
                            st.metric("Volume", f"{info['volume']:,}")
                        fig = create_candlestick_chart(df, symbol)
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.error(f"No data available for {symbol}.")
            st.success(f"✅ Data updated at {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")
            st.session_state.refresh_trigger = False
else:
    st.info("Add a stock symbol to the watchlist to start tracking.")
