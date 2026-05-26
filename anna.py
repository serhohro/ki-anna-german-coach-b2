import streamlit as st
import requests
import re
import random
import base64
from pathlib import Path
from gtts import gTTS
import tempfile
import os
import time
import speech_recognition as sr

BASE_PATH = Path(__file__).parent

# ============ ИМПОРТ СЛОВАРЯ ============
try:
    from words_b2 import WORDS
    print(f"✅ Загружено {len(WORDS)} слов из words_b2.py")
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    WORDS = {}
    st.warning("Файл words_b2.py не найден! Используется пустой словарь.")

# ============ ФРАЗЫ ============
PHRASES = {
    "как добраться до вокзала": "Wie komme ich zum Bahnhof?",
    "сколько стоит": "Wie viel kostet das?",
    "я сегодня выходной": "Heute habe ich frei",
    "спасибо": "Danke",
    "привет": "Hallo",
    "пока": "Tschüss",
    "как дела": "Wie geht es dir?",
}

# ============ ФУНКЦИЯ ПОИСКА ВИДЕО ============
def get_anna_video():
    for f in BASE_PATH.iterdir():
        if f.is_file() and f.suffix.lower() == '.mp4' and 'anna' in f.name.lower():
            return str(f)
    return None

# ============ ОЗВУЧКА (TTS) ============
def speak_german(text):
    """Генерирует mp3 и возвращает аудио-байты для проигрывания"""
    if not st.session_state.get('sound_activated', False):
        return None
    if not text or len(text) < 3:
        return None
    try:
        clean = re.sub(r'[а-яА-ЯёЁ]', '', text)
        clean = re.sub(r'[^\w\s\.\,\!\?\-]', '', clean)
        clean = clean.strip()[:200]
        if len(clean) < 2:
            return None
        tts = gTTS(text=clean, lang='de', slow=False)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
            tts.write_to_fp(fp)
            temp_path = fp.name
        with open(temp_path, 'rb') as f:
            audio_bytes = f.read()
        os.unlink(temp_path)
        return audio_bytes
    except Exception as e:
        print(f"TTS error: {e}")
        return None

# ============ АКТИВАЦИЯ АННЫ (один раз) ============
def activate_anna():
    """Показывает видео (видимое, автозапуск), ждёт 4 секунды, затем активирует TTS"""
    if not st.session_state.get('anna_activated', False):
        video_path = get_anna_video()
        if video_path:
            try:
                with open(video_path, "rb") as f:
                    video_data = base64.b64encode(f.read()).decode()
                # Показываем видео в основном окне
                st.markdown(f'''
                <div style="margin: 20px 0;">
                    <video autoplay controls style="width:100%; max-width:400px; border-radius:10px;">
                        <source src="data:video/mp4;base64,{video_data}" type="video/mp4">
                    </video>
                    <p>🎤 Анна говорит приветствие...</p>
                </div>
                ''', unsafe_allow_html=True)
                # Даём видео время на воспроизведение (4 секунды)
                time.sleep(4)
                st.session_state.anna_activated = True
                st.session_state.sound_activated = True
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка воспроизведения видео: {e}")
                st.session_state.anna_activated = True
                st.session_state.sound_activated = True
                st.rerun()
        else:
            st.error("❌ Видео anna.mp4 не найдено! Положите видео в папку с программой.")
            st.session_state.anna_activated = True
            st.session_state.sound_activated = True
            st.rerun()

# ============ ОСТАЛЬНЫЕ ФУНКЦИИ ============
def listen_audio():
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            st.info("🎤 Настройка...")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            st.warning("🎤 ГОВОРИТЕ СЕЙЧАС!")
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=6)
            st.info("🔄 Распознаю...")
            text = recognizer.recognize_google(audio, language="ru-RU")
            if text:
                st.success(f"✅ Распознано: {text}")
                return text
            return None
    except sr.WaitTimeoutError:
        st.error("⏰ Не услышала")
        return None
    except sr.UnknownValueError:
        st.error("❌ Не поняла")
        return None
    except Exception as e:
        st.error(f"Ошибка: {e}")
        return None

def find_translation(question):
    q = question.lower().strip()
    for key, value in PHRASES.items():
        if key in q:
            return value
    for de_word, data in WORDS.items():
        if data["ru"].lower() in q or de_word.lower() in q:
            return de_word
    return None

