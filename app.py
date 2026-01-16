import streamlit as st
import google.generativeai as genai
import requests
import feedparser
import urllib.parse
import datetime

# --- アプリ基本設定 ---
st.set_page_config(page_title="FX AI-Analyst 2026", page_icon="📈", layout="centered")

# --- 安定稼働が確認できたモデル取得ロジック ---
def get_ai_model():
    if "GEMINI_API_KEY" not in st.secrets:
        st.error("SecretsにGEMINI_API_KEYが設定されていません。")
        return None, None
        
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    # あなたの環境で動作確認済みの2.5-flashを最優先に設定
    model_names = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-pro']
    
    for m_name in model_names:
        try:
            # モデルの存在確認を兼ねてインスタンス化
            m = genai.GenerativeModel(m_name)
            return m, m_name
        except:
            continue
    return None, None

# --- 最新ニュース取得エンジン (2026年仕様) ---
@st.cache_data(ttl=300)
def get_latest_forex_news():
    news_list = []
    # 2026年1月の最新情報を取得するための高度な検索クエリ
    # "when:1d" で24時間以内に限定、かつノイズを減らす
    search_query = 'USD JPY "forex" OR "円安" OR "円高" when:1d'
    encoded_query = urllib.parse.quote(search_query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    
    try:
        feed = feedparser.parse(rss_url)
        # 最新10件を取得
        for entry in feed.entries[:10]:
            # 日付情報をAIが認識しやすい形式で付与
            published_date = entry.get('published', '不明な日時')
            news_list.append(f"【公開日時: {published_date}】\nタイトル: {entry.title}")
    except Exception as e:
        st.error(f"ニュース取得中にエラーが発生しました: {e}")
        
    return news_list

# --- UI構築 ---
st.title("📈 ドル円 AI実戦司令塔")
st.subheader("2026 高市政権・実戦モード")
st.caption(f"現在の時刻: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

# メイン解析ボタン
if st.button("最新相場を1クリック解析", use_container_width=True, type="primary"):
    with st.spinner("2026年現在の最新情報を収集・解析中..."):
        model, model_name = get_ai_model()
        news_data = get_latest_forex_news()
        
        if model and news_data:
            # AIへのプロンプト：時間軸と前提条件を厳格に指定
            prompt = f"""
            あなたは2026年1月現在、第一線で活躍するプロのFXトレーダーです。
            以下の最新ニュース（直近24時間以内）に基づき、ドル円（USD/JPY）の分析を行ってください。

            【厳守すべき前提条件】
            1. 現在は「2026年1月」です。
            2. 高市氏は既に自民党総裁および内閣総理大臣に就任しており、政権を運営している「現職」です。
            3. 「総裁選の可能性」などの過去（2024年〜2025年）の古いニュースが混ざっている場合は、それを「完全に無視」し、現在の政権下での経済政策や日銀への影響のみを考慮してください。
            4. 非常に慎重な判断を行い、「だまし」の可能性がある場合はHOLDを推奨してください。

            【解析対象ニュース】
            {chr(10).join(news_data)}

            【出力形式】
            ■判定: [BUY/SELL/HOLD]
            ■信頼度: [0-100]%
            ■理由: (2026年の情勢に基づき簡潔に)
            ■テクニカル/ファンダの要点: 
            ■警戒すべき材料: 
            """
            
            try:
                response = model.generate_content(prompt)
                st.success(f"解析完了 (使用モデル: {model_name})")
                st.markdown("---")
                st.markdown(response.text)
                
                # 参考として取得した生データを表示（デバッグ用）
                with st.expander("取得した元ニュースを確認"):
                    for n in news_data:
                        st.write(n)
                        
            except Exception as e:
                st.error(f"AI解析エラー: {e}")
        else:
            st.error("解析に必要なデータ、またはAIモデルの準備ができませんでした。")

# --- サイドバー：資金管理 ---
with st.sidebar:
    st.header("資金管理設定")
    balance = st.number_input("運用残高(円)", value=1000000, step=10000)
    risk_rate = st.slider("1トレードの許容リスク(%)", 0.1, 5.0, 1.0, 0.1)
    
    st.divider()
    loss_amount = int(balance * (risk_rate / 100))
    st.metric("最大許容損失額", f"{loss_amount:,} 円")
    st.caption("この金額を超える含み損が出るロット数は持たないでください。")
