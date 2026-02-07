import streamlit as st
import google.generativeai as genai
import feedparser
import urllib.parse
import datetime
import pytz
import yfinance as ticker_data
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="FX AI-Analyst Stable", page_icon="💹", layout="wide")
JST = pytz.timezone('Asia/Tokyo')

if 'history' not in st.session_state:
    st.session_state.history = []

# --- 1. 市場データ取得（30分キャッシュで制限回避） ---
@st.cache_data(ttl=1800)
def fetch_safe_data():
    current_rate = 150.0
    df_d = pd.DataFrame()
    try:
        # 取得間隔を広げて負荷を軽減
        fx = ticker_data.Ticker("JPY=X")
        df_d = fx.history(period="30d", interval="1d")
        if not df_d.empty:
            current_rate = round(df_d['Close'].iloc[-1], 3)
    except:
        pass 
    return df_d, current_rate

# --- 2. ニュース取得 ---
@st.cache_data(ttl=1800)
def fetch_safe_news():
    try:
        query = urllib.parse.quote('USD JPY "ドル円" when:1d')
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(rss_url)
        return [f"・{e.title}" for e in feed.entries[:5]]
    except:
        return ["ニュースは現在取得できません。"]

# データの実行
df_d, current_rate = fetch_safe_data()
news_list = fetch_safe_news()

st.title("💹 FX AI-Analyst (安定版)")

c1, c2 = st.columns(2)
c1.metric("USD/JPY", f"{current_rate}円")
c2.metric("JST時刻", datetime.datetime.now(JST).strftime('%H:%M'))

if not df_d.empty:
    fig = go.Figure(data=[go.Candlestick(x=df_d.index, open=df_d['Open'], high=df_d['High'], low=df_d['Low'], close=df_d['Close'])])
    fig.update_layout(height=400, template="plotly_dark", margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

if st.button("🚀 AI予測を実行する", use_container_width=True, type="primary"):
    with st.spinner("AIが情勢を分析中..."):
        try:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            
            # モデル名の指定を最も確実なものに変更
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"現在のドル円は{current_rate}円です。最新ニュース:\n" + "\n".join(news_list) + "\n\n上記を踏まえ、24時間後の予測を[BUY/SELL/HOLD]のいずれかで答え、理由も簡潔に述べてください。"
            
            response = model.generate_content(prompt)
            res_text = response.text
            
            # 判定の抽出
            judgment = "HOLD"
            if "[BUY]" in res_text.upper(): judgment = "BUY"
            elif "[SELL]" in res_text.upper(): judgment = "SELL"
            
            st.session_state.history.append({
                "time": datetime.datetime.now(JST),
                "rate": current_rate,
                "pred": judgment
            })
            
            st.subheader(f"🔮 AI判定: {judgment}")
            st.markdown(res_text)
            
        except Exception as e:
            # 具体的な解決策を表示
            if "429" in str(e):
                st.error("AIの無料枠上限に達しました。1時間ほど待ってから再度お試しください。")
            elif "404" in str(e):
                st.error("AIモデルの接続エラーです。コード内のモデル名を修正する必要があります。")
            else:
                st.error(f"エラーが発生しました: {e}")

# 履歴表示
if st.session_state.history:
    st.subheader("📜 今回の予測ログ")
    for h in reversed(st.session_state.history):
        st.write(f"{h['time'].strftime('%H:%M')} | {h['pred']} ({h['rate']}円)")
