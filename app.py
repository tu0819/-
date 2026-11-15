import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 設定網頁標題與寬度
st.set_page_config(page_title="專業級智慧股票與資產管理平台", layout="wide")

st.title("專業級智慧股票與量化資產管理平台 (券商一鍵套用版)")

# ==================== 初始化 Session State ====================
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["0050.TW", "2330.TW", "2317.TW", "009816.TW"]

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

# ==================== 側邊欄設定 ====================
st.sidebar.header("參數與導航面板")

selected_fav = st.sidebar.selectbox("快速載入收藏股票", ["-- 選擇收藏股票 --"] + st.session_state.watchlist)
default_symbol = selected_fav if selected_fav != "-- 選擇收藏股票 --" else "0050.TW"
stock_symbol = st.sidebar.text_input("輸入或修改股票代號 (台股加 .TW)", value=default_symbol)

col_fav1, col_fav2 = st.sidebar.columns(2)
with col_fav1:
    if st.button("加入收藏"):
        if stock_symbol.upper() not in st.session_state.watchlist:
            st.session_state.watchlist.append(stock_symbol.upper())
            st.success(f"已將 {stock_symbol.upper()} 加入收藏！")
with col_fav2:
    if st.button("移除收藏"):
        if stock_symbol.upper() in st.session_state.watchlist:
            st.session_state.watchlist.remove(stock_symbol.upper())
            st.warning(f"已將 {stock_symbol.upper()} 移除收藏。")

st.sidebar.markdown("---")
benchmark_symbol = st.sidebar.text_input("大盤對標代號", value="^TWII")
period = st.sidebar.selectbox("選擇回測時間範圍", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=1)

# 【新增】券商一鍵選擇與交易成本設定
st.sidebar.subheader("交易成本與券商設定 (台股)")
include_fees = st.sidebar.checkbox("計入手續費與證交稅", value=True, help="自動扣除買賣手續費及證交稅（ETF享0.1%優惠稅率）")

broker_options = {
    "台新證券 (預設 2.8 折)": 2.8,
    "富邦證券 (預設 2.0 折)": 2.0,
    "國泰證券 (預設 2.8 折)": 2.8,
    "元大證券 (預設 3.0 折)": 3.0,
    "永豐金證券 (預設 2.0 折)": 2.0,
    "玉山證券 (預設 3.0 折)": 3.0,
    "凱基證券 (預設 2.8 折)": 2.8,
    "自訂手續費折扣": 2.8
}

selected_broker = st.sidebar.selectbox("選擇您的交割券商", list(broker_options.keys()))

if selected_broker == "自訂手續費折扣":
    broker_discount = st.sidebar.slider("自訂電子手續費折扣 (折)", 1.0, 10.0, 2.8, 0.1)
else:
    broker_discount = broker_options[selected_broker]
    st.sidebar.caption(f"ℹ️ 已自動套用 {selected_broker} 常用電子折扣：**{broker_discount} 折**")

st.sidebar.subheader("停損與停利設定")
enable_sl = st.sidebar.checkbox("啟用停損機制 (Stop-Loss)", value=True)
sl_pct = st.sidebar.slider("停損跌幅 (%)", 1.0, 20.0, 5.0, 0.5)

enable_tp = st.sidebar.checkbox("啟用停利機制 (Take-Profit)", value=True)
tp_pct = st.sidebar.slider("停利漲幅 (%)", 2.0, 50.0, 15.0, 0.5)

# 個股專屬持倉評估與即時現價覆蓋
st.sidebar.subheader("當前個股持倉與現價校正")
user_cost = st.sidebar.number_input("此股票平均買價 (若無持倉填 0)", value=0.0, step=0.1)
user_shares = st.sidebar.number_input("此股票持有股數 (若無持倉填 0)", value=0.0, step=100.0)
user_manual_price = st.sidebar.number_input(
    "手動覆蓋現價 (若填 0 則自動抓取行情)", 
    value=0.0, 
    step=0.01, 
    help="💡 若想與券商 App 完全一致，可在此輸入當下現價！"
)

# ==================== 資料載入函數 (高穩定度) ====================
@st.cache_data
def load_stock_data(symbol, time_period):
    try:
        df = yf.download(symbol, period=time_period)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        st.error(f"下載股票資料發生錯誤: {e}")
        return pd.DataFrame()

@st.cache_data
def load_benchmark(bench_symbol, time_period):
    try:
        bench = yf.download(bench_symbol, period=time_period)
        if isinstance(bench.columns, pd.MultiIndex):
            bench.columns = bench.columns.get_level_values(0)
        return bench
    except:
        return pd.DataFrame()

data = load_stock_data(stock_symbol, period)
bench_data = load_benchmark(benchmark_symbol, period)

