from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from config import cfg
from core.cache import llm_cache

# Initialize the local LLM running on your machine
llm = OllamaLLM(model=cfg.model, base_url=cfg.ollama_url, temperature=0.1)

_prompt = PromptTemplate.from_template(
    "You are a senior developer reviewing code. Keep it brief, polite, and helpful (max 2 sentences).\n"
    "Rule Violation: {msg}\n"
    "Code snippet:\n{code}\n"
    "Explain why this is an issue and suggest how to fix it. Do NOT use markdown code blocks for the whole response."
)

chain = _prompt | llm

def explain_issue(issue: dict, code_context: str) -> str:
    # 1. DSA Optimization: Check LRU Cache
    cache_key = llm_cache.make_key(issue.get("rule"), issue.get("msg"), code_context)
    cached = llm_cache.get(cache_key)
    if cached:
        return cached

    # 2. Invoke Local AI
    try:
        res = chain.invoke({
            "msg": issue.get("msg", ""),
            "code": code_context[:500] 
        })
        explanation = res.strip()
        
        # 3. Save to Cache
        llm_cache.put(cache_key, explanation)
        return explanation
    except Exception as e:
        print(f"LLM Error: {e}")
        return "Please review this line for potential issues."