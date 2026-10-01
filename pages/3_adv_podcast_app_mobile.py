import asyncio
import base64
import json
import os
from io import BytesIO
from google import genai
from google.genai import types
import edge_tts
import streamlit as st

PODCAST_DATA_FILE = "podcast_history.json"

st.set_page_config(
    page_title="팟캐스트 생성",
    page_icon="🎧",
    layout="centered",
    initial_sidebar_state="expanded",
)

# CSS 스타일 및 자바스크립트
st.markdown(
    """
<style>
    html, body, [data-testid="stAppViewContainer"] {
        overflow-x: hidden !important;
    }
    .block-container { 
        padding-top: 1.0rem !important; 
        padding-bottom: 7.0rem !important; 
        padding-left: 0.8rem !important; 
        padding-right: 0.8rem !important; 
        max-width: 100% !important;
    }

    /* 카드 컨테이너 */
    .podcast-card-container {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 12px;
    }

    .podcast-card {
        flex: 1;
        background-color: #f8f9fa;
        border-left: 4px solid #1E88E5;
        padding: 10px 12px;
        border-radius: 8px;
        transition: all 0.2s ease;
    }

    /* 💡 클릭 시 활성화되는 노란색 하이라이트 */
    .podcast-card.active-card {
        background-color: #FFF9C4 !important;
        border-left: 4px solid #FBC02D !important;
    }

    .speaker-name { font-weight: bold; color: #1E88E5; font-size: 13px; margin-bottom: 2px; }
    .script-en { font-size: 15px; line-height: 1.45; color: #212121; word-break: break-word; }

    /* 커스텀 버튼 스타일 */
    .action-btn {
        background-color: #f0f2f6;
        border: 1px solid #dcdfe6;
        border-radius: 6px;
        padding: 8px 12px;
        cursor: pointer;
        font-size: 14px;
        transition: background 0.2s;
    }
    .action-btn:hover {
        background-color: #e0e4ec;
    }

    /* 하단 플로팅 번역 팝업 */
    #bottom-translation-popover {
        display: none;
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        width: calc(100% - 32px);
        max-width: 720px;
        background-color: #1e1e24;
        color: #ffffff;
        border: 1px solid #33333e;
        border-radius: 12px;
        padding: 14px 16px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        z-index: 999999;
        box-sizing: border-box;
    }

    .popover-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
        font-weight: bold;
        color: #64B5F6;
        font-size: 13px;
    }

    .popover-close {
        cursor: pointer;
        color: #aaa;
        font-size: 16px;
    }
    .popover-close:hover { color: #fff; }

    .popover-body {
        font-size: 14px;
        line-height: 1.45;
        color: #f1f3f5;
    }
</style>

<!-- 프론트엔드 자바스크립트 로직 -->
<script>
function toggleHighlightAndTranslate(cardId, speaker, textKo) {
    const card = document.getElementById(cardId);
    const popover = document.getElementById('bottom-translation-popover');
    const popoverSpeaker = document.getElementById('popover-speaker');
    const popoverText = document.getElementById('popover-text');

    // 이미 활성화된 카드를 다시 누른 경우 -> 팝업 닫기 & 색상 해제
    if (card.classList.contains('active-card')) {
        card.classList.remove('active-card');
        popover.style.display = 'none';
    } else {
        // 기존 active 카드들 색상 초기화
        document.querySelectorAll('.podcast-card').forEach(el => el.classList.remove('active-card'));
        
        // 현재 카드 하이라이트 적용
        card.classList.add('active-card');
        
        // 팝업 데이터 갱신 및 표시
        popoverSpeaker.innerText = '🇰🇷 ' + speaker + ' 번역';
        popoverText.innerText = textKo;
        popover.style.display = 'block';
    }
}

function closePopover() {
    document.getElementById('bottom-translation-popover').style.display = 'none';
    document.querySelectorAll('.podcast-card').forEach(el => el.classList.remove('active-card'));
}
</script>

<!-- 번역 팝업 엘리먼트 -->
<div id="bottom-translation-popover">
    <div class="popover-header">
        <span id="popover-speaker">🇰🇷 번역</span>
        <span class="popover-close" onclick="closePopover()">✖</span>
    </div>
    <div id="popover-text" class="popover-body"></div>
</div>
""",
    unsafe_allow_html=True,
)

