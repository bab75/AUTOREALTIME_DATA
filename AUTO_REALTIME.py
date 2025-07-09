import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from datetime import datetime, time as dt_time, timedelta
import pytz
import threading
from streamlit_autorefresh import st_autorefresh
import numpy as np

# Initialize session state
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = {}
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 60  # Default to 60 seconds
if 'last_refresh_time' not in st.session_state:
    st.session_state.last_refresh_time = time.time()
if 'refresh_count' not in st.session_state:
    st.session_state.refresh_count = 0

# Custom RSI calculation
def calculate_rsi(data, periods=14):
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=periods, min_periods=1).mean()
    avg_loss = loss.rolling(window=periods, min_periods=1).mean()
    rs = avg_gain / avg_loss.where(avg_loss != 0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi

# Detect breakout patterns
def detect_breakout(df, lookback=20):
    if len(df) < lookback:
        return None, None
    recent_data = df[-lookback:]
    resistance = recent_data['High'].max()
    support = recent_data['Low'].min()
    avg_volume = recent_data['Volume'].mean()
    current_price = df['Close'].iloc[-1]
    current_volume = df['Volume'].iloc[-1]
    
    if current_price > resistance and current_volume > 1.5 * avg_volume:
        return 'Bullish', f"Price broke above resistance (${resistance:.2f}) with high volume"
    elif current_price < support and current_volume > 1.5 * avg_volume:
        return 'Bearish', f"Price broke below support (${support:.2f}) with high volume"
    return None, None

# Detect candlestick patterns
def detect_candlestick_patterns(df):
    patterns = []
    if len(df) < 3:
        return patterns
    
    for i in range(2, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        prev2 = df.iloc[i-2]
        open_c, close_c, high_c, low_c = curr['Open'], curr['Close'], curr['High'], curr['Low']
        open_p, close_p, high_p, low_p = prev['Open'], prev['Close'], prev['High'], prev['Low']
        open_p2, close_p2, high_p2, low_p2 = prev2['Open'], prev2['Close'], prev2['High'], prev2['Low']
        
        # Calculate confidence
        avg_volume = df['Volume'].iloc[max(0, i-20):i].mean()
        volume_score = 50 if df['Volume'].iloc[i] > 1.5 * avg_volume else 0
        rsi = calculate_rsi(df.iloc[:i+1]).iloc[-1] if len(df.iloc[:i+1]) >= 14 else 50
        
        # Bullish Engulfing
        if close_p < open_p and close_c > open_c and close_c > open_p and open_c < close_p:
            rsi_score = 50 * (rsi / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Bullish Engulfing',
                'Signal': 'Bullish',
                'Details': 'Price may rise after engulfing prior bearish candle',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Bearish Engulfing
        elif close_p > open_p and close_c < open_c and close_c < open_p and open_c > close_p:
            rsi_score = 50 * ((100 - rsi) / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Bearish Engulfing',
                'Signal': 'Bearish',
                'Details': 'Price may fall after engulfing prior bullish candle',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Doji
        elif abs(close_c - open_c) <= (high_c - low_c) * 0.1:
            rsi_score = 50 * (rsi / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Doji',
                'Signal': 'Neutral',
                'Details': 'Market indecision; watch for breakout',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Hammer
        elif (high_c - low_c) > 2 * abs(close_c - open_c) and (close_c - low_c) >= 0.7 * (high_c - low_c) and (open_c - low_c) >= 0.7 * (high_c - low_c):
            rsi_score = 50 * (rsi / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Hammer',
                'Signal': 'Bullish',
                'Details': 'Potential reversal upward after downtrend',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Shooting Star
        elif (high_c - low_c) > 2 * abs(close_c - open_c) and (high_c - close_c) >= 0.7 * (high_c - low_c) and (high_c - open_c) >= 0.7 * (high_c - low_c):
            rsi_score = 50 * ((100 - rsi) / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Shooting Star',
                'Signal': 'Bearish',
                'Details': 'Potential reversal downward after uptrend',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Morning Star
        elif close_p2 > open_p2 and close_p < open_p and abs(close_p - open_p) < (high_p - low_p) * 0.3 and close_c > open_c and close_c > (open_p2 + close_p2) / 2:
            rsi_score = 50 * (rsi / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Morning Star',
                'Signal': 'Bullish',
                'Details': 'Strong reversal upward after downtrend',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Evening Star
        elif close_p2 < open_p2 and close_p > open_p and abs(close_p - open_p) < (high_p - low_p) * 0.3 and close_c < open_c and close_c < (open_p2 + close_p2) / 2:
            rsi_score = 50 * ((100 - rsi) / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Evening Star',
                'Signal': 'Bearish',
                'Details': 'Strong reversal downward after uptrend',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Bullish Harami
        elif close_p < open_p and close_c > open_c and open_c >= close_p and close_c <= open_p:
            rsi_score = 50 * (rsi / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Bullish Harami',
                'Signal': 'Bullish',
                'Details': 'Potential reversal upward; small bullish candle inside bearish candle',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Bearish Harami
        elif close_p > open_p and close_c < open_c and open_c <= close_p and close_c >= open_p:
            rsi_score = 50 * ((100 - rsi) / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Bearish Harami',
                'Signal': 'Bearish',
                'Details': 'Potential reversal downward; small bearish candle inside bullish candle',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Bullish Kicker
        elif close_p < open_p and close_c > open_c and open_c > high_p:
            rsi_score = 50 * (rsi / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Bullish Kicker',
                'Signal': 'Bullish',
                'Details': 'Strong bullish reversal with gap up after downtrend',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Bearish Kicker
        elif close_p > open_p and close_c < open_c and open_c < low_p:
            rsi_score = 50 * ((100 - rsi) / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Bearish Kicker',
                'Signal': 'Bearish',
                'Details': 'Strong bearish reversal with gap down after uptrend',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Three White Soldiers
        if i >= 3 and close_c > open_c and close_p > open_p and close_p2 > open_p2 and \
           (close_c - open_c) > (high_c - low_c) * 0.5 and (close_p - open_p) > (high_p - low_p) * 0.5 and \
           (close_p2 - open_p2) > (high_p2 - low_p2) * 0.5:
            rsi_score = 50 * (rsi / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Three White Soldiers',
                'Signal': 'Bullish',
                'Details': 'Strong upward momentum with three consecutive bullish candles',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Three Black Crows
        elif i >= 3 and close_c < open_c and close_p < open_p and close_p2 < open_p2 and \
             (open_c - close_c) > (high_c - low_c) * 0.5 and (open_p - close_p) > (high_p - low_p) * 0.5 and \
             (open_p2 - close_p2) > (high_p2 - low_p2) * 0.5:
            rsi_score = 50 * ((100 - rsi) / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Three Black Crows',
                'Signal': 'Bearish',
                'Details': 'Strong downward momentum with three consecutive bearish candles',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Piercing Line
        elif close_p < open_p and close_c > open_c and close_c > (open_p + close_p) / 2 and open_c < close_p:
            rsi_score = 50 * (rsi / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Piercing Line',
                'Signal': 'Bullish',
                'Details': 'Bullish reversal; bullish candle pierces bearish candle midpoint',
                'Confidence': round(volume_score + rsi_score, 1)
            })
        # Dark Cloud Cover
        elif close_p > open_p and close_c < open_c and close_c < (open_p + close_p) / 2 and open_c > close_p:
            rsi_score = 50 * ((100 - rsi) / 100)
            patterns.append({
                'Timestamp': curr.name.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'Pattern': 'Dark Cloud Cover',
                'Signal': 'Bearish',
                'Details': 'Bearish reversal; bearish candle covers bullish candle midpoint',
                'Confidence': round(volume_score + rsi_score, 1)
            })
    
    return patterns

# Style candlestick patterns table
def style_patterns_df(df):
    def color_rows(row):
        if row['Signal'] == 'Bullish':
            return ['background-color: #90EE90'] * len(row)
        elif row['Signal'] == 'Bearish':
            return ['background-color: #FFB6C1'] * len(row)
        else:
            return ['background-color: #FFFFFF'] * len(row)
    return df.style.apply(color_rows, axis=1).format({'Confidence': '{:.1f}'})

# Custom functions
def get_stock_data(symbol, interval, extended_hours=False):
    try:
        supported_intervals = {'1m': '1m', '2m': '2m', '3m': '1m', '5m': '5m', '10m': '1m', 
                              '15m': '15m', '30m': '30m', '45m': '1m', '1h': '1h', 
                              '2h': '1h', '3h': '1h', '4h': '1h'}
        period = '7d' if interval in ['2h', '3h', '4h'] else '1d'
        fetch_interval = supported_intervals[interval]
        
        stock = yf.Ticker(symbol)
        df = stock.history(period=period, interval=fetch_interval)
        if df.empty or len(df) < 2:
            st.error(f"No sufficient data for {symbol} with interval {interval}")
            return None
        
        # Resample for non-standard intervals
        if interval == '3m':
            df = df.resample('3min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 
                                        'Close': 'last', 'Volume': 'sum'}).dropna()
        elif interval == '10m':
            df = df.resample('10min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 
                                         'Close': 'last', 'Volume': 'sum'}).dropna()
        elif interval == '45m':
            df = df.resample('45min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 
                                         'Close': 'last', 'Volume': 'sum'}).dropna()
        elif interval in ['2h', '3h', '4h']:
            hours = int(interval[0])
            df = df.resample(f'{hours}H').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 
                                             'Close': 'last', 'Volume': 'sum'}).dropna()
        
        # Filter for current trading day or extended hours
        local_tz = pytz.timezone('America/New_York')
        df = df.tz_convert(local_tz)
        today = datetime.now(local_tz).date()
        if extended_hours:
            df = df.between_time(dt_time(4, 0), dt_time(20, 0))  # Pre/post-market
        else:
            df = df[df.index.date == today]
        
        if df.empty or len(df) < 2:
            # Fallback to previous trading day
            yesterday = today - timedelta(days=1)
            df = stock.history(period='2d', interval=fetch_interval)
            df = df.tz_convert(local_tz)
            df = df[df.index.date == yesterday]
            if extended_hours:
                df = df.between_time(dt_time(4, 0), dt_time(20, 0))
            else:
                df = df.between_time(dt_time(9, 30), dt_time(16, 0))
            
            if df.empty or len(df) < 2:
                st.warning(f"No data for {symbol} on current or previous trading day with interval {interval}")
                return None
        
        current_price = df['Close'].iloc[-1]
        previous_price = df['Close'].iloc[-2]
        current_volume = df['Volume'].iloc[-1]
        previous_volume = df['Volume'].iloc[-2]
        timestamp = df.index[-1]
        timestamp_local = timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')
        change_pct = round(((current_price - previous_price) / previous_price) * 100, 3)
        volume_change_pct = round(((current_volume - previous_volume) / previous_volume) * 100, 3) if previous_volume > 0 else 0
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

def get_volume_trend_data(symbol, extended_hours=False):
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period='2d', interval='1m')
        if df.empty or len(df) < 2:
            st.error(f"No intraday data for {symbol}")
            return None
        local_tz = pytz.timezone('America/New_York')
        df = df.tz_convert(local_tz)
        today = datetime.now(local_tz).date()
        
        # Try current day first
        df_today = df[df.index.date == today]
        if extended_hours:
            df_today = df_today.between_time(dt_time(4, 0), dt_time(20, 0))
        else:
            df_today = df_today.between_time(dt_time(9, 30), dt_time(16, 0))
        
        if not df_today.empty and len(df_today) >= 2:
            return df_today
        
        # Fallback to previous trading day
        yesterday = today - timedelta(days=1)
        df_yesterday = df[df.index.date == yesterday]
        if extended_hours:
            df_yesterday = df_yesterday.between_time(dt_time(4, 0), dt_time(20, 0))
        else:
            df_yesterday = df_yesterday.between_time(dt_time(9, 30), dt_time(16, 0))
        
        if df_yesterday.empty or len(df_yesterday) < 2:
            st.warning(f"No data for {symbol} on current or previous trading day")
            return None
        return df_yesterday
    except Exception as e:
        st.error(f"Error fetching intraday data for {symbol}: {str(e)}")
        return None

def create_candlestick_chart(df, symbol, interval):
    if df is not None and not df.empty:
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.1, 
                           subplot_titles=('Candlestick', 'Volume', 'RSI'), row_heights=[0.5, 0.3, 0.2])
        
        # Candlestick
        fig.add_trace(go.Candlestick(x=df.index,
                                    open=df['Open'],
                                    high=df['High'],
                                    low=df['Low'],
                                    close=df['Close'],
                                    name=symbol),
                     row=1, col=1)
        
        # SMA
        if len(df) >= 50:
            sma = df['Close'].rolling(window=50).mean()
            fig.add_trace(go.Scatter(x=df.index, y=sma, name='50-Period SMA', line=dict(color='orange', width=2)), row=1, col=1)
        else:
            st.warning(f"Insufficient data for 50-period SMA ({len(df)} candles < 50)")
        
        # Volume
        colors = ['green' if df['Volume'].iloc[i] >= df['Volume'].iloc[max(0, i-1)] else 'red' for i in range(len(df))]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color=colors), row=2, col=1)
        
        # RSI
        if len(df) >= 14:
            rsi = calculate_rsi(df)
            fig.add_trace(go.Scatter(x=df.index, y=rsi, name='RSI (14)', line=dict(color='purple', width=2)), row=3, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
        else:
            st.warning(f"Insufficient data for RSI ({len(df)} candles < 14)")
        
        # Pattern markers
        patterns = detect_candlestick_patterns(df)
        for pattern in patterns:
            timestamp = pd.to_datetime(pattern['Timestamp'])
            if timestamp in df.index:
                price = df.loc[timestamp]['High'] * 1.01  # Slightly above high
                marker_color = 'green' if pattern['Signal'] == 'Bullish' else 'red' if pattern['Signal'] == 'Bearish' else 'gray'
                fig.add_trace(go.Scatter(
                    x=[timestamp],
                    y=[price],
                    mode='markers',
                    marker=dict(symbol='triangle-down', size=10, color=marker_color),
                    name=pattern['Pattern'],
                    text=[pattern['Pattern']],
                    textposition='top center'
                ), row=1, col=1)
        
        fig.update_layout(
            title=f"{symbol} Candlestick Chart ({interval})",
            yaxis_title="Price",
            yaxis2_title="Volume",
            yaxis3_title="RSI",
            xaxis_title="Time",
            xaxis_rangeslider_visible=False,
            template="plotly_white"
        )
        return fig
    return None

def create_volume_trend_chart(df, symbol):
    if df is not None and not df.empty and len(df) >= 2:
        volume_data = df['Volume']
        labels = volume_data.index.strftime('%H:%M')
        today = datetime.now(pytz.timezone('America/New_York')).date()
        chart_date = df.index.date[0]
        date_str = "Last Trading Day" if chart_date != today else "Current Trading Day"
        
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
            title=f"Volume Trend for {symbol} ({date_str})",
            xaxis_title="Time (EDT)",
            yaxis_title="Volume",
            template="plotly_white",
            showlegend=True
        )
        return fig
    return None

def create_portfolio_chart(symbols, changes):
    if symbols and changes and all(isinstance(c, (int, float, np.floating)) and not np.isnan(c) for c in changes):
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=symbols,
            y=changes,
            marker_color=['#4CAF50' if c >= 0 else '#F44336' for c in changes],
            marker_line_color=['#388E3C' if c >= 0 else '#D32F2F' for c in changes],
            marker_line_width=1,
            text=[f"{c:.3f}%" for c in changes],
            textposition='auto'
        ))
        
        fig.update_layout(
            title="Portfolio Performance",
            xaxis_title="Stocks",
            yaxis_title="Percentage Change",
            template="plotly_white",
            showlegend=False,
            yaxis=dict(zeroline=True, zerolinecolor='black', zerolinewidth=1)
        )
        return fig
    else:
        st.warning("Invalid or missing data for portfolio chart")
        return None

def generate_recommendations(symbol, df_volume, change_pct, df_candlestick):
    recommendations = []
    
    # Breakout detection
    breakout_signal, breakout_details = detect_breakout(df_candlestick)
    if breakout_signal:
        recommendations.append(f"{breakout_signal} breakout detected: {breakout_details}")
    
    # Volume spikes
    if df_volume is not None and not df_volume.empty:
        volume_data = df_volume['Volume']
        volume_changes = volume_data.pct_change() * 100
        spike_threshold = 50
        spikes = volume_changes[volume_changes > spike_threshold]
        if not spikes.empty:
            spike_times = spikes.index.strftime('%H:%M')
            recommendations.append(f"High volume spikes detected at {', '.join(spike_times)} EDT, indicating strong buying/selling pressure.")
    
    # Price momentum
    if isinstance(change_pct, (int, float, np.floating)) and not np.isnan(change_pct):
        if change_pct > 2:
            recommendations.append(f"{symbol} (+{change_pct:.3f}%) shows bullish momentum; consider holding or buying on dips.")
        elif change_pct < -2:
            recommendations.append(f"{symbol} ({change_pct:+.3f}%) shows bearish momentum; consider selling or waiting for a reversal.")
        else:
            recommendations.append(f"{symbol} ({change_pct:+.3f}%) is stable; monitor for breakout patterns or candlestick signals.")
    
    # Candlestick patterns
    patterns = detect_candlestick_patterns(df_candlestick)
    for pattern in patterns[-3:]:  # Show last 3 patterns
        recommendations.append(f"{pattern['Signal']} pattern detected at {pattern['Timestamp']}: {pattern['Pattern']} ({pattern['Details']}, Confidence: {pattern['Confidence']:.1f})")
    
    # SMA
    if df_candlestick is not None and len(df_candlestick) >= 50:
        sma = df_candlestick['Close'].rolling(window=50).mean().iloc[-1]
        current_price = df_candlestick['Close'].iloc[-1]
        if current_price > sma:
            recommendations.append("Price is above 50-period SMA; bullish trend indicated.")
        elif current_price < sma:
            recommendations.append("Price is below 50-period SMA; bearish trend indicated.")
    
    # RSI
    if df_candlestick is not None and len(df_candlestick) >= 14:
        rsi = calculate_rsi(df_candlestick).iloc[-1]
        if rsi > 70:
            recommendations.append("RSI above 70; stock may be overbought, consider taking profits.")
        elif rsi < 30:
            recommendations.append("RSI below 30; stock may be oversold, potential buying opportunity.")
    
    recommendations.append("Note: These are not financial advice; consult a professional.")
    return recommendations if recommendations else ["No specific recommendations; monitor market conditions. Note: These are not financial advice; consult a professional."]

def generate_alerts(symbol, change_pct, volume_change_pct, df_candlestick):
    alerts = []
    if isinstance(change_pct, (int, float, np.floating)) and not np.isnan(change_pct) and abs(change_pct) > 5:
        alerts.append(f"Significant price movement in {symbol}: {change_pct:+.3f}%")
    if isinstance(volume_change_pct, (int, float, np.floating)) and not np.isnan(volume_change_pct) and volume_change_pct > 100:
        alerts.append(f"Significant volume spike in {symbol}: +{volume_change_pct:.3f}%")
    breakout_signal, breakout_details = detect_breakout(df_candlestick)
    if breakout_signal:
        alerts.append(f"{breakout_signal} breakout detected for {symbol}: {breakout_details}")
    return alerts

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

clock_placeholder = st.empty()
threading.Thread(target=display_clock, daemon=True).start()

# Title and description
st.title("📈 Real-Time Stock Monitoring Dashboard")
st.markdown("Track multiple stocks with interactive candlestick charts, breakout patterns, and candlestick signals")

# Auto-refresh logic
if st.session_state.auto_refresh:
    refresh_count = st_autorefresh(interval=st.session_state.refresh_interval * 1000, key="stockrefresh")
    if refresh_count > 0:
        with st.spinner("🔄 Auto-refreshing stock data..."):
            any_data_updated = False
            for symbol in list(st.session_state.watchlist.keys()):
                data = get_stock_data(symbol, st.session_state.watchlist[symbol]['interval'], extended_hours=True)
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
            st.session_state.last_refresh_time = time.time()
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
        "1m": "1 Minute", "2m": "2 Minutes", "3m": "3 Minutes", "5m": "5 Minutes",
        "10m": "10 Minutes", "15m": "15 Minutes", "30m": "30 Minutes",
        "45m": "45 Minutes", "1h": "1 Hour", "2h": "2 Hours",
        "3h": "3 Hours", "4h": "4 Hours"
    }
    selected_interval = st.selectbox(
        "Select Chart Time Interval",
        options=list(interval_options.keys()),
        format_func=lambda x: interval_options[x],
        index=3,  # Default to 5m
        help="Each candle represents this time period (intraday)"
    )
    
    extended_hours = st.toggle(
        #"Include Extended Hours (Pre/Post-Market)",
        "EH Hours(Pre/Post)",
        value=False,
        help="Include pre-market (4:00 AM–9:30 AM EDT) and post-market (4:00 PM–8:00 PM EDT) data"
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
                data = get_stock_data(symbol, selected_interval, extended_hours)
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
                data = get_stock_data(symbol, st.session_state.watchlist[symbol]['interval'], extended_hours)
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
    
    st.subheader("🔄 Refresh Status")
    st.markdown(f"**Auto-Refresh Enabled:** {'Yes' if st.session_state.auto_refresh else 'No'}")
    st.markdown(f"**Last Refresh:** {datetime.fromtimestamp(st.session_state.last_refresh_time).astimezone(pytz.timezone('America/New_York')).strftime('%Y-%m-%d %H:%M:%S %Z') if st.session_state.last_refresh_time else 'N/A'}")
    st.markdown(f"**Refresh Count:** {st.session_state.refresh_count}")

    st.subheader("📈 Volume Trend")
    selected_volume_stock = st.selectbox(
        "Select Stock for Volume Trend",
        options=list(st.session_state.watchlist.keys()) if st.session_state.watchlist else ["No stocks available"],
        help="Select a stock to view its volume trend (last trading day)"
    )

# Main content with tabs
tab1, tab2, tab3 = st.tabs(["Watchlist", "Portfolio Overview", "Volume Trend & Recommendations"])

with tab1:
    st.header("Watchlist")
    if not st.session_state.watchlist:
        st.info("📝 Add stocks to your watchlist using the sidebar to get started!")
    else:
        watchlist_data = pd.DataFrame([
            {
                'Symbol': symbol,
                'Price': info['price'],
                'Change (%)': info['change_pct'],
                'Volume': info['volume'],
                'Open': info['open'],
                'High': info['high'],
                'Low': info['low'],
                'Last Updated': info['last_update']
            } for symbol, info in st.session_state.watchlist.items()
        ])
        st.download_button(
            label="📥 Download Watchlist",
            data=watchlist_data.to_csv(index=False),
            file_name="watchlist.csv",
            mime="text/csv"
        )
        
        for symbol, stock_info in st.session_state.watchlist.items():
            with st.container():
                st.subheader(f"📊 {symbol}")
                
                alerts = generate_alerts(symbol, stock_info['change_pct'], stock_info['volume_change_pct'], stock_info['data'])
                for alert in alerts:
                    st.warning(f"⚠️ {alert}")
                
                st.markdown(f"**Last Updated:** {stock_info['last_update']}")
                
                # Single-line metrics display
                col1, col2, col3, col4, col5 = st.columns([1.5, 1, 1, 1, 1.5])
                with col1:
                    st.markdown(f"<span style='font-size: 16px; font-weight: bold; color: {'#4CAF50' if stock_info['change_pct'] >= 0 else '#F44336'};'>Price: ${stock_info['price']:.2f} ({stock_info['change_pct']:+.3f}%)</span>", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"<span style='font-size: 16px; font-weight: bold;'>Open: ${stock_info['open']:.2f}</span>", unsafe_allow_html=True)
                with col3:
                    st.markdown(f"<span style='font-size: 16px; font-weight: bold;'>High: ${stock_info['high']:.2f}</span>", unsafe_allow_html=True)
                with col4:
                    st.markdown(f"<span style='font-size: 16px; font-weight: bold;'>Low: ${stock_info['low']:.2f}</span>", unsafe_allow_html=True)
                with col5:
                    st.markdown(f"<span style='font-size: 16px; font-weight: bold; color: {'#4CAF50' if stock_info['volume_change_pct'] >= 0 else '#F44336'};'>Volume: {int(stock_info['volume']):,}</span>", unsafe_allow_html=True)
                
                fig = create_candlestick_chart(stock_info['data'], symbol, stock_info['interval'])
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No data available for chart")
                
                # Candlestick Patterns Table
                with st.expander(f"Candlestick Patterns for {symbol}"):
                    st.markdown("""
                    **Confidence Score (0–100)**: Measures pattern reliability.  
                    - **Volume Score**: 50 if volume > 1.5x 20-candle average, else 0.  
                    - **RSI Score**: For Bullish/Neutral, RSI/2 (0–50); for Bearish, (100–RSI)/2 (0–50).  
                    - **Total**: Volume + RSI scores. Higher scores indicate stronger signals.
                    """)
                    patterns = detect_candlestick_patterns(stock_info['data'])
                    if patterns:
                        patterns_df = pd.DataFrame(patterns)
                        filter_option = st.selectbox(
                            "Filter Patterns",
                            options=["All", "Bullish", "Bearish", "Neutral"],
                            key=f"filter_{symbol}"
                        )
                        if filter_option != "All":
                            patterns_df = patterns_df[patterns_df['Signal'] == filter_option]
                        if not patterns_df.empty:
                            st.dataframe(style_patterns_df(patterns_df), use_container_width=True)
                            # Add confidence note to CSV
                            csv_data = patterns_df.to_csv(index=False)
                            csv_data = f"Confidence Score (0-100): Measures pattern reliability. Volume Score: 50 if volume > 1.5x 20-candle average, else 0. RSI Score: For Bullish/Neutral, RSI/2 (0-50); for Bearish, (100-RSI)/2 (0-50). Total: Volume + RSI scores. Higher scores indicate stronger signals.\n\n{csv_data}"
                            st.download_button(
                                label="📥 Download Candlestick Patterns",
                                data=csv_data,
                                file_name=f"{symbol}_candlestick_patterns.csv",
                                mime="text/csv"
                            )
                        else:
                            st.info(f"No {filter_option.lower()} patterns detected")
                    else:
                        st.info("No candlestick patterns detected for this stock")
                
                st.divider()

with tab2:
    st.header("Portfolio Performance Overview")
    st.markdown("Percentage change for all stocks in your watchlist")
    if st.session_state.watchlist:
        symbols = list(st.session_state.watchlist.keys())
        changes = []
        valid_symbols = []
        for symbol in symbols:
            change = st.session_state.watchlist[symbol]['change_pct']
            if isinstance(change, (int, float, np.floating)) and not np.isnan(change):
                changes.append(change)
                valid_symbols.append(symbol)
            else:
                st.warning(f"Invalid change_pct for {symbol}: {change}")
        
        # Debug output
        #st.write(f"Valid Symbols: {valid_symbols}")
        #st.write(f"Valid Changes: {changes}")
        
        if not valid_symbols:
            st.warning("No valid stocks available for portfolio performance chart")
        else:
            fig = create_portfolio_chart(valid_symbols, changes)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Failed to render portfolio performance chart")
    else:
        st.info("No stocks in watchlist to display portfolio performance.")

with tab3:
    st.header("Volume Trend & Recommendations")
    if st.session_state.watchlist and selected_volume_stock in st.session_state.watchlist:
        st.subheader(f"📈 Volume Trend for {selected_volume_stock}")
        st.markdown("Volume from current or last trading day")
        
        df_volume = get_volume_trend_data(selected_volume_stock, extended_hours)
        fig = create_volume_trend_chart(df_volume, selected_volume_stock)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Not enough data for volume trend chart (current or last trading day)")
        
        st.subheader("Recommendations")
        df_candlestick = st.session_state.watchlist[selected_volume_stock]['data']
        change_pct = st.session_state.watchlist[selected_volume_stock]['change_pct']
        recommendations = generate_recommendations(selected_volume_stock, df_volume, change_pct, df_candlestick)
        for rec in recommendations:
            st.markdown(f"- {rec}")
    else:
        st.info("Select a stock from the watchlist to view volume trend and recommendations.")

# Footer
st.markdown("---")
st.markdown("🔍 **Data provided by Yahoo Finance** | 📊 **Real-Time Stock Monitoring Dashboard**")
