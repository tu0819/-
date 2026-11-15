import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 設定網頁標題與寬度
st.set_page_config(page_title="專業級智慧股票與資產管理平台", layout="wide")

st.title("專業級智慧股票與量化資產管理平台")

# ==================== 初始化 Session State (記憶收藏與持股) ====================
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["0050.TW", "2330.TW", "2317.TW"]

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

# ==================== 側邊欄設定 ====================
st.sidebar.header("參數與導航面板")

# 1. 收藏選單快速切換
st.sidebar.subheader("我的收藏清單 (Watchlist)")
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
period = st.sidebar.selectbox("選擇回測時間範圍", ["1d", "5d", "7d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=3)

# 資料細緻度選擇
interval = st.sidebar.selectbox(
    "選擇資料頻率 (細緻度)", 
    ["1d", "1h", "30m", "15m", "5m", "1m"], 
    index=0,
    help="Yahoo限制：1m僅支援7天內；1h/30m/15m/5m支援60天內。若選擇不相容會自動幫您調整。"
)

# 【防呆機制】自動檢查 Yahoo API 限制
if interval == "1m" and period not in ["1d", "5d", "7d"]:
    st.sidebar.warning("⚠️ 提醒：1分鐘線(1m)最多只能查詢 7 天內，已自動將時間範圍調為 7d。")
    period = "7d"
elif interval in ["1h", "30m", "15m", "5m"] and period in ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]:
    st.sidebar.warning(f"⚠️ 提醒：{interval} 頻率最多支援 60 天內，已自動將時間範圍調為 60d 以內可用的範圍。")
    if period in ["1mo"]:
        pass # 1個月大致在60天內，勉強可過
    else:
        period = "1mo"

st.sidebar.subheader("停損與停利設定")
enable_sl = st.sidebar.checkbox("啟用停損機制 (Stop-Loss)", value=True)
sl_pct = st.sidebar.slider("停損跌幅 (%)", 1.0, 20.0, 5.0, 0.5)

enable_tp = st.sidebar.checkbox("啟用停利機制 (Take-Profit)", value=True)
tp_pct = st.sidebar.slider("停利漲幅 (%)", 2.0, 50.0, 15.0, 0.5)

# 個股專屬持倉評估輸入框
st.sidebar.subheader("當前個股持倉評估")
user_cost = st.sidebar.number_input("此股票平均買價 (若無持倉填 0)", value=0.0, step=0.1)
user_shares = st.sidebar.number_input("此股票持有股數 (若無持倉填 0)", value=0.0, step=100.0)

# ==================== 資料載入與處理 ====================
@st.cache_data
def load_data(symbol, bench_symbol, time_period, data_interval):
    try:
        df = yf.download(symbol, period=time_period, interval=data_interval)
        bench = yf.download(bench_symbol, period=time_period, interval=data_interval)
    except:
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

data, bench_data = load_data(stock_symbol, benchmark_symbol, period, interval)
fund_info = load_fundamentals(stock_symbol)

# ==================== 主畫面分頁籤設計 ====================
tab1, tab2 = st.tabs(["個股深度分析與持倉建議", "我的多檔持股總覽與資產診斷"])

with tab1:
    if not data.empty and len(data) > 0:
        if fund_info:
            st.subheader(f"{fund_info['name']} ({stock_symbol.upper()}) 基本面與基金概況")
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

        # 技術指標與回測計算
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

        # 圖表繪製
        st.subheader(f"{stock_symbol.upper()} 多時間點技術分析與進出場訊號圖 (頻率: {interval})")
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
        st.subheader("量化回測表現與每筆交易期望值 (EV)")
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

        # 個股專屬持倉績效與風控評估
        st.markdown("---")
        st.subheader(f"{stock_symbol.upper()} 個人持倉分析與進出場建議")

        latest_close = float(data['Close'].iloc[-1])

        if user_cost > 0 and user_shares > 0:
            total_cost = user_cost * user_shares
            market_value = latest_close * user_shares
            pnl_amount = market_value - total_cost
            my_return = (latest_close - user_cost) / user_cost * 100
            my_sl_price = user_cost * (1 - sl_pct / 100)
            my_tp_price = user_cost * (1 + tp_pct / 100)

            mc1, mc2, mc3, mc4 = st.columns(4)
            with mc1:
                st.metric("持倉總市值 / 總成本", f"{market_value:,.0f} / {total_cost:,.0f}")
            with mc2:
                st.metric("未實現損益 (金額 / %)", f"{pnl_amount:+,.0f} 元", delta=f"{my_return:.2f}%", delta_color="normal" if my_return >= 0 else "inverse")
            with mc3:
                st.metric(f"依成本停損價 (-{sl_pct}%)", f"{my_sl_price:.2f}")
            with mc4:
                st.metric(f"依成本停利價 (+{tp_pct}%)", f"{my_tp_price:.2f}")
            
            if latest_close <= my_sl_price:
                st.error(f"【當下出場警示】目前最新價 ({latest_close:.2f}) 已跌破您的停損價 ({my_sl_price:.2f})！建議果斷執行紀律停損出場。")
            elif latest_close >= my_tp_price:
                st.success(f"【當下出場警示】目前最新價 ({latest_close:.2f}) 已達到您的停利價 ({my_tp_price:.2f})！建議考慮獲利了結或分批減碼。")
            else:
                buffer_amt = latest_close - my_sl_price
                st.info(f"【續抱建議】目前持倉安全運作中。距離停損價還有 {buffer_amt:.2f} 元的緩衝空間，可繼續續抱觀望。")
        else:
            st.info("提示：若您目前持有這檔股票，請在左側側邊欄輸入您的「平均買價」與「持有股數」，這裡將會即時為您分析該檔股票的未實現損益與具體進出場建議！")

        # 當下技術面綜合操作指引
        st.markdown("---")
        st.subheader("當下技術面綜合操作指引")
        latest_sma5 = float(data['SMA_5'].iloc[-1])
        latest_sma20 = float(data['SMA_20'].iloc[-1])
        latest_rsi = float(data['RSI'].iloc[-1])

        if latest_sma5 > latest_sma20:
            if latest_rsi > 70:
                action_title = "多頭格局但短線過熱（建議觀望 / 逢高分批減碼）"
                action_desc = "目前短期均線大於長期均線（多頭排列），但 RSI 指標已進入 70 以上超買區，短線有回檔壓力。"
                box_func = st.warning
            else:
                action_title = "建議偏多操作 / 可考慮進場續抱"
                action_desc = "目前短期均線大於長期均線且 RSI 處於健康區間，符合多頭趨勢。"
                box_func = st.success
        else:
            if latest_rsi < 30:
                action_title = "空頭排列但跌至超賣區（醞釀反彈 / 可輕倉試單）"
                action_desc = "均線雖屬空頭，但 RSI 已跌破 30 進入超賣區，可能出現跌深反彈。"
                box_func = st.info
            else:
                action_title = "建議空手觀望 / 暫時避險"
                action_desc = "短期均線小於長期均線（空頭排列），趨勢向下，建議耐心等待黃金交叉。"
                box_func = st.error

        box_func(f"### {action_title}\n{action_desc}")
    else:
        st.error("找不到該股票代號或所選頻率與時間範圍不相容。若您選擇了 '1m' 分鐘線，請將時間範圍縮短至 7d（例如 5d 或 7d）。")

with tab2:
    st.subheader("我的多檔持股總覽與資產配置診斷")
    st.markdown("在此新增您名下的各個持股部位，App 將自動串接最新行情幫您計算總市值、總未實現損益，並提供全面診斷！")

    # 新增持股表單
    with st.form("add_holding_form"):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            new_sym = st.text_input("股票代號 (例如 2330.TW)", value="2330.TW")
        with col_f2:
            new_shares = st.number_input("持有股數", value=1000.0, step=100.0)
        with col_f3:
            new_cost = st.number_input("平均買價", value=500.0, step=0.5)
        
        submitted = st.form_submit_button("新增至我的持股清單")
        if submitted:
            st.session_state.portfolio.append({
                "symbol": new_sym.upper(),
                "shares": new_shares,
                "cost": new_cost
            })
            st.success(f"成功新增 {new_sym.upper()}！")

    # 顯示目前持股列表與總計
    if len(st.session_state.portfolio) > 0:
        st.markdown("### 目前持股明細")
        portfolio_data = []
        total_market_value = 0
        total_cost_value = 0

        for idx, item in enumerate(st.session_state.portfolio):
            sym = item['symbol']
            shs = item['shares']
            cst = item['cost']
            
            try:
                t_obj = yf.Ticker(sym)
                curr_p = t_obj.fast_info.get('last_price', None)
                if not curr_p:
                    t_df = t_obj.history(period="1d")
                    curr_p = float(t_df['Close'].iloc[-1])
            except:
                curr_p = cst

            m_val = curr_p * shs
            c_val = cst * shs
            pnl = m_val - c_val
            pnl_pct = ((curr_p - cst) / cst * 100) if cst > 0 else 0

            total_market_value += m_val
            total_cost_value += c_val

            portfolio_data.append({
                "代號": sym,
                "股數": shs,
                "平均成本": cst,
                "現價": round(curr_p, 2),
                "市值": round(m_val, 2),
                "未實現損益(元)": round(pnl, 2),
                "報酬率(%)": f"{pnl_pct:.2f}%"
            })

        pf_df = pd.DataFrame(portfolio_data)
        st.dataframe(pf_df, use_container_width=True)

        total_pnl = total_market_value - total_cost_value
        total_pnl_pct = (total_pnl / total_cost_value * 100) if total_cost_value > 0 else 0

        st.markdown("---")
        st.subheader("整體資產總結")
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            st.metric("總投資成本", f"{total_cost_value:,.2f} 元")
        with pc2:
            st.metric("目前總市值", f"{total_market_value:,.2f} 元")
        with pc3:
            st.metric("總未實現損益", f"{total_pnl:+,.2f} 元", delta=f"{total_pnl_pct:.2f}%", delta_color="normal" if total_pnl >= 0 else "inverse")

        if st.button("清空所有持股紀錄"):
            st.session_state.portfolio = []
            st.rerun()
    else:
        st.info("目前尚無持股紀錄，請透過上方表格新增您的股票部位。")