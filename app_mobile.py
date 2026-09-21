import json
import os
import random
import time
from google import genai
from google.genai import types
import streamlit as st

DATA_FILE = "vocabulary.json"

# 모바일 화면 비율 및 레이아웃 설정
st.set_page_config(
    page_title="영어 AI 튜터",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# 모바일 커스텀 CSS
st.markdown(
    """
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; padding-left: 0.8rem; padding-right: 0.8rem; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.2rem; font-weight: bold; }
    .stTextInput>div>div>input { font-size: 16px; }
</style>
""",
    unsafe_allow_html=True,
)

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

# 실력 테스트용 Session State
if "test_questions" not in st.session_state:
    st.session_state.test_questions = None
if "test_results" not in st.session_state:
    st.session_state.test_results = None
if "test_difficulty" not in st.session_state:
    st.session_state.test_difficulty = "중 (중급)"

SYSTEM_PROMPT = """
You are a Steven English style tutor focusing on visual concepts and left-to-right progressive reading.

[Absolute Restriction]
1. NEVER output abstract, figurative, or cultural idioms.
2. Focus ONLY on concrete, physical, space-based, and movement-based English expressions.

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

💡 **미션 힌트**: [Provide structural pattern ONLY with placeholders]
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

# 난이도별 가이드라인 생성 함수
def get_test_eval_prompt(difficulty):
    difficulty_instructions = {
        "하 (초급)": """
- Difficulty Level: Low (Beginner)
- Grade leniently regarding complex clause structures.
- Focus strictly on whether the fundamental root image/meaning of the target expression is understood in a simple, clear sentence.
""",
        "중 (중급)": """
- Difficulty Level: Medium (Intermediate)
- Grade with moderate strictness.
- Expect standard, natural sentence construction with accurate word order, basic modifiers, and correct tense usage.
""",
        "상 (고급)": """
- Difficulty Level: High (Advanced)
- Grade strictly with high expectations.
- Evaluate for rich vocabulary, advanced clause/phrasal structures (relative clauses, conjunctions, complex modifiers), and highly natural native-level phrasing.
"""
    }

    selected_guide = difficulty_instructions.get(difficulty, difficulty_instructions["중 (중급)"])

    return f"""
You are an English exam grader evaluating students at the selected difficulty level: **{difficulty}**.

Difficulty Standard:
{selected_guide}

Evaluation Rules:
1. Grade each question strictly using one of these three status labels:
   - "정답" (100% correct matching the target difficulty level)
   - "부분 정답" (Target word used, but grammar/word order has small errors or structure falls slightly short of the target difficulty)
   - "오답" (Incorrect target word, major grammatical failure, or completely inadequate for the difficulty)
2. Score allocation: "정답" = 10 points, "부분 정답" = 5 points, "오답" = 0 points.
3. Write detailed feedback in Korean explaining why it's correct/incorrect according to the chosen difficulty level ({difficulty}) and provide an ideal model answer in English that matches this level.

Required Response Format (Use exact markdown headers):
### 📊 난이도 [{difficulty}] 평가 결과 (최종 점수: [Total Score] / [Max Score]점)

---

#### Q1. [Target Word]
- **상태**: [정답 / 부분 정답 / 오답]
- **내 답안**: [User Answer]
- **모범 답안 ({difficulty} 수준)**: [Ideal Model English Sentence]
- **해설**: [Korean Explanation considering difficulty requirement]

(Repeat Q2, Q3... sequentially for all questions)
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

                if st.button(
                    "🗑️ 삭제", key=f"del_{idx}", use_container_width=True
                ):
                    st.session_state.history.pop(idx)
                    save_history(st.session_state.history)
                    st.rerun()

        st.divider()
        if st.button(
            "🔥 단어장 전체 삭제", type="primary", use_container_width=True
        ):
            st.session_state.history = []
            save_history([])
            st.session_state.current_card = None
            st.session_state.test_questions = None
            st.session_state.test_results = None
            st.rerun()

# --- [메인 영역] ---
st.title("🎬 영어 AI 튜터")

tab1, tab2, tab3 = st.tabs(
    ["🎲 자동 추천", "✏️ 직접 입력", "📝 실력 테스트"]
)


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
            cleaned = (
                line.replace("*", "")
                .replace("📌", "")
                .replace("주제/단어", "")
                .replace(":", "")
                .strip()
            )
            if cleaned:
                target_word = cleaned
            break

    new_card = {
        "target": target_word,
        "result": result_text,
        "user_answer": None,
        "feedback": None,
        "is_challenge_mode": False,
        "show_hint": False,
    }

    st.session_state.current_card = new_card
    st.session_state.history.append(new_card)
    save_history(st.session_state.history)


with tab1:
    if st.button(
        "🚀 새로운 주제로 학습 시작",
        type="primary",
        use_container_width=True,
        key="btn_auto",
    ):
        current_time = time.time()
        if (
            current_time - st.session_state.last_click_time
            < COOLDOWN_SECONDS
        ):
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
                            "a core basic verb with rich physical root images",
                        ]
                        selected_category = random.choice(CONCEPT_CATEGORIES)
                        learned_targets = [
                            item.get("target", "").lower()
                            for item in st.session_state.history
                            if item.get("target")
                        ]
                        exclusion_clause = (
                            f" Do NOT pick these: [{', '.join(set(learned_targets))}]."
                            if learned_targets
                            else ""
                        )

                        prompt = f"Pick 1 NEW English target in category '{selected_category}'. Concrete physical action/space ONLY. Seed: {random.randint(10000,99999)}.{exclusion_clause}"
                        generate_card(prompt, "추천 주제")
                        st.session_state.last_click_time = time.time()
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

