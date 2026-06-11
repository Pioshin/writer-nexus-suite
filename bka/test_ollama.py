import requests

url = "http://127.0.0.1:11434/api/generate"
payload = {
    "model": "gpt-oss:latest",
    "prompt": "Say hello",
    "stream": False
}

print(f"Testing connection to {url}...")
try:
    response = requests.post(url, json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:200]}...")
except Exception as e:
    print(f"FAILED: {e}")
