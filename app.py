import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# 設定網頁標題與寬度
st.set_page_config(page_title="ProTrader 專業級智慧資產管理平台", layout="wide", initial_sidebar_state="expanded")

# ==================== 自訂現代化高質感 CSS 樣式 ====================
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 18px 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 10px;
    }
    h1, h2, h3 {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        letter-spacing: -0.5px;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚡ ProTrader 專業級量化資產管理與自動看盤平台")
st.markdown("<p style='color: #8b949e; margin-top: -10px;'>具備自動定時更新行情、逢低佈局判定、分批加碼試算與台股精準稅費校正的智慧投資儀表板</p>", unsafe_allow_html=True)

# ==================== 初始化 Session State ====================
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["0050.TW", "2330.TW", "2317.TW", "009816.TW"]

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

if 'batches' not in st.session_state:
    st.session_state.batches = []

# ==================== 側邊欄設定 ====================
st.sidebar.header("🎛️ 參數與導航控制台")

# 【全新】自動更新開關與頻率設定
st.sidebar.subheader("🔄 即時行情自動更新設定")
auto_refresh = st.sidebar.checkbox("啟用背景自動更新行情", value=False, help="勾選後，頁面將會依照設定的秒數自動重新整理抓取最新股價")
refresh_interval = st.sidebar.slider("更新頻率 (秒)", 10, 300, 30, 10, help="建議設定在 30 秒以上，避免頻繁請求被 Yahoo 阻擋")

if auto_refresh:
    # 利用 Streamlit 內建的 rerun 機制實作安全自動更新
    time.sleep(refresh_interval)
    st.rerun()

if st.sidebar.button("🔄 立即手動重新整理", use_container_width=True):
    st.cache_data.clear()
    st.success("已清除快取並更新最新行情！")
    st.rerun()

st.sidebar.markdown("---")

selected_fav = st.sidebar.selectbox("⭐ 快速載入收藏股票", ["-- 選擇收藏股票 --"] + st.session_state.watchlist)
default_symbol = selected_fav if selected_fav != "-- 選擇收藏股票 --" else "0050.TW"
stock_symbol = st.sidebar.text_input("📝 輸入或修改股票代號 (台股加 .TW)", value=default_symbol)

col_fav1, col_fav2 = st.sidebar.columns(2)
with col_fav1:
    if st.button("➕ 加入收藏", use_container_width=True):
        if stock_symbol.upper() not in st.session_state.watchlist:
            st.session_state.watchlist.append(stock_symbol.upper())
            st.success("已加入！")
with col_fav2:
    if st.button("🗑️ 移除收藏", use_container_width=True):
        if stock_symbol.upper() in st.session_state.watchlist:
            st.session_state.watchlist.remove(stock_symbol.upper())
            st.warning("已移除。")

st.sidebar.markdown("---")
benchmark_symbol = st.sidebar.text_input("📈 大盤對標代號", value="^TWII")
period = st.sidebar.selectbox("⏳ 選擇回測時間範圍", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=1)

st.sidebar.subheader("💰 交易成本與券商設定")
include_fees = st.sidebar.checkbox("自動扣除買賣手續費及證交稅", value=True, help="ETF享0.1%優惠稅率，一般股票0.3%")

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

selected_broker = st.sidebar.selectbox("🏦 選擇您的交割券商", list(broker_options.keys()))

if selected_broker == "自訂手續費折扣":
    broker_discount = st.sidebar.slider("自訂電子手續費折扣 (折)", 1.0, 10.0, 2.8, 0.1)
else:
    broker_discount = broker_options[selected_broker]
    st.sidebar.caption(f"✨ 已套用 {selected_broker} 常用折扣：**{broker_discount} 折**")

st.sidebar.subheader("🛑 風控與停損停利")
enable_sl = st.sidebar.checkbox("啟用停損機制 (Stop-Loss)", value=True)
sl_pct = st.sidebar.slider("停損跌幅 (%)", 1.0, 20.0, 5.0, 0.5)

enable_tp = st.sidebar.checkbox("啟用停利機制 (Take-Profit)", value=True)
tp_pct = st.sidebar.slider("停利漲幅 (%)", 2.0, 50.0, 15.0, 0.5)

st.sidebar.subheader("🎯 當前個股持倉與現價校正")
user_cost = st.sidebar.number_input("平均買價 (無持倉填0)", value=0.0, step=0.1)
user_shares = st.sidebar.number_input("持有股數 (無持倉填0)", value=0.0, step=100.0)
user_manual_price = st.sidebar.number_input("手動覆蓋現價 (填0則自動抓行情)", value=0.0, step=0.01, help="可輸入券商 App 當下現價以完美對齊！")

# ==================== 資料載入函數 ====================
@st.cache_data(ttl=60)  # 快取有效時間設定為 60 秒，確保自動更新能抓到最新行情
def load_stock_data(symbol, time_period):
    try:
        df = yf.download(symbol, period=time_period)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        st.error(f"下載股票資料發生錯誤: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
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
tab1, tab2, tab3 = st.tabs([
    "📊 個股深度分析與逢低佈局", 
    "📋 我的多檔持股總覽與資產診斷", 
    "🧮 定期定額與分批加碼試算器"
])

with tab1:
    if not data.empty and len(data) > 0:
        st.markdown(f"### 📈 `{stock_symbol.upper()}` 技術走勢與逢低訊號")

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

        recent_low = data['Close'].min()
        recent_high = data['Close'].max()
        current_close = float(data['Close'].iloc[-1])
        latest_rsi = float(data['RSI'].iloc[-1])

        is_near_low = (current_close <= recent_low * 1.03) or (latest_rsi < 35)

        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.03, 
                            row_heights=[0.6, 0.2, 0.2],
                            subplot_titles=("價格、均線、布林通道與支撐區", "成交量 (Volume)", "RSI 強弱指標"))
        
        fig.add_trace(go.Scatter(x=data.index, y=data['Close'], name='收盤價', line=dict(color='#58a6ff', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA_5'], name='短期均線 (5MA)', line=dict(color='#ffa657', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA_20'], name='長期均線 (20MA)', line=dict(color='#1f6feb', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['BB_Upper'], name='布林上軌', line=dict(color='rgba(88,166,255,0.2)', dash='dash')), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['BB_Lower'], name='布林下軌', line=dict(color='rgba(88,166,255,0.2)', dash='dash'), fill='tonexty'), row=1, col=1)
        
        if not bench_data.empty and len(bench_data) > 0:
            bench_close = bench_data['Close'] / bench_data['Close'].iloc[0] * data['Close'].iloc[0]
            fig.add_trace(go.Scatter(x=bench_data.index, y=bench_close, name=f'大盤基準 ({benchmark_symbol})', line=dict(color='#8b949e', dash='dot')), row=1, col=1)

        colors = ['#da3633' if row['Close'] < row['Open'] else '#2ea043' for index, row in data.iterrows()]
        fig.add_trace(go.Bar(x=data.index, y=data['Volume'], name='成交量', marker_color=colors), row=2, col=1)
        
        fig.add_trace(go.Scatter(x=data.index, y=data['RSI'], name='RSI', line=dict(color='#bc8cff', width=1)), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="#da3633", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#2ea043", row=3, col=1)

        fig.update_layout(
            height=750,
            template="plotly_dark",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#161b22",
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        # 個人持倉績效與風控評估
        st.markdown("---")
        st.markdown(f"### 🛡️ `{stock_symbol.upper()}` 個人持倉與風險管理")

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
                st.metric(f"未實現損益{label_suffix}", f"{pnl_amount:+,.0f} 元", delta=f"{my_return:.2f}%", delta_color="normal" if pnl_amount >= 0 else "inverse")
            with mc3:
                st.metric(f"依成本停損價 (-{sl_pct}%)", f"{my_sl_price:.2f}")
            with mc4:
                st.metric(f"依成本停利價 (+{tp_pct}%)", f"{my_tp_price:.2f}")
            
            if effective_close <= my_sl_price:
                st.error(f"🚨 **【停損警示】** 目前參考價 ({effective_close:.2f}) 已觸及或跌破停損價 ({my_sl_price:.2f})！建議果斷執行紀律出場。")
            elif effective_close >= my_tp_price:
                st.success(f"🎯 **【停利警示】** 目前參考價 ({effective_close:.2f}) 已達到停利目標 ({my_tp_price:.2f})！建議考慮獲利了結。")
            else:
                buffer_amt = effective_close - my_sl_price
                st.info(f"🛡️ **【持倉安全】** 目前營運正常，距離停損價尚有 {buffer_amt:.2f} 元緩衝空間。")
        else:
            st.markdown("""
                <div style='background-color: #161b22; border: 1px dashed #30363d; padding: 15px; border-radius: 8px; color: #8b949e; text-align: center;'>
                    💡 提示：若您目前持有這檔股票，請在左側側邊欄輸入您的<strong>「平均買價」</strong>與<strong>「持有股數」</strong>，系統將即時為您計算含手續費與稅費的精準損益！
                </div>
            """, unsafe_allow_html=True)

        with st.expander("🔍 點擊展開：詳細歷史價格與變動明細表"):
            detail_df = data[['Open', 'High', 'Low', 'Close', 'Volume']].tail(30).copy()
            detail_df['價格變動(元)'] = detail_df['Close'].diff()
            detail_df['漲跌幅(%)'] = detail_df['Close'].pct_change() * 100
            detail_df = detail_df.sort_index(ascending=False)
            st.dataframe(detail_df.style.format({
                'Open': '{:.2f}', 'High': '{:.2f}', 'Low': '{:.2f}', 'Close': '{:.2f}',
                'Volume': '{:,.0f}', '價格變動(元)': '{:+.2f}', '漲跌幅(%)': '{:+.2f}%'
            }), use_container_width=True)

        st.markdown("---")
        st.markdown("### 🤖 逢低佈局與進場點判定指引")
        
        if is_near_low:
            box_func = st.success
            action_title = "🔥 接近近期低點 / 適合逢低佈局進場"
            action_desc = f"目前收盤價 ({current_close:.2f}) 已接近本區間之近期低點 ({recent_low:.2f}) 或 RSI 進入超賣區 (RSI: {latest_rsi:.1f})。符合您尋找低點、適合分批承接的進場時機！"
        else:
            if latest_rsi > 70:
                box_func = st.warning
                action_title = "⚠️ 短線乖離過大 / 暫時不宜追高"
                action_desc = f"目前 RSI 已來到 {latest_rsi:.1f} 的超買區，股價距離近期低點較遠，建議等待拉回再找買點。"
            else:
                box_func = st.info
                action_title = "👀 價格震盪整理中 / 可採取分批小額試單"
                action_desc = f"目前股價處於中段震盪區間（近期低點: {recent_low:.2f} ~ 近期高點: {recent_high:.2f}），若想進場可考慮分批佈局，不需一次重壓。"

        box_func(f"#### {action_title}\n{action_desc}")
    else:
        st.error("找不到該股票代號的歷史資料，請確認代號是否正確（台股請加 .TW，例如 0050.TW）。")

with tab2:
    st.markdown("### 📋 多檔持股總覽與資產配置診斷")
    st.markdown("在此新增您名下的各個持股部位，App 將自動套用您所選券商的折扣與稅費，計算真實淨市值與未實現損益！")

    with st.form("add_holding_form"):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            new_sym = st.text_input("股票代號 (例如 2330.TW)", value="2330.TW")
        with col_f2:
            new_shares = st.number_input("持有股數", value=1000.0, step=100.0)
        with col_f3:
            new_cost = st.number_input("平均買價", value=500.0, step=0.5)
        
        submitted = st.form_submit_button("➕ 新增至我的持股清單", use_container_width=True)
        if submitted:
            st.session_state.portfolio.append({
                "symbol": new_sym.upper(),
                "shares": new_shares,
                "cost": new_cost
            })
            st.success(f"成功新增 {new_sym.upper()}！")

    if len(st.session_state.portfolio) > 0:
        st.markdown("#### 目前持股明細")
        portfolio_data = []
        total_market_value = 0
        total_cost_value = 0

        for idx, item in enumerate(st.session_state.portfolio):
            sym = item['symbol']
            shs = item['shares']
            cst = item['cost']
            
            try:
                t_df = load_stock_data(sym, "1mo")
                curr_p = float(t_df['Close'].iloc[-1]) if not t_df.empty else cst
            except:
                curr_p = cst

            b_val = cst * shs
            s_val = curr_p * shs
            is_etf = sym.strip().upper().startswith("0")
            tax_r = 0.001 if is_etf else 0.003

            if include_fees:
                b_fee = max(20.0, b_val * 0.001425 * (broker_discount / 10.0))
                s_fee = max(20.0, s_val * 0.001425 * (broker_discount / 10.0))
                s_tax = s_val * tax_r
                item_cost = b_val + b_fee
                item_net_val = s_val - s_fee - s_tax
                pnl = item_net_val - item_cost
                pnl_pct = (pnl / item_cost * 100) if item_cost > 0 else 0
            else:
                item_cost = b_val
                item_net_val = s_val
                pnl = s_val - b_val
                pnl_pct = ((curr_p - cst) / cst * 100) if cst > 0 else 0

            total_market_value += item_net_val
            total_cost_value += item_cost

            portfolio_data.append({
                "代號": sym,
                "股數": shs,
                "平均成本": cst,
                "現價": round(curr_p, 2),
                "含稅淨市值(元)": round(item_net_val, 2),
                "未實現損益(元)": round(pnl, 2),
                "報酬率(%)": f"{pnl_pct:.2f}%"
            })

        pf_df = pd.DataFrame(portfolio_data)
        st.dataframe(pf_df, use_container_width=True)

        total_pnl = total_market_value - total_cost_value
        total_pnl_pct = (total_pnl / total_cost_value * 100) if total_cost_value > 0 else 0

        st.markdown("---")
        st.markdown("### 💰 整體資產總結 (含交易成本)")
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            st.metric("總投資成本 (含買進手續費)", f"{total_cost_value:,.2f} 元")
        with pc2:
            st.metric("目前總淨市值 (扣除賣出費稅)", f"{total_market_value:,.2f} 元")
        with pc3:
            st.metric("總未實現損益", f"{total_pnl:+,.2f} 元", delta=f"{total_pnl_pct:.2f}%", delta_color="normal" if total_pnl >= 0 else "inverse")

        if st.button("🗑️ 清空所有持股紀錄"):
            st.session_state.portfolio = []
            st.rerun()
    else:
        st.info("目前尚無持股紀錄，請透過上方表格新增您的股票部位。")

with tab3:
    st.markdown("### 🧮 定期定額與分批加碼成本試算器")
    st.markdown("如果您是分批買進（例如每個月買一次 0050 或 009816），可以在此新增每一筆的買進價格與股數，系統會自動幫您算出**加權平均成本**與含手續費的總投組狀態！")

    with st.form("batch_form"):
        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            batch_date_label = st.text_input("批次標籤/日期", value="第 1 批 (2026/11)")
        with bc2:
            batch_price = st.number_input("買進價格", value=100.0, step=0.1)
        with bc3:
            batch_shares = st.number_input("買進股數", value=1000.0, step=100.0)
        
        add_batch_btn = st.form_submit_button("➕ 新增這筆加碼紀錄", use_container_width=True)
        if add_batch_btn:
            st.session_state.batches.append({
                "label": batch_date_label,
                "price": batch_price,
                "shares": batch_shares
            })
            st.success(f"成功新增 {batch_date_label}！")

    if len(st.session_state.batches) > 0:
        st.markdown("#### 📜 分批買進紀錄明細")
        batch_df = pd.DataFrame(st.session_state.batches)
        st.dataframe(batch_df, use_container_width=True)

        total_batch_shares = sum(b['shares'] for b in st.session_state.batches)
        total_batch_raw_cost = sum(b['price'] * b['shares'] for b in st.session_state.batches)
        weighted_avg_cost = total_batch_raw_cost / total_batch_shares if total_batch_shares > 0 else 0
        
        total_buy_fee = sum(max(20.0, (b['price'] * b['shares']) * 0.001425 * (broker_discount / 10.0)) for b in st.session_state.batches)
        grand_total_cost = total_batch_raw_cost + total_buy_fee

        bc_res1, bc_res2, bc_res3 = st.columns(3)
        with bc_res1:
            st.metric("累計總持有股數", f"{total_batch_shares:,.0f} 股")
        with bc_res2:
            st.metric("加權平均買價", f"{weighted_avg_cost:.2f} 元")
        with bc_res3:
            st.metric("含手續費總投入成本", f"{grand_total_cost:,.2f} 元")

        if st.button("🗑️ 清空所有加碼紀錄"):
            st.session_state.batches = []
            st.rerun()
    else:
        st.info("目前尚無分批加碼紀錄，請透過上方表格新增您的分批買進明細。")