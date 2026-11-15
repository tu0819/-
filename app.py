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
stock_symbol = st.sidebar.text_input("輸入股票代號 (台股加 .TW)", value="2330.TW")
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
    # 下載個股與大盤資料
    df = yf.download(symbol, period=time_period)
    bench = yf.download(bench_symbol, period=time_period)
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if isinstance(bench.columns, pd.MultiIndex):
        bench.columns = bench.columns.get_level_values(0)
        
    return df, bench

# 取得基本面資訊
@st.cache_data
def load_fundamentals(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return {
            "name": info.get("longName", symbol),
            "pe_ratio": info.get("trailingPE", "N/A"),
            "div_yield": info.get("dividendYield", 0),
            "market_cap": info.get("marketCap", "N/A"),
            "sector": info.get("sector", "N/A")
        }
    except:
        return None

data, bench_data = load_data(stock_symbol, benchmark_symbol, period)
fund_info = load_fundamentals(stock_symbol)

if not data.empty:
    # ==================== 基本面資訊展示 ====================
    if fund_info:
        st.subheader(f"🏢 {fund_info['name']} ({stock_symbol.upper()}) 基本面概況")
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            st.metric("產業類別", fund_info['sector'])
        with f2:
            pe = f"{fund_info['pe_ratio']:.2f}" if isinstance(fund_info['pe_ratio'], (int, float)) else "資料不足"
            st.metric("本益比 (P/E)", pe)
        with f3:
            dy = f"{fund_info['div_yield']*100:.2f}%" if fund_info['div_yield'] else "無/未知"
            st.metric("預估殖利率", dy)
        with f4:
            mc = f"{fund_info['market_cap'] / 1e9:,.2f} 億" if isinstance(fund_info['market_cap'], (int, float)) else "N/A"
            st.metric("市值", mc)
        st.markdown("---")

    # ==================== 技術指標計算 ====================
    # 1. 均線
    data['SMA_5'] = data['Close'].rolling(window=5).mean()
    data['SMA_20'] = data['Close'].rolling(window=20).mean()
    
    # 2. 布林通道 (Bollinger Bands)
    data['BB_Middle'] = data['Close'].rolling(window=20).mean()
    bb_std = data['Close'].rolling(window=20).std()
    data['BB_Upper'] = data['BB_Middle'] + (bb_std * 2)
    data['BB_Lower'] = data['BB_Middle'] - (bb_std * 2)
    
    # 3. RSI 相對強弱指標 (14日)
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))

    # 4. 基礎訊號 (黃金交叉 / 死亡交叉)
    data['Position'] = np.where(data['SMA_5'] > data['SMA_20'], 1, 0)
    data['Signal'] = data['Position'].diff()

    # ==================== 模擬帶有停損停利的逐筆交易回測 ====================
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
            
            # 檢查停損 / 停利 / 死亡交叉出場
            hit_sl = enable_sl and (current_return <= -sl_pct / 100.0)
            hit_tp = enable_tp and (current_return >= tp_pct / 100.0)
            hit_signal_exit = row['Signal'] == -1
            
            if hit_sl or hit_tp or hit_signal_exit:
                trades.append(current_return)
                in_trade = False
                
    # 若結算時仍在持倉中
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

    # ==================== 繪製多功能互動圖表 (子圖表) ====================
    st.subheader(f"📊 {stock_symbol.upper()} 多功能技術分析與大盤對比圖")
    
    # 建立 3 個子圖：1. 價格與布林/均線, 2. 成交量, 3. RSI
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, 
                        row_heights=[0.6, 0.2, 0.2],
                        subplot_titles=(f"價格、均線與布林通道", "成交量 (Volume)", "RSI 強弱指標"))
    
    # 1. 價格與均線、布林通道
    fig.add_trace(go.Scatter(x=data.index, y=data['Close'], name='收盤價', line=dict(color='black', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA_5'], name='5日線', line=dict(color='orange', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA_20'], name='20日月線', line=dict(color='blue', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data['BB_Upper'], name='布林上軌', line=dict(color='rgba(0,0,255,0.2)', dash='dash')), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data['BB_Lower'], name='布林下軌', line=dict(color='rgba(0,0,255,0.2)', dash='dash'), fill='tonexty'), row=1, col=1)
    
    # 加入大盤對比 (標準化至同一起跑點)
    if not bench_data.empty:
        bench_close = bench_data['Close'] / bench_data['Close'].iloc[0] * data['Close'].iloc[0]
        fig.add_trace(go.Scatter(x=bench_data.index, y=bench_close, name=f'大盤基準 ({benchmark_symbol})', line=dict(color='gray', dash='dot')), row=1, col=1)

    # 2. 成交量 (Volume)
    colors = ['red' if row['Close'] < row['Open'] else 'green' for index, row in data.iterrows()]
    fig.add_trace(go.Bar(x=data.index, y=data['Volume'], name='成交量', marker_color=colors), row=2, col=1)
    
    # 3. RSI 指標
    fig.add_trace(go.Scatter(x=data.index, y=data['RSI'], name='RSI', line=dict(color='purple', width=1)), row=3, col=1)
    # 劃出 RSI 超買(70) 與超賣(30) 線
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    # 已移除會導致報錯的 xaxis_datagaps=[]
    fig.update_layout(height=800)
    st.plotly_chart(fig, use_container_width=True)

    # ==================== 策略期望值與表現看板 ====================
    st.subheader("🎯 量化回測表現與每筆交易期望值 (EV)")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("總回測交易次數", f"{total_trades} 次")
    with c2:
        st.metric("勝率 (Win Rate)", f"{win_rate * 100:.2f}%")
    with c3:
        st.metric("平均賺賠比", f"賺 {avg_win*100:.2f}% / 賠 {avg_loss*100:.2f}%")
    with c4:
        st.metric("每筆交易期望值 (EV)", f"{expected_value * 100:.2f}%", 
                  delta="正向優勢" if expected_value > 0 else "負向劣勢")
        
    # 當下狀態提示
    latest_rsi = data['RSI'].iloc[-1]
    latest_sma5 = data['SMA_5'].iloc[-1]
    latest_sma20 = data['SMA_20'].iloc[-1]
    
    st.subheader("🤖 當下技術指標綜合評估")
    col_a, col_b = st.columns(2)
    with col_a:
        if latest_sma5 > latest_sma20:
            st.success("🔥 **均線結構：多頭排列 (5日線 > 20日線)**")
        else:
            st.warning("⚠️ **均線結構：空頭排列 (5日線 < 20日線)**")
    with col_b:
        if latest_rsi > 70:
            st.warning(f"⚠️ **RSI 狀態：目前數值為 {latest_rsi:.1f}，進入超買區（慎防回檔）**")
        elif latest_rsi < 30:
            st.info(f"💡 **RSI 狀態：目前數值為 {latest_rsi:.1f}，進入超賣區（可能醞釀反彈）**")
        else:
            st.success(f"✅ **RSI 狀態：目前數值為 {latest_rsi:.1f}，處於健康中性區間**")

else:
    st.error("找不到該股票代號，請確認代號是否正確（台股請加 .TW，例如 2330.TW）。")