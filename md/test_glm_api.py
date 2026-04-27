"""
Test GLM API Key don gian nhat
"""

from openai import OpenAI
import os

# GLM API Key
api_key = "a8de4f7a86a04fa4b6d0ee2be0ef014a.szYaZRl8KSvGTZs3"

# Khoi tao client GLM
client = OpenAI(api_key=api_key, base_url="https://api.z.ai/api/paas/v4")

# Test request
print("Dang test GLM API Key...")
try:
    response = client.chat.completions.create(
        model="GLM-4-Plus",
        messages=[{"role": "user", "content": "2+2=?"}]
    )

    # In ket qua
    print(f"Ket qua: {response.choices[0].message.content}")
    print("=> GLM API HOAT DONG!")
except Exception as e:
    print(f"LOI: {e}")
