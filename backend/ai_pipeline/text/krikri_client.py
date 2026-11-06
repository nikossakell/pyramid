"""
ai_pipeline/text/krikri_client.py — σύνδεση με το Krikri μέσω OpenAI-compatible API.

Το ίδιο API (POST {base_url}/chat/completions) το προσφέρουν:
    llama.cpp   llama-server -hf ilsp/Llama-Krikri-8B-Instruct-GGUF:Q4_K_M --port 8080   -> http://localhost:8080/v1
    Ollama      ollama run hf.co/ilsp/Llama-Krikri-8B-Instruct-GGUF:Q4_K_M               -> http://localhost:11434/v1
    vLLM        vllm serve ilsp/Llama-Krikri-8B-Instruct                                 -> http://localhost:8000/v1
Έτσι ο κώδικας δεν αλλάζει όταν περάσουμε από το laptop (Ollama) στον server του ΑΠΘ (llama.cpp ή vLLM).
Η Δομή_project αφήνει ανοιχτό αν θα σερβίρεται με Ollama ή llama.cpp· με αυτό το API δεν χρειάζεται απόφαση τώρα.

Μόνο stdlib (urllib): καμία νέα εξάρτηση.
ΣΗΜΑΝΤΙΚΟ: ο server του μοντέλου πρέπει να είναι τοπικός ή στο δίκτυο του ΑΠΘ. Κανένα δεδομένο σε τρίτους.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional, Protocol, Union

KRIKRI_GGUF = "ilsp/Llama-Krikri-8B-Instruct-GGUF:Q4_K_M"


class LLMError(RuntimeError):
    """Οποιαδήποτε αποτυχία κλήσης (δίκτυο, timeout, HTTP, απάντηση χωρίς κείμενο). Ο presenter κάνει fallback."""


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str
    latency_s: float
    finish_reason: Optional[str] = None


class ChatClient(Protocol):
    model_id: str

    def generate(self, messages: list[dict], temperature: float, max_tokens: int,
                 seed: Optional[int] = None) -> GenerationResult: ...


class OpenAICompatibleClient:
    def __init__(self, base_url: str, model: str, api_key: Optional[str] = None, timeout_s: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.model_id = model
        self.api_key = api_key
        self.timeout_s = timeout_s
        host = urllib.parse.urlparse(self.base_url).hostname or ""
        # τοπικός server: ποτέ μέσω proxy του συστήματος (αλλιώς τα αιτήματα θα έφευγαν προς τα έξω)
        self._opener = (urllib.request.build_opener(urllib.request.ProxyHandler({}))
                        if host in {"localhost", "127.0.0.1", "::1"} else urllib.request.build_opener())

    def _request(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self._opener.open(req, timeout=self.timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise LLMError(f"HTTP {e.code} from {self.base_url}{path}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise LLMError(f"cannot reach {self.base_url}{path}: {e}") from e
        except json.JSONDecodeError as e:
            raise LLMError("response is not JSON") from e

    def generate(self, messages: list[dict], temperature: float, max_tokens: int,
                 seed: Optional[int] = None) -> GenerationResult:
        payload = {"model": self.model, "messages": messages, "temperature": temperature,
                   "max_tokens": max_tokens, "stream": False}
        if seed is not None:
            payload["seed"] = seed
        t0 = time.monotonic()
        body = self._request("POST", "/chat/completions", payload)
        latency = time.monotonic() - t0
        try:
            choice = body["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError("unexpected response shape") from e
        if not isinstance(text, str) or not text.strip():
            raise LLMError("empty completion")
        return GenerationResult(text, body.get("model", self.model), latency, choice.get("finish_reason"))

    def available_models(self) -> list[str]:
        """GET /models: για έλεγχο ότι ο server τρέχει και ότι το μοντέλο υπάρχει."""
        return [m.get("id", "") for m in self._request("GET", "/models").get("data", [])]


class ScriptedClient:
    """ΜΟΝΟ για tests και demo χωρίς μοντέλο: επιστρέφει προκαθορισμένες απαντήσεις με τη σειρά, ή καλεί
    συνάρτηση (messages -> κείμενο). Ένα στοιχείο Exception προκαλεί LLMError (π.χ. για να φανεί το fallback)."""

    def __init__(self, replies: Union[list, Callable[[list[dict]], str]], model_id: str = "scripted-demo"):
        self.replies = replies
        self.model_id = model_id
        self.calls: list[list[dict]] = []

    def generate(self, messages, temperature, max_tokens, seed=None) -> GenerationResult:
        self.calls.append(messages)
        if callable(self.replies):
            reply = self.replies(messages)
        else:
            if not self.replies:
                raise LLMError("no scripted reply left")
            reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise LLMError(str(reply)) from reply
        return GenerationResult(reply, self.model_id, 0.0, "stop")
