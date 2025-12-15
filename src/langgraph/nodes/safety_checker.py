from typing import Dict, Any

def safety_checker(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Final guardrail node that checks the output and appends a medical disclaimer.
    """
    final_answer = state.get("final_answer", "")
    
    # Simple check: Does it already have a disclaimer?
    # We'll use a standard one.
    disclaimer = """
---
**⚠️ Medical Disclaimer:** This AI assistant is for informational purposes only and does not constitute medical advice. Always consult a qualified healthcare professional for diagnosis and treatment.
"""
    
    # Updated check for the new synthesizer format
    if "Medical Disclaimer" not in final_answer and "**⚠️ Medical Disclaimer:**" not in final_answer:
        print("🛡️ [Safety Guard] Appending disclaimer")
        final_answer += disclaimer
    else:
        print("🛡️ [Safety Guard] Disclaimer already present")

    return {
        **state,
        "final_answer": final_answer
    }
