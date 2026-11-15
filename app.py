import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.title("📈 智慧股票分析與期望值計算 App")

st.sidebar.header("設定參數")
stock_symbol = st.sidebar.text_input("輸入股票代號", value="2330.TW")
period = st.sidebar.selectbox("選擇時間範圍", ["1y", "2y", "5y", "10y"], index=1)

@st.cache_data
def load_data(symbol, time_period):
    df = yf.download(symbol, period=time_period)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

data = load_data(stock_symbol, period)

if not data.empty:
    st.subheader(f"{stock_symbol.upper()} 均線策略與歷史交易回測")
    
    # 1. 計算技術指標 (5日線與20日線)
    data['SMA_5'] = data['Close'].rolling(window=5).mean()
    data['SMA_20'] = data['Close'].rolling(window=20).mean()
    
    # 2. 定義進出場訊號
    data['Position'] = np.where(data['SMA_5'] > data['SMA_20'], 1, 0)
    data['Signal'] = data['Position'].diff()  # 1 為買進，-1 為賣出
    
    buy_signals = data[data['Signal'] == 1]
    sell_signals = data[data['Signal'] == -1]
    
    # 3. 逐筆交易分析與期望值計算
    trades = []
    in_trade = False
    entry_price = 0
    
    for date, row in data.iterrows():
        if row['Signal'] == 1 and not in_trade:
            entry_price = row['Close']
            in_trade = True
        elif row['Signal'] == -1 and in_trade:
            exit_price = row['Close']
            trade_return = (exit_price - entry_price) / entry_price
            trades.append(trade_return)
            in_trade = False
            
    # 如果最後一筆還在持股中，用最新價格計算未實現交易
    if in_trade:
        exit_price = data['Close'].iloc[-1]
        trade_return = (exit_price - entry_price) / entry_price
        trades.append(trade_return)
        
    trades_df = pd.Series(trades) if len(trades) > 0 else pd.Series()
    
    if not trades_df.empty:
        winning_trades = trades_df[trades_df > 0]
        losing_trades = trades_df[trades_df < 0]
        
        total_trades = len(trades_df)
        win_rate = len(winning_trades) / total_trades
        loss_rate = 1 - win_rate
        
        avg_win = winning_trades.mean() if len(winning_trades) > 0 else 0
        avg_loss = abs(losing_trades.mean()) if len(losing_trades) > 0 else 0
        
        # 計算數學期望值 (每筆交易平均報酬率期望值)
        expected_value = (win_rate * avg_win) - (loss_rate * avg_loss)
    else:
        total_trades, win_rate, avg_win, avg_loss, expected_value = 0, 0, 0, 0, 0

    # 4. 繪製圖表
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=data['Close'], name='收盤價', line=dict(color='lightgray', width=1.5)))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA_5'], name='5日短期線', line=dict(color='orange', width=1.5)))
    fig.add_trace(go.Scatter(x=data.index, y=data['SMA_20'], name='20日月線', line=dict(color='blue', width=1.5)))
    
    fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['Close'], mode='markers', name='買進點', marker=dict(symbol='triangle-up', size=12, color='green')))
    fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals['Close'], mode='markers', name='賣出點', marker=dict(symbol='triangle-down', size=12, color='red')))
    
    fig.update_layout(title=f"{stock_symbol} 買賣點與歷史交易分佈", xaxis_title="日期", yaxis_title="價格")
    st.plotly_chart(fig, use_container_width=True)
    
    # 5. 顯示期望值與統計看板
    st.subheader("🎯 交易期望值與統計指標（基於歷史回測）")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("歷史總交易次數", f"{total_trades} 次")
    with col2:
        st.metric("勝率 (Win Rate)", f"{win_rate * 100:.2f}%")
    with col3:
        st.metric("平均賺賠比", f"賺 {avg_win*100:.2f}% / 賠 {avg_loss*100:.2f}%")
    with col4:
        st.metric("每筆交易期望值 (EV)", f"{expected_value * 100:.2f}%", 
                  delta="優勢向上" if expected_value > 0 else "劣勢向下")
        
    # 當下狀態判斷
    latest_sma5 = data['SMA_5'].iloc[-1]
    latest_sma20 = data['SMA_20'].iloc[-1]
    
    st.subheader("🤖 當下進出場狀態評估")
    if latest_sma5 > latest_sma20:
        st.success("🔥 **【當下狀態：多頭持倉中 / 具備進場優勢】**\n目前短均線大於長均線。若依據此歷史策略，過去在這種狀態下的平均期望報酬如上所示。")
    else:
        st.warning("⚠️ **【當下狀態：空頭觀望中 / 訊號偏保守】**\n目前短均線低於長均線，歷史統計顯示此時進場的勝率或期望值相對較低，建議等待黃金交叉。")

else:
    st.error("找不到該股票代號，請確認代號是否正確（台股請加 .TW，例如 2330.TW）。")