try:
    client = genai.Client()
except Exception as e:
    st.error("API 키를 확인해주세요. (GOOGLE_API_KEY 환경 변수 필요)")


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


if "podcast_history" not in st.session_state:
    st.session_state.podcast_history = load_podcast_history()

if "current_podcast" not in st.session_state:
    st.session_state.current_podcast = None

if "show_settings" not in st.session_state:
    st.session_state.show_settings = True

if "active_audio_key" not in st.session_state:
    st.session_state.active_audio_key = None

if "audio_speed" not in st.session_state:
    st.session_state.audio_speed = 1.0

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
3. NO DUPLICATE SPECIFIC EPISODES: You will be provided with previous topics. Do NOT reuse identical plot points or exact specific sub-topics.

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


def generate_edge_audio_single(text, speaker="Alex"):
    voice = (
        "en-US-ChristopherNeural"
        if speaker.strip().lower() == "alex"
        else "en-US-JennyNeural"
    )

    async def _generate():
        communicate = edge_tts.Communicate(text, voice)
        fp = BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fp.write(chunk["data"])
        fp.seek(0)
        return fp

    try:
        return asyncio.run(_generate())
    except Exception as e:
        st.error(f"오디오 생성 오류: {e}")
        return None


def generate_all_audio_chunks(script_list):
    async def _generate():
        chunks = []
        for item in script_list:
            speaker = item.get("speaker", "Alex")
            text_en = item.get("text_en", "")
            voice = (
                "en-US-ChristopherNeural"
                if speaker.strip().lower() == "alex"
                else "en-US-JennyNeural"
            )
            communicate = edge_tts.Communicate(text_en, voice)
            fp = BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    fp.write(chunk["data"])
            fp.seek(0)
            b64 = base64.b64encode(fp.read()).decode("utf-8")
            chunks.append(b64)
        return chunks

    try:
        return asyncio.run(_generate())
    except Exception as e:
        st.error(f"오디오 변환 오류: {e}")
        return []


def play_hidden_single_audio(audio_fp, speed=1.0):
    audio_bytes = audio_fp.read()
    b64_audio = base64.b64encode(audio_bytes).decode("utf-8")

    js_code = f"""
    <audio id="tts_player" style="display:none;" autoplay>
        <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3">
    </audio>
    <script>
        var player = document.getElementById('tts_player');
        player.playbackRate = {speed};
    </script>
    """
    st.components.v1.html(js_code, height=0, width=0)


def play_continuous_audio_pure(audio_b64_list, speed=1.0):
    json_audio = json.dumps(audio_b64_list)

    js_code = f"""
    <script>
        const audioList = {json_audio};
        const playbackSpeed = {speed};
        let currentIndex = 0;

        function playNext() {{
            if (currentIndex >= audioList.length) return;

            let currentAudio = new Audio('data:audio/mp3;base64,' + audioList[currentIndex]);
            currentAudio.playbackRate = playbackSpeed;
            currentAudio.play();

            currentAudio.onended = function() {{
                currentIndex++;
                playNext();
            }};
        }}

        playNext();
    </script>
    """
    st.components.v1.html(js_code, height=0, width=0)


