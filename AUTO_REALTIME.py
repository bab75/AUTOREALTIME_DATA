import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import time
from datetime import datetime, timedelta

# Initialize session state
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []
if 'last_update' not in st.session_state:
    st.session_state.last_update = time.time()
if 'selected_interval' not in st.session_state:
    st.session_state.selected_interval = '1m'
if 'input_key' not in st.session_state:
    st.session_state.input_key = 0

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
        timestamp = df.index[-1].strftime('%Y-%m-%d %H:%M:%S') if not df.empty else None
        return df, {
            'price': current_price,
            'volume': volume,
            'low': low_price,
            'high': high_price,
            'timestamp': timestamp
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
            st.session_state.input_key += 1  # Reset input field
            st.sidebar.success(f"{symbol_input} added to watchlist!")
        else:
            st.sidebar.warning(f"{symbol_input} is already in the watchlist!")
    else:
        st.sidebar.error("Please enter a valid stock symbol.")

# Main app
st.title("Stock Market Watchlist")

# Display watchlist
if st.session_state.watchlist:
    st.subheader("Watchlist")
    for symbol in st.session_state.watchlist:
        st.write(f"- {symbol}")

    # Fetch and display data for each stock with spinner
    with st.spinner("Updating stock data..."):
        for symbol in st.session_state.watchlist:
            st.subheader(f"Stock: {symbol}")
            df, info = get_stock_data(symbol, st.session_state.selected_interval)
            
            if df is not None and info:
                # Display stock details with timestamp
                st.write(f"**As of {info['timestamp']}**")
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
        st.success(f"Data updated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Auto-refresh logic with slight delay
    current_time = time.time()
    refresh_interval = interval_options[st.session_state.selected_interval]
    if current_time - st.session_state.last_update >= refresh_interval:
        time.sleep(0.5)  # Short delay to stabilize UI
        st.session_state.last_update = current_time
        st.rerun()
else:
    st.info("Add a stock symbol to the watchlist to start tracking.")
