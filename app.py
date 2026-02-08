import streamlit as st
import google.generativeai as genai
import feedparser
import urllib.parse
import datetime
import pytz
import yfinance as ticker_data
import plotly.graph_objects as go
import pandas as pd

# 1. ページ基本設定
st.set_page_config(page_title="FX AI-Analyst 2026", layout="wide")
JST = pytz.timezone('Asia/Tokyo')

if 'history' not in st.session_state:
    st.session_state.history = []

# 2. 為替・ニュースデータ取得（負荷軽減のためキャッシュ化）
@st.cache_data(ttl=600)
def get_data():
    rate, df, news = 150.0, pd.DataFrame(), []
    try:
        fx = ticker_data.Ticker("JPY=X")
        df = fx.history(period="30d", interval="1d")
        if not df.empty: rate = round(df['Close'].iloc[-1], 3)
    except: pass
    try:
        query = urllib.parse.quote('USD JPY "ドル円" when:1d')
        rss = feedparser.parse(f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja")
        news = [f"・{e.title}" for e in rss.entries[:5]]
    except: news = ["ニュース取得制限中"]
    return df, rate, news

df_history, current_rate, news_list = get_data()

# 3. UI表示
st.title("💹 FX AI-Analyst (Final)")
st.metric("USD/JPY", f"{current_rate}円", delta_color="normal")

if not df_history.empty:
    fig = go.Figure(data=[go.Candlestick(x=df_history.index, open=df_history['Open'], high=df_history['High'], low=df_history['Low'], close=df_history['Close'])])
    fig.update_layout(height=400, template="plotly_dark", margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# 4. AI予測実行（エラー対策を最大化）
if st.button("🚀 AI予測を実行する", use_container_width=True, type="primary"):
    with st.spinner("AIが通信を試みています..."):
        try:
            # APIキーの設定確認
            api_key = st.secrets["GEMINI_API_KEY"]
            if not api_key or "YOUR_" in api_key:
                st.error("APIキーが正しく設定されていません。StreamlitのSecretsを確認してください。")
            else:
                genai.configure(api_key=api_key)
                
                # 最も汎用性の高いモデル名から順に試行
                success = False
                for m_name in ['gemini-1.5-flash', 'gemini-1.5-pro']:
                    try:
                        model = genai.GenerativeModel('gemini-1.5-flash-8b') # 最も軽量で制限が緩いモデル
                        response = model.generate_content(f"ドル円{current_rate}円。24時間後を[BUY/SELL/HOLD]で判定し、日本語で理由を述べて。")
                        res_text = response.text
                        success = True
                        break
                    except:
                        continue
                
                if success:
                    judgment = "BUY" if "[BUY]" in res_text.upper() else "SELL" if "[SELL]" in res_text.upper() else "HOLD"
                    st.session_state.history.append({"time": datetime.datetime.now(JST), "rate": current_rate, "pred": judgment})
                    st.subheader(f"🔮 AI判定: {judgment}")
                    st.markdown(res_text)
                else:
                    st.error("Google AI Studio側でアクセスが拒否されました。新しいAPIキーを試すか、数時間待機が必要です。")
        except Exception as e:
            st.error(f"システムエラー: {e}")

# 5. 履歴表示
if st.session_state.history:
    st.divider()
    for h in reversed(st.session_state.history):
        st.write(f"【{h['time'].strftime('%H:%M')}】 {h['pred']} ({h['rate']}円)")
