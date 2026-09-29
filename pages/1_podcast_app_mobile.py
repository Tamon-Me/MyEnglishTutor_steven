import json
import os
import time
from google import genai
from google.genai import types
import streamlit as st

PODCAST_DATA_FILE = "podcast_history.json"

# 모바일 호환 레이아웃 설정
st.set_page_config(
    page_title="CEFR 팟캐스트 스튜디오",
    page_icon="🎧",
    layout="centered",
    initial_sidebar_state="expanded",
)

# 모바일 최적화 및 타이트한 대본 카드 커스텀 CSS
st.markdown(
    """
<style>
    .block-container { padding-top: 1.0rem; padding-bottom: 2rem; padding-left: 0.8rem; padding-right: 0.8rem; }
    .stButton>button { width: 100%; border-radius: 8px; height: 2.8rem; font-weight: bold; }
    
    /* 대본 카드 레이아웃 극대화 */
    .podcast-card {
        background-color: #f8f9fa;
        border-left: 4px solid #1E88E5;
        padding: 8px 10px;
        margin-bottom: 6px;
        border-radius: 6px;
    }
    .speaker-name { font-weight: bold; color: #1E88E5; font-size: 13px; margin-bottom: 2px; }
    .script-en { font-size: 15px; line-height: 1.4; color: #212121; }

    /* 사이드바 보관함 모바일 1줄 고정 */
    [data-testid="column"] {
        padding: 0px 2px !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

try:
    client = genai.Client()
except Exception as e:
    st.error("API 키를 확인해주세요. (GEMINI_API_KEY 환경 변수 필요)")


# 로컬 저장소 함수
def load_podcast_history():
    if os.path.exists(PODCAST_DATA_FILE):
        try:
            with open(PODCAST_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_podcast_history(history):
    with open(PODCAST_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# Session State 초기화
if "podcast_history" not in st.session_state:
    st.session_state.podcast_history = load_podcast_history()

if "current_podcast" not in st.session_state:
    st.session_state.current_podcast = None

if "show_settings" not in st.session_state:
    st.session_state.show_settings = True

PODCAST_SYSTEM_PROMPT = """
You are a professional podcast script writer for English learners.
Generate an engaging, natural podcast script based on the requested CEFR level and topic.

Strict Output Rules:
1. Output MUST be valid JSON format only, matching the exact schema below.
2. Keep the target CEFR level guidelines strictly:
   - A1: Very simple present tense, short sentences, core everyday words.
   - A2: Oxford 3000 vocabulary, simple past/future, basic connectors.
   - B1: Broader vocabulary, express opinions, reasons, everyday stories.
   - B2: Richer expressions, abstract topics, natural idioms.
3. NO DUPLICATE SPECIFIC EPISODES: You will be provided with previous topics. Do NOT reuse identical plot points or exact specific sub-topics. Change the story perspective, context, or angle completely.

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


def generate_podcast_script(level, topic_input, podcast_type, previous_topics):
    topic_prompt = (
        f"Requested Topic: {topic_input}"
        if topic_input
        else "Requested Topic: Daily life, interesting everyday experiences, or popular hobbies."
    )

    exclusion_clause = ""
    if previous_topics:
        exclusion_clause = f"\n[CRITICAL: DO NOT REPEAT THESE PREVIOUS EPISODES/TOPICS]\nPrevious Topics: {', '.join(previous_topics)}\nEnsure this new script has a fresh plot, new situation, or different angle."

    prompt = f"""
    Create a {podcast_type} podcast script.
    - CEFR Level: {level}
    - {topic_prompt}
    {exclusion_clause}
    - Generate approximately 12-18 dialogue turns suitable for a ~3-5 minute engaging listening practice.
    """

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=PODCAST_SYSTEM_PROMPT,
            temperature=0.75,
            response_mime_type="application/json",
        ),
    )

    return json.loads(response.text)


