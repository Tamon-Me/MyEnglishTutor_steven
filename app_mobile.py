import time
import json
import os
import random
import streamlit as st
from google import genai
from google.genai import types

DATA_FILE = "vocabulary.json"

# 모바일 화면 비율 및 레이아웃 설정
st.set_page_config(
    page_title="영어 AI 튜터", 
    page_icon="🎬",
    layout="centered", 
    initial_sidebar_state="collapsed" # 모바일에서 사이드바 자동 접힘
)

# 모바일 커스텀 CSS (여백 축소 및 터치 영역 확대)
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; padding-left: 0.8rem; padding-right: 0.8rem; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.2rem; font-weight: bold; }
    .stTextInput>div>div>input { font-size: 16px; } /* 모바일 자동 확대 방지 */
</style>
""", unsafe_allow_html=True)

try:
    client = genai.Client()
except Exception as e:
    st.error("API 키를 확인해주세요. (GEMINI_API_KEY 환경 변수 필요)")

COOLDOWN_SECONDS = 5.0

if "last_click_time" not in st.session_state:
    st.session_state.last_click_time = 0.0

if "is_processing" not in st.session_state:
    st.session_state.is_processing = False

if "last_api_time" not in st.session_state:
    st.session_state.last_api_time = 0.0

def check_rpm_limit():
    current_time = time.time()
    elapsed = current_time - st.session_state.last_api_time
    if elapsed < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - elapsed) + 1
        return False, remaining
    st.session_state.last_api_time = current_time
    return True, 0

def load_history():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history(history):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

if "history" not in st.session_state:
    st.session_state.history = load_history()

if "current_card" not in st.session_state:
    st.session_state.current_card = None

SYSTEM_PROMPT = """
You are a Steven English style tutor focusing on visual concepts and left-to-right progressive reading.

[Absolute Restriction]
1. NEVER output abstract, figurative, or cultural idioms (e.g., "miss the boat", "in the long run", "bite the bullet").
2. Focus ONLY on concrete, physical, space-based, and movement-based English expressions that can be drawn as a physical picture.

[Strict Output & Language Rules]
1. ALL template labels and explanatory texts MUST be in Korean.
2. English words, target expressions, and slash-separated English reading sequences MUST remain in English.
3. NEVER reorder English sentences into Korean grammar order. Translate left-to-right progressively.
4. "🎬 이미지 리딩" MUST attach a simple physical/spatial visual explanation in Korean inside parentheses BEFORE each slash '/'.
   - CRITICAL: Do NOT write natural Korean translations (의역/결과적 번역 금지). 
   - CRITICAL: Write ONLY the direct, core physical image or spatial movement of each word/chunk.
   - Example 1 (Preposition/Movement): out of (공간 밖으로 벗어나)
   - Example 2 (Verb): pulls (당기는 동작)
   - CORRECT FORMAT: He (그는) / pulls (자신 쪽으로 당기다) / his phone (그의 폰을) / out of (~의 안에서 밖으로) / his pocket (그의 주머니)
   - WRONG FORMAT (Natural translation): out of (바깥쪽 공간으로 꺼내다) -> "꺼내다" is a translated action of "pull out", not the standalone meaning of "out of".
5. CRITICAL RULE FOR HINT: "💡 미션 힌트" MUST NOT reveal the full answer sentence. Provide ONLY a structural pattern using brackets and placeholders (e.g., "pull [물체] out of [장소]" or "put [대상] in [공간]").
6. IMPORTANT: Each output field MUST be separated by a new line.

[Output Format]
📌 **주제/단어**: [Target English word/expression]

🎨 **뿌리 이미지**: [Visual concept described in Korean, 1-2 short sentences]

🎬 **이미지 리딩**: [Example: The cat (그 고양이는) / sleeps (잠을 자다) / under (바로 아래 공간에) / the bed (그 침대의)]

❓ **오늘의 미션**: [1 simple situation quiz in Korean related to the visual concept]

