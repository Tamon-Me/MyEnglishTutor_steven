import json
import os
from io import BytesIO
from google import genai
from google.genai import types
from gtts import gTTS
import streamlit as st

PODCAST_DATA_FILE = "podcast_history.json"

# 모바일 호환 레이아웃 설정
st.set_page_config(
    page_title="팟캐스트 생성",
    page_icon="🎧",
    layout="centered",
    initial_sidebar_state="expanded",
)

# 모바일 최적화 및 하단 플로팅 카드 CSS (화면 고정/블러 없음)
st.markdown(
    """
<style>
    /* 기본 스크롤 및 여백 (하단 바 공간 확보를 위해 padding-bottom 지정) */
    html, body, [data-testid="stAppViewContainer"] {
        overflow-x: hidden !important;
    }
    .block-container { 
        padding-top: 1.0rem !important; 
        padding-bottom: 7.0rem !important; /* 하단 팝업에 대본 마지막 내용이 가려지지 않도록 공간 확보 */
        padding-left: 0.8rem !important; 
        padding-right: 0.8rem !important; 
        max-width: 100% !important;
    }

    /* 대본 카드 및 버튼 레이아웃 */
    [data-testid="stHorizontalBlock"] {
        align-items: center !important;
        flex-wrap: nowrap !important;
        gap: 6px !important;
    }
    
    .podcast-card {
        background-color: #f8f9fa;
        border-left: 4px solid #1E88E5;
        padding: 10px 12px;
        border-radius: 8px;
    }
    .speaker-name { font-weight: bold; color: #1E88E5; font-size: 13px; margin-bottom: 2px; }
    .script-en { font-size: 15px; line-height: 1.45; color: #212121; word-break: break-word; }

    /* ==========================================
       🖤 메인 화면 영향 없는 하단 플로팅 팝업 카드
       ========================================== */
    .bottom-floating-card {
        position: fixed;
        bottom: 16px;
        left: 50%;
        transform: translateX(-50%);
        width: calc(100% - 32px);
        max-width: 720px;
        background-color: #1e1e24;
        border: 1px solid #33333e;
        border-radius: 12px;
        padding: 14px 16px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        z-index: 99998;
        box-sizing: border-box;
        animation: slideUp 0.18s ease-out;
    }

    @keyframes slideUp {
        from { transform: translate(-50%, 20px); opacity: 0; }
        to { transform: translate(-50%, 0); opacity: 1; }
    }

    .floating-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }

    .floating-card-title {
        color: #64B5F6;
        font-weight: bold;
        font-size: 13px;
        text-align: left; /* 좌측 정렬 */
    }

    .floating-card-body {
        color: #f1f3f5;
        font-size: 14px;
        line-height: 1.45;
        word-break: break-word;
    }

    /* 사이드바 스타일 */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        align-items: center !important;
        flex-wrap: nowrap !important;
        gap: 2px !important;
    }
    [data-testid="stSidebar"] .stButton>button {
        padding: 2px 4px !important;
        font-size: 11px !important;
        height: 32px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

try:
    client = genai.Client()
except Exception as e:
    st.error("API 키를 확인해주세요. (GOOGLE_API_KEY 환경 변수 필요)")


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

if "active_trans_index" not in st.session_state:
    st.session_state.active_trans_index = None

if "active_audio_key" not in st.session_state:
    st.session_state.active_audio_key = None  # 오디오 재생 상태 키 초기화

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


# gTTS 오디오 생성 함수 (메모리 내 변환)
def generate_gtts_audio(text, lang="en"):
    try:
        fp = BytesIO()
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as e:
        st.error(f"오디오 생성 중 오류 발생: {e}")
        return None


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


# --- 사이드바 (이전 대본 목록 관리) ---
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

            col_btn, col_del = st.columns([82, 18])
            with col_btn:
                if st.button(
                    btn_label, key=f"load_p_{idx}", use_container_width=True
                ):
                    st.session_state.current_podcast = item
                    st.session_state.show_settings = False
                    st.session_state.active_trans_index = None
                    st.session_state.active_audio_key = None
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
                        st.session_state.active_trans_index = None
                        st.session_state.active_audio_key = None
                    st.rerun()

        st.divider()
        if st.button(
            "🔥 보관함 전체 삭제", type="primary", use_container_width=True
        ):
            st.session_state.podcast_history = []
            save_podcast_history([])
            st.session_state.current_podcast = None
            st.session_state.active_trans_index = None
            st.session_state.active_audio_key = None
            st.rerun()

# --- 메인 화면 ---
st.title("🎧 팟캐스트 생성")

# 대본 설정 헤더 및 접기/열기 버튼 (모바일 1줄 고정)
head_col1, head_col2 = st.columns([75, 25])
with head_col1:
    st.subheader("⚙️ 대본 설정")
with head_col2:
    toggle_label = (
        "🙈 닫기" if st.session_state.show_settings else "⚙️️ 열기"
    )
    if st.button(
        toggle_label, key="btn_toggle_settings", use_container_width=True
    ):
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
                st.session_state.active_trans_index = None
                st.session_state.active_audio_key = None
                st.success("대본 생성이 완료되었습니다!")
                st.rerun()
            except Exception as e:
                st.error(f"대본 생성 중 오류가 발생했습니다: {e}")

st.divider()

# --- 대본 출력 및 오디오/번역 영역 ---
podcast = st.session_state.current_podcast
if podcast:
    st.markdown(f"### 📻 {podcast['title']}")
    st.caption(
        f"📌 **주제**: {podcast['topic']} | **난이도**: {podcast['level']}"
    )

    # ==========================================
    # 🎧 전체 대본 통합 오디오 재생기
    # ==========================================
    full_audio_key = "full_podcast_audio"
    col_full_card, col_full_btn = st.columns([85, 15])
    with col_full_card:
        st.markdown("**🎙️ 전체 대본 한 번에 듣기**")
    with col_full_btn:
        is_playing_full = st.session_state.active_audio_key == full_audio_key
        full_btn_label = "⏹️" if is_playing_full else "🎧"

        if st.button(
            full_btn_label, key="btn_full_audio", use_container_width=True
        ):
            if is_playing_full:
                st.session_state.active_audio_key = None
            else:
                st.session_state.active_audio_key = full_audio_key
            st.rerun()

    # 전체 오디오 재생 실행
    if st.session_state.active_audio_key == full_audio_key:
        full_text = ". ".join([
            f"{item.get('speaker', '')} says, {item.get('text_en', '')}"
            for item in podcast["script"]
        ])
        audio_fp = generate_gtts_audio(full_text)
        if audio_fp:
            st.audio(audio_fp, format="audio/mp3", autoplay=True)

    st.divider()

    # ==========================================
    # 📜 문장별 대본 카드 및 재생/돋보기 버튼
    # ==========================================
    for idx, item in enumerate(podcast["script"]):
        speaker = item.get("speaker", "Speaker")
        text_en = item.get("text_en", "")
        item_audio_key = f"audio_{idx}"

        col_card, col_audio, col_trans = st.columns([70, 15, 15])

        with col_card:
            st.markdown(
                f"""
                <div class="podcast-card">
                    <div class="speaker-name">🗣️ {speaker}</div>
                    <div class="script-en">{text_en}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # 🔊/⏹️ 문장별 오디오 버튼 (돋보기 좌측)
        with col_audio:
            is_playing = st.session_state.active_audio_key == item_audio_key
            audio_btn_label = "⏹️" if is_playing else "🔊"

            if st.button(
                audio_btn_label, key=f"audio_btn_{idx}", use_container_width=True
            ):
                if is_playing:
                    st.session_state.active_audio_key = None
                else:
                    st.session_state.active_audio_key = item_audio_key
                st.rerun()

        # 🔍 번역 버튼
        with col_trans:
            if st.button(
                "🔍", key=f"trans_btn_{idx}", use_container_width=True
            ):
                if st.session_state.active_trans_index == idx:
                    st.session_state.active_trans_index = None
                else:
                    st.session_state.active_trans_index = idx
                st.rerun()

        # 현재 선택된 문장 오디오만 재생 (동시 재생 방지)
        if st.session_state.active_audio_key == item_audio_key:
            audio_fp = generate_gtts_audio(text_en)
            if audio_fp:
                st.audio(audio_fp, format="audio/mp3", autoplay=True)

    # ==========================================
    # 🖤 하단 플로팅 번역 팝업 카드 (닫기 버튼 없음)
    # ==========================================
    if st.session_state.active_trans_index is not None:
        active_idx = st.session_state.active_trans_index
        if active_idx < len(podcast["script"]):
            trans_info = podcast["script"][active_idx]
            speaker = trans_info.get("speaker", "")
            text_ko = trans_info.get("text_ko", "")

            floating_card_html = f"""
            <div class="bottom-floating-card">
                <div class="floating-card-header">
                    <span class="floating-card-title">🇰🇷 {speaker} 번역</span>
                </div>
                <div class="floating-card-body">{text_ko}</div>
            </div>
            """
            st.markdown(floating_card_html, unsafe_allow_html=True)

else:
    st.info("상단에서 대본을 생성하거나, 왼쪽 보관함에서 대본을 선택해주세요.")