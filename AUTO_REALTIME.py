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
if 'animation_start' not in st.session_state:
    st.session_state.animation_start = time.time()

# Custom CSS/JavaScript for animated progress ring
st.markdown("""
<style>
.progress-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin: 20px 0;
    background: rgba(0, 0, 0, 0.1);
    padding: 20px;
    border-radius: 10px;
    box-shadow: 0 0 20px rgba(0, 255, 255, 0.3);
}
.progress-ring {
    position: relative;
    width: 120px;
    height: 120px;
}
.progress-ring__circle {
    transform: rotate(-90deg);
    transform-origin: 50% 50%;
    transition: stroke-dashoffset 0.1s linear;
}
.progress-text {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 20px;
    font-weight: bold;
    color: #ffffff;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
}
.progress-interval {
    font-size: 18px;
    color: #00ffcc;
    font-weight: bold;
    margin-top: 10px;
}
body {
    background: linear-gradient(135deg, #1e3c72, #2a5298);
}
.system-time {
    font-size: 16px;
    color: #ffffff;
    margin-bottom: 10px;
}
</style>
<script>
function updateProgressRing(intervalSeconds, startTime) {
    const circle = document.getElementById('progress-circle');
    const text = document.getElementById('progress-text');
    const circumference = 2 * Math.PI * 50; // Radius = 50
    circle.style.strokeDasharray = `${circumference} ${circumference}`;
    
    function animate() {
        const elapsed = (Date.now() / 1000) - startTime;
        const progress = Math.min(elapsed / intervalSeconds, 1);
        const dashOffset = circumference * (1 - progress);
        circle.style.strokeDashoffset = dashOffset;
        text.textContent = Math.ceil(intervalSeconds - elapsed) + 's';
        if (progress < 1) {
            requestAnimationFrame(animate);
        } else {
            circle.style.strokeDashoffset = circumference; // Reset
            text.textContent = intervalSeconds + 's';
            setTimeout(() => updateProgressRing(intervalSeconds, Date.now() / 1000), 1000);
        }
    }
    animate();
}
</script>
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
        # Convert yfinance timestamp to local system timezone
        local_tz = datetime.now().astimezone().tzinfo
        timestamp_local = timestamp.tz_convert(local_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
        return df, {
            'price': current_price,
            'volume': volume,
            'low': low_price,
            'high': high_price,
            'timestamp': timestamp_local,
            'timestamp_original': timestamp
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

# Sidebar for input
st.sidebar.header("Stock Watchlist")
symbol_input = st.sidebar.text_input("Enter Stock Symbol (e.g., AAPL)", "", key=f"symbol_input_{st.session_state.input_key}").upper()
interval_options = {'1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600}
interval = st.sidebar.selectbox("Select Interval", options=list(interval_options.keys()), index=0)
if st.sidebar.button("Add to Watchlist"):
    if symbol_input:
        if symbol_input not in st.session_state.watchlist:
            st.session_state.watchlist.append(symbol_input)
            st.session_state.selected_interval = interval
            st.session_state.input_key += 1
            st.session_state.animation_start = time.time()
            st.sidebar.success(f"{symbol_input} added to watchlist!")
        else:
            st.sidebar.warning(f"{symbol_input} is already in the watchlist!")
    else:
        st.sidebar.error("Please enter a valid stock symbol.")

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

    # Display animated progress ring
    interval_seconds = interval_options[st.session_state.selected_interval]
    st.markdown(f"""
    <div class="progress-container">
        <div class="progress-ring">
            <svg width="120" height="120">
                <circle cx="60" cy="60" r="50" stroke="#e0e0e0" stroke-width="10" fill="none"/>
                <circle id="progress-circle" class="progress-ring__circle" cx="60" cy="60" r="50" stroke="url(#gradient)" stroke-width="10" fill="none"/>
                <defs>
                    <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#3498db;stop-opacity:1"/>
                        <stop offset="100%" style="stop-color:#9b59b6;stop-opacity:1"/>
                    </linearGradient>
                </defs>
            </svg>
            <div id="progress-text" class="progress-text">{interval_seconds}s</div>
        </div>
        <div class="progress-interval">Interval: {st.session_state.selected_interval}</div>
    </div>
    <script>
        updateProgressRing({interval_seconds}, {st.session_state.animation_start});
    </script>
    """, unsafe_allow_html=True)

    # Fetch and display data with spinner and progress bar
    with st.spinner("Fetching stock data..."):
        progress_bar = st.progress(0)
        total_stocks = len(st.session_state.watchlist)
        for i, symbol in enumerate(st.session_state.watchlist):
            st.subheader(f"Stock: {symbol}")
            df, info = get_stock_data(symbol, st.session_state.selected_interval)
            
            if df is not None and info:
                # Display stock details with timestamps
                st.markdown(f"<h3 style='color: #ffffff;'>As of {info['timestamp']}</h3>", unsafe_allow_html=True)
                st.markdown(f"<p style='color: #00ffcc;'>yfinance Time (Local): {info['timestamp']}</p>", unsafe_allow_html=True)
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Current Price", f"${info['price']:.2f}")
                with col2:
                    st.metric("Low Price", f"${info['low']:.2f}")
                with col3:
                    st.metric("High Price", f"${info['high']:.2f}")
                with col4:
                    st.metric("Volume", f"{info['volume']:,}")
                
                # Display candlestick chart
                fig = create_candlestick_chart(df, symbol)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.error(f"No data available for {symbol}.")
            
            # Update progress bar
            progress = (i + 1) / total_stocks
            progress_bar.progress(progress)
        
        st.success(f"Data updated at {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # Auto-refresh logic
    current_time = time.time()
    refresh_interval = interval_options[st.session_state.selected_interval]
    if current_time - st.session_state.last_update >= refresh_interval:
        st.session_state.last_update = current_time
        st.session_state.animation_start = current_time
        st.rerun()
else:
    st.info("Add a stock symbol to the watchlist to start tracking.")
