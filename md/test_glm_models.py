"""
Test GLM API models
"""

from openai import OpenAI

# GLM API Key
api_key = "a8de4f7a86a04fa4b6d0ee2be0ef014a.szYaZRl8KSvGTZs3"

# Khoi tao client GLM
client = OpenAI(api_key=api_key, base_url="https://api.z.ai/api/paas/v4")

# List cac model de test
models = [
    "glm-4-plus",
    "glm-4-flash",
    "glm-4",
    "glm-4-air",
    "chatglm3-6b",
    "glm-4.5-air:free"
]

for model_name in models:
    print(f"\nDang test model: {model_name}")
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "2+2=?"}]
        )

        # In ket qua
        print(f"Ket qua: {response.choices[0].message.content}")
        print(f"==> {model_name} HOAT DONG!")
    except Exception as e:
        print(f"LOI: {e}")
