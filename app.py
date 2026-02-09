import streamlit as st
import google.generativeai as genai
import datetime
import pytz

st.set_page_config(page_title="Debug Mode")
JST = pytz.timezone('Asia/Tokyo')

st.title("🔧 接続診断モード")

if st.button("🚀 接続テスト実行"):
    try:
        # 1. Secretsの読み込みチェック
        key = st.secrets.get("GEMINI_API_KEY", "未設定")
        st.write(f"APIキー取得状況: {'✅ 取得成功' if key != '未設定' else '❌ 未設定'}")
        
        # 2. Google AI 設定
        genai.configure(api_key=key)
        
        # 3. モデル一覧を取得できるかテスト
        st.write("利用可能なモデルを探索中...")
        models = [m.name for m in genai.list_models()]
        st.write(f"利用可能モデル一覧: {models}")
        
        # 4. 実際に会話してみる
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("Hi")
        st.success(f"AIからの返答: {response.text}")
        
    except Exception as e:
        st.error("🚨 エラーが発生しました")
        st.code(str(e)) # ここに表示される詳細な英語が解決のヒントになります
        st.info("この上の黒い枠の中の文字を教えてください。")
