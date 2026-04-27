"""
Test cac OpenRouter free models
"""

from openai import OpenAI

api_key = "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"

client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

# List cac model free de test
models = [
    "google/gemma-3-4b-it:free",
    "meta-llama/llama-3-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "microsoft/phi-3-mini-128k-instruct:free",
    "qwen/qwen-2-7b-instruct:free"
]

for model_name in models:
    print(f"\nDang test model: {model_name}")
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "2+2=?"}]
        )
        print(f"Ket qua: {response.choices[0].message.content}")
        print(f"==> {model_name} HOAT DONG!")
    except Exception as e:
        print(f"LOI: {e}")
