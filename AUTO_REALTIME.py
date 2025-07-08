import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import time
from datetime import datetime
import pytz

# Initialize session state
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []
if 'last_update' not in st.session_state:
    st.session_state.last_update = time.time()
if 'selected_interval' not in st.session_state:
    st.session_state.selected_interval = '5m'
if 'input_key' not in st.session_state:
    st.session_state.input_key = 0
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = False
if 'data_cache' not in st.session_state:
    st.session_state.data_cache = {}

# Define interval options (in seconds)
interval_options = {'1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600}

# Custom CSS and JavaScript for styling and dynamic refresh
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
.stock-data {
    margin-top: 10px;
}
.stock-metrics {
    display: flex;
    justify-content: space-between;
    width: 100%;
    margin-top: 5px;
}
.stock-metric {
    font-size: 14px;
    padding: 5px;
}
</style>
<script>
function refreshData() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            document.getElementById('stock-data').innerHTML = this.responseText;
        }
    };
    xhttp.open("GET", window.location.pathname + "?refresh=true", true);
    xhttp.send();
}
setInterval(refreshData, 300000); // Refresh every 300 seconds (5 minutes)
</script>
""", unsafe_allow_html=True)

# Function to get stock data
def get_stock_data(symbol, interval, period='1d'):
    try:
        if symbol not in st.session_state.data_cache or st.session_state.refresh_trigger:
            stock = yf.Ticker(symbol)
            df = stock.history(period=period, interval=interval)
            if df.empty:
                st.error(f"No data available for {symbol} with interval {interval}")
                return None, None
            current_price = df['Close'].iloc[-1] if not df.empty else None
            volume = df['Volume'].iloc[-1] if 'Volume' in df.columns and not pd.isna(df['Volume'].iloc[-1]) else 0
            low_price = df['Low'].min() if not df.empty else None
            high_price = df['High'].max() if not df.empty else None
            timestamp = df.index[-1]
            local_tz = datetime.now().astimezone().tzinfo
            timestamp_local = timestamp.tz_convert(local_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            st.session_state.data_cache[symbol] = {
                'price': current_price,
                'volume': volume,
                'low': low_price,
                'high': high_price,
                'timestamp': timestamp_local
            }
        return df, st.session_state.data_cache[symbol]
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

# Sidebar for input
st.sidebar.header("Stock Watchlist")
symbol_input = st.sidebar.text_input("Enter Stock Symbol (e.g., AAPL)", "", key=f"symbol_input_{st.session_state.input_key}").upper()
interval = st.sidebar.selectbox("Select Interval", options=list(interval_options.keys()), index=1, key=f"interval_select_{st.session_state.input_key}")
if st.sidebar.button("Add to Watchlist"):
    if symbol_input:
        if symbol_input not in st.session_state.watchlist:
            st.session_state.watchlist.append(symbol_input)
            st.session_state.selected_interval = interval
            st.session_state.input_key += 1
            st.session_state.last_update = time.time()
            st.session_state.refresh_trigger = True
            st.rerun()
        else:
            st.sidebar.warning(f"{symbol_input} is already in the watchlist!")
    else:
        st.sidebar.error("Please enter a valid stock symbol.")

# Dynamic timer display
if st.session_state.watchlist:
    countdown_placeholder = st.sidebar.empty()
    progress_placeholder = st.sidebar.empty()

    current_time = time.time()
    elapsed = current_time - st.session_state.last_update
    refresh_interval = interval_options[st.session_state.selected_interval]
    progress_value = min(elapsed / refresh_interval, 1.0)
    time_remaining = max(0, refresh_interval - elapsed)

    with countdown_placeholder.container():
        st.markdown(f"""
        <div class="progress-container">
            <div class="progress-interval">Refresh Interval: {st.session_state.selected_interval}</div>
            <div class="progress-text">Time until next refresh: {int(time_remaining)}s</div>
        </div>
        """, unsafe_allow_html=True)
    with progress_placeholder.container():
        st.progress(progress_value)

# Main app
st.title("Stock Market Watchlist")

# Display current system time
current_system_time = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
st.markdown(f"<div class='system-time'>System Time: {current_system_time}</div>", unsafe_allow_html=True)

# Display watchlist with dynamic refresh
if st.session_state.watchlist:
    st.subheader("Watchlist")
    for symbol in st.session_state.watchlist:
        st.write(f"- {symbol}")

    # Handle refresh request from JavaScript
    if 'refresh' in st.experimental_get_query_params():
        st.session_state.refresh_trigger = True
        st.experimental_rerun()

    # Update data
    if st.session_state.refresh_trigger:
        with st.spinner("Fetching stock data..."):
            data_html = ""
            for i, symbol in enumerate(st.session_state.watchlist):
                st.subheader(f"Stock: {symbol}")
                data_placeholder = st.empty()
                df, info = get_stock_data(symbol, st.session_state.selected_interval)
                if df is not None and info:
                    data_html += f"""
                    <div class="stock-data">
                        <div class='stock-timestamp'>Last Updated: {info['timestamp']}</div>
                        <div class='stock-metrics'>
                            <div class='stock-metric'><strong>Current Price:</strong> ${info['price']:.2f}</div>
                            <div class='stock-metric'><strong>Low Price:</strong> ${info['low']:.2f}</div>
                            <div class='stock-metric'><strong>High Price:</strong> ${info['high']:.2f}</div>
                            <div class='stock-metric'><strong>Volume:</strong> {info['volume']:,}</div>
                        </div>
                    </div>
                    """
                    if df is not None and create_candlestick_chart(df, symbol):
                        st.plotly_chart(create_candlestick_chart(df, symbol), use_container_width=True)
                else:
                    data_html += f"<div class='stock-data'>Failed to fetch data for {symbol}.</div>"
            st.markdown(f"<div id='stock-data'>{data_html}</div>", unsafe_allow_html=True)
            st.success(f"✅ Data updated at {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")
            st.session_state.refresh_trigger = False
            st.session_state.last_update = time.time()
else:
    st.info("Add a stock symbol to the watchlist to start tracking.")
