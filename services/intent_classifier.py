import urllib.request
import json
import time
import logging

logger = logging.getLogger(__name__)

def classify_intent_llm(user_text: str, model: str = "gemma4:e4b") -> tuple[bool, float]:
    """
    Returns (True if product_search, False otherwise), and latency_s
    """
    prompt = f"Kalimat: '{user_text}'. Apakah kalimat ini mencari atau bertanya spesifikasi/rekomendasi komputer/laptop? Jawab HANYA 'YA' atau 'TIDAK'."
    req_body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 4} # one word output
    }
    
    t0 = time.time()
    try:
        req = urllib.request.Request("http://localhost:11434/api/generate", data=json.dumps(req_body).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            ans = res_data.get("response", "").strip().upper()
            latency = time.time() - t0
            return ("YA" in ans), latency
    except Exception as e:
        logger.error(f"Error LLM intent classifier: {e}")
        return False, time.time() - t0
