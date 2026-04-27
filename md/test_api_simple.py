"""
Test OpenRouter API Key don gian nhat
"""

from openai import OpenAI
import os

# OpenRouter API Key
api_key = "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"

# Khoi tao client OpenRouter
client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

# Test request
print("Dang test OpenRouter API Key...")
response = client.chat.completions.create(
    model="google/gemma-3-4b-it:free",
    messages=[{"role": "user", "content": "2+2=?"}]
)

# In ket qua
print(f"Ket qua: {response.choices[0].message.content}")
print("=> OpenRouter API HOAT DONG!")