def get_ollama_models():
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        if r.status_code == 200:
            return [m['name'] for m in r.json().get('models', [])]
        return []
    except:
        return []

def ask_ollama(prompt, model):
    try:
        r = requests.post("http://127.0.0.1:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.3, "num_predict": 200}})
        if r.status_code == 200:
            response = r.json().get("response", "")
            response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
            return response.strip()
        return None
    except:
        return None

# ============ НАСТРОЙКА СТРАНИЦЫ ============
st.set_page_config(page_title="🇩🇪 Анна B2", page_icon="🇩🇪", layout="wide")

# Инициализация состояний
if 'anna_activated' not in st.session_state:
    st.session_state.anna_activated = False
if 'sound_activated' not in st.session_state:
    st.session_state.sound_activated = False
if 'model' not in st.session_state:
    st.session_state.model = None

# ============ САЙДБАР ============
with st.sidebar:
    if not st.session_state.anna_activated:
        st.markdown("### 🎬 Активация")
        if st.button("▶️ Запустить Анну", use_container_width=True):
            activate_anna()
        st.caption("Нажмите, чтобы Анна начала говорить")
    else:
        st.success("🔊 Анна активирована")
    
    st.markdown("---")
    st.markdown("### ⚙️ Настройки")
    
    st.markdown("### 🤖 Модель AI")
    models = get_ollama_models()
    if models:
        model = st.selectbox("Выберите модель", models)
        st.session_state.model = model
        st.success(f"✅ {model[:25]}")
    else:
        st.warning("⚠️ Ollama не запущена")
        st.info("Запустите: `ollama serve`")
    
    st.markdown("---")
    
    if 'known_words' not in st.session_state:
        st.session_state.known_words = []
    
    total = len(WORDS)
    learned = len(st.session_state.known_words)
    percent = int(learned / total * 100) if total > 0 else 0
    
    st.markdown(f"### 📊 Прогресс")
    st.markdown(f"✅ Выучено: **{learned}** / **{total}**")
    st.progress(percent / 100)
    
    st.markdown("---")
    st.caption("💡 Учите по 10-15 слов в день")

# ============ ЗАГОЛОВОК ============
st.markdown(f"""
<div style="text-align: center; padding: 1rem; background: linear-gradient(135deg, #667eea, #764ba2); border-radius: 1rem; margin-bottom: 1rem;">
    <h1 style="color: white;">🇩🇪 Анна — German Coach B2</h1>
    <p style="color: #e0d4ff;">📚 {total} слов B2 | 🎤 Голосовой ввод | 🤖 AI</p>
</div>
""", unsafe_allow_html=True)

# ============ РЕЖИМЫ ============
col1, col2, col3, col4 = st.columns(4)

if col1.button("💬 Чат", use_container_width=True):
    st.session_state.mode = "💬 Чат"
    st.rerun()
if col2.button("📚 Словарь", use_container_width=True):
    st.session_state.mode = "📚 Словарь"
    st.rerun()
if col3.button("🎯 Тест", use_container_width=True):
    st.session_state.mode = "🎯 Тест"
    st.rerun()
if col4.button("🎤 Голос", use_container_width=True):
    st.session_state.mode = "🎤 Голос"
    st.rerun()

mode = st.session_state.get('mode', '🎤 Голос')
st.markdown("---")

# ============ РЕЖИМ СЛОВАРЯ ============
if mode == "📚 Словарь":
    st.subheader(f"📚 Словарь B2 — {total} слов")
    
    search = st.text_input("🔍 Поиск", placeholder="Введите слово...")
    
    filtered = {k: v for k, v in WORDS.items() if not search or search.lower() in k.lower() or search.lower() in v["ru"].lower()}
    st.markdown(f"🔎 Найдено: **{len(filtered)}** слов из {total}")
    
    for word, data in list(filtered.items())[:50]:
        with st.expander(f"📖 **{word}** — {data['ru']}"):
            st.markdown(f"**Пример:** {data['example']}")
            st.markdown(f"**Перевод:** {data['example_ru']}")
            
            if word in st.session_state.known_words:
                st.markdown("✅ **Выучено**")
            else:
                if st.button(f"✓ Отметить", key=f"learn_{word}"):
                    st.session_state.known_words.append(word)
                    st.rerun()
            
            # Кнопки озвучки (только после активации)
            if st.session_state.sound_activated:
                if st.button(f"🔊 Слово", key=f"speak_{word}"):
                    audio = speak_german(word)
                    if audio:
                        st.audio(audio, format='audio/mp3', start_time=0)
                if st.button(f"🔊 Пример", key=f"speak_ex_{word}"):
                    audio = speak_german(data['example'])
                    if audio:
                        st.audio(audio, format='audio/mp3', start_time=0)

# ============ РЕЖИМ ЧАТА ============
elif mode == "💬 Чат":
    st.subheader("💬 Чат с Анной")
    
    if 'messages' not in st.session_state:
        st.session_state.messages = [{"role": "anna", "text": f"🇩🇪 Hallo! Ich bin Anna. Ich kenne {total} Wörter!"}]
    
    for idx, msg in enumerate(st.session_state.messages[-20:]):
        if msg['role'] == 'user':
            st.markdown(f"<div style='background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 10px 15px; border-radius: 18px 18px 5px 18px; margin: 8px 0; max-width: 80%; margin-left: auto;'>👤 {msg['text']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='background: #f0f2f6; padding: 10px 15px; border-radius: 18px 18px 18px 5px; margin: 8px 0; max-width: 80%;'>🇩🇪 {msg['text']}</div>", unsafe_allow_html=True)
            # Озвучиваем только последний ответ Анны (если звук активирован)
            if st.session_state.sound_activated and 'audio' in msg and msg['audio'] and idx == len(st.session_state.messages[-20:]) - 1:
                if os.path.exists(msg['audio']):
                    with open(msg['audio'], 'rb') as f:
                        audio_bytes = f.read()
                    st.audio(audio_bytes, format='audio/mp3', start_time=0)
    
    user_input = st.text_area("Ваш вопрос:", height=80, placeholder="Например: Was bedeutet 'sich einsetzen für'?")
    
    if st.button("📨 Отправить", type="primary"):
        if user_input:
            st.session_state.messages.append({"role": "user", "text": user_input})
            
            if st.session_state.model:
                response = ask_ollama(f"Отвечай на немецком кратко. Студент: {user_input}", st.session_state.model)
            else:
                response = f"🇩🇪 Gute Frage zu '{user_input}'!"
            
            if not response:
                response = f"🇩🇪 Danke für deine Frage!"
            
            # Генерируем аудио только если звук активирован
            audio_file = None
            if st.session_state.sound_activated:
                audio_file = speak_german(response)
            st.session_state.messages.append({"role": "anna", "text": response, "audio": audio_file})
            st.rerun()

# ============ РЕЖИМ ТЕСТА ============
elif mode == "🎯 Тест":
    st.subheader("🎯 Проверь знания B2")
    
    # Инициализация
    if 'quiz_words_list' not in st.session_state:
        st.session_state.quiz_words_list = list(WORDS.keys())
        st.session_state.quiz_current_index = 0
        st.session_state.quiz_answered = False
        st.session_state.quiz_correct = st.session_state.get('quiz_correct', 0)
        st.session_state.quiz_total = st.session_state.get('quiz_total', 0)
        st.session_state.quiz_user_answer = ""
        st.session_state.quiz_last_result = None
        st.session_state.quiz_last_message = ""
        st.session_state.quiz_show_balloons = False  # Флаг для шариков
    
    total_words = len(st.session_state.quiz_words_list)
    current_idx = st.session_state.quiz_current_index
    
    # Прогресс и статистика
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"📊 **Слово {current_idx + 1} из {total_words}**")
    with col2:
        if st.session_state.quiz_total > 0:
            score = int(st.session_state.quiz_correct / st.session_state.quiz_total * 100)
            st.markdown(f"✅ **Правильно:** {st.session_state.quiz_correct} / {st.session_state.quiz_total} ({score}%)")
    
    st.progress((current_idx) / total_words if total_words > 0 else 0)
    
    # Текущее слово
    word = st.session_state.quiz_words_list[current_idx]
    data = WORDS.get(word, {})
    correct_raw = data.get("ru", "")
    correct_variants = [v.strip().lower() for v in correct_raw.split(',')]
    main_correct = correct_variants[0]
    example = data.get("example", "")
    example_ru = data.get("example_ru", "")
    
    # Отображение вопроса
    st.markdown(f"### Как переводится слово?")
    st.markdown(f"## **{word}**")
    if example:
        st.caption(f"📝 Подсказка: _{example}_")
        st.caption(f"💡 Перевод: _{example_ru}_")
    
    col_q1, col_q2 = st.columns([4, 1])
    with col_q2:
        if st.button("🔊 Озвучить слово", key="quiz_speak_word"):
            audio = speak_german(word)
            if audio:
                st.audio(audio, format='audio/mp3', autoplay=True)
    
    st.markdown("---")
    
    # === ШАРИКИ ПРИ ПРАВИЛЬНОМ ОТВЕТЕ ===
    if st.session_state.quiz_show_balloons:
        st.balloons()
        st.session_state.quiz_show_balloons = False
    
    # === ПОКАЗ РЕЗУЛЬТАТА ПОСЛЕДНЕГО ОТВЕТА ===
    if st.session_state.quiz_last_result == 'correct':
        st.success(st.session_state.quiz_last_message)
    elif st.session_state.quiz_last_result == 'wrong':
        st.error(st.session_state.quiz_last_message)
        if example:
            st.info(f"💡 Запомните: {example} — {example_ru}")
    
    # === ВВОД ОТВЕТА (только если ещё не отвечали) ===
    if not st.session_state.quiz_answered:
        input_mode = st.radio("Способ ввода:", ["📋 Выбрать из вариантов", "✏️ Написать вручную"], horizontal=True)
        
        if input_mode == "📋 Выбрать из вариантов":
            # Генерация вариантов ответов
            all_translations = []
            for w, d in WORDS.items():
                trans = d.get("ru", "").split(',')[0].strip().lower()
                if trans and trans not in all_translations:
                    all_translations.append(trans)
            
            options = [main_correct]
            others = [t for t in all_translations if t != main_correct]
            if len(others) >= 3:
                options.extend(random.sample(others, 3))
            else:
                options.extend(others)
            random.shuffle(options)
            
            for opt in options:
                if st.button(opt, key=f"quiz_opt_{opt}", use_container_width=True):
                    st.session_state.quiz_total += 1
                    if opt.strip().lower() in correct_variants:
                        st.session_state.quiz_correct += 1
                        st.session_state.quiz_last_result = 'correct'
                        st.session_state.quiz_last_message = "✅ Правильно!"
                        st.session_state.quiz_show_balloons = True  # Включаем шарики
                    else:
                        st.session_state.quiz_last_result = 'wrong'
                        st.session_state.quiz_last_message = f"❌ Неправильно! Правильно: {main_correct}"
                    st.session_state.quiz_answered = True
                    st.rerun()
        
        else:  # Режим "Написать вручную"
            user_answer = st.text_input("Введите перевод слова:", value=st.session_state.quiz_user_answer, 
                                         placeholder="Например: сохранять", key="quiz_manual_input")
            st.session_state.quiz_user_answer = user_answer
            
            if st.button("✅ Проверить ответ", type="primary", use_container_width=True):
                st.session_state.quiz_total += 1
                if user_answer.strip().lower() in correct_variants:
                    st.session_state.quiz_correct += 1
                    st.session_state.quiz_last_result = 'correct'
                    st.session_state.quiz_last_message = "✅ Правильно!"
                    st.session_state.quiz_show_balloons = True  # Включаем шарики
                else:
                    st.session_state.quiz_last_result = 'wrong'
                    st.session_state.quiz_last_message = f"❌ Неправильно! Правильно: {main_correct}"
                st.session_state.quiz_answered = True
                st.rerun()
    
    # === НАВИГАЦИОННЫЕ КНОПКИ ===
    st.markdown("---")
    st.markdown("### 🎮 Навигация")
    
    col_nav1, col_nav2, col_nav3, col_nav4 = st.columns([1, 1, 1, 1])
    
    with col_nav1:
        if current_idx > 0:
            if st.button("◀ Предыдущее", use_container_width=True):
                st.session_state.quiz_current_index -= 1
                st.session_state.quiz_answered = False
                st.session_state.quiz_last_result = None
                st.session_state.quiz_user_answer = ""
                st.rerun()
        else:
            st.button("◀ Предыдущее", disabled=True, use_container_width=True)
    
    with col_nav2:
        if current_idx < total_words - 1:
            if st.button("Следующее ▶", use_container_width=True, type="primary"):
                st.session_state.quiz_current_index += 1
                st.session_state.quiz_answered = False
                st.session_state.quiz_last_result = None
                st.session_state.quiz_user_answer = ""
                st.rerun()
        else:
            st.button("Следующее ▶", disabled=True, use_container_width=True)
    
    with col_nav3:
        if st.button("🔄 Случайное", use_container_width=True):
            random_index = random.randint(0, total_words - 1)
            st.session_state.quiz_current_index = random_index
            st.session_state.quiz_answered = False
            st.session_state.quiz_last_result = None
            st.session_state.quiz_user_answer = ""
            st.rerun()
    
    with col_nav4:
        if st.button("🏆 Завершить", use_container_width=True):
            if st.session_state.quiz_total > 0:
                st.success(f"🏆 Тест завершён! Результат: {st.session_state.quiz_correct} из {st.session_state.quiz_total}")
                st.balloons()  # Шарики при завершении
            # Сброс теста
            st.session_state.quiz_words_list = list(WORDS.keys())
            st.session_state.quiz_current_index = 0
            st.session_state.quiz_answered = False
            st.session_state.quiz_correct = 0
            st.session_state.quiz_total = 0
            st.session_state.quiz_last_result = None
            st.session_state.quiz_user_answer = ""
            st.rerun()
    
    # Индикатор статуса
    st.markdown("---")
    if st.session_state.quiz_answered:
        st.info("💡 **Вы уже ответили на это слово.** Нажмите «Следующее» или другое слово, чтобы продолжить.")
    else:
        st.info("📝 **Выберите ответ или введите перевод.**")

