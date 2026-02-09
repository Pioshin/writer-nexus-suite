import os
import json
import logging
import requests
import numpy as np

# --- 1. PATCH MEMVID DEPENDENCIES (PRIMA DELL'IMPORT) ---
import memvid.index
from memvid import config as memval_config

class OllamaEmbedder:
    """Sostituto di SentenceTransformer che usa Ollama locale."""
    def __init__(self, model_name="embeddinggemma:latest"):
        self.model = model_name
        self.api_url = "http://localhost:11434/api/embeddings"
        # Importante: la dimensione deve corrispondere al modello (768 per embeddinggemma/nomic)
        self.dimension = 768 
        print(f"🔹 OllamaEmbedder inizializzato (Modello: {self.model}, Dim: {self.dimension})")

    def encode(self, sentences, show_progress_bar=False, batch_size=32, convert_to_numpy=True, normalize_embeddings=True):
        if isinstance(sentences, str): sentences = [sentences]
        embeddings = []
        
        for text in sentences:
            try:
                # Timeout breve per non bloccare tutto se Ollama è giù
                res = requests.post(self.api_url, json={"model": self.model, "prompt": text}, timeout=30)
                if res.status_code == 200:
                    emb = res.json().get('embedding')
                    if emb:
                        embeddings.append(emb)
                    else:
                        logging.warning(f"Ollama embedding vuoto per '{text[:20]}...'")
                        embeddings.append(np.zeros(self.dimension))
                else:
                    logging.error(f"Ollama Error {res.status_code}: {res.text}")
                    embeddings.append(np.zeros(self.dimension))
            except Exception as e:
                logging.error(f"Ollama Connection Error: {e}")
                embeddings.append(np.zeros(self.dimension))
        
        arr = np.array(embeddings, dtype='float32')
        if normalize_embeddings:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            arr = arr / (norms + 1e-10)
        return arr

# Sostituiamo la classe originale
memvid.index.SentenceTransformer = OllamaEmbedder

# 3. Importiamo anche gli altri moduli per patchare le loro referenze a get_default_config
import memvid.encoder
import memvid.retriever

# Aggiorniamo la config di default per riflettere le dimensioni
_original_get_config = memval_config.get_default_config
def _patched_get_config():
    c = _original_get_config()
    c["embedding"]["model"] = "embeddinggemma:latest"
    c["embedding"]["dimension"] = 768
    return c

# Applichiamo la patch ovunque
memval_config.get_default_config = _patched_get_config
memvid.index.get_default_config = _patched_get_config
memvid.encoder.get_default_config = _patched_get_config
memvid.retriever.get_default_config = _patched_get_config
# --------------------------------------------------------

from memvid import MemvidEncoder, MemvidRetriever
import toon

# GLOBAL CACHE PER EVITARE RELOAD PESANTI
_encoder_cache = None
_retriever_cache = {} # Mappa path_video -> retriever

class MemoryManager:
    def __init__(self, sandbox_root):
        self.sandbox_root = sandbox_root
        self.memory_file = os.path.join(sandbox_root, "agent_memory.mp4")
        self.index_file = os.path.join(sandbox_root, "agent_memory.json")
        self.raw_memory_file = os.path.join(sandbox_root, "long_term_memory.toon")

    def _get_encoder(self):
        global _encoder_cache
        if _encoder_cache is None:
            print("Caricamento Encoder Memoria (MemVid + TOON)...")
            _encoder_cache = MemvidEncoder()
            # Se esiste un file TOON con i ricordi, carichiamolo
            if os.path.exists(self.raw_memory_file):
                try:
                    with open(self.raw_memory_file, 'r', encoding='utf-8') as f:
                        all_memories = f.read()
                    if all_memories.strip():
                        _encoder_cache.add_text(all_memories)
                except Exception as e:
                    print(f"Errore caricamento TOON memory: {e}")
        return _encoder_cache

    def _get_retriever(self, force_reload=False):
        global _retriever_cache
        if not os.path.exists(self.memory_file) or not os.path.exists(self.index_file):
            return None
        
        if self.memory_file not in _retriever_cache or force_reload:
            print(f"Inizializzazione Retriever per {self.memory_file}...")
            try:
                _retriever_cache[self.memory_file] = MemvidRetriever(self.memory_file, self.index_file)
            except Exception as e:
                print(f"Errore caricamento retriever: {e}")
                return None
        return _retriever_cache[self.memory_file]

    def store(self, text):
        try:
            # 1. Converte in TOON per efficienza
            toon_data = toon.to_toon(text)
            
            # 2. Salva nel file TOON
            with open(self.raw_memory_file, 'a', encoding='utf-8') as f:
                f.write(toon_data + "\n")
            
            # 3. Aggiorna l'encoder cache
            encoder = self._get_encoder()
            encoder.add_text(toon_data)
            
            # 4. Costruisci il video e l'indice
            print(f"Costruzione video memoria (TOON) in corso...")
            encoder.build_video(self.memory_file, self.index_file, show_progress=False)
            
            # 5. Forza il ricaricamento del retriever
            self._get_retriever(force_reload=True)
            
            return f"Memorizzato in formato TOON ({os.path.basename(self.memory_file)})."
        except Exception as e:
            return f"Errore salvataggio memoria TOON: {str(e)}"

    def search(self, query, top_k=3):
        retriever = self._get_retriever()
        if not retriever:
            return []
        
        try:
            results = retriever.search(query, top_k=top_k)
            return results
        except Exception as e:
            print(f"Errore ricerca memoria: {e}")
            return []
