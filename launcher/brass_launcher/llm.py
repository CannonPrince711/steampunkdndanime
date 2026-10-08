"""OpenAI-compatible chat client (stdlib only) + robust file-block extraction.

Works with OpenAI, any /v1/chat/completions server, Ollama (http://host:11434/v1),
LM Studio, vLLM, etc. The response contract for a step is:

    {"files": [{"path": "relative/path.json", "content": "..."}]}
"""
import json
import re
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    pass


def chat(base_url, api_key, model, system, user, timeout=900, max_tokens=16000,
         temperature=0.4):
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        raise LLMError(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"cannot reach {url}: {exc.reason}") from exc
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"unexpected response shape: {str(data)[:300]}") from exc


def _strip_fences(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _balanced_object(text):
    """First top-level {...} that parses as JSON, string-aware brace scanning."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    cand = text[start:i + 1]
                    try:
                        return json.loads(cand)
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def extract_files(text):
    """Pull the {"files":[{path,content}]} contract out of a model reply.

    Returns (files, error). files is a list of dicts; error is None on success.
    """
    if not text:
        return None, "empty response"
    cleaned = _strip_fences(text)
    candidates = []
    try:
        candidates.append(json.loads(cleaned))
    except json.JSONDecodeError:
        pass
    candidates.append(_balanced_object(cleaned))
    # last-resort: brace-greedy between first { and last }
    lo, hi = cleaned.find("{"), cleaned.rfind("}")
    if lo != -1 and hi > lo:
        try:
            candidates.append(json.loads(cleaned[lo:hi + 1]))
        except json.JSONDecodeError:
            pass
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        files = cand.get("files")
        if isinstance(files, list) and files and all(
                isinstance(f, dict) and f.get("path") and "content" in f
                for f in files):
            return files, None
    return None, "no valid {\"files\":[...]} object found in response"


STEP_SYSTEM = """You are the BRASS INITIATIVE series orchestrator, executing exactly ONE
production step of an episode pipeline. You are the named agent for this step and
nothing else.

HARD RULES:
- Follow the agent prompt exactly: its RULES, its output format, its SELF-AUDIT.
- Use only the input files provided. Do not invent new canon.
- Everything measurable: hex, cm, mm, Kelvin, frames. No stubs, no TODO, no
  placeholder content.
- Respond with ONLY one JSON object, no markdown fences, no commentary:
  {"files": [{"path": "<relative path>", "content": "<complete file content>"}]}
- The paths must be exactly the step's WRITE list, no more, no less.
- Content must be complete and valid (JSON must parse; reports must end with the
  required machine-readable lines)."""


def build_user_prompt(task, agent_prompt, inputs, max_input_chars=120000):
    parts = ["TASK (machine-readable):", json.dumps(task, indent=2, default=str), ""]
    parts.append("AGENT PROMPT (follow exactly):")
    parts.append(agent_prompt.strip())
    parts.append("")
    parts.append("INPUT FILES:")
    budget = max_input_chars
    for name, content in inputs:
        head = f"=== {name} ===\n"
        if len(content) > budget:
            content = content[:budget] + "\n[TRUNCATED BY BUDGET — rely on the files you already hold]\n"
            budget = 0
        parts.append(head)
        parts.append(content)
        budget -= len(content)
        if budget <= 0:
            break
    parts.append("")
    parts.append("Write every file in the step's WRITE list now. "
                 "Respond with only the JSON object.")
    return "\n".join(parts)
