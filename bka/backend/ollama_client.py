import json
import time
import re
from llm_client import LLMClient

class OllamaClient:
    def __init__(self, model=None, base_url=None, provider=None, api_key=None, ctx=None, timeout=None, keep_alive=None):
        # LiteLLM-compatible: model aliases, base_url defaults to LiteLLM :4000/v1, config from config.json
        # Ignore legacy params provider/ctx/keep_alive (OpenAI format doesn't use them)
        self.client = LLMClient(
            model=model or "default",
            base_url=base_url or "http://127.0.0.1:4000/v1",
            api_key=api_key or "",
            timeout=timeout or 300
        )

    def update_config(self, provider=None, model=None, base_url=None, api_key=None, ctx=None, timeout=None, keep_alive=None):
        """Update configuration dynamically (legacy compatibility)."""
        self.client.update_config(model=model, base_url=base_url, api_key=api_key)

    @property
    def model(self): return self.client.model
    @property
    def base_url(self): return self.client.base_url
    @property
    def ctx(self): return 4096  # default context window for Ollama
    @property
    def timeout(self): return self.client.timeout
    @property
    def provider(self): return "litellm"
    @property
    def api_key(self): return self.client.api_key
    @property
    def keep_alive(self): return "5m"

    def extract_json(self, text):
        """Estrae JSON con fallback progressivi e riparazione automatica (StoryForge style)."""
        # Pulizia iniziale markdown
        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
        
        # Tentativo 1: parsing diretto
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
            
        # Isola il primo blocco JSON { ... } oppure [ ... ]
        i_brace  = cleaned.find("{")
        i_brack  = cleaned.find("[")
        start = min(
            i_brace  if i_brace  != -1 else len(cleaned),
            i_brack  if i_brack  != -1 else len(cleaned),
        )
        end = max(cleaned.rfind("}"), cleaned.rfind("]")) + 1
        
        parsed_text = cleaned
        if start < end:
            parsed_text = cleaned[start:end]
            
        # Tentativi successivi sul blocco isolato
        for candidate in [parsed_text, cleaned]:
            # Tentativo 2: rimuovi virgole finali
            fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

            # Tentativo 3: commenti stile JS
            fixed = re.sub(r"//[^\n\"]*", "", fixed)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

            # Tentativo 4: commenti multilinea
            fixed = re.sub(r"/\*.*?\*/", "", fixed, flags=re.DOTALL)
            fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

        # Tentativo 5: Riparazione JSON troncato (chiusura intelligente delle parentesi aperte)
        try:
            patched = parsed_text.strip()
            patched = re.sub(r",\s*$", "", patched)
            open_braces = patched.count("{") - patched.count("}")
            open_brackets = patched.count("[") - patched.count("]")
            # L'ordine corretto di chiusura è prima le graffe '}' poi le quadre ']'
            patched += "}" * max(0, open_braces) + "]" * max(0, open_brackets)
            return json.loads(patched)
        except Exception as e:
            print(f"WARN: JSON parse/repair failed: {e}\nRaw response: {text[:300]}")
            
        # Fallback finale usando il vecchio regex search su tutto il testo
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
            
        return []

    def refine_with_streaming(self, prompt, on_token=None, force_json=False):
        """
        Esegue una richiesta LLM con streaming.
        """
        full_response = ""
        try:
            stream = self.client.chat([{"role": "user", "content": prompt}], stream=True, force_json=force_json)
            for token in stream:
                full_response += token
                if on_token:
                    on_token(token)
        except Exception as e:
            print(f"Streaming error: {e}")
            raise
        
        return full_response

    def refine_characters_streaming(self, char_list, on_progress=None):
        """
        Versione streaming di refine_characters con progress callback.
        """
        # 1. SORT to ensure duplicates (Hector, Hector Starborn) are adjacent
        char_list.sort(key=lambda x: x.get("name", "").lower())
        
        batch_size = 20
        refined_results = []
        total_batches = (len(char_list) - 1) // batch_size + 1 if char_list else 0
        
        for i in range(0, len(char_list), batch_size):
            batch = char_list[i : i + batch_size]
            batch_num = i // batch_size + 1
            
            if on_progress:
                on_progress({
                    "type": "batch_start",
                    "batch": batch_num,
                    "total": total_batches,
                    "message": f"Elaborazione batch {batch_num}/{total_batches}..."
                })
            
            prompt = f"""
            You are a literary editor expert in Italian literature.
            I have a raw list of potential characters extracted from a text.
            
            INPUT DATA (JSON):
            {json.dumps(batch, indent=2)}

            YOUR TASKS:
            1. CLEANUP: Identifying true characters. Remove non-persons.
            2. MERGE: Combine duplicates/variations. 
               - Example: "Hector", "Hector Starborn", "Hector 'no-one' Starborn" -> MUST becomes SINGLE entry "Hector Starborn".
               - Merge roles and contexts.
            3. ROLES: Infer role from context.
            
            IMPORTANT:
            - OUTPUT VALUES (role, context) MUST BE IN ITALIAN.
            - Even if keys are English, the content MUST be Italian.

            OUTPUT FORMAT:
            Return ONLY a raw JSON list of objects. No markdown, no wrapping text.
            Example: [ {{"name": "Renzo", "role": "Sposo"}} ]
            """
            
            try:
                tokens_received = []
                def collect_token(token):
                    tokens_received.append(token)
                    if on_progress:
                        on_progress({"type": "token", "token": token})
                
                response_text = self.refine_with_streaming(prompt, on_token=collect_token, force_json=True)
                
                batch_result = self.extract_json(response_text)
                if isinstance(batch_result, dict):
                    batch_result = [batch_result]
                
                if isinstance(batch_result, list):
                    refined_results.extend(batch_result)
                    if on_progress:
                        on_progress({
                            "type": "batch_complete",
                            "batch": batch_num,
                            "items": len(batch_result)
                        })
            except Exception as e:
                print(f"ERROR: Batch {batch_num} failed: {e}")
                refined_results.extend(batch)
                if on_progress:
                    on_progress({"type": "error", "message": str(e)})
        
        return refined_results

    def refine_characters(self, char_list):
        """
        Refine characters using batching (Non-streaming legacy support).
        """
        # 1. SORT to ensure duplicates (Hector, Hector Starborn) are adjacent
        char_list.sort(key=lambda x: x.get("name", "").lower())
        
        batch_size = 20
        refined_results = []
        
        for i in range(0, len(char_list), batch_size):
            batch = char_list[i : i + batch_size]
            print(f"DEBUG: Processing batch {i//batch_size + 1}...")
            
            prompt = f"""
            You are a literary editor expert in Italian literature.
            I have a raw list of potential characters extracted from a text.
            
            INPUT DATA (JSON):
            {json.dumps(batch, indent=2)}

            YOUR TASKS:
            1. CLEANUP: Identifying true characters. Remove non-persons.
            2. MERGE: Combine duplicates/variations. 
               - Example: "Hector", "Hector Starborn", "Hector 'no-one' Starborn" -> MUST becomes SINGLE entry "Hector Starborn".
               - Merge roles and contexts.
            3. ROLES: Infer role from context.
            
            IMPORTANT:
            - OUTPUT VALUES (role, context) MUST BE IN ITALIAN.
            - Even if keys are English, the content MUST be Italian.

            OUTPUT FORMAT:
            Return ONLY a raw JSON list of objects. No markdown, no wrapping text.
            Example: [ {{"name": "Renzo", "role": "Sposo"}} ]
            """
            
            try:
                response_text = self.client.completion(prompt, force_json=True)
                batch_result = self.extract_json(response_text)
                
                if isinstance(batch_result, dict):
                    batch_result = [batch_result]
                
                if isinstance(batch_result, list):
                    refined_results.extend(batch_result)
                else:
                    refined_results.extend(batch)
                    
            except Exception as e:
                print(f"ERROR: Batch failed: {e}")
                refined_results.extend(batch)
        
        return refined_results

    def refine_world_elements(self, world_list):
        """
        Refines world building elements.
        """
        batch_size = 8
        refined_results = []
        
        for i in range(0, len(world_list), batch_size):
            batch = world_list[i : i + batch_size]
            print(f"DEBUG: Refining World Batch {i//batch_size + 1}...")
            
            prompt = f"""
            You are a World Building expert assistant.
            I have a raw list of extracted entities (Places, Organizations, Objects) from a manuscript.

            CATEGORIES:
            - "Place" (Luoghi, Cities, Buildings, Rooms)
            - "Object" (Relevant items, Artifacts, Unique Weapons)
            - "System" (Magic systems, Technology, Government, Economy, Payment methods)
            - "Geography" (Natural environments, Mountains, Rivers, Weather)
            - "History" (Myths, Legends, Historical events)
            - "Culture" (Religions, Customs, Society, Festivals)

            INPUT DATA (JSON):
            {json.dumps(batch, indent=2)}

            TASKS:
            1. CLEANUP: Remove generic words, noise, or actual characters (people).
            2. CATEGORIZE: Assign the best CATEGORY from the list above.
            3. DESCRIPTION: Enhance 'raw_type' to a short description based on context.

            IMPORTANT:
            - OUTPUT VALUES (context, description) MUST BE IN ITALIAN.

            OUTPUT FORMAT (JSON List):
            Return ONLY a raw JSON list of objects. No markdown, no wrapping text.
            [ {{"name": "Atlantis", "category": "Place", "context": "Città perduta..."}} ]
            """
            
            try:
                response_text = self.client.completion(prompt, force_json=True)
                batch_result = self.extract_json(response_text)
                
                if isinstance(batch_result, dict):
                    batch_result = [batch_result]
                
                if isinstance(batch_result, list):
                    refined_results.extend(batch_result)
                else:
                    refined_results.extend(batch)
            except Exception as e:
                print(f"ERROR World Batch: {e}")
                refined_results.extend(batch)

        return refined_results

    def refine_glossary(self, term_list):
        """
        Refines potential glossary terms (neologisms, invented words, specific terminology).
        """
        batch_size = 15
        refined_results = []
        
        for i in range(0, len(term_list), batch_size):
            batch = term_list[i : i + batch_size]
            print(f"DEBUG: Refining Glossary Batch {i//batch_size + 1}...")
            
            prompt = f"""
            You are a Lexicographer for a Sci-Fi/Fantasy universe.
            I have a raw list of potential neologisms or specific terms extracted from a manuscript.
            
            INPUT DATA (JSON):
            {json.dumps(batch, indent=2)}
            
            TASKS:
            1. FILTER: Keep ONLY terms that are:
               - Invented words / Neologisms
               - Fictional Technology / Magic / Science terms
               - Specific cultural rankings or titles (that are not standard real-world ones)
               - Unique proper nouns for objects/concepts (NOT People, NOT Places).
            2. DISCARD: Common words, slight typos of real words, actual people names, actual place names.
            3. DEFINE: Write a short, in-world definition based on the provided context.
            
            IMPORTANT:
            - OUTPUT VALUES (definition) MUST BE IN ITALIAN.
            
            OUTPUT FORMAT (JSON List):
            Return ONLY a raw JSON list of objects. No markdown, no wrapping text.
            [ {{"term": "Lightsaber", "definition": "Arma elegante, una lama di energia..."}} ]
            """
            
            try:
                response_text = self.client.completion(prompt, force_json=True)
                batch_result = self.extract_json(response_text)
                
                if isinstance(batch_result, dict):
                    batch_result = [batch_result]
                    
                if isinstance(batch_result, list):
                    refined_results.extend(batch_result)
                else:
                    print(f"WARN: Glossary batch returned invalid format: {type(batch_result)}")
            except Exception as e:
                print(f"ERROR Glossary Batch: {e}")
                
        return refined_results

    def generate_synopsis(self, text, num_posts=5):
        """
        Genera riassunti POST.
        """
        text_length = len(text)
        chunk_size = text_length // num_posts
        synopses = []
        
        for i in range(num_posts):
            start = i * chunk_size
            end = (i + 1) * chunk_size if i < num_posts - 1 else text_length
            chunk = text[start:end]
            
            if end < text_length:
                last_para = chunk.rfind('\\n\\n')
                if last_para > chunk_size * 0.5:
                    chunk = chunk[:last_para]
            
            print(f"DEBUG: Generating synopsis for POST {i+1}/{num_posts}...")
            
            prompt = f"""
            Sei un esperto editor letterario italiano.
            Ti viene fornito un estratto da un manoscritto. Crea un riassunto breve e coinvolgente per un "POST" (sezione/capitolo).
            
            ESTRATTO:
            {chunk[:8000]}
            
            ISTRUZIONI:
            1. Scrivi un riassunto di 2-3 frasi che catturi l'essenza di questa sezione
            2. Menziona i personaggi principali coinvolti
            3. Indica l'ambientazione se rilevante
            4. Non usare spoiler per eventi futuri
            
            FORMATO OUTPUT:
            Restituisci SOLO un JSON con questa struttura. No markdown, no wrapping text.
            {{"post_number": {i+1}, "title": "Titolo breve", "summary": "Il riassunto..."}}
            """
            
            try:
                response_text = self.client.completion(prompt, force_json=True)
                parsed = self.extract_json(response_text)
                
                if isinstance(parsed, list) and len(parsed) > 0:
                    synopses.append(parsed[0])
                elif isinstance(parsed, dict):
                    synopses.append(parsed)
                else:
                    synopses.append({
                        "post_number": i + 1,
                        "title": f"POST {i+1}",
                        "summary": "Impossibile generare riassunto"
                    })
            except Exception as e:
                print(f"ERROR Synopsis {i+1}: {e}")
                synopses.append({
                    "post_number": i + 1,
                    "title": f"POST {i+1}",
                    "summary": f"Errore: {str(e)}"
                })
        
        return synopses

    def analyze_chunk(self, chunk, mode="characters"):
        """
        Analizza un singolo chunk di testo.
        """
        if mode == "characters":
            prompt = f"""
            Sei un esperto analista letterario.
            Estrai i personaggi presenti in questo segmento di testo.
            
            TESTO:
            {chunk[:6000]}
            
            ISTRUZIONI:
            1. Estrai solo PERSONAGGI (Persone, Entità senzienti).
            2. Ignora comparse senza nome.
            3. Inferisci il ruolo dal contesto immediato.

            IMPORTANT:
            - OUTPUT VALUES (role, context) MUST BE IN ITALIAN.
            
            OUTPUT (JSON List):
            Return ONLY a raw JSON list of objects. No markdown, no wrapping text.
            [ {{"name": "Nome", "role": "Ruolo", "context": "Breve frase contesto"}} ]
            """
        elif mode == "synopsis":
             prompt = f"""
            Sei un esperto editor letterario italiano.
            Ti viene fornito un estratto da un manoscritto. Crea un riassunto breve e coinvolgente.
            
            ESTRATTO:
            {chunk[:6000]}
            
            ISTRUZIONI:
            1. Scrivi un riassunto di 2-3 frasi che catturi l'essenza di questa sezione.
            2. Menziona i personaggi principali coinvolti.
            3. Indica l'ambientazione se rilevante.
            
            FORMATO OUTPUT (JSON):
            Return ONLY a raw JSON object. No markdown, no wrapping text.
            {{"title": "Titolo breve", "summary": "Il riassunto..."}}
            """
        elif mode == "world":
             prompt = f"""
            Sei un esperto di World Building.
            Estrai elementi di ambientazione in questo segmento.
            
            TESTO:
            {chunk[:6000]}
            
            CATEGORIE: Place, Object, System, History, Culture.

            IMPORTANT:
            - OUTPUT VALUES (context) MUST BE IN ITALIAN.
            
            OUTPUT (JSON List):
            Return ONLY a raw JSON list of objects. No markdown, no wrapping text.
            [ {{"name": "Nome", "category": "Categoria", "context": "Descrizione"}} ]
            """
        else: # glossary
             prompt = f"""
            Sei un Lexicographer esperto in Sci-Fi/Fantasy.
            Estrai potenziali neologismi o termini specifici dal testo.
            
            TESTO:
            {chunk[:6000]}
            
            ISTRUZIONI:
            1. Trova parole inventate, tecnologia fittizia, magia.
            2. Ignora Nomi propri di persona o Luoghi comuni.
            3. Fornisci una definizione basata sul contesto.

            IMPORTANT:
            - OUTPUT VALUES (definition, context) MUST BE IN ITALIAN.
            
            OUTPUT (JSON List):
            Return ONLY a raw JSON list of objects. No markdown, no wrapping text.
            [ {{"term": "Termine", "definition": "Definizione", "context": "Contesto"}} ]
            """
            
        try:
            response_text = self.client.chat([{"role": "user", "content": prompt}], force_json=True)
            res = self.extract_json(response_text)
            if mode != "synopsis" and isinstance(res, dict):
                res = [res]
            return res
        except Exception as e:
            print(f"Chunk Analysis Error: {e}")
            return []

    def merge_results(self, results_list, mode="characters"):
        """
        Consolida una lista di risultati grezzi (unendo duplicati).
        """
        prompt = f"""
        Sei un Editor esperto. 
        Ho una lista di {mode} estratti da vari capitoli. Ci sono duplicati e variazioni (es. "John", "John Doe").
        
        INPUT LIST:
        {json.dumps(results_list, indent=2)}
        
        COMPITI:
        1. Unifica i duplicati (scegli il nome più completo).
        2. Somma eventuali conteggi (se presenti) o stima importanza.
        3. Unisci i contesti per creare una descrizione coerente.

        IMPORTANT:
        - OUTPUT VALUES (role, context) MUST BE IN ITALIAN.
        
        OUTPUT (JSON List):
        Return ONLY a raw JSON list of objects. No markdown, no wrapping text.
        Restituisci una lista pulita e consolidata.
        """
        
        try:
            response_text = self.client.chat([{"role": "user", "content": prompt}], force_json=True)
            res = self.extract_json(response_text)
            if isinstance(res, dict):
                res = [res]
            return res
        except Exception as e:
            print(f"Merge Error: {e}")
            return results_list

ollama_client = OllamaClient()
