"""
MemVid Integration for BookAnalyzer
Allows indexing and semantic search of entire manuscripts.
"""
import os
import json
import logging
import requests
import numpy as np

# --- PATCH MEMVID DEPENDENCIES ---
try:
    import memvid.index
    from memvid import config as memvid_config
    
    class OllamaEmbedder:
        """Sostituto di SentenceTransformer che usa Ollama locale."""
        def __init__(self, model_name="embeddinggemma:latest"):
            self.model = model_name
            self.api_url = "http://localhost:11434/api/embeddings"
            self.dimension = 768
            print(f"🔹 OllamaEmbedder inizializzato (Modello: {self.model}, Dim: {self.dimension})")

        def encode(self, sentences, show_progress_bar=False, batch_size=32, convert_to_numpy=True, normalize_embeddings=True):
            if isinstance(sentences, str): 
                sentences = [sentences]
            embeddings = []
            
            for text in sentences:
                try:
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
    
    # Patch config
    import memvid.encoder
    import memvid.retriever
    
    _original_get_config = memvid_config.get_default_config
    def _patched_get_config():
        c = _original_get_config()
        c["embedding"]["model"] = "embeddinggemma:latest"
        c["embedding"]["dimension"] = 768
        return c
    
    memvid_config.get_default_config = _patched_get_config
    memvid.index.get_default_config = _patched_get_config
    memvid.encoder.get_default_config = _patched_get_config
    memvid.retriever.get_default_config = _patched_get_config
    
    from memvid import MemvidEncoder, MemvidRetriever
    MEMVID_AVAILABLE = True
    
except ImportError as e:
    logging.warning(f"MemVid not available: {e}")
    MEMVID_AVAILABLE = False

# Import local toon
try:
    from . import toon
except ImportError:
    pass


class ManuscriptMemory:
    """
    Gestisce l'indicizzazione e la ricerca semantica di un manoscritto.
    """
    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.memory_file = os.path.join(project_dir, "manuscript.mp4")
        self.index_file = os.path.join(project_dir, "manuscript.json")
        self.chunks_file = os.path.join(project_dir, "chunks.json")
        
        self._encoder = None
        self._retriever = None
        self._chunks = []
    
    def is_available(self):
        """Check if MemVid is available and working."""
        return MEMVID_AVAILABLE
    
    def is_indexed(self):
        """Check if manuscript is already indexed."""
        return os.path.exists(self.memory_file) and os.path.exists(self.index_file)
    
    def _split_into_chunks(self, text, chunk_size=1500, overlap=200):
        """
        Split text into overlapping chunks.
        Each chunk is roughly chunk_size chars with overlap chars of context.
        """
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at paragraph or sentence
            if end < len(text):
                # Look for paragraph break
                last_para = chunk.rfind('\n\n')
                if last_para > chunk_size * 0.5:
                    end = start + last_para + 2
                    chunk = text[start:end]
                else:
                    # Look for sentence end
                    last_sentence = max(chunk.rfind('. '), chunk.rfind('! '), chunk.rfind('? '))
                    if last_sentence > chunk_size * 0.5:
                        end = start + last_sentence + 2
                        chunk = text[start:end]
            
            chunks.append({
                "text": chunk.strip(),
                "start": start,
                "end": end
            })
            start = end - overlap
        
        return chunks
    
    def index_manuscript(self, text, on_progress=None):
        """
        Index an entire manuscript for semantic search.
        
        Args:
            text: Full manuscript text
            on_progress: Optional callback(current, total, message)
        
        Returns:
            Number of chunks indexed
        """
        if not MEMVID_AVAILABLE:
            raise RuntimeError("MemVid not available. Install with: pip install memvid")
        
        if on_progress:
            on_progress(0, 100, "Splitting text into chunks...")
        
        # Split into chunks
        self._chunks = self._split_into_chunks(text)
        
        # Save chunks for later reference
        with open(self.chunks_file, 'w', encoding='utf-8') as f:
            json.dump(self._chunks, f, ensure_ascii=False, indent=2)
        
        if on_progress:
            on_progress(10, 100, f"Found {len(self._chunks)} chunks. Indexing...")
        
        # Create encoder and add chunks
        self._encoder = MemvidEncoder()
        
        for i, chunk in enumerate(self._chunks):
            self._encoder.add_text(chunk["text"])
            if on_progress and i % 10 == 0:
                progress = 10 + int(70 * i / len(self._chunks))
                on_progress(progress, 100, f"Indexing chunk {i+1}/{len(self._chunks)}...")
        
        if on_progress:
            on_progress(80, 100, "Building search index...")
        
        # Build video index
        self._encoder.build_video(self.memory_file, self.index_file, show_progress=False)
        
        if on_progress:
            on_progress(100, 100, "Indexing complete!")
        
        return len(self._chunks)
    
    def search(self, query, top_k=5):
        """
        Search for relevant chunks in the indexed manuscript.
        
        Args:
            query: Search query
            top_k: Number of results to return
        
        Returns:
            List of relevant text chunks
        """
        if not self.is_indexed():
            return []
        
        if self._retriever is None:
            try:
                self._retriever = MemvidRetriever(self.memory_file, self.index_file)
            except Exception as e:
                logging.error(f"Failed to load retriever: {e}")
                return []
        
        try:
            results = self._retriever.search(query, top_k=top_k)
            return results
        except Exception as e:
            logging.error(f"Search error: {e}")
            return []
    
    def get_context_for_analysis(self, analysis_type="characters", max_tokens=8000):
        """
        Get relevant context for a specific type of analysis.
        Uses semantic search to find most relevant chunks.
        
        Args:
            analysis_type: "characters", "world", "synopsis"
            max_tokens: Approximate token limit
        
        Returns:
            Concatenated relevant text
        """
        queries = {
            "characters": [
                "personaggi principali protagonista eroe",
                "nome personaggio descrizione carattere",
                "dialogo parlò disse rispose"
            ],
            "world": [
                "luogo città pianeta mondo ambientazione",
                "tecnologia sistema magia potere",
                "organizzazione governo società cultura"
            ],
            "synopsis": [
                "capitolo intro inizio storia",
                "eventi principali successe accadde",
                "finale conclusione risoluzione"
            ]
        }
        
        all_results = []
        for query in queries.get(analysis_type, queries["characters"]):
            results = self.search(query, top_k=3)
            all_results.extend(results)
        
        # Deduplicate and truncate
        seen = set()
        unique_results = []
        char_count = 0
        max_chars = max_tokens * 4  # Rough estimate
        
        for result in all_results:
            if result not in seen and char_count < max_chars:
                seen.add(result)
                unique_results.append(result)
                char_count += len(result)
        
        return "\n\n---\n\n".join(unique_results)


# Singleton instance (can be replaced per project)
_memory_instance = None

def get_memory(project_dir):
    """Get or create memory instance for a project."""
    global _memory_instance
    if _memory_instance is None or _memory_instance.project_dir != project_dir:
        _memory_instance = ManuscriptMemory(project_dir)
    return _memory_instance