with tab2:
    user_input = st.text_input(
        "학습할 표현:", placeholder="예: at, look for", key="user_text_input"
    )
    if st.button(
        "학습하기", type="primary", use_container_width=True, key="btn_submit"
    ):
        if user_input:
            can_proceed, wait_sec = check_rpm_limit()
            if not can_proceed:
                st.warning(f"⏳ {wait_sec}초 후 이용해 주세요.")
            else:
                with st.spinner("분석 중..."):
                    try:
                        generate_card(
                            f"Explain this target word: {user_input}", user_input
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

# --- TAB 3: 실력 테스트 (난이도 선택 기능 반영) ---
with tab3:
    st.subheader("📝 단어장 기반 실력 테스트")
    st.caption(
        "단어장에 등록된 학습 항목(최대 10개) 중 난이도를 선택하여 힌트 없이 테스트합니다."
    )

    if not st.session_state.history:
        st.info(
            "단어장이 비어 있습니다. 먼저 학습을 진행해 단어장에 기록을 추가해주세요!"
        )
    else:
        # 난이도 선택 분할 제어 UI (하 / 중 / 상)
        difficulty = st.radio(
            "🎯 테스트 난이도를 선택하세요:",
            ["하 (초급)", "중 (중급)", "상 (고급)"],
            index=1,
            horizontal=True,
            key="radio_difficulty",
        )
        st.session_state.test_difficulty = difficulty

        # 난이도별 요구사항 안내
        if difficulty == "하 (초급)":
            st.caption("💡 **하 수준**: 단어의 핵심 의미를 살린 명확하고 단순한 기초 문장을 완성하세요.")
        elif difficulty == "중 (중급)":
            st.caption("💡 **중 수준**: 올바른 시제와 적절한 수식어를 포함한 자연스러운 완성형 문장을 작성하세요.")
        else:
            st.caption("💡 **상 수준**: 다양하고 복합적인 문장 구조(관계사, 부사절 등)를 활용한 완성도 높은 문장을 작성하세요.")

        st.write("")

        # 시험 시작 / 재시작 버튼
        if st.button(
            f"🎲 [{difficulty}] 시험 출제하기",
            type="primary",
            use_container_width=True,
            key="btn_start_test",
        ):
            sample_size = min(10, len(st.session_state.history))
            selected_items = random.sample(st.session_state.history, sample_size)

            questions = []
            for item in selected_items:
                full_text = item["result"]
                q_text = ""
                if "오늘의 미션" in full_text:
                    split_key = (
                        "❓ **오늘의 미션**:"
                        if "❓ **오늘의 미션**:" in full_text
                        else "❓ 오늘의 미션:"
                    )
                    parts = full_text.split(split_key)
                    if len(parts) > 1:
                        remaining = parts[1].strip()
                        hint_key = (
                            "💡 **미션 힌트**:"
                            if "💡 **미션 힌트**:" in remaining
                            else "💡 미션 힌트:"
                        )
                        q_text = remaining.split(hint_key)[0].strip()
                if not q_text:
                    q_text = f"'{item['target']}' 표현을 활용하여 주어진 상황에 맞는 영문장을 작성하세요."

                questions.append({"target": item["target"], "question": q_text})

            st.session_state.test_questions = questions
            st.session_state.test_results = None
            st.rerun()

        # 시험지 출력
        if st.session_state.test_questions:
            st.divider()
            st.markdown(
                f"### 📋 테스트 문제 (난이도: **{st.session_state.test_difficulty}**, 총 {len(st.session_state.test_questions)}문항)"
            )

            with st.form(key="test_form"):
                user_answers = {}
                for idx, q in enumerate(st.session_state.test_questions):
                    st.markdown(f"**Q{idx+1}. [{q['target']}]** {q['question']}")
                    user_answers[f"q_{idx}"] = st.text_input(
                        f"Q{idx+1} 영문 답안:",
                        key=f"test_ans_{idx}",
                        placeholder=f"[{st.session_state.test_difficulty}] 수준에 맞추어 영문으로 작성하세요...",
                    )
                    st.write("")

                submit_test = st.form_submit_button(
                    "💯 시험 제출 및 채점하기",
                    type="primary",
                    use_container_width=True,
                )

            if submit_test:
                can_proceed, wait_sec = check_rpm_limit()
                if not can_proceed:
                    st.warning(f"⏳ {wait_sec}초 후 이용 가능합니다.")
                else:
                    with st.spinner("AI 선생님이 선택하신 난이도 기준에 맞추어 채점 중입니다..."):
                        try:
                            eval_payload = [f"Selected Difficulty Level: {st.session_state.test_difficulty}\n"]
                            for idx, q in enumerate(
                                st.session_state.test_questions
                            ):
                                ans = user_answers.get(f"q_{idx}", "")
                                eval_payload.append(
                                    f"Q{idx+1}. Target: {q['target']}\nQuestion: {q['question']}\nStudent Answer: {ans}"
                                )

                            prompt_content = "\n\n".join(eval_payload)
                            dynamic_prompt = get_test_eval_prompt(st.session_state.test_difficulty)

                            test_response = client.models.generate_content(
                                model="gemini-3.5-flash-lite",
                                contents=prompt_content,
                                config=types.GenerateContentConfig(
                                    system_instruction=dynamic_prompt,
                                    temperature=0.2,
                                ),
                            )
                            st.session_state.test_results = test_response.text
                            st.rerun()
                        except Exception as e:
                            st.error(f"채점 과정 중 오류가 발생했습니다: {e}")

        # 채점 결과 출력
        if st.session_state.test_results:
            st.divider()
            st.markdown("## 📝 채점 결과 레포트")
            st.markdown(st.session_state.test_results)


# --- [학습 & 미션 영역 (기존 1개 미션 플로우 유지)] ---
if st.session_state.current_card:
    st.divider()
    card = st.session_state.current_card
    full_result = card["result"]

    study_content = full_result
    mission_question = ""
    hint_text = ""

    if "오늘의 미션" in full_result:
        split_key = (
            "❓ **오늘의 미션**:"
            if "❓ **오늘의 미션**:" in full_result
            else "❓ 오늘의 미션:"
        )
        parts = full_result.split(split_key)
        study_content = parts[0].strip()

        if len(parts) > 1:
            remaining = parts[1].strip()
            hint_key = (
                "💡 **미션 힌트**:"
                if "💡 **미션 힌트**:" in remaining
                else "💡 미션 힌트:"
            )
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
        if st.button(
            "🎯 오늘의 미션 도전하기 (학습 내용 가리기)",
            type="primary",
            use_container_width=True,
        ):
            card["is_challenge_mode"] = True
            st.rerun()

    else:
        with st.expander(
            "🙈 학습 내용 가려짐 (클릭하여 다시 보기)", expanded=False
        ):
            st.markdown(study_content)

        st.subheader(f"🎯 오늘의 미션 ({card['target']})")
        if mission_question:
            st.info(f"❓ **문제**: {mission_question}")

        if hint_text:
            if not card.get("show_hint", False):
                if st.button(
                    "💡 미션 힌트 보기", key=f"hint_btn_{card['target']}"
                ):
                    card["show_hint"] = True
                    st.rerun()
            else:
                st.warning(f"💡 **미션 힌트**: {hint_text}")

        with st.form(
            key=f"mission_form_{card['target']}", clear_on_submit=False
        ):
            answer_input = st.text_input(
                "영문 답안 입력:",
                value=card.get("user_answer") or "",
                placeholder="영문장 작성 후 제출",
                key=f"quiz_answer_{card['target']}",
            )
            submit_btn = st.form_submit_button(
                "🎯 미션 제출 및 검증",
                type="primary",
                use_container_width=True,
            )

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
                        st.session_state.current_card["user_answer"] = (
                            answer_input
                        )
                        st.session_state.current_card["feedback"] = feedback

                        if st.session_state.history:
                            st.session_state.history[-1]["user_answer"] = (
                                answer_input
                            )
                            st.session_state.history[-1]["feedback"] = (
                                feedback
                            )
                            save_history(st.session_state.history)

                        st.success("검증 완료!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

    if card.get("feedback"):
        st.success(f"**피드백 결과:**\n\n{card['feedback']}")