💡 **미션 힌트**: [Provide structural pattern ONLY with placeholders. Example: [주어] + sleep(잠을 자다) + under (바로 아래 공간에) + [장소]]
"""

CHECK_PROMPT = """
You are an encouraging English tutor. Evaluate the user's answer for the given quiz.
Criteria:
- Is the target word used correctly based on left-to-right visual concepts?
- Minor typos are okay, focus on word order and visual accuracy.

Response Format :
- ⭕/💡 (Pass or Advice)
- [1 sentence short feedback in Korean]
- [recommand sentence in english]
"""

# --- [사이드바 (단어장)] ---
with st.sidebar:
    st.title("🎬 영어 AI 튜터")
    st.caption("이미지 리딩 단어장")
    st.divider()

    st.header("📚 나의 단어장")
    if not st.session_state.history:
        st.info("저장된 학습 기록이 없습니다.")
    else:
        total_items = len(st.session_state.history)
        for idx in range(total_items - 1, -1, -1):
            item = st.session_state.history[idx]
            status_icon = "✅" if item.get("user_answer") else "📖"
            
            with st.expander(f"{status_icon} {item['target']}"):
                st.markdown(item["result"])
                if "user_answer" in item and item["user_answer"]:
                    st.divider()
                    st.caption(f"✍️ 내 답안: {item['user_answer']}")
                    st.caption(f"📝 피드백: {item['feedback']}")
                
                if st.button("🗑️ 삭제", key=f"del_{idx}", use_container_width=True):
                    st.session_state.history.pop(idx)
                    save_history(st.session_state.history)
                    st.rerun()

        st.divider()
        if st.button("🔥 단어장 전체 삭제", type="primary", use_container_width=True):
            st.session_state.history = []
            save_history([])
            st.session_state.current_card = None
            st.rerun()

# --- [메인 영역] ---
st.title("🎬 영어 AI 튜터")

tab1, tab2 = st.tabs(["🎲 자동 추천", "✏️ 직접 입력"])

def generate_card(prompt_text, default_target="추천 주제"):
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt_text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.95,
        ),
    )
    result_text = response.text
    
    target_word = default_target
    for line in result_text.split("\n"):
        if "주제/단어" in line:
            cleaned = line.replace("*", "").replace("📌", "").replace("주제/단어", "").replace(":", "").strip()
            if cleaned:
                target_word = cleaned
            break

    new_card = {
        "target": target_word,
        "result": result_text,
        "user_answer": None,
        "feedback": None,
        "is_challenge_mode": False,
        "show_hint": False
    }
    
    st.session_state.current_card = new_card
    st.session_state.history.append(new_card)
    save_history(st.session_state.history)

with tab1:
    if st.button("🚀 새로운 주제로 학습 시작", type="primary", use_container_width=True, key="btn_auto"):
        current_time = time.time()
        if current_time - st.session_state.last_click_time < COOLDOWN_SECONDS:
            st.warning("⏳ 잠시 후 다시 눌러주세요.")
        else:
            can_proceed, wait_sec = check_rpm_limit()
            if not can_proceed:
                st.warning(f"⏳ {wait_sec}초 후 다시 이용 가능합니다.")
            else:
                with st.spinner("개념 구성 중..."):
                    try:
                        CONCEPT_CATEGORIES = [
                            "a spatial preposition with clear physical placement",
                            "a highly visual phrasal verb depicting direct physical movement",
                            "a core basic verb with rich physical root images"
                        ]
                        selected_category = random.choice(CONCEPT_CATEGORIES)
                        learned_targets = [item.get("target", "").lower() for item in st.session_state.history if item.get("target")]
                        exclusion_clause = f" Do NOT pick these: [{', '.join(set(learned_targets))}]." if learned_targets else ""
                        
                        prompt = f"Pick 1 NEW English target in category '{selected_category}'. Concrete physical action/space ONLY. Seed: {random.randint(10000,99999)}.{exclusion_clause}"
                        generate_card(prompt, "추천 주제")
                        st.session_state.last_click_time = time.time()
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

with tab2:
    user_input = st.text_input("학습할 표현:", placeholder="예: at, look for", key="user_text_input")
    if st.button("학습하기", type="primary", use_container_width=True, key="btn_submit"):
        if user_input:
            can_proceed, wait_sec = check_rpm_limit()
            if not can_proceed:
                st.warning(f"⏳ {wait_sec}초 후 이용해 주세요.")
            else:
                with st.spinner("분석 중..."):
                    try:
                        generate_card(f"Explain this target word: {user_input}", user_input)
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

# --- [학습 & 미션 영역] ---
if st.session_state.current_card:
    st.divider()
    card = st.session_state.current_card
    full_result = card["result"]
    
    study_content = full_result
    mission_question = ""
    hint_text = ""

    if "오늘의 미션" in full_result:
        split_key = "❓ **오늘의 미션**:" if "❓ **오늘의 미션**:" in full_result else "❓ 오늘의 미션:"
        parts = full_result.split(split_key)
        study_content = parts[0].strip()
        
        if len(parts) > 1:
            remaining = parts[1].strip()
            hint_key = "💡 **미션 힌트**:" if "💡 **미션 힌트**:" in remaining else "💡 미션 힌트:"
            if hint_key in remaining:
                m_parts = remaining.split(hint_key)
                mission_question = m_parts[0].strip()
                if len(m_parts) > 1:
                    hint_text = m_parts[1].strip()
            else:
                mission_question = remaining

    if not card.get("is_challenge_mode", False):
        st.markdown(study_content)
        st.divider()
        if st.button("🎯 오늘의 미션 도전하기 (학습 내용 가리기)", type="primary", use_container_width=True):
            card["is_challenge_mode"] = True
            st.rerun()

    else:
        with st.expander("🙈 학습 내용 가려짐 (클릭하여 다시 보기)", expanded=False):
            st.markdown(study_content)

        st.subheader(f"🎯 오늘의 미션 ({card['target']})")
        if mission_question:
            st.info(f"❓ **문제**: {mission_question}")

        if hint_text:
            if not card.get("show_hint", False):
                if st.button("💡 미션 힌트 보기", key=f"hint_btn_{card['target']}"):
                    card["show_hint"] = True
                    st.rerun()
            else:
                st.warning(f"💡 **미션 힌트**: {hint_text}")

        with st.form(key=f"mission_form_{card['target']}", clear_on_submit=False):
            answer_input = st.text_input("영문 답안 입력:", value=card.get("user_answer") or "", placeholder="영문장 작성 후 제출", key=f"quiz_answer_{card['target']}")
            submit_btn = st.form_submit_button("🎯 미션 제출 및 검증", type="primary", use_container_width=True)

        if submit_btn and answer_input:
            can_proceed, wait_sec = check_rpm_limit()
            if not can_proceed:
                st.warning(f"⏳ {wait_sec}초 후 이용 가능합니다.")
            else:
                with st.spinner("검증 중..."):
                    try:
                        check_response = client.models.generate_content(
                            model="gemini-3.5-flash-lite",
                            contents=f"Quiz Context:\n{card['result']}\n\nUser's Answer: {answer_input}",
                            config=types.GenerateContentConfig(
                                system_instruction=CHECK_PROMPT,
                                temperature=0.1,
                            ),
                        )
                        feedback = check_response.text
                        st.session_state.current_card["user_answer"] = answer_input
                        st.session_state.current_card["feedback"] = feedback
                        
                        if st.session_state.history:
                            st.session_state.history[-1]["user_answer"] = answer_input
                            st.session_state.history[-1]["feedback"] = feedback
                            save_history(st.session_state.history)
                        
                        st.success("검증 완료!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

    if card.get("feedback"):
        st.success(f"**피드백 결과:**\n\n{card['feedback']}")