# ==================== 主畫面分頁籤設計 ====================
tab1, tab2 = st.tabs(["個股深度分析與持倉建議", "我的多檔持股總覽與資產診斷"])

with tab1:
    if not data.empty and len(data) > 0:
        st.subheader(f"📊 {stock_symbol.upper()} 技術分析與進出場訊號圖")

        window_len = min(5, len(data))
        long_window = min(20, len(data))
        
        data['SMA_5'] = data['Close'].rolling(window=window_len).mean()
        data['SMA_20'] = data['Close'].rolling(window=long_window).mean()
        
        data['BB_Middle'] = data['Close'].rolling(window=long_window).mean()
        bb_std = data['Close'].rolling(window=long_window).std()
        data['BB_Upper'] = data['BB_Middle'] + (bb_std * 2)
        data['BB_Lower'] = data['BB_Middle'] - (bb_std * 2)
        
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))

        data['Position'] = np.where(data['SMA_5'] > data['SMA_20'], 1, 0)
        data['Signal'] = data['Position'].diff()

        buy_signals = data[data['Signal'] == 1]
        sell_signals = data[data['Signal'] == -1]

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

        # 繪製圖表
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.03, 
                            row_heights=[0.6, 0.2, 0.2],
                            subplot_titles=("價格、均線、布林通道與進出場點", "成交量 (Volume)", "RSI 強弱指標"))
        
        fig.add_trace(go.Scatter(x=data.index, y=data['Close'], name='收盤價', line=dict(color='black', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA_5'], name='短期均線', line=dict(color='orange', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA_20'], name='長期均線', line=dict(color='blue', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['BB_Upper'], name='布林上軌', line=dict(color='rgba(0,0,255,0.2)', dash='dash')), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['BB_Lower'], name='布林下軌', line=dict(color='rgba(0,0,255,0.2)', dash='dash'), fill='tonexty'), row=1, col=1)
        
        fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['Close'], mode='markers', name='建議進場 (買)', marker=dict(symbol='triangle-up', size=14, color='green')), row=1, col=1)
        fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals['Close'], mode='markers', name='建議出場 (賣)', marker=dict(symbol='triangle-down', size=14, color='red')), row=1, col=1)
        
        if not bench_data.empty and len(bench_data) > 0:
            bench_close = bench_data['Close'] / bench_data['Close'].iloc[0] * data['Close'].iloc[0]
            fig.add_trace(go.Scatter(x=bench_data.index, y=bench_close, name=f'大盤基準 ({benchmark_symbol})', line=dict(color='gray', dash='dot')), row=1, col=1)

        colors = ['red' if row['Close'] < row['Open'] else 'green' for index, row in data.iterrows()]
        fig.add_trace(go.Bar(x=data.index, y=data['Volume'], name='成交量', marker_color=colors), row=2, col=1)
        
        fig.add_trace(go.Scatter(x=data.index, y=data['RSI'], name='RSI', line=dict(color='purple', width=1)), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

        fig.update_layout(height=800)
        st.plotly_chart(fig, use_container_width=True)

        # 策略績效看板
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

        # 個人持倉績效與風控評估
        st.markdown("---")
        st.subheader(f"🛡️ {stock_symbol.upper()} 個人持倉分析與進出場建議")

        market_latest_close = float(data['Close'].iloc[-1])
        effective_close = user_manual_price if user_manual_price > 0 else market_latest_close

        if user_cost > 0 and user_shares > 0:
            buy_val = user_cost * user_shares
            sell_val = effective_close * user_shares
            
            is_etf = stock_symbol.strip().upper().startswith("0")
            tax_rate = 0.001 if is_etf else 0.003
            
            if include_fees:
                buy_fee = max(20.0, buy_val * 0.001425 * (broker_discount / 10.0))
                sell_fee = max(20.0, sell_val * 0.001425 * (broker_discount / 10.0))
                sell_tax = sell_val * tax_rate
                total_cost = buy_val + buy_fee
                net_sell_val = sell_val - sell_fee - sell_tax
                pnl_amount = net_sell_val - total_cost
                my_return = (pnl_amount / total_cost) * 100
            else:
                total_cost = buy_val
                pnl_amount = sell_val - buy_val
                my_return = (effective_close - user_cost) / user_cost * 100

            my_sl_price = user_cost * (1 - sl_pct / 100)
            my_tp_price = user_cost * (1 + tp_pct / 100)

            mc1, mc2, mc3, mc4 = st.columns(4)
            with mc1:
                st.metric("持倉總市值 / 總成本", f"{sell_val:,.0f} / {total_cost:,.0f}")
            with mc2:
                label_suffix = " (含手續費/稅)" if include_fees else ""
                st.metric(f"未實現損益{label_suffix