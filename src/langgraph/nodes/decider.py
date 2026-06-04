import os
import json
from langchain_groq import ChatGroq

def push_event(state, event_type, data):
    """Helper to push events to the Flask SSE queue if present."""
    q = state.get("metadata", {}).get("event_queue")
    if q and hasattr(q, "put"):
        q.put({"type": event_type, **data})

def decide_tool(state):
    """
    LLM-based smart router with context-aware query rewriting.
    Resolves references/pronouns using conversational history.
    """
    query = state.get("query", "")
    history = state.get("history", [])

    # Initialize metadata if not exists
    if "metadata" not in state:
        state["metadata"] = {}

    push_event(state, "status", {"message": "🏥 Medical Coordinator: Deciding clinical routing..."})
    print(f"\n🔍 [LLM Router] Analyzing query: '{query}'")

    # Format history for prompt
    history_str = ""
    if history:
        history_str = "Conversation History:\n" + "\n".join(
            f"- {'Patient' if h['is_user'] else 'AI Assistant'}: {h['message']}" for h in history
        ) + "\n\n"

    # Initialize router LLM (use 8b-instant for fast, low-latency routing)
    try:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured in environment variables.")

        llm = ChatGroq(
            model="llama-3.1-8b-instant",
            api_key=api_key,
            temperature=0.0
        ).bind(response_format={"type": "json_object"})

        prompt = f"""You are an advanced medical query router and intent classifier.
Analyze the patient's medical query and previous conversation history to determine which tools to execute.

{history_str}User Query: "{query}"

Available Tools:
- "rag": Local disease/symptom/treatment knowledge base. Use for general questions about conditions ("what is diabetes"), symptoms ("my head hurts"), side effects, definitions, standard medical guidance.
- "research": Europe PMC database. Use for academic research topics, search for scientific papers, clinical trials, and general medical literature searches.
- "pubmed": PubMed (NCBI) database. Use for specialized medical literature, clinical studies, PubMed databases.
- "websearch": Tavily web search. Use for latest medical news, new guidelines (e.g. 2024/2025/2026), current updates, breakthrough announcements.
- "general": General conversation, greetings ("hi", "hello", "how are you"), bot identity/metadata questions ("what is your model", "who built you"), or simple off-topic queries that do not require any medical database lookup.
- "multi": Use when the query combines multiple distinct intents requiring more than one tool (e.g., "Tell me about migraine symptoms AND search for the latest research on them").

Instructions:
1. Classify the query into a primary "tool" (either "rag", "research", "pubmed", "websearch", "general", or "multi").
2. Resolve any references, pronouns ("it", "they", "this", "those"), or implicit context in the User Query using the Conversation History to create a standalone, search-friendly query. For example, if history is "Patient: I have migraine" and the query is "What is its treatment?", rewrite it to "migraine treatment".
3. If "tool" is "multi", list the sub-tools in the "tools" array (subset of ["rag", "research", "pubmed", "websearch"]), and provide standalone "rewritten_queries" for each tool.
4. If "tool" is not "multi", leave the "tools" array empty, and provide a single rewritten query for that primary tool in "rewritten_queries".

You must output a JSON object matching this schema EXACTLY:
{{
  "tool": "rag" | "research" | "pubmed" | "websearch" | "general" | "multi",
  "reasoning": "brief explanation of tool choice",
  "tools": ["tool1", "tool2"],
  "rewritten_queries": {{
    "rag": "rewritten query or empty string",
    "research": "rewritten query or empty string",
    "pubmed": "rewritten query or empty string",
    "websearch": "rewritten query or empty string"
  }}
}}
"""

        response = llm.invoke(prompt)
        res_text = response.content if hasattr(response, 'content') else str(response)
        decision = json.loads(res_text)

        tool_decision = decision.get("tool", "rag")
        reasoning = decision.get("reasoning", "")
        tools_to_run = decision.get("tools", [])
        rewritten_queries = decision.get("rewritten_queries", {})

        print(f"🎯 [LLM Router] Decision: {tool_decision.upper()}")
        print(f"💡 [LLM Router] Reasoning: {reasoning}")

        push_event(state, "status", {"message": f"Routed query to: {tool_decision.upper()} - {reasoning}"})

        # Update state based on decision
        state["tool"] = tool_decision
        
        if tool_decision == "multi":
            # Filter tools to make sure they are valid
            valid_tools = ["rag", "research", "pubmed", "websearch"]
            final_tools = [t for t in tools_to_run if t in valid_tools]
            if not final_tools:
                final_tools = ["rag", "websearch"]
                
            state["metadata"] = {
                "multi_tool": True,
                "tools": final_tools,
                "queries": rewritten_queries
            }
            print(f"🔀 [LLM Router] Multi tools: {final_tools}")
            print(f"🔀 [LLM Router] Multi queries: {rewritten_queries}")
        else:
            # For single tool, update state query to be the rewritten query for that tool
            rewritten_query = rewritten_queries.get(tool_decision, query)
            if rewritten_query:
                state["query"] = rewritten_query
                print(f"🔄 [LLM Router] Rewrote query to: '{rewritten_query}'")

        return state

    except Exception as e:
        print(f"❌ [LLM Router] Error routing query, falling back to rule-based: {e}")
        return decide_tool_fallback(state)