# --- 사이드바 (이전 대본 목록 관리 - 모바일 1줄 레이아웃 최적화) ---
with st.sidebar:
    st.title("🎧 팟캐스트 스튜디오")
    st.divider()

    st.header("📚 저장된 대본 보관함")
    if not st.session_state.podcast_history:
        st.info("저장된 대본이 없습니다.")
    else:
        total_p = len(st.session_state.podcast_history)
        for idx in range(total_p - 1, -1, -1):
            item = st.session_state.podcast_history[idx]
            btn_label = f"[{item.get('level', 'A2')}] {item.get('title', '대본')}"

            col_btn, col_del = st.columns([85, 15])
            with col_btn:
                if st.button(
                    btn_label, key=f"load_p_{idx}", use_container_width=True
                ):
                    st.session_state.current_podcast = item
                    st.session_state.show_settings = False
                    st.rerun()

            with col_del:
                if st.button("🗑️", key=f"del_p_{idx}"):
                    st.session_state.podcast_history.pop(idx)
                    save_podcast_history(st.session_state.podcast_history)
                    if (
                        st.session_state.current_podcast
                        and st.session_state.current_podcast.get("title")
                        == item.get("title")
                    ):
                        st.session_state.current_podcast = None
                    st.rerun()

        st.divider()
        if st.button(
            "🔥 보관함 전체 삭제", type="primary", use_container_width=True
        ):
            st.session_state.podcast_history = []
            save_podcast_history([])
            st.session_state.current_podcast = None
            st.rerun()

# --- 메인 화면 ---
st.title("🎧 CEFR 팟캐스트 스튜디오")

# 대본 설정 토글 헤더
head_col1, head_col2 = st.columns([3, 1])
with head_col1:
    st.subheader("⚙️ 대본 설정")
with head_col2:
    toggle_label = (
        "🙈 설정 닫기" if st.session_state.show_settings else "⚙️ 설정 열기"
    )
    if st.button(toggle_label, key="btn_toggle_settings"):
        st.session_state.show_settings = not st.session_state.show_settings
        st.rerun()

# 설정 UI 영역
if st.session_state.show_settings:
    col1, col2 = st.columns(2)
    with col1:
        selected_level = st.selectbox(
            "🎯 CEFR 난이도",
            ["A1 (입문)", "A2 (초급)", "B1 (중급)", "B2 (고급)"],
            index=1,
        )

    with col2:
        podcast_format = st.selectbox(
            "🎙️ 포맷",
            ["2인 대화형 (Host & Guest)", "1인 모놀로그 (Solo Presenter)"],
            index=0,
        )

    topic_custom = st.text_input(
        "💡 주제 (선택 사항)",
        placeholder="예: 카페 주문, 주말 여행 등 (비워두면 자동 추천)",
    )

    if st.button(
        "🚀 팟캐스트 대본 생성하기", type="primary", use_container_width=True
    ):
        with st.spinner("AI 작가가 중복 없는 맞춤형 대본을 작성 중입니다..."):
            try:
                level_code = selected_level.split(" ")[0]
                p_type = (
                    "2-person dialogue"
                    if "2인" in podcast_format
                    else "1-person monologue"
                )

                # 기존 스크립트 주제 수집 (중복 방지용)
                prev_topics = [
                    f"{p.get('title', '')} ({p.get('topic', '')})"
                    for p in st.session_state.podcast_history
                ]

                result_json = generate_podcast_script(
                    level_code, topic_custom, p_type, prev_topics
                )

                podcast_data = {
                    "title": result_json.get("title", "English Podcast"),
                    "topic": result_json.get("topic", ""),
                    "level": result_json.get("level", level_code),
                    "script": result_json.get("script", []),
                }

                st.session_state.current_podcast = podcast_data
                st.session_state.podcast_history.append(podcast_data)
                save_podcast_history(st.session_state.podcast_history)

                st.session_state.show_settings = False
                st.success("대본 생성이 완료되었습니다!")
                st.rerun()
            except Exception as e:
                st.error(f"대본 생성 중 오류가 발생했습니다: {e}")

st.divider()

# --- 대본 출력 영역 (영문 위주 & 우측 작고 깔끔한 번역 버튼) ---
if st.session_state.current_podcast:
    podcast = st.session_state.current_podcast
    st.markdown(f"### 📻 {podcast['title']}")
    st.caption(
        f"📌 **주제**: {podcast['topic']} | **난이도**: {podcast['level']}"
    )
    st.write("")

    for idx, item in enumerate(podcast["script"]):
        speaker = item.get("speaker", "Speaker")
        text_en = item.get("text_en", "")
        text_ko = item.get("text_ko", "")

        card_col, btn_col = st.columns([88, 12])

        with card_col:
            st.markdown(
                f"""
                <div class="podcast-card">
                    <div class="speaker-name">🗣️ {speaker}</div>
                    <div class="script-en">{text_en}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with btn_col:
            # 클릭 시 하단 작업표시줄 형태(Toast)로 번역 1줄 출력
            if st.button("🔍", key=f"tr_btn_{idx}"):
                st.toast(f"🇰🇷 **{speaker}**: {text_ko}", icon="🗣️")

else:
    st.info("상단에서 대본을 생성하거나, 왼쪽 보관함에서 대본을 선택해주세요.")