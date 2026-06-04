"""
Vision Agent - Medical Image Analyzer Node using Google Gemini 2.5 Flash
"""
import os
import base64
import io
from PIL import Image
import google.generativeai as genai

def push_event(state, event_type, data):
    """Helper to push events to the Flask SSE queue if present."""
    q = state.get("metadata", {}).get("event_queue")
    if q and hasattr(q, "put"):
        q.put({"type": event_type, **data})

def vision_agent(state):
    """
    Analyzes medical images (X-rays, skin lesions, reports) using Gemini 2.5 Flash.
    """
    query = state.get("query", "Analyze this medical image.")
    image_data = state.get("image")
    
    print("🧠 [Vision Agent] Processing medical image...")
    push_event(state, "status", {"message": "Clinical Vision: Decoding and analyzing medical image..."})
    
    # 1. Check for API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        error_msg = (
            "### 🔑 Google Gemini API Key Not Configured\n\n"
            "To enable medical image analysis, please configure your **GEMINI_API_KEY**:\n\n"
            "1. **Get a free API key** from Google AI Studio at **[aistudio.google.com](https://aistudio.google.com/)**.\n"
            "2. **Add the key** to your `.env` file in the project root:\n"
            "   ```env\n"
            "   GEMINI_API_KEY=your_api_key_here\n"
            "   ```\n"
            "3. **Restart the server** to apply the new configuration.\n\n"
            "*Your image upload is working correctly, but the AI vision model requires an active API key to perform diagnostic analysis.*"
        )
        return {
            **state,
            "results": [error_msg]
        }
        
    # 2. Decode the Base64 image
    try:
        # Expected format: data:image/png;base64,iVBORw0KGgoAAAANS...
        if "," in image_data:
            header, base64_str = image_data.split(",", 1)
        else:
            base64_str = image_data
            
        decoded = base64.b64decode(base64_str)
        img = Image.open(io.BytesIO(decoded))
    except Exception as e:
        print(f"❌ [Vision Agent] Error decoding image: {e}")
        return {
            **state,
            "results": [f"Error decoding image: {e}"]
        }
        
    # 3. Call Gemini 2.5 Flash
    try:
        genai.configure(api_key=api_key)
        
        # Configure model
        model = genai.GenerativeModel(model_name="gemini-2.5-flash")
        
        # Inject Patient intake form data if present
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
            
        prompt = f"""Role: You are an expert Clinical Medical Image Analyzer Agent.

{intake_context}User Query: "{query}"

Task: Perform a detailed and professional analysis of the attached medical image (e.g. X-ray, MRI, CT, ultrasound, pathology slide, clinical/dermatology photograph, or lab report) in the context of the user's query.

Instructions (STRICT):
1. **Modality & Technique**: Identify the imaging modality, anatomical region, and view/orientation (e.g., posterior-anterior chest X-ray, axial T2 brain MRI, macro-photograph of skin). Assess if the image quality is sufficient for evaluation.
2. **Detailed Anatomical & Pathological Findings**: Systematically describe the visual findings. Note any abnormalities such as tissue densities, consolidations, lesions, growths, calcifications, structural deviations, fluid levels, or bone fractures. Describe their size, location, borders, and appearance.
3. **Clinical Interpretation**: Correlate these visual findings with the User Query and any Patient Profile Context (such as Age, Sex, chronic conditions, and allergies). For example, if a lung lesion is seen in a patient with asthma, or a skin rash is found in a patient with drug allergies, detail how these factors interact.
4. **Differential Diagnoses**: Suggest a list of potential clinical indications or differential diagnoses. Always present them as possibilities rather than absolute diagnoses, using terms like "suggestive of," "consistent with," or "cannot rule out."
5. **Next Steps & Recommendations**: Provide clear, standard-of-care recommendations for further evaluation (e.g., specific follow-up scans, lab tests, biopsies, or immediate clinical consultation).

Tone: Highly objective, calm, expert, and clinical. Do not make definitive, final diagnoses. Offer medical guidance to support clinical decision-making.
"""
        
        print("🤖 [Vision Agent] Querying Gemini 2.5 Flash...")
        response = model.generate_content([img, prompt])
        analysis = response.text
        
        print("✅ [Vision Agent] Completed image analysis")
        push_event(state, "status", {"message": "Vision Agent: Image analysis complete."})
        
        return {
            **state,
            "results": [analysis]
        }
        
    except Exception as e:
        print(f"❌ [Vision Agent] API Error: {e}")
        return {
            **state,
            "results": [f"Gemini API Error: {e}"]
        }
