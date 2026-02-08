import streamlit as st
import google.generativeai as genai
import feedparser
import urllib.parse
import datetime
import pytz
import yfinance as ticker_data
import plotly.graph_objects as go
import pandas as pd

# --- 1. 基本設定 ---
st.set_page_config(page_title="FX AI-Analyst 2026", page_icon="💹", layout="wide")
JST = pytz.timezone('Asia/Tokyo')

# ブラウザを閉じない限り、予測結果を画面に残すためのメモリ
if 'history' not in st.session_state:
    st.session_state.history = []

# --- 2. 為替データとニュースの取得（キャッシュで負荷軽減） ---
@st.cache_data(ttl=900) # 15分間は再取得せず使い回す
def get_market_data():
    rate = 150.0 # 取得失敗時の予備
    df = pd.DataFrame()
    news = []
    
    # 為替データの取得
    try:
        fx = ticker_data.Ticker("JPY=X")
        df = fx.history(period="30d", interval="1d")
        if not df.empty:
            rate = round(df['Close'].iloc[-1], 3)
    except:
        pass

    # ニュースの取得
    try:
        query = urllib.parse.quote('USD JPY "ドル円" when:1d')
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(rss_url)
        news = [f"・{e.title}" for e in feed.entries[:5]]
    except:
        news = ["ニュースを取得できませんでした。"]
        
    return df, rate, news

df_history, current_rate, news_list = get_market_data()

# --- 3. UI（見た目）の構築 ---
st.title("💹 FX AI-Analyst (2026 Stable)")

c1, c2, c3 = st.columns(3)
c1.metric("USD/JPY", f"{current_rate}円")
c2.metric("時刻(JST)", datetime.datetime.now(JST).strftime('%H:%M'))
c3.metric("予測数", f"{len(st.session_state.history)}件")

# チャート表示
if not df_history.empty:
    fig = go.Figure(data=[go.Candlestick(
        x=df_history.index, open=df_history['Open'], 
        high=df_history['High'], low=df_history['Low'], close=df_history['Close']
    )])
    fig.update_layout(height=400, template="plotly_dark", margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- 4. AI予測実行エリア ---
col_l, col_r = st.columns([2, 1])

with col_l:
    if st.button("🚀 AIに24時間後の予測を命令する", use_container_width=True, type="primary"):
        with st.spinner("AI分析中... (無料枠のため時間がかかる場合があります)"):
            try:
                # API設定
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                
                # 【重要】404エラー対策：モデル名を最新の指定形式に
                # gemini-2.0-flash を試用
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                prompt = f"""
                あなたはFXのプロフェッショナルです。
                現在、ドル円は{current_rate}円です。
                最新ニュース:
                {" ".join(news_list)}
                
                上記を踏まえ、24時間後の予測を[BUY]（買い）、[SELL]（売り）、[HOLD]（様子見）のいずれかで判定し、その理由を初心者にも分かりやすく解説してください。
                必ず[BUY][SELL][HOLD]のいずれかの単語を文中に含めてください。
                """
                
                response = model.generate_content(prompt)
                res_text = response.text
                
                # 判定結果の抽出
                judgment = "HOLD"
                if "[BUY]" in res_text.upper(): judgment = "BUY"
                elif "[SELL]" in res_text.upper(): judgment = "SELL"
                
                # 履歴に追加
                st.session_state.history.append({
                    "time": datetime.datetime.now(JST),
                    "rate": current_rate,
                    "pred": judgment
                })
                
                st.subheader(f"🔮 AI判定: {judgment}")
                st.markdown(res_text)
                
            except Exception as e:
                # 429(制限)や404(名前間違い)への対策メッセージ
                error_msg = str(e)
                if "429" in error_msg:
                    st.error("AIの無料枠の回数制限に達しました。10分〜1時間ほど待ってから再度お試しください。")
                elif "404" in error_msg:
                    st.error("AIモデルの接続先が見つかりません。APIキーの設定を確認するか、しばらくお待ちください。")
                else:
                    st.error(f"接続エラーが発生しました。しばらく待ってリロードしてください。")
                st.caption(f"エラー詳細: {e}")

with col_r:
    st.subheader("📰 最新ニュース")
    for n in news_list:
        st.caption(n)
    
    if st.session_state.history:
        st.divider()
        st.subheader("📜 今回の履歴")
        for h in reversed(st.session_state.history):
            icon = "🔼" if h['pred'] == "BUY" else "🔽" if h['pred'] == "SELL" else "⏸"
            st.write(f"{icon} {h['time'].strftime('%H:%M')} | {h['pred']} ({h['rate']}円)")
