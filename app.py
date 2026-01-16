import streamlit as st
import google.generativeai as genai

st.title("FX AI 接続テスト")

# API設定
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Secretsにキーが見つかりません")

if st.button("テスト解析開始"):
    with st.spinner("AIを呼び出し中..."):
        # 404エラーを回避するための「動くモデルを自動で探す」仕組み
        try:
            target_model = None
            # 利用可能なモデルをリストアップ
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            # 優先順位をつけてモデルを探す
            priority_list = ['models/gemini-1.5-flash', 'models/gemini-1.5-flash-latest', 'models/gemini-pro']
            
            for p in priority_list:
                if p in available_models:
                    target_model = p
                    break
            
            # もしリストにない場合は、見つかった最初のモデルを使う
            if not target_model and available_models:
                target_model = available_models[0]
            
            if target_model:
                model = genai.GenerativeModel(target_model)
                response = model.generate_content("今日のドル円相場について一言で予測して")
                st.write(f"使用モデル: {target_model}")
                st.success(response.text)
            else:
                st.error("利用可能なGeminiモデルが見つかりませんでした。")
                
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
            st.info("APIキーが正しく設定されているか、Google AI Studioのプロジェクト設定を確認してください。")
