import requests
import json
import re
import time
import os

class LLMClient:
    def __init__(self, provider="ollama", model="gpt-oss:latest", base_url="http://127.0.0.1:11434", api_key="", ctx=32768, timeout=180, keep_alive="5m"):
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_config.json")
        
        # Defaults
        self.provider = provider
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.ctx = ctx
        self.timeout = timeout
        self.keep_alive = keep_alive
        
        # Load Config
        self.load_config()
        
        # Ollama specific
        self.ollama_api_chat = f"{self.base_url}/api/chat"
        self.ollama_api_generate = f"{self.base_url}/api/generate"

    def load_config(self):
        """Load configuration from JSON file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.provider = config.get("provider", self.provider)
                    self.model = config.get("model", self.model)
                    self.base_url = config.get("base_url", self.base_url)
                    self.api_key = config.get("api_key", self.api_key)
                    self.ctx = config.get("ctx", self.ctx)
                    self.timeout = config.get("timeout", self.timeout)
                    self.keep_alive = config.get("keep_alive", self.keep_alive)
                    print(f"Loaded LLM Config: {self.provider}/{self.model}")
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_config(self):
        """Save current configuration to JSON file."""
        config = {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "ctx": self.ctx,
            "timeout": self.timeout,
            "keep_alive": self.keep_alive
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            print("LLM Config saved.")
        except Exception as e:
            print(f"Error saving config: {e}")

    def update_config(self, provider=None, model=None, base_url=None, api_key=None, ctx=None, timeout=None, keep_alive=None):
        """Update configuration dynamically and save to disk."""
        if provider: self.provider = provider
        if model: self.model = model
        if base_url: 
            self.base_url = base_url
            self.ollama_api_chat = f"{base_url}/api/chat"
            self.ollama_api_generate = f"{base_url}/api/generate"
        if api_key is not None: self.api_key = api_key
        if ctx: self.ctx = ctx
        if timeout: self.timeout = timeout
        if keep_alive: self.keep_alive = keep_alive
        
        print(f"LLM Config updated: provider={self.provider}, model={self.model}")
        self.save_config()

    def extract_json(self, text):
        """Extract JSON from LLM response (markdown, plain text, etc)."""
        text = text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        match = re.search(r'\[\s*\{[\s\S]*?\}\s*\]', text)
        if match:
            try: return json.loads(match.group())
            except: pass
        
        match = re.search(r'\{[\s\S]*?\}', text)
        if match:
            try:
                result = json.loads(match.group())
                return [result] if isinstance(result, dict) else result
            except: pass
        
        print(f"WARN: JSON extraction failed for: {text[:200]}...")
        return []

    def _make_request(self, payload, stream=False, call_type="chat"):
        """Internal dispatcher for providers."""
        if self.provider == "ollama":
            url = self.ollama_api_chat if call_type == "chat" else self.ollama_api_generate
            # Add Ollama specific options
            if "options" not in payload:
                payload["options"] = {"num_ctx": self.ctx, "temperature": 0.7}
            payload["keep_alive"] = self.keep_alive
            
            response = requests.post(url, json=payload, stream=stream, timeout=self.timeout)
            response.raise_for_status()
            
            if stream: return response
            return response.json()

        elif self.provider == "openai":
            # OpenAI Compatible (or real OpenAI)
            url = f"{self.base_url}/chat/completions" if self.base_url else "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            # Map payload to OpenAI format if needed
            openai_payload = {
                "model": self.model,
                "messages": payload.get("messages", []),
                "stream": stream,
                # "max_tokens": self.ctx  # Not always safe to send context length as max tokens
            }
            if "prompt" in payload: # Handle generate vs chat
                 openai_payload["messages"] = [{"role": "user", "content": payload["prompt"]}]

            response = requests.post(url, headers=headers, json=openai_payload, stream=stream, timeout=self.timeout)
            response.raise_for_status()
            
            if stream: return response
            return response.json()

        elif self.provider == "gemini":
            # Google Gemini
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            if stream: url = url.replace("generateContent", "streamGenerateContent")
            
            headers = {"Content-Type": "application/json"}
            
            # Convert messages to Gemini format (contents -> parts -> text)
            messages = payload.get("messages", [])
            if "prompt" in payload: messages = [{"role": "user", "content": payload["prompt"]}]
            
            gemini_contents = []
            for m in messages:
                role = "user" if m["role"] == "user" else "model"
                gemini_contents.append({
                    "role": role,
                    "parts": [{"text": m["content"]}]
                })
            
            gemini_payload = {"contents": gemini_contents}
            
            response = requests.post(url, headers=headers, json=gemini_payload, stream=stream, timeout=self.timeout)
            response.raise_for_status()
            
            if stream: return response
            return response.json()
            
        elif self.provider == "claude":
            # Anthropic Claude
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            messages = payload.get("messages", [])
            if "prompt" in payload: messages = [{"role": "user", "content": payload["prompt"]}]
            
            claude_payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 4096, # Claude requires max_tokens
                "stream": stream
            }
            
            response = requests.post(url, headers=headers, json=claude_payload, stream=stream, timeout=self.timeout)
            response.raise_for_status()
            
            if stream: return response
            return response.json()

        raise ValueError(f"Unknown provider: {self.provider}")

    def chat(self, messages, stream=False):
        """Generic chat method."""
        payload = {"model": self.model, "messages": messages, "stream": stream}
        
        try:
            response = self._make_request(payload, stream=stream, call_type="chat")
            
            if stream:
                return self._handle_stream(response)
            else:
                return self._parse_response(response)
                
        except Exception as e:
            print(f"LLM Error: {e}")
            raise

    def completion(self, prompt, stream=False):
        """Generic completion (uses chat internally for most modern LLMs)."""
        return self.chat([{"role": "user", "content": prompt}], stream=stream)

    def _parse_response(self, response_data):
        """Normalize response to string."""
        if self.provider == "ollama":
            return response_data.get("message", {}).get("content", "") or response_data.get("response", "")
        elif self.provider == "openai":
            return response_data["choices"][0]["message"]["content"]
        elif self.provider == "gemini":
            # Gemini JSON structure is complex
            try:
                return response_data["candidates"][0]["content"]["parts"][0]["text"]
            except:
                return "" # Handle safety blocks etc
        elif self.provider == "claude":
            return response_data["content"][0]["text"]
        return ""

    def _handle_stream(self, response_stream):
        """Yields tokens from stream."""
        for line in response_stream.iter_lines():
            if not line: continue
            
            try:
                line_text = line.decode('utf-8')
                if self.provider == "ollama":
                    body = json.loads(line_text)
                    yield body.get("message", {}).get("content", "")
                elif self.provider == "openai":
                    if line_text.startswith("data: "):
                        json_str = line_text[6:]
                        if json_str == "[DONE]": break
                        body = json.loads(json_str)
                        delta = body["choices"][0].get("delta", {})
                        yield delta.get("content", "")
                elif self.provider == "gemini":
                    # Gemini returns full JSON array in valid JSON mode, but streaming returns 'data: ' ? No, standard REST stream
                    # Actually Gemini REST stream returns JSON objects separated or in array
                    # This is tricky without SDK. Assuming standard SSE or NDJSON matching requests
                    # Typically standard REST requests.post(stream=True) gives raw chunks
                    # We might need to accumulate valid JSON for Gemini
                     # Simplified for now assuming NDJSON-like behavior or strict chunks
                    if line_text.startswith("data:"): # SSE
                         body = json.loads(line_text[5:])
                         yield body["candidates"][0]["content"]["parts"][0]["text"]
                    else:
                         # Attempt raw parse
                         try:
                             body = json.loads(line_text)
                             yield body["candidates"][0]["content"]["parts"][0]["text"]
                         except: pass
                    
                elif self.provider == "claude":
                    if line_text.startswith("data: "):
                        body = json.loads(line_text[6:])
                        if body["type"] == "content_block_delta":
                            yield body["delta"]["text"]
            except Exception as e:
                # print(f"Stream decode error: {e}")
                pass

    def check_connection(self):
        """Verifica la connessione al provider e restituisce (bool, message)."""
        try:
            models = self.list_models()
            return True, f"Connesso! {len(models)} modelli trovati."
        except Exception as e:
            return False, str(e)

    def list_models(self):
        """Recupera la lista dei modelli disponibili dal provider."""
        if self.provider == "ollama":
            url = f"{self.base_url}/api/tags"
            try:
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
            except Exception as e:
                raise Exception(f"Ollama Error: {e}")

        elif self.provider == "openai":
            url = f"{self.base_url}/models" if self.base_url else "https://api.openai.com/v1/models"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                return [m["id"] for m in data.get("data", [])]
            except Exception as e:
                # Fallback per endpoint non standard
                raise Exception(f"OpenAI Error: {e}")

        elif self.provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                # Filtra solo modelli che supportano generateContent
                models = []
                for m in data.get("models", []):
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        models.append(m["name"].replace("models/", ""))
                return models
            except Exception as e:
                raise Exception(f"Gemini Error: {e}")

        elif self.provider == "claude":
            # Anthropic non ha un endpoint list_models pubblico semplice.
            # Ritorniamo lista statica dei modelli attuali.
            return [
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
                "claude-2.1",
                "claude-2.0"
            ]

        return [self.model] # Fallback
