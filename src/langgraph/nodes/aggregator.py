"""
Aggregator Node - Final Medical Response Synthesizer Agent
"""
import os
from langchain_groq import ChatGroq


def aggregate_response(state):
    """
    Synthesizes results from all tools into a single, authoritative medical response.
    Role: Final Medical Response Synthesizer Agent.
    """
    tool = state["tool"]
    results = state.get("results", [])
    query = state["query"]

    print(f"🔄 Aggregator: Synthesizing {len(results)} results from '{tool}'")

    # Handle empty results
    if not results:
        return {
            **state,
            "final_answer": "I couldn't find specific medical information for your query. Please consult a healthcare professional for advice."
        }

    # Initialize LLM
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",  # Use larger model for better synthesis
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3
    )

    # Prepare context
    combined_context = "\n\n".join(str(r) for r in results)

    # Format history context
    history = state.get("history", [])
    history_context = ""
    if history:
        history_context = "Conversation History:\n" + "\n".join(
            f"- {'Patient' if h['is_user'] else 'AI Assistant'}: {h['message']}" for h in history
        ) + "\n\n"

    # Format patient profile context
    intake_data = state.get("metadata", {}).get("intake_data")
    intake_context = ""
    if intake_data:
        pregnant_str = " (Pregnant)" if intake_data.get("pregnant") else ""
        intake_context = (
            f"Patient Profile Context:\n"
            f"- Age: {intake_data.get('age')}\n"
            f"- Sex: {intake_data.get('sex')}{pregnant_str}\n"
            f"- Chronic Conditions: {intake_data.get('conditions')}\n"
            f"- Known Allergies: {intake_data.get('allergies')}\n\n"
        )

    # FINAL MEDICAL RESPONSE SYNTHESIZER PROMPT
    prompt = f"""Role: You are the Final Medical Response Synthesizer Agent.

Input: You receive raw outputs from multiple agents (research, guidelines, news, analysis) regarding the user's query: "{query}"

{intake_context}{history_context}Raw Outputs:
{combined_context}

Task: Merge, deduplicate, and refine all inputs into one coherent, authoritative response suitable for a medical chatbot.

Output Rules (STRICT):
- Produce a single, well-structured answer (not agent-wise sections)
- Use professional medical headings and concise bullet points
- Remove UI labels, timestamps, headlines, and repeated disclaimers
- Resolve overlaps and contradictions using clinical best practices
- Summarize research into actionable clinical insights, not paper descriptions
- Use neutral, evidence-based language
- No raw URLs, no agent names, no meta commentary
- One short medical disclaimer at the end only
- Adapt treatment guidelines and precautions using the Patient Profile Context (e.g. emphasize warnings if any drug interactions or allergic contraindications exist based on reported allergies and chronic conditions)

Required Structure:
### Brief Overview
[Concise summary of the condition/topic]

### Key Clinical Features
[Bullet points of symptoms, signs, or characteristics]

### Diagnosis & Monitoring
[How it is identified and tracked]

### Treatment & Management
[Standard of care, therapies, and lifestyle factors]

### Recent Evidence & Guideline Updates
[Concise summary of research/news findings]

### Practical Patient Guidance
[Actionable advice for the patient]

### Medical Disclaimer
(One line only: This AI assistant is for informational purposes only and does not constitute medical advice. Always consult a qualified healthcare professional.)

Tone: Calm, expert, human-readable, non-alarmist.
Audience: General public with basic health literacy.
"""

    def push_event(state, event_type, data):
        """Helper to push events to the Flask SSE queue if present."""
        q = state.get("metadata", {}).get("event_queue")
        if q and hasattr(q, "put"):
            q.put({"type": event_type, **data})

    try:
        # Try with high-quality model first
        print("🤖 Aggregator: Attempting streaming synthesis with Llama-3.3-70b...")
        push_event(state, "status", {"message": "Synthesizing and formatting final medical response..."})
        
        final_text = ""
        for chunk in llm.stream(prompt):
            token = chunk.content if hasattr(chunk, 'content') else str(chunk)
            final_text += token
            push_event(state, "token", {"text": token})

    except Exception as e_main:
        print(f"⚠️ Aggregator 70b Error: {e_main}")
        print("🔄 Switching to fallback model (Llama-3.1-8b-instant)...")
        push_event(state, "status", {"message": "High-capacity model busy, switching to fallback synthesizer..."})
        
        try:
            # Fallback to faster model
            fallback_llm = ChatGroq(
                model="llama-3.1-8b-instant",
                api_key=os.getenv("GROQ_API_KEY"),
                temperature=0.3
            )
            final_text = ""
            for chunk in fallback_llm.stream(prompt):
                token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                final_text += token
                push_event(state, "token", {"text": token})
            
        except Exception as e_fallback:
            print(f"❌ Aggregator Fallback Error: {e_fallback}")
            final_text = "Error synthesizing response. Here are the raw results:\n\n" + combined_context
            push_event(state, "token", {"text": final_text})

    print(f"✅ Aggregator: Generated synthesized response ({len(final_text)} chars)")

    return {
        **state,
        "final_answer": final_text
    }

