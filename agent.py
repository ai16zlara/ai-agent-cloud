# agent.py — МАКСИМАЛЬНОЕ ЛОГИРОВАНИЕ + БЕЗ ОШИБОК
from langchain_ollama import ChatOllama
import chromadb
from duckduckgo_search import DDGS
import json, datetime, traceback, sys

# === ЛОГИРОВАНИЕ В ФАЙЛ ===
LOG_FILE = "agent_debug.log"
def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")

log("=== АГЕНТ ЗАПУЩЕН ===")

# === МОДЕЛЬ ===
try:
    log("Инициализация модели llama3.1:8b...")
    llm = ChatOllama(model="llama3.1:8b", temperature=0.7)
    log("Модель успешно загружена")
except Exception as e:
    log(f"ОШИБКА МОДЕЛИ: {e}\n{traceback.format_exc()}")
    sys.exit(1)

# === ПАМЯТЬ ===
try:
    log("Инициализация ChromaDB...")
    db = chromadb.PersistentClient(path="memory_db")
    col = db.get_or_create_collection("memory")
    log("Память готова")
except Exception as e:
    log(f"ОШИБКА ПАМЯТИ: {e}\n{traceback.format_exc()}")

# === ИНСТРУМЕНТЫ ===
def web_search(q):
    log(f"→ Поиск в интернете: {q}")
    try:
        results = [r for r in DDGS().text(q, max_results=3)]
        result = json.dumps(results, ensure_ascii=False, indent=2)
        log(f"Поиск успешен: {len(results)} результатов")
        return result
    except Exception as e:
        log(f"ОШИБКА ПОИСКА: {e}\n{traceback.format_exc()}")
        return "Нет интернета"

def save(text):
    log(f"→ Сохранение в память: {text[:50]}...")
    try:
        col.add(ids=[str(datetime.datetime.now().timestamp())], documents=[text])
        log("Сохранено")
    except Exception as e:
        log(f"ОШИБКА СОХРАНЕНИЯ: {e}\n{traceback.format_exc()}")

def get_mem(q):
    log(f"→ Поиск в памяти: {q}")
    try:
        r = col.query(query_texts=[q], n_results=3)
        docs = r['documents'][0]
        if docs:
            log(f"Найдено в памяти: {len(docs)} записей")
            return "\n".join(docs)
        else:
            log("Память пуста")
            return ""
    except Exception as e:
        log(f"ОШИБКА ПАМЯТИ: {e}\n{traceback.format_exc()}")
        return ""

# === ЗАПУСК ===
log("Аватар готов! Вводи (или 'выход')")
print("\nАватар готов! (введи 'выход' для завершения)")
print("-" * 60)

while True:
    try:
        q = input("\nТы: ").strip()
        if not q:
            continue
        log(f"ПОЛЬЗОВАТЕЛЬ: {q}")

        if q.lower() in ["выход", "exit", "q"]:
            log("Пользователь завершил сессию")
            print("Аватар выключен.")
            break

        # Память
        log("Шаг 1: Поиск в памяти...")
        mem = get_mem(q)

        # Промпт — строка за строкой
        log("Шаг 2: Формирование промпта...")
        prompt_lines = [
            "Ты — Аватар, умный локальный ИИ.",
            f"ПАМЯТЬ: {mem}",
            f"ВОПРОС: {q}",
            "ИНСТРУМЕНТЫ: web_search(query)",
            "Если нужно — используй JSON:",
            "```json",
            '{"tool": "web_search", "args": {"query": "что искать"}}',
            "```",
            "Сначала подумай, потом действуй."
        ]
        prompt = "\n".join(prompt_lines)
        log(f"Промпт сформирован ({len(prompt_lines)} строк)")

        # Ответ
        log("Шаг 3: Отправка в LLM...")
        try:
            response = llm.invoke(prompt)
            resp = response.content if hasattr(response, 'content') else str(response)
            log("Ответ получен от модели")
        except Exception as e:
            log(f"ОШИБКА LLM: {e}\n{traceback.format_exc()}")
            resp = "Ошибка модели"
        
        log(f"Сырой ответ: {resp[:200]}...")

        # JSON
        if "```json" in resp:
            log("Шаг 4: Обнаружен JSON — парсинг...")
            try:
                start = resp.find("```json") + 7
                end = resp.find("```", start)
                json_str = resp[start:end].strip()
                log(f"JSON извлечён: {json_str}")
                tool_call = json.loads(json_str)
                tool = tool_call["tool"]
                args = tool_call["args"]
                log(f"Инструмент: {tool}, аргументы: {args}")

                if tool == "web_search":
                    result = web_search(args["query"])
                    print(f"\n[ПОИСК В ИНТЕРНЕТЕ]\n{result}")
                    final = result
                else:
                    print(f"\nАватар: {resp}")
                    final = resp

            except Exception as e:
                log(f"ОШИБКА JSON: {e}\n{traceback.format_exc()}")
                print(f"\nАватар: {resp}")
                final = resp
        else:
            log("JSON не найден — прямой ответ")
            print(f"\nАватар: {resp}")
            final = resp

        # Сохранение
        log("Шаг 5: Сохранение в память...")
        save(f"Q: {q} | A: {final}")
        log("Цикл завершён успешно\n")

    except KeyboardInterrupt:
        log("Прервано пользователем")
        print("\nОстановлено.")
        break
    except Exception as e:
        log(f"КРИТИЧЕСКАЯ ОШИБКА: {e}\n{traceback.format_exc()}")
        print(f"\nОшибка: {e}")

log("=== АГЕНТ ЗАВЕРШЁН ===")