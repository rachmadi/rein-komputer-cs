import urllib.request
import json
import time
import logging

logger = logging.getLogger(__name__)

def classify_intent_llm(user_text: str, model: str = "gemma4:e4b") -> tuple[bool, float]:
    """
    Returns (True if product_search, False otherwise), and latency_s
    """
    low = user_text.lower()
    computer_terms = ["laptop", "komputer", "pc", "notebook", "desktop", "gaming", "ram", "vram", "ssd", "rtx", "gtx", "core i", "ryzen", "printer", "monitor"]
    if any(t in low for t in computer_terms):
        return True, 0.001

    prompt = f"Kalimat: '{user_text}'. Apakah kalimat ini mencari atau bertanya spesifikasi/rekomendasi komputer/laptop? Jawab HANYA 'YA' atau 'TIDAK'."
    req_body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 250, "temperature": 0.0}
    }
    
    t0 = time.time()
    try:
        req = urllib.request.Request("http://localhost:11434/api/generate", data=json.dumps(req_body).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=25) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            ans = res_data.get("response", "").strip().upper()
            if not ans:
                th = res_data.get("thinking", "").upper()
                if "OUTPUT: YA" in th or "HASIL: YA" in th or "\nYA" in th or "JAWAB: YA" in th or "YA." in th:
                    ans = "YA"
            latency = time.time() - t0
            return ("YA" in ans), latency
    except Exception as e:
        logger.error(f"Error LLM intent classifier: {e}")
        return False, time.time() - t0
