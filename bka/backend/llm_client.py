import requests
import json
import re
import time
import os

import sys
# Import shared config manager
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from config_manager import UnifiedConfigManager

class LLMClient:
    def __init__(self, provider=None, model=None, base_url=None, api_key=None, ctx=None, timeout=None, keep_alive=None):
        self.config_manager = UnifiedConfigManager()
        
        # Load Initial Config from Manager
        self.load_config()
        
        # Overrides if provided in init (rarely used now)
        if provider: self.provider = provider
        if model: self.model = model
        if base_url: self.base_url = base_url
        if api_key: self.api_key = api_key
        if ctx: self.ctx = ctx
        if timeout: self.timeout = timeout
        if keep_alive: self.keep_alive = keep_alive
        
        # Ollama specific
        self.ollama_api_chat = f"{self.base_url}/api/chat"
        self.ollama_api_generate = f"{self.base_url}/api/generate"

    def load_config(self):
        """Load configuration from Shared Config Manager."""
        try:
            ai_config = self.config_manager.get_ai_config()
            self.provider = ai_config.get("provider", "ollama")
            self.model = ai_config.get("model", "adam:latest")
            self.base_url = ai_config.get("url", "http://127.0.0.1:11434")
            self.api_key = ai_config.get("api_key", "")
            self.ctx = ai_config.get("ctx", 32768)
            self.timeout = ai_config.get("timeout", 180)
            self.keep_alive = ai_config.get("keep_alive", "5m")
            print(f"Loaded Shared LLM Config: {self.provider}/{self.model}")
        except Exception as e:
            print(f"Error loading shared config: {e}")

    def save_config(self):
        """Save current configuration to Shared Config."""
        try:
            self.config_manager.update_ai_config(
                provider=self.provider,
                model=self.model,
                url=self.base_url,
                api_key=self.api_key,
                ctx=self.ctx,
                timeout=self.timeout,
                keep_alive=self.keep_alive
            )
            print("Shared LLM Config saved.")
        except Exception as e:
            print(f"Error saving shared config: {e}")

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

    def _make_request(self, payload, stream=False, call_type="chat", force_json=False):
        """Internal dispatcher for providers."""
        if self.provider == "ollama":
            url = self.ollama_api_chat if call_type == "chat" else self.ollama_api_generate
            
            # Parametri Ollama: rispettano le impostazioni dell'utente (shared config)
            options = {
                "num_ctx": int(self.ctx or 32768),
                "num_predict": 8192,
                "temperature": 0.7
            }
            payload["options"] = options
            payload["keep_alive"] = self.keep_alive or "5m"
            
            if force_json:
                payload["format"] = "json"
                # Disabilita thinking per Gemma4 in format=json (previene loop/blocchi)
                payload["think"] = False
                
            try:
                response = requests.post(url, json=payload, stream=True, timeout=self.timeout)
                response.raise_for_status()
            except requests.exceptions.ConnectionError:
                raise Exception("Ollama non raggiungibile. Assicurati che sia in esecuzione (ollama serve).")
            except requests.exceptions.Timeout:
                raise Exception(f"Timeout di connessione a Ollama dopo {self.timeout}s.")
            
            if stream: 
                return response
            
            # Accumuliamo content e thinking in modo sincrono per gestire il fallback Gemma4
            full_content = ""
            thinking_content = ""
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line.decode('utf-8'))
                except Exception:
                    continue
                
                if call_type == "chat":
                    msg = chunk.get("message", {})
                    full_content += msg.get("content", "")
                    thinking_content += msg.get("thinking", "")
                else:
                    full_content += chunk.get("response", "")
                    thinking_content += chunk.get("thinking", "")
                
                if chunk.get("done"):
                    break
            
            # Gemma4: se content non contiene JSON ma thinking sì, usa thinking come fallback
            content_has_json = "{" in full_content or "[" in full_content
            thinking_has_json = "{" in thinking_content or "[" in thinking_content
            
            if not content_has_json and thinking_has_json:
                print(f"DEBUG: content non-JSON, uso thinking come fallback ({len(thinking_content)} chars)")
                full_content = thinking_content
                
            if call_type == "chat":
                return {"message": {"content": full_content}}
            else:
                return {"response": full_content}

        elif self.provider == "openai":
            # OpenAI Compatible (or real OpenAI)
            url = f"{self.base_url}/chat/completions" if self.base_url else "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            # Map payload to OpenAI format if needed
            openai_payload = {
                "model": self.model,
                "messages": payload.get("messages", []),
                "stream": stream,
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

    def chat(self, messages, stream=False, force_json=False):
        """Generic chat method."""
        # Ricarica config condivisa: cambiamenti fatti da IODA o altre app si propagano
        self.load_config()
        payload = {"model": self.model, "messages": messages, "stream": stream}
        
        try:
            response = self._make_request(payload, stream=stream, call_type="chat", force_json=force_json)
            
            if stream:
                return self._handle_stream(response)
            else:
                return self._parse_response(response)
                
        except Exception as e:
            print(f"LLM Error: {e}")
            raise

    def completion(self, prompt, stream=False, force_json=False):
        """Generic completion (uses chat internally for most modern LLMs)."""
        return self.chat([{"role": "user", "content": prompt}], stream=stream, force_json=force_json)

    def _parse_response(self, response_data):
        """Normalize response to string."""
        if self.provider == "ollama":
            return response_data.get("message", {}).get("content", "") or response_data.get("response", "")
        elif self.provider == "openai":
            return response_data["choices"][0]["message"]["content"]
        elif self.provider == "gemini":
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
                    msg = body.get("message", {})
                    content_token = msg.get("content", "")
                    thinking_token = msg.get("thinking", "")
                    # Emetti thinking_token come fallback se non c'è content_token
                    yield content_token or thinking_token
                elif self.provider == "openai":
                    if line_text.startswith("data: "):
                        json_str = line_text[6:]
                        if json_str == "[DONE]": break
                        body = json.loads(json_str)
                        delta = body["choices"][0].get("delta", {})
                        yield delta.get("content", "")
                elif self.provider == "gemini":
                    if line_text.startswith("data:"): # SSE
                         body = json.loads(line_text[5:])
                         yield body["candidates"][0]["content"]["parts"][0]["text"]
                    else:
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
                raise Exception(f"OpenAI Error: {e}")

        elif self.provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                models = []
                for m in data.get("models", []):
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        models.append(m["name"].replace("models/", ""))
                return models
            except Exception as e:
                raise Exception(f"Gemini Error: {e}")

        elif self.provider == "claude":
            return [
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
                "claude-2.1",
                "claude-2.0"
            ]

        return [self.model]