def generate_podcast_script(level, topic_input, podcast_type, previous_topics):
    topic_prompt = (
        f"Requested Topic: {topic_input}"
        if topic_input
        else "Requested Topic: Daily life, interesting everyday experiences, or popular hobbies."
    )
    exclusion_clause = (
        f"\nPrevious Topics: {', '.join(previous_topics)}"
        if previous_topics
        else ""
    )

    prompt = f"""
    Create a {podcast_type} podcast script.
    - CEFR Level: {level}
    - {topic_prompt}
    {exclusion_clause}
    - Generate approximately 12-18 dialogue turns.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=PODCAST_SYSTEM_PROMPT,
            temperature=0.75,
            response_mime_type="application/json",
        ),
    )
    return json.loads(response.text)


# --- 사이드바 ---
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
                        st.session_state.active_audio_key = None
                    st.rerun()

# --- 메인 화면 ---
st.title("🎧 팟캐스트 생성")

head_col1, head_col2 = st.columns([75, 25])
with head_col1:
    st.subheader("⚙️ 대본 설정")
with head_col2:
    toggle_label = (
        "🙈 닫기" if st.session_state.show_settings else "⚙️ 열기"
    )
    if st.button(
        toggle_label, key="btn_toggle_settings", use_container_width=True
    ):
        st.session_state.show_settings = not st.session_state.show_settings
        st.rerun()

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
                st.session_state.active_audio_key = None
                st.success("대본 생성이 완료되었습니다!")
                st.rerun()
            except Exception as e:
                st.error(f"대본 생성 중 오류가 발생했습니다: {e}")

st.divider()

podcast = st.session_state.current_podcast
if podcast:
    st.markdown(f"### 📻 {podcast['title']}")
    st.caption(
        f"📌 **주제**: {podcast['topic']} | **난이도**: {podcast['level']}"
    )

    speed_col1, speed_col2 = st.columns([35, 65])
    with speed_col1:
        st.markdown("**⚡ 재생 속도 설정**")
    with speed_col2:
        speed_labels = ["0.8x", "1.0x", "1.2x", "1.5x"]
        speed_values = [0.8, 1.0, 1.2, 1.5]

        current_idx = (
            speed_values.index(st.session_state.audio_speed)
            if st.session_state.audio_speed in speed_values
            else 1
        )

        selected_label = st.radio(
            "재생 속도",
            options=speed_labels,
            index=current_idx,
            horizontal=True,
            label_visibility="collapsed",
            key="radio_audio_speed",
        )

        new_speed = float(selected_label.replace("x", ""))
        if new_speed != st.session_state.audio_speed:
            st.session_state.audio_speed = new_speed
            st.rerun()

    full_audio_key = "full_podcast_audio"
    col_full_card, col_full_btn = st.columns([85, 15])
    with col_full_card:
        st.markdown(
            f"**🎙 전체 대본 한 번에 듣기 (속도: {st.session_state.audio_speed}x)**"
        )
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

    if st.session_state.active_audio_key == full_audio_key:
        with st.spinner("전체 오디오 재생 준비 중..."):
            audio_chunks = generate_all_audio_chunks(podcast["script"])
            if audio_chunks:
                play_continuous_audio_pure(
                    audio_b64_list=audio_chunks,
                    speed=st.session_state.audio_speed,
                )

    st.divider()

    # --- 대본 목록 출력 ---
    for idx, item in enumerate(podcast["script"]):
        speaker = item.get("speaker", "Speaker")
        text_en = item.get("text_en", "")
        text_ko = item.get("text_ko", "").replace("'", "\\'").replace('"', '\\"')
        item_audio_key = f"audio_{idx}"

        is_playing_this_sentence = (
            st.session_state.active_audio_key == item_audio_key
        )

        col_card, col_audio = st.columns([85, 15])

        with col_card:
            # 💡 자바스크립트로 직접 노란색 하이라이트 및 번역 팝업 제어
            card_html = f"""
            <div class="podcast-card-container">
                <div id="card_{idx}" class="podcast-card">
                    <div class="speaker-name">🗣️ {speaker}</div>
                    <div class="script-en">{text_en}</div>
                </div>
                <button class="action-btn" onclick="toggleHighlightAndTranslate('card_{idx}', '{speaker}', '{text_ko}')">🔍</button>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)

        with col_audio:
            audio_btn_label = "⏹️" if is_playing_this_sentence else "🔊"

            if st.button(
                audio_btn_label, key=f"audio_btn_{idx}", use_container_width=True
            ):
                if is_playing_this_sentence:
                    st.session_state.active_audio_key = None
                else:
                    st.session_state.active_audio_key = item_audio_key
                st.rerun()

        # 개별 오디오 재생 처리
        if is_playing_this_sentence:
            audio_fp = generate_edge_audio_single(text_en, speaker=speaker)
            if audio_fp:
                play_hidden_single_audio(
                    audio_fp, speed=st.session_state.audio_speed
                )

else:
    st.info("상단에서 대본을 생성하거나, 왼쪽 보관함에서 대본을 선택해주세요.")