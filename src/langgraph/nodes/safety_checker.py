import os
import json
from typing import Dict, Any
from langchain_groq import ChatGroq

def safety_checker(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Final guardrail node that runs an LLM safety audit on the generated answer,
    appends disclaimers, and adds warning callouts for emergency symptoms.
    """
    final_answer = state.get("final_answer", "")
    query = state.get("query", "").lower()
    
    # Initialize metadata if not exists
    if "metadata" not in state:
        state["metadata"] = {}

    # Standard disclaimer
    disclaimer = """
---
**Medical Disclaimer:** This AI assistant is for informational purposes only and does not constitute medical advice. Always consult a qualified healthcare professional for diagnosis and treatment.
"""

    # If the answer is empty or default, return immediately
    if not final_answer or final_answer.startswith("I couldn't find specific"):
        return state

    print("🛡️ [Safety Guard] Running LLM safety audit...")

    try:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured.")

        llm = ChatGroq(
            model="llama-3.1-8b-instant",
            api_key=api_key,
            temperature=0.0
        ).bind(response_format={"type": "json_object"})

        prompt = f"""You are a clinical safety evaluation assistant.
Analyze the generated medical response and the user's query to identify any safety violations.

User Query: "{query}"
Generated Response:
"{final_answer}"

Rules to evaluate:
1. absolute_diagnosis: Does the response diagnose the patient with absolute certainty? (It should use tentative language like "possible conditions", "may indicate", "suggests", rather than "you have X").
2. dangerous_dosage: Does the response specify prescription drug dosages that could be harmful if self-administered?
3. emergency_warning_needed: Does the User Query contain warning signs of an emergency (e.g., chest pain, breathing difficulty, severe bleeding, sudden weakness, numbness, suicidal thoughts, poisoning)?

You must respond in JSON format matching this schema:
{{
  "absolute_diagnosis": true | false,
  "dangerous_dosage": true | false,
  "emergency_warning_needed": true | false,
  "audit_reasoning": "brief explanation"
}}
"""

        response = llm.invoke(prompt)
        res_text = response.content if hasattr(response, 'content') else str(response)
        audit = json.loads(res_text)

        absolute_diag = audit.get("absolute_diagnosis", False)
        dangerous_dose = audit.get("dangerous_dosage", False)
        emergency_warn = audit.get("emergency_warning_needed", False)

        print(f"🛡️ [Safety Guard] Audit: Absolute Diag: {absolute_diag}, Dangerous Dose: {dangerous_dose}, Emergency: {emergency_warn}")
        print(f"🛡️ [Safety Guard] Reasoning: {audit.get('audit_reasoning', '')}")

        # Prepend emergency notice if flagged
        if emergency_warn:
            emergency_notice = """> [!CAUTION]
> **EMERGENCY NOTICE:** Your query mentions symptoms (such as chest pain or breathing difficulty) that could indicate a life-threatening medical emergency. **Please call 911 or go to the nearest emergency room immediately.** Do not delay seeking professional emergency care.
\n"""
            if "EMERGENCY NOTICE" not in final_answer:
                final_answer = emergency_notice + final_answer

        # Append clarification if absolute diagnosis flagged
        if absolute_diag:
            clarification = "\n\n*Note: The conditions listed above are tentative possibilities. Only a licensed physician can provide a definitive medical diagnosis and treatment plan.*"
            if "tentative possibilities" not in final_answer:
                final_answer += clarification

    except Exception as e:
        print(f"⚠️ [Safety Guard] Error during LLM audit: {e}. Falling back to standard disclaimer checks.")

    # Fallback/Additional check: Ensure standard disclaimer is present
    if "Medical Disclaimer" not in final_answer and "**⚠️ Medical Disclaimer:**" not in final_answer:
        print("🛡️ [Safety Guard] Appending standard disclaimer")
        final_answer += disclaimer
    else:
        print("🛡️ [Safety Guard] Disclaimer already present")

    return {
        **state,
        "final_answer": final_answer
    }
