import json
import time
from google import genai
from google.genai import types
import streamlit as st

# 모바일 호환 레이아웃 설정
st.set_page_config(
    page_title="CEFR 팟캐스트 스튜디오",
    page_icon="🎧",
    layout="centered",
    initial_sidebar_state="expanded",
)

# 모바일 커스텀 CSS
st.markdown(
    """
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; padding-left: 0.8rem; padding-right: 0.8rem; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.2rem; font-weight: bold; }
    .podcast-dialogue { background-color: #f8f9fa; border-left: 4px solid #1E88E5; padding: 12px 14px; margin-bottom: 6px; border-radius: 8px; }
    .speaker-name { font-weight: bold; color: #1E88E5; font-size: 14px; margin-bottom: 4px; }
    .script-en { font-size: 16px; line-height: 1.5; color: #212121; }
    /* expander 스타일 모바일 최적화 */
    .streamlit-expanderHeader { font-size: 13px !important; color: #666 !important; padding-top: 0px !important; padding-bottom: 0px !important; }
</style>
""",
    unsafe_allow_html=True,
)

try:
    client = genai.Client()
except Exception as e:
    st.error("API 키를 확인해주세요. (GEMINI_API_KEY 환경 변수 필요)")

# Session State 초기화
if "podcast_script" not in st.session_state:
    st.session_state.podcast_script = None
if "podcast_metadata" not in st.session_state:
    st.session_state.podcast_metadata = None

# 프롬프트 제어
PODCAST_SYSTEM_PROMPT = """
You are a professional podcast script writer for English learners.
Generate an engaging, natural, 2-person dialogue podcast script based on the requested CEFR level and topic.

Strict Output Rules:
1. Output MUST be valid JSON format only, matching the exact schema below.
2. Do not wrap the JSON in Markdown code fences if possible, or ensure it is strictly parseable JSON.
3. Keep the target CEFR level guidelines strictly:
   - A1: Very simple present tense, short sentences, core everyday words.
   - A2: Oxford 3000 vocabulary, simple past/future, basic connectors.
   - B1: Broader vocabulary, express opinions, reasons, everyday stories.
   - B2: Richer expressions, abstract topics, natural idioms.

JSON Output Schema:
{
  "title": "[Podcast Title in English]",
  "topic": "[Topic Summary in Korean]",
  "level": "[A1/A2/B1/B2]",
  "script": [
    {
      "id": 1,
      "speaker": "Alex",
      "text_en": "English dialogue sentence...",
      "text_ko": "한국어 번역..."
    }
  ]
}
"""


def generate_podcast_script(level, topic_input, podcast_type):
    topic_prompt = (
        f"Topic: {topic_input}"
        if topic_input
        else "Topic: Daily life, interesting everyday experiences, or popular hobbies."
    )

    prompt = f"""
    Create a {podcast_type} podcast script.
    - CEFR Level: {level}
    - {topic_prompt}
    - Generate approximately 12-18 dialogue turns suitable for a ~3-5 minute engaging listening practice.
    """

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=PODCAST_SYSTEM_PROMPT,
            temperature=0.7,
            response_mime_type="application/json",
        ),
    )

    return json.loads(response.text)


# --- UI 구성 ---
st.title("🎧 CEFR 팟캐스트 스튜디오")
st.caption("수준별 맞춤 팟캐스트 대본을 생성하여 리스닝 및 스피킹을 학습하세요.")

st.divider()

# 설정 패널
st.subheader("⚙️ 대본 설정")

col1, col2 = st.columns(2)

with col1:
    selected_level = st.selectbox(
        "🎯 CEFR 난이도 선택",
        ["A1 (입문)", "A2 (초급)", "B1 (중급)", "B2 (고급)"],
        index=1,
    )

with col2:
    podcast_format = st.selectbox(
        "🎙️ 팟캐스트 포맷",
        ["2인 대화형 (Host & Guest)", "1인 모놀로그 (Solo Presenter)"],
        index=0,
    )

topic_custom = st.text_input(
    "💡 다룰 주제 (선택 사항)",
    placeholder="예: 주말 여행 계획, 카페에서 주문하기 등 (비워두면 자동 추천)",
)

if st.button(
    "🚀 팟캐스트 대본 생성하기", type="primary", use_container_width=True
):
    with st.spinner("AI 작가가 맞춤형 팟캐스트 대본을 작성 중입니다..."):
        try:
            level_code = selected_level.split(" ")[0]
            p_type = (
                "2-person dialogue"
                if "2인" in podcast_format
                else "1-person monologue"
            )

            result_json = generate_podcast_script(
                level_code, topic_custom, p_type
            )

            st.session_state.podcast_script = result_json.get("script", [])
            st.session_state.podcast_metadata = {
                "title": result_json.get("title", "English Podcast"),
                "topic": result_json.get("topic", ""),
                "level": result_json.get("level", level_code),
            }
            st.success("대본 생성이 완료되었습니다!")
            st.rerun()
        except Exception as e:
            st.error(f"대본 생성 중 오류가 발생했습니다: {e}")

# --- 대본 출력 영역 ---
if st.session_state.podcast_script:
    meta = st.session_state.podcast_metadata
    st.divider()

    st.markdown(f"### 📻 {meta['title']}")
    st.caption(f"📌 **주제**: {meta['topic']} | **난이도**: {meta['level']}")
    st.write("")

    # 문장별 개별 확인 방식 안내
    st.caption("💡 각 문장 하단의 **'🔍 번역 확인'**을 누르면 한국어 뜻을 볼 수 있습니다.")

    # 대본 출력 (문장별 개별 토글 형태)
    for idx, item in enumerate(st.session_state.podcast_script):
        speaker = item.get("speaker", "Speaker")
        text_en = item.get("text_en", "")
        text_ko = item.get("text_ko", "")

        # 1. 영문 대본 카드 출력
        st.markdown(
            f"""
            <div class="podcast-dialogue">
                <div class="speaker-name">🗣️ {speaker}</div>
                <div class="script-en">{text_en}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 2. 개별 문장 번역 토글 (모바일 화면 최적화)
        with st.expander("🔍 번역 확인", expanded=False):
            st.caption(f"🇰🇷 {text_ko}")

        st.write("")

    st.divider()
    st.info(
        "💡 **다음 로드맵 안내**: 2단계에서는 이 대본을 음성(TTS)으로 들어볼 수 있는 오디오 플레이어가 추가될 예정입니다!"
    )