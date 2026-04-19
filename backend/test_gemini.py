import os
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path

# Load .env from current directory
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
print(f"Using API Key: {api_key[:10]}...")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

def test_analysis():
    prompt = """You are an expert clinical medical assistant AI. Based on the following real-time physiological readings:
Temperature: 37.5 °C
Heart Rate: 80 bpm
SpO2: 98 %

Provide professional clinical analysis with these exact sections:
- prediction: Overall health status
- diagnosis: List 2-3 possible conditions
- explanation: Key findings
- advice: 3-4 specific recommendations

Return ONLY a valid JSON string with these keys: "prediction", "diagnosis", "explanation", "advice"."""

    try:
        response = model.generate_content(prompt)
        print("Raw Response:")
        print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_analysis()
