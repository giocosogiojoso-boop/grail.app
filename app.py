import streamlit as st
from streamlit_gsheets import GSheetsConnection
import google.generativeai as genai
import feedparser
import urllib.parse
import datetime
import pytz
import yfinance as ticker_data
import plotly.graph_objects as go
import pandas as pd

# --- アプリ基本設定 ---
st.set_page_config(page_title="FX AI-Analyst Cloud Pro", page_icon="💹", layout="wide")
JST = pytz.timezone('Asia/Tokyo')

# --- 1. スプレッドシート接続設定 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_history():
    # スプレッドシートからデータを読み込む
    try:
        return conn.read(worksheet="Sheet1", ttl="0") # キャッシュを無効にして最新を取得
    except:
        return pd.DataFrame(columns=['time', 'rate', 'pred', 'status', 'final_rate'])

def update_sheet(df):
    # スプレッドシートを更新
    conn.update(worksheet="Sheet1", data=df)

# --- 2. 市場データ & ニュース取得 ---
@st.cache_data(ttl=300)
def fetch_market_info():
    fx = ticker_data.Ticker("JPY=X")
    df_d = fx.history(period="60d", interval="1d")
    df_h = fx.history(period="5d", interval="1h")
    
    try:
        tnx = ticker_data.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
        vix = ticker_data.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
    except:
        tnx, vix = 0.0, 0.0

    # テクニカル指標
    df_d['SMA20'] = df_d['Close'].rolling(window=20).mean()
    delta = df_d['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df_d['RSI'] = 100 - (100 / (1 + (gain / loss)))

    # ニュース取得
    query = urllib.parse.quote('USD JPY "ドル円" when:1d')
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    feed = feedparser.parse(rss_url)
    news = [f"・{e.title}" for e in feed.entries[:8]]
    
    return df_d, df_h, round(tnx, 3), round(vix, 2), news

# --- 3. 自動的中判定ロジック ---
def process_auto_judgment(df_history, current_price):
    now = datetime.datetime.now(JST)
    updated = False
    
    for index, row in df_history.iterrows():
        # statusが 'Pending' かつ 24時間(86400秒)経過している場合
        # time列は文字列で保存されるためパース
        predict_time = pd.to_datetime(row['time']).tz_localize(JST) if pd.to_datetime(row['time']).tzinfo is None else pd.to_datetime(row['time'])
        
        if row['status'] == 'Pending' and (now - predict_time).total_seconds() >= 86400:
            is_win = False
            rate_at_predict = float(row['rate'])
            if row['pred'] == "BUY" and current_price > rate_at_predict: is_win = True
            elif row['pred'] == "SELL" and current_price < rate_at_predict: is_win = True
            elif row['pred'] == "HOLD" and abs(current_price - rate_at_predict) < 0.15: is_win = True
            
            df_history.at[index, 'status'] = 'Win' if is_win else 'Loss'
            df_history.at[index, 'final_rate'] = current_price
            updated = True
            
    if updated:
        update_sheet(df_history)
        st.toast("24時間経過した予測を自動判定しました！")
    return df_history

# --- メイン処理 ---
df_d, df_h, us10y, vix, news_list = fetch_market_info()
current_rate = round(df_d['Close'].iloc[-1], 3)

# スプレッドシートから履歴読み込み & 判定
history_df = get_history()
history_df = process_auto_judgment(history_df, current_rate)

# 的中率計算
total_checked = len(history_df[history_df['status'].isin(['Win', 'Loss'])])
wins = len(history_df[history_df['status'] == 'Win'])
win_rate = (wins / total_checked * 100) if total_checked > 0 else 0

# --- UI構築 ---
st.title("💹 ドル円 AI実戦司令塔 Cloud Pro")

cols = st.columns(5)
cols[0].metric("USD/JPY", f"{current_rate}円")
cols[1].metric("米10年債利回り", f"{us10y}%")
cols[2].metric("VIX(恐怖指数)", vix)
cols[3].metric("AI的中率(累計)", f"{win_rate:.1f}%", f"判定済:{total_checked}件")
cols[4].metric("JST時刻", datetime.datetime.now(JST).strftime('%H:%M'))

# チャート
cl, cr = st.columns(2)
def draw_chart(df):
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.update_layout(height=300, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False, template="plotly_dark")
    return fig
cl.plotly_chart(draw_chart(df_d), use_container_width=True)
cr.plotly_chart(draw_chart(df_h), use_container_width=True)

st.divider()

col_main, col_sub = st.columns([2, 1])

with col_main:
    if st.button("🚀 ニュースを分析して予測を実行（シートに保存）", use_container_width=True, type="primary"):
        with st.spinner("AIが最新情勢をスキャン中..."):
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            prompt = f"現在は2026年1月、ドル円={current_rate}円。以下のニュースと市場データから24時間後の[BUY/SELL/HOLD]を判定せよ。\n\n【ニュース】\n" + "\n".join(news_list)
            response = model.generate_content(prompt)
            res_text = response.text
            judgment = "BUY" if "[BUY]" in res_text.upper() else "SELL" if "[SELL]" in res_text.upper() else "HOLD"
            
            # 新しい予測をスプレッドシートに追記
            new_entry = {
                "time": datetime.datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S'),
                "rate": current_rate,
                "pred": judgment,
                "status": "Pending",
                "final_rate": ""
            }
            # DataFrameを更新して保存
            updated_history = pd.concat([history_df, pd.DataFrame([new_entry])], ignore_index=True)
            update_sheet(updated_history)
            
            st.subheader(f"🔮 AI判定: {judgment}")
            st.markdown(res_text)

with col_sub:
    st.subheader("📰 最新ニュース")
    for n in news_list[:5]: st.caption(n)
    
    st.divider()
    st.subheader("📜 累計予測ログ")
    # スプレッドシートのデータを表示
    display_df = history_df.sort_values(by='time', ascending=False).head(10)
    for _, row in display_df.iterrows():
        icon = "⏳" if row['status'] == 'Pending' else "✅" if row['status'] == 'Win' else "❌"
        st.write(f"{icon} {row['time'][5:16]} | {row['pred']} ({row['status']})")
