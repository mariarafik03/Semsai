import requests
import json

url = "http://127.0.0.1:8000/agents/step"
# Payload matching Flutter initial state exactly
payload = {
    "state": {
        "user_input": None,
        "purpose": None,
        "budget": None,
        "location": None,
        "next_step": None,
        "payment_type": None,
        "Downpayment": None,
        "monthlyinstall": None,
    },
    "user_input": None
}
try:
    res = requests.post(url, json=payload)
    print(f"Status Code: {res.status_code}")
    print(f"Response: {res.text}")
except Exception as e:
    print(f"Request failed: {e}")