def decide_tool_fallback(state):
    """
    Fallback keyword-matching tool decision
    """
    query = state["query"].lower()
    original_query = state["query"]

    # Initialize metadata if not exists
    if "metadata" not in state:
        state["metadata"] = {}

    print(f"🔍 [Fallback Router] Analyzing: '{original_query}'")

    # Personal health indicators
    has_personal = any(phrase in query for phrase in [
        "i have", "i'm", "i am", "my", "suffering",
        "experiencing", "diagnosed", "i feel"
    ])

    # Research/study indicators
    has_research = any(word in query for word in [
        "research", "study", "studies", "paper", "papers",
        "clinical trial", "trials", "scientific", "evidence",
        "findings", "publication", "literature"
    ])

    # News/updates indicators
    has_news = any(word in query for word in [
        "latest", "recent", "new", "today", "current",
        "update", "updates", "breakthrough", "2024", "2025",
        "news", "announcement", "guideline"
    ])

    # Medical info indicators (RAG)
    has_medical_info = any(word in query for word in [
        "treatment", "symptom", "disease", "condition",
        "cure", "cause", "prevent", "diagnosis", "options",
        "what is", "how to", "tell me about"
    ])

    # Conjunction check (indicates multiple intents)
    has_conjunction = any(word in query for word in [
        " and ", " also ", " plus ", " as well as "
    ])

    # PubMed indicators
    has_pubmed = any(word in query for word in [
        "pubmed", "ncbi", "medline", "nih"
    ])

    # Pattern 1: Personal health + Research
    if has_personal and has_research:
        medical_topic = extract_topic(original_query)
        state["tool"] = "multi"
        state["metadata"] = {
            "multi_tool": True,
            "tools": ["rag", "research", "pubmed"],
            "queries": {
                "rag": original_query,
                "research": f"{medical_topic} research",
                "pubmed": f"{medical_topic} research"
            }
        }
        return state

    # Pattern 2: Medical info + Research
    if has_medical_info and has_research and has_conjunction:
        medical_topic = extract_topic(original_query)
        state["tool"] = "multi"
        state["metadata"] = {
            "multi_tool": True,
            "tools": ["rag", "research", "pubmed"],
            "queries": {
                "rag": original_query,
                "research": f"{medical_topic} research",
                "pubmed": f"{medical_topic} research"
            }
        }
        return state

    # Pattern 3: Medical info + News
    if has_medical_info and has_news and has_conjunction:
        medical_topic = extract_topic(original_query)
        state["tool"] = "multi"
        state["metadata"] = {
            "multi_tool": True,
            "tools": ["rag", "websearch"],
            "queries": {
                "rag": original_query,
                "websearch": f"{medical_topic} latest news"
            }
        }
        return state

    # Pattern 4: Research + News
    if has_research and has_news:
        medical_topic = extract_topic(original_query)
        state["tool"] = "multi"
        state["metadata"] = {
            "multi_tool": True,
            "tools": ["research", "pubmed", "websearch"],
            "queries": {
                "research": f"{medical_topic} research",
                "pubmed": f"{medical_topic} research",
                "websearch": f"{medical_topic} latest news"
            }
        }
        return state

    # Single-tool routing
    if has_pubmed:
        state["tool"] = "pubmed"
        return state

    if has_personal:
        state["tool"] = "rag"
        return state

    if has_research and not has_medical_info:
        medical_topic = extract_topic(original_query)
        state["tool"] = "multi"
        state["metadata"] = {
            "multi_tool": True,
            "tools": ["research", "pubmed"],
            "queries": {
                "research": f"{medical_topic} research",
                "pubmed": f"{medical_topic} research"
            }
        }
        return state

    if has_news and not has_medical_info:
        state["tool"] = "websearch"
        return state

    # Greetings / chit-chat/ metadata indicators for general
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "who are you", "what is your name", "model name", "how are you"]
    if any(g in query for g in greetings) or len(query.strip().split()) <= 2:
        state["tool"] = "general"
        return state

    if has_medical_info:
        state["tool"] = "rag"
        return state

    # Fallback to RAG
    state["tool"] = "rag"
    return state


def extract_topic(query):
    """Extract core medical topic from query"""
    noise = [
        "i have", "i want", "i need", "show me", "find me",
        "give me", "tell me", "and", "latest", "recent",
        "research", "papers", "studies", "news", "update",
        "treatment options", "about", "information"
    ]

    cleaned = query.lower()
    for word in noise:
        cleaned = cleaned.replace(word, " ")

    cleaned = " ".join(cleaned.split()).strip()
    return cleaned if cleaned else query.split()[0]