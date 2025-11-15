# app.py — АГЕНТ НА RENDER.COM
from flask import Flask, request, jsonify, render_template_string
from langchain_ollama import ChatOllama
import chromadb, os, json, datetime, fitz, whisper
from PIL import Image
import pytesseract

app = Flask(__name__)

# === МОДЕЛЬ ===
llm = ChatOllama(model="llama3.1:8b", temperature=0.7)

# === ПАМЯТЬ ===
db = chromadb.PersistentClient(path="memory_db")
col = db.get_or_create_collection("memory")

# === WHISPER ===
try:
    whisper_model = whisper.load_model("tiny")
except: whisper_model = None

# === ИНСТРУМЕНТЫ ===
def web_search(q):
    try:
        from duckduckgo_search import DDGS
        r = [i for i in DDGS().text(q, max_results=2)]
        return json.dumps(r, ensure_ascii=False, indent=2)
    except: return "Нет интернета"

def save_memory(key, content):
    try:
        col.add(ids=[key], documents=[content[:50000]])
    except: pass

def search_memory(q):
    try:
        r = col.query(query_texts=[q], n_results=3)
        return "\n".join(r['documents'][0]) if r['documents'][0] else ""
    except: return ""

# === ЗАГРУЗКА ФАЙЛОВ ===
def load_all():
    for folder in ["articles", "videos", "audio", "screenshots"]:
        if not os.path.exists(folder): continue
        for f in os.listdir(folder):
            path = f"{folder}/{f}"
            if f.endswith(".pdf"):
                doc = fitz.open(path)
                text = "".join(p.get_text() for p in doc)
                save_memory(f"pdf_{f}", text)
            elif f.endswith((".mp4", ".mp3", ".wav")) and whisper_model:
                text = whisper_model.transcribe(path, language="ru")["text"]
                save_memory(f"media_{f}", text)
            elif f.endswith((".png", ".jpg")):
                text = pytesseract.image_to_string(Image.open(path), lang="rus+eng")
                save_memory(f"ocr_{f}", text)

# === ГЛАВНАЯ СТРАНИЦА ===
@app.route("/")
def index():
    return render_template_string("""
    <h1>Аватар в облаке (Render.com)</h1>
    <p>Агент работает 24/7!</p>
    <form action="/chat" method="post">
        <input name="q" placeholder="Твой вопрос..." style="width:300px;padding:10px;font-size:16px;">
        <button type="submit" style="padding:10px 20px;">Отправить</button>
    </form>
    <p><small>Команды: <b>загрузи всё</b>, <b>привет</b></small></p>
    """)

# === ЧАТ ===
@app.route("/chat", methods=["POST"])
def chat():
    q = request.form["q"]
    if q == "загрузи всё":
        load_all()
        return "<p>Всё загружено!</p><a href='/'>← Назад</a>"

    mem = search_memory(q)
    prompt = f"Вопрос: {q}\nПамять: {mem}\nИнструменты: web_search\nЕсли нужно — JSON: ```json {{\"tool\":\"web_search\",\"args\":{{\"query\":\"...\"}}}}```"

    try:
        resp = llm.invoke(prompt).content
        if "```json" in resp:
            j = json.loads(resp.split("```json")[1].split("```")[0].strip())
            if j["tool"] == "web_search":
                result = web_search(j["args"]["query"])
                return f"<pre>{result}</pre><a href='/'>← Назад</a>"
        return f"<p><b>Аватар:</b> {resp}</p><a href='/'>← Назад</a>"
    except Exception as e:
        return f"<p>Ошибка: {e}</p><a href='/'>← Назад</a>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
