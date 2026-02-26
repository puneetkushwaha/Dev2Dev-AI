import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found.")
    exit(1)

client = genai.Client(api_key=api_key)

with open("models_list.txt", "w") as f:
    try:
        for m in client.models.list():
            f.write(f"{m.name}\n")
    except Exception as e:
        f.write(f"Error: {e}\n")
