import streamlit as st
import google.generativeai as genai
import feedparser
import urllib.parse
import datetime
import pytz
import yfinance as ticker_data
import plotly.graph_objects as go
import pandas as pd

# --- 1. アプリ基本設定 ---
st.set_page_config(page_title="FX AI-Analyst 2026", layout="wide")
JST = pytz.timezone('Asia/Tokyo')

# ブラウザ上での履歴保持
if 'history' not in st.session_state:
    st.session_state.history = []

# --- 2. データ取得（キャッシュで負荷軽減） ---
@st.cache_data(ttl=600)
def get_market_data():
    rate, df, news = 150.0, pd.DataFrame(), []
    try:
        # 為替取得
        fx = ticker_data.Ticker("JPY=X")
        df = fx.history(period="30d", interval="1d")
        if not df.empty:
            rate = round(df['Close'].iloc[-1], 3)
    except:
        pass
    try:
        # ニュース取得
        query = urllib.parse.quote('USD JPY "ドル円" when:1d')
        rss = feedparser.parse(f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja")
        news = [f"・{e.title}" for e in rss.entries[:5]]
    except:
        news = ["ニュースを取得できませんでした。"]
    return df, rate, news

df_history, current_rate, news_list = get_market_data()

# --- 3. メイン画面の構築 ---
st.title("💹 FX AI-Analyst (2026 Stable Ver.)")
st.metric("USD/JPY", f"{current_rate}円")

# チャート表示
if not df_history.empty:
    fig = go.Figure(data=[go.Candlestick(
        x=df_history.index, open=df_history['Open'], 
        high=df_history['High'], low=df_history['Low'], close=df_history['Close']
    )])
    fig.update_layout(height=400, template="plotly_dark", margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- 4. 予測実行ロジック ---
if st.button("🚀 AI予測を実行する", use_container_width=True, type="primary"):
    with st.spinner("AIと通信中..."):
        try:
            # SecretsからAPIキー取得
            api_key = st.secrets["GEMINI_API_KEY"]
            if not api_key:
                st.error("APIキーがSecretsに設定されていません。")
            else:
                genai.configure(api_key=api_key)
                
                # 最も確実に動くモデル名を固定で指定
                # モデル名の前後に 'models/' をつけない形式が現在の主流です
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # プロンプト（指示文）
                prompt = f"""
                現在のドル円レートは {current_rate}円です。
                最新ニュース: {" ".join(news_list)}
                24時間後の予測を[BUY/SELL/HOLD]のいずれかで判定し、その理由を日本語で簡潔に述べてください。
                """
                
                # AIにリクエスト
                response = model.generate_content(prompt)
                
                if response and response.text:
                    res_text = response.text
                    # 判定の抽出
                    judgment = "HOLD"
                    if "[BUY]" in res_text.upper(): judgment = "BUY"
                    elif "[SELL]" in res_text.upper(): judgment = "SELL"
                    
                    # 履歴保存
                    st.session_state.history.append({
                        "time": datetime.datetime.now(JST),
                        "rate": current_rate,
                        "pred": judgment
                    })
                    
                    st.subheader(f"🔮 AI判定: {judgment}")
                    st.markdown(res_text)
                else:
                    st.error("AIから有効な回答が得られませんでした。APIの設定を確認してください。")
                    
        except Exception as e:
            # エラーの詳細をわかりやすく表示
            error_msg = str(e)
            if "403" in error_msg:
                st.error("アクセス拒否(403): APIキーが無効か、Google CloudでAPIが有効化されていません。")
            elif "404" in error_msg:
                st.error("モデル未検出(404): 指定したモデル名が見つかりません。")
            elif "429" in error_msg:
                st.error("回数制限(429): 無料枠の上限です。数分待ってください。")
            else:
                st.error(f"接続エラーが発生しました: {e}")

# --- 5. 履歴表示 ---
if st.session_state.history:
    st.divider()
    st.subheader("📜 予測ログ")
    for h in reversed(st.session_state.history):
        st.write(f"【{h['time'].strftime('%H:%M')}】 {h['pred']} ({h['rate']}円)")