# ============ РЕЖИМ ГОЛОСА ============
elif mode == "🎤 Голос":
    st.subheader("🎤 Голосовой переводчик")
    
    if 'voice_messages' not in st.session_state:
        st.session_state.voice_messages = []
    
    for idx, msg in enumerate(st.session_state.voice_messages[-15:]):
        if msg['role'] == 'user':
            st.markdown(f"<div style='background: #667eea; color: white; padding: 10px 15px; border-radius: 18px 18px 5px 18px; margin: 8px 0; max-width: 80%; margin-left: auto;'>🎤 {msg['text']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='background: #f0f2f6; padding: 10px 15px; border-radius: 18px 18px 18px 5px; margin: 8px 0; max-width: 80%;'>🇩🇪 {msg['text']}</div>", unsafe_allow_html=True)
            if st.session_state.sound_activated and 'audio' in msg and msg['audio'] and idx == len(st.session_state.voice_messages[-15:]) - 1:
                if os.path.exists(msg['audio']):
                    with open(msg['audio'], 'rb') as f:
                        audio_bytes = f.read()
                    st.audio(audio_bytes, format='audio/mp3', start_time=0)
    
    st.markdown("---")
    st.markdown("### ✏️ Введите текст для перевода:")
    
    text_input = st.text_input("", placeholder="Например: как добраться до вокзала", key="voice_text")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("📝 Перевести текст", use_container_width=True):
            if text_input:
                st.session_state.voice_messages.append({"role": "user", "text": text_input})
                translation = find_translation(text_input)
                if not translation and st.session_state.model:
                    translation = ask_ollama(f"Переведи на немецкий: {text_input}", st.session_state.model)
                if not translation:
                    translation = f'Wie sagt man "{text_input}" auf Deutsch?'
                audio_file = speak_german(translation) if st.session_state.sound_activated else None
                st.session_state.voice_messages.append({"role": "anna", "text": translation, "audio": audio_file})
                st.rerun()
    
    with col2:
        if st.button("🎤 Голосовой ввод", use_container_width=True):
            user_text = listen_audio()
            if user_text:
                st.session_state.voice_messages.append({"role": "user", "text": user_text})
                translation = find_translation(user_text)
                if not translation and st.session_state.model:
                    translation = ask_ollama(f"Переведи на немецкий: {user_text}", st.session_state.model)
                if not translation:
                    translation = f'Wie sagt man "{user_text}" auf Deutsch?'
                audio_file = speak_german(translation) if st.session_state.sound_activated else None
                st.session_state.voice_messages.append({"role": "anna", "text": translation, "audio": audio_file})
                st.rerun()
            else:
                st.warning("Не удалось распознать речь")

    if st.button("🗑️ Очистить историю", use_container_width=True):
        st.session_state.voice_messages = []
        st.rerun()

# ============ ФУТЕР ============
st.markdown("---")
st.caption(f"🇩🇪 Анна B2 Coach | 📚 {total} слов | 🤖 Модель: {st.session_state.get('model', 'нет')} | 🔊 {'Вкл' if st.session_state.sound_activated else 'Выкл'}")