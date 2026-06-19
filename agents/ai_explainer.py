from langchain_core.prompts import PromptTemplate
from config import cfg
from core.cache import llm_cache

# Initialize based on provider
if cfg.llm_provider == "groq":
    from langchain_groq import ChatGroq
    llm = ChatGroq(model=cfg.groq_model, api_key=cfg.groq_api_key, temperature=0.1)
else:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(model=cfg.model, api_key=cfg.gemini_api_key, temperature=0.1)

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

    # 2. Invoke Gemini AI
    try:
        res = chain.invoke({
            "msg": issue.get("msg", ""),
            "code": code_context[:500] 
        })
        explanation = res.content.strip() if hasattr(res, "content") else str(res).strip()
        
        # 3. Save to Cache
        llm_cache.put(cache_key, explanation)
        return explanation
    except Exception as e:
        print(f"LLM Error: {e}")
        return "Please review this line for potential issues."