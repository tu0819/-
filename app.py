import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 設定網頁標題與寬度
st.set_page_config(page_title="專業級智慧股票分析 App", layout="wide")

st.title("📈 專業級智慧股票與量化回測分析平台")

# ==================== 側邊欄設定 ====================
st.sidebar.header("⚙️ 參數設定面板")
stock_symbol = st.sidebar.text_input("輸入股票代號 (台股加 .TW，如 2330.TW 或 0050.TW)", value="0050.TW")
benchmark_symbol = st.sidebar.text_input("輸入大盤對標代號", value="^TWII") # 台股加權指數
period = st.sidebar.selectbox("選擇回測時間範圍", ["3mo", "6mo", "1y", "2y", "5y", "max"], index=2)

st.sidebar.subheader("🛡️ 停損與停利設定")
enable_sl = st.sidebar.checkbox("啟用停損機制 (Stop-Loss)", value=True)
sl_pct = st.sidebar.slider("停損跌幅 (%)", 1.0, 20.0, 5.0, 0.5)

enable_tp = st.sidebar.checkbox("啟用停利機制 (Take-Profit)", value=True)
tp_pct = st.sidebar.slider("停利漲幅 (%)", 2.0, 50.0, 15.0, 0.5)

# ==================== 資料載入與處理 ====================
@st.cache_data
def load_data(symbol, bench_symbol, time_period):
    df = yf.download(symbol, period=time_period)
    bench = yf.download(bench_symbol, period=time_period)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if isinstance(bench.columns, pd.MultiIndex):
        bench.columns = bench.columns.get_level_values(0)
        
    return df, bench

@st.cache_data
def load_fundamentals(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        sector = info.get("sector", None)
        if not sector:
            sector = "指數股票型基金 (ETF)"
        return {
            "name": info.get("longName", symbol),
            "pe_ratio": info.get("trailingPE", "N/A"),
            "div_yield": info.get("dividendYield", None),
            "market_cap": info.get("marketCap", "N/A"),
            "sector": sector
        }
    except:
        return None

data, bench_data = load_data(stock_symbol, benchmark_symbol, period)
fund_info = load_fundamentals(stock_symbol)

if not data.empty:
    # ==================== 基本面資訊展示 ====================
    if fund_info:
        st.subheader(f"🏢 {fund_info['name']} ({stock_symbol.upper()}) 基本面與基金概況")
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            st.metric("類型 / 產業", fund_info['sector'])
        with f2:
            pe = f"{fund_info['pe_ratio']:.2f}" if isinstance(fund_info['pe_ratio'], (int, float)) else "資料未提供"
            st.metric("本益比 (P/E)", pe)
        with f3:
            dy_val = fund_info['div_yield']
            if dy_val is not None and isinstance(dy_val, (int, float)):
                dy_str = f"{dy_val:.2f}%" if dy_val > 1 else f"{dy_val * 100:.2f}%"
            else:
                dy_str = "依當年度配息而定"
            st.metric("預估殖利率", dy_str)
        with f4:
            mc = f"{fund_info['market_cap'] / 1e9:,.2f} 億" if isinstance(fund_info['market_cap'], (int, float)) else "N/A"
            st.metric("市值 / 規模", mc)
        st.markdown("---")

    # ==================== 技術指標與訊號計算 ====================
    data['SMA_5'] = data['Close'].rolling(window=5).mean()
    data['SMA_20'] = data['Close'].rolling(window=20).mean()
    
    # 布林通道
    data['BB_Middle'] = data['Close'].rolling(window=20).mean()
    bb_std = data['Close'].rolling(window=20).std()
    data['BB_Upper'] = data['BB_Middle'] + (bb_std * 2)
    data['BB_Lower'] = data['BB_Middle'] - (bb_std * 2)
    
    # RSI 指標
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))

    # 交易訊號
    data['Position'] = np.where(data['SMA_5'] > data['SMA_20'], 1, 0)
    data['Signal'] = data['Position'].diff()

    buy_signals = data[data['Signal'] == 1]
    sell_signals = data[data['Signal'] == -1]

    # ==================== 回測模擬 ====================
    trades = []
    in_trade = False
    entry_price = 0
    
    for i in range(len(data)):
        row = data.iloc[i]
        price = row['Close']
        
        if not in_trade:
            if row['Signal'] == 1:
                entry_price = price
                in_trade = True
        else:
            current_return = (price - entry_price) / entry_price
            hit_sl = enable_sl and (current_return <= -sl_pct / 100.0)
            hit_tp = enable_tp and (current_return >= tp_pct / 100.0)
            hit_signal_exit = row['Signal'] == -1
            
            if hit_sl or hit_tp or hit_signal_exit:
                trades.append(current_return)
                in_trade = False
                
    if in_trade:
        trades.append((data['Close'].iloc[-1] - entry_price) / entry_price)
        
    trades_df = pd.Series(trades) if len(trades) > 0 else pd.Series()
    
    if not trades_df.empty:
        winning = trades_df[trades_df > 0]
        losing = trades_df[trades_df < 0]
        total_trades = len(trades_df)
        win_rate = len(winning) / total_trades if total_trades > 0 else 0
        loss_rate = 1 - win_rate
        avg_win = winning.mean() if len(winning) > 0 else 0
        avg_loss = abs(losing.mean()) if len(losing) > 0 else 0
        expected_value = (win_rate * avg_win) - (loss_rate * avg_loss)
    else:
        total_trades, win_rate, avg_win, avg_loss, expected_value = 0, 0, 0, 0, 0

    # ==================== 繪製圖表 ====================
    st.subheader(f"📊 {stock_symbol.upper()} 多功能技術分析與進出場訊號圖")
    
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, 
                        row_heights=[0.6, 0.2, 0.2],
                        subplot_titles=(f"價格、均線、布林通道與進出場點", "成交量 (Volume)", "RSI 強弱指標"))
    
    fig.add_trace(go.Scatter(x=data.index, y=data['Close'], name='收盤價', line=dict(color='black', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA_5'], name='5日線', line=dict(color='orange', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA_20'], name='20日月線', line=dict(color='blue', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data['BB_Upper'], name='布林上軌', line=dict(color='rgba(0,0,255,0.2)', dash='dash')), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data['BB_Lower'], name='布林下軌', line=dict(color='rgba(0,0,255,0.2)', dash='dash'), fill='tonexty'), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['Close'], mode='markers', name='建議進場 (買)', marker=dict(symbol='triangle-up', size=14, color='green')), row=1, col=1)
    fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals['Close'], mode='markers', name='建議出場 (賣)', marker=dict(symbol='triangle-down', size=14, color='red')), row=1, col=1)
    
    if not bench_data.empty:
        bench_close = bench_data['Close'] / bench_data['Close'].iloc[0] * data['Close'].iloc[0]
        fig.