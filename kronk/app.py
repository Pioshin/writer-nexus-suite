import os
import re
import json
import requests
import logging
import traceback
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

import sandbox
import memory
try:
    from llm_client import LLMClient
except ImportError:
    # Fallback/Mock se llm_client non copiato (ma dovremmo averlo)
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from llm_client import LLMClient

app = Flask(__name__)
global_llm_client = LLMClient()

# ===== LOGGING CONFIGURATION =====
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler()]
)

# CONFIGURAZIONE
OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags" # URL per la lista modelli
MODEL_NAME = "qwen3-vl:latest" 
OLLAMA_TIMEOUT = 120 # Secondi prima del timeout

# Assicuriamo che la default esista
if not os.path.exists(sandbox.DEFAULT_SANDBOX_DIR):
    os.makedirs(sandbox.DEFAULT_SANDBOX_DIR)

# ===== GLOBAL ERROR HANDLER =====
@app.errorhandler(Exception)
def handle_exception(e):
    """Cattura qualsiasi errore non gestito e lo trasforma in JSON."""
    logging.error(f"Uncaught Exception: {repr(e)}\n{traceback.format_exc()}")
    return jsonify({
        "error": "Internal Server Error",
        "message": str(e)
    }), 500

@app.route('/models', methods=['GET'])
def get_models():
    """Recupera la lista dei modelli disponibili su Ollama."""
    try:
        base_url = request.args.get('ollama_url', OLLAMA_API_URL).replace('/api/chat', '')
        r = requests.get(f"{base_url}/api/tags", timeout=5)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        logging.warning(f"Errore recupero modelli: {e}")
        return jsonify({"error": str(e), "models": []})

@app.route('/api/config', methods=['GET'])
def get_config():
    """Recupera configurazione LLM corrente."""
    return jsonify({
        "provider": global_llm_client.provider,
        "model": global_llm_client.model,
        "base_url": global_llm_client.base_url,
        "api_key": global_llm_client.api_key,
        "ctx": global_llm_client.ctx,
        "timeout": global_llm_client.timeout,
        "keep_alive": global_llm_client.keep_alive
    })

@app.route('/api/config', methods=['POST'])
def update_config():
    """Aggiorna configurazione LLM globale."""
    try:
        data = request.get_json(force=True)
        global_llm_client.update_config(
            provider=data.get("provider"),
            model=data.get("model"),
            base_url=data.get("url") or data.get("base_url"),
            api_key=data.get("api_key"),
            ctx=data.get("ctx"),
            timeout=data.get("timeout"),
            keep_alive=data.get("keep_alive")
        )
        return jsonify({"status": "updated", "config": data})
    except Exception as e:
        logging.error(f"Errore config: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/chat/rename', methods=['POST'])
def rename_chat():
    """Rinomina una chat esistente."""
    try:
        data = request.get_json(force=True)
        chat_id = data.get('chat_id')
        new_title = data.get('new_title')
        
        if not chat_id or not new_title:
             return jsonify({"error": "Missing params"}), 400

        filepath = os.path.join(CHAT_HISTORY_DIR, f"chat_{chat_id}.json")
        if not os.path.exists(filepath):
            return jsonify({"error": "Chat not found"}), 404
            
        with open(filepath, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
        
        chat_data["title"] = new_title
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, indent=4)
            
        return jsonify({"success": True, "new_title": new_title})
    except Exception as e:
        logging.error(f"Errore rinomina chat: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/unload', methods=['POST'])
def unload_model():
    """Scarica un modello dalla memoria (keep_alive=0). SOLO OLLAMA."""
    # ... legacy support for ollama only ...
    return jsonify({"success": True})

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/files', methods=['GET'])
def get_files():
    try:
        req_path = request.args.get('path')
        sandbox_root = sandbox.get_sandbox_path(req_path)
        return jsonify({"files": sandbox.list_files(sandbox_root), "current_path": sandbox_root})
    except Exception as e:
        logging.error(f"Errore lista file: {e}")
        return jsonify({"files": [], "error": str(e)})

@app.route('/read', methods=['GET'])
def read_file_content():
    try:
        filename = request.args.get('filename')
        req_path = request.args.get('path')
        sandbox_root = sandbox.get_sandbox_path(req_path)
        
        if not filename:
            return jsonify({"error": "Filename required"}), 400
            
        content = sandbox.read_file(filename, sandbox_root)
        return jsonify({"content": content, "filename": filename})
    except Exception as e:
        logging.error(f"Errore lettura file API: {e}")
        return jsonify({"error": str(e)}), 500

CHAT_HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history")
if not os.path.exists(CHAT_HISTORY_DIR):
    os.makedirs(CHAT_HISTORY_DIR)

@app.route('/chats', methods=['GET'])
def list_chats():
    try:
        chats = []
        for filename in os.listdir(CHAT_HISTORY_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(CHAT_HISTORY_DIR, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        chat_data = json.load(f)
                        chats.append({
                            "id": filename.replace(".json", ""),
                            "title": chat_data.get("title", "Nuova Chat"),
                            "timestamp": chat_data.get("last_updated", "")
                        })
                except: continue
        chats.sort(key=lambda x: x['timestamp'], reverse=True)
        return jsonify(chats)
    except Exception as e:
        logging.error(f"Errore lista chat: {e}")
        return jsonify([])

@app.route('/chat/<chat_id>', methods=['GET'])
def get_chat(chat_id):
    filepath = os.path.join(CHAT_HISTORY_DIR, f"{chat_id}.json")
    if not os.path.exists(filepath):
        return jsonify({"error": "Chat non trovata"}), 404
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except Exception as e:
        logging.error(f"Errore caricamento sessione {chat_id}: {e}")
        return jsonify({"error": str(e)}), 500

def save_chat_session(chat_id, history, title=None):
    try:
        filepath = os.path.join(CHAT_HISTORY_DIR, f"{chat_id}.json")
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        old_data = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
            except: pass
        
        # Logic: If 'title' arg is provided, use it (Renaming). 
        # Otherwise keep existing title. Verification: 'title' arg is passed when generating specific new title.
        final_title = title if title else old_data.get("title", "Nuova Chat")
        
        chat_data = {
            "id": chat_id,
            "history": history,
            "last_updated": now,
            "title": final_title
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, indent=4)
    except Exception as e:
        logging.error(f"Impossibile salvare sessione {chat_id}: {e}")

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json(force=True)
        user_msg = data.get('message')
        history = data.get('history', [])
        chat_id = data.get('chat_id')
        
        if not user_msg:
            return jsonify({"error": "Messaggio mancante"}), 400
        
        model_name = data.get('model', '')
        
        req_path = data.get('sandbox_path')
        sandbox_root = sandbox.get_sandbox_path(req_path)

        # Utilizza global_llm_client invece di params locali
        # (Opzionale: aggiornare config temporanea se arrivano params? Per ora usiamo globale)

        def generate_title(hist):
            try:
                # Genera titolo solo se siamo all'inizio (es. 2 messaggi)
                if len(hist) >= 2 and len(hist) <= 4:
                    title_prompt = "Genera un titolo brevissimo (max 4 parole) per questa chat. Rispondi solo col titolo.\n" + \
                                   "\n".join([f"{m['role']}: {m['content']}" for m in hist])
                    
                    new_title = global_llm_client.completion(title_prompt).strip().strip('"')
                    if new_title:
                        save_chat_session(chat_id, hist, title=new_title)
            except Exception as e:
                logging.warning(f"Errore generazione titolo: {e}")

        def generate():
            try:
                yield json.dumps({"action": "Inizio generazione..."}) + "\n"
                
                # Sincronizzazione Memoria
                yield json.dumps({"action": "Ricerca memoria..."}) + "\n"
                try:
                    mem = memory.MemoryManager(sandbox_root)
                    memory_context = mem.search(user_msg, top_k=2)
                    mem_str = "\n".join([f"- {m}" for m in memory_context]) if memory_context else "Nessun ricordo trovato."
                except Exception as me:
                    # logging.warning(f"Errore Memoria: {me}")
                    mem_str = "Memoria non disponibile."

                # SOMMARIO STORICO (Distillazione)
                history_summary = ""
                if len(history) > 20: 
                    yield json.dumps({"action": "Compressione contesto..."}) + "\n"
                    try:
                        summary_prompt = "Riassumi i punti chiave di questa conversazione:\n" + \
                                         "\n".join([f"{m['role']}: {m['content']}" for m in history[:-5]])
                        history_summary = global_llm_client.completion(summary_prompt)
                    except: history_summary = "Conversazione in corso."
                
                # LISTA FILE
                latest_files = sandbox.list_files(sandbox_root)
                files_str = "\n".join([f['display'] for f in latest_files]) if latest_files else "Nessun file."

                # SYSTEM PROMPT (Anti-Hallucination & Context)
                # Se il modello è custom ("adam" o "adan"), NON sovrascrivere la persona "Sei Kronk".
                # Ma fornisci comunque il contesto operativo (File, Memoria).
                is_custom_persona = 'adam' in model_name.lower() or 'adan' in model_name.lower()
                
                if is_custom_persona:
                    sys_content = (
                        f"CONTESTO OPERATIVO:\n"
                        f"CARTELLA DI LAVORO: {sandbox_root}\n"
                        f"FILE DISPONIBILI:\n{files_str}\n\n"
                        f"NOTE MEMORIA: {mem_str}\n\n"
                        "ISTRUZIONI SANDBOX:\n"
                        "1. Usa [[WRITE: filename | content]] per creare file.\n"
                        "2. Usa [[READ: filename]] per leggere file.\n"
                        "3. Usa [[MEM_SAVE: text]] per salvare ricordi.\n"
                    )
                else:
                    sys_content = (
                        "Sei Kronk, un assistente AI avanzato che opera in una Sandbox.\n"
                        f"CARTELLA DI LAVORO: {sandbox_root}\n"
                        f"FILE DISPONIBILI:\n{files_str}\n\n"
                        f"NOTE MEMORIA: {mem_str}\n\n"
                        "REGOLE FONDAMENTALI (Anti-Allucinazione):\n"
                        "1. NON inventare il contenuto dei file. Se ti viene chiesto di un file che non hai letto (non presente nella chat history con tag [[READ]]), devi dire 'Devo leggere il file X prima di rispondere' o usare lo strumento [[READ: filename]].\n"
                        "2. Se un file non è nella lista 'FILE DISPONIBILI', non esiste.\n"
                        "3. Usa [[WRITE: filename | content]] per creare/modificare file.\n"
                        "4. Usa [[READ: filename]] per leggere file.\n"
                        "5. Usa [[MEM_SAVE: text]] per salvare informazioni importanti nella memoria a lungo termine.\n"
                    )
                
                if history_summary:
                    sys_content += f"\nRIASSUNTO PRECEDENTE: {history_summary}"

                # NOTA: Ollama sostituisce il SYSTEM del Modelfile se mandiamo un messaggio "system".
                # Per i modelli custom, accodiamo il contesto all'ultimo messaggio USER o usiamo un ruolo diverso?
                # Se usiamo "system", la persona "Adam" definita nel Modelfile viene persa.
                # TRUCCO: Per i custom, mettiamo il contesto come primo messaggio USER (o pre-prompt).
                
                if is_custom_persona:
                    # Inseriamo il contesto come messaggio utente fittizio o nascosto all'inizio?
                    # Meglio metterlo come primo messaggio della history per questa turn.
                    # Oppure, se appendiamo a user_msg, rischiamo di confondere il modello.
                    # Proviamo a metterlo come SYSTEM ma che NON ridefinisce "Sei X". 
                    # Purtroppo Ollama sovrascrive TUTTO il blocco SYSTEM.
                    # SOLUZIONE: Leggere il Modelfile? No, troppo lento.
                    # SOLUZIONE MIGLIORE: Inserire il contesto come messaggio "user" prima della history?
                    # O accodarlo all'ultimo user message.
                    messages = [] # Nessun system message esplicito che sovrascrive
                    # Ma dobbiamo passare il contesto. Lo mettiamo come primo messaggio USER di 'setup'.
                    messages.append({"role": "user", "content": f"SYSTEM_INJECTION [Context Info]:\n{sys_content}\n\n(Ignora questo messaggio come input utente, usalo solo come contesto)."})
                    messages.append({"role": "assistant", "content": "Ricevuto. Contesto aggiornato."})
                else:
                    messages = [{"role": "system", "content": sys_content}]
                
                # Aggiungi ultimi messaggi (max 10)
                messages.extend(history[-10:]) 
                messages.append({"role": "user", "content": user_msg})

                # Generazione Streaming
                full_response = ""
                
                # Chiama global_llm_client.chat con streaming
                # Nota: chat() restituisce un generatore se stream=True
                stream = global_llm_client.chat(messages, stream=True)
                
                for token in stream:
                    full_response += token
                    yield json.dumps({"token": token}) + "\n"
                
                # WRITE Handling
                wm = re.search(r'\[\[WRITE:\s*(.*?)\|\s*(.*?)\]\]', full_response, re.DOTALL)
                if wm:
                    fname = wm.group(1).strip()
                    fcont = wm.group(2).strip()
                    sandbox.write_file(fname, fcont, sandbox_root)
                    yield json.dumps({"action": f"💾 Scritto: {fname}"}) + "\n"

                # MEM_SAVE Handling
                mm = re.search(r'\[\[MEM_SAVE:\s*(.*?)\]\]', full_response, re.DOTALL)
                if mm:
                    txt = mm.group(1).strip()
                    # if 'mem' in locals():
                    try:
                         # Re-instantiate mem if needed or ensure it's available
                         mem = memory.MemoryManager(sandbox_root) 
                         m_res = mem.store(txt)
                         yield json.dumps({"action": f"Ricordo: {m_res}"}) + "\n"
                    except: pass

                # READ Handling (Simple feedback)
                rm = re.search(r'\[\[READ:\s*(.*?)\]\]', full_response)
                if rm:
                    r_fname = rm.group(1).strip()
                    content = sandbox.read_file(r_fname, sandbox_root)
                    if content:
                        yield json.dumps({"action": f"📖 Letto: {r_fname}"}) + "\n"
                        # Per ora non facciamo loop automatico complesso, ma salviamo nel log che è stato letto?
                        # O appendiamo al prossimo messaggio utente?
                        # Strategia semplice: appendiamo un messaggio system fake alla history salvata
                        messages.append({"role": "system", "content": f"CONTENUTO {r_fname}:\n{content[:2000]}..."})
                        # Ma non rigeneriamo ora. L'utente vedrà che ha letto.
                        
                save_chat_session(chat_id, history + [{"role": "user", "content": user_msg}, {"role": "assistant", "content": full_response}])
                if len(history) <= 4:
                     generate_title(history + [{"role": "user", "content": user_msg}, {"role": "assistant", "content": full_response}])
                
                yield json.dumps({"action": "Pronto"}) + "\n"

            except Exception as ge:
                logging.error(f"Errore fatale in generate(): {ge}\n{traceback.format_exc()}")
                yield json.dumps({"error": "Errore interno durante lo streaming."}) + "\n"

        return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

    except Exception as e:
        logging.error(f"Errore in /chat POST: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== BIBBIA ENDPOINTS ====================
import bibbia

# Directory di default per BIBBIA
BIBBIA_WORK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "WORK")

@app.route('/bibbia/load', methods=['GET'])
def bibbia_load():
    """Carica la configurazione BIBBIA corrente."""
    try:
        manager = bibbia.BibbiaManager(BIBBIA_WORK_DIR)
        dna = manager.load_dna()
        sinossi = manager.get_sinossi_text()
        
        return jsonify({
            "success": True,
            "dna": dna,
            "sinossi": sinossi,
            "dna_tokens": manager.count_tokens_estimate(dna),
            "sinossi_tokens": manager.count_tokens_estimate(sinossi)
        })
    except Exception as e:
        logging.error(f"Errore caricamento BIBBIA: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/bibbia/save', methods=['POST'])
def bibbia_save():
    """Salva la configurazione BIBBIA (DNA e Sinossi)."""
    try:
        data = request.get_json(force=True)
        dna = data.get('dna', '')
        sinossi = data.get('sinossi', '')
        
        manager = bibbia.BibbiaManager(BIBBIA_WORK_DIR)
        
        dna_ok = manager.save_dna(dna)
        sinossi_ok = True
        
        if sinossi:
            sinossi_ok = manager.save_sinossi_text(sinossi)
            
        if dna_ok and sinossi_ok:
            # Ricostruisci anche il video MEMVID
            manager.build_memory_video()
            return jsonify({
                "success": True,
                "message": "BIBBIA e SINOSSI salvate e memoria aggiornata.",
                "tokens": manager.count_tokens_estimate(dna)
            })
        else:
            return jsonify({"success": False, "error": "Errore salvataggio"}), 500
    except Exception as e:
        logging.error(f"Errore salvataggio BIBBIA: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/bibbia/generate-modelfile', methods=['POST'])
def bibbia_generate_modelfile():
    """Genera il MODELFILE per Ollama con il DNA incluso."""
    try:
        data = request.get_json(force=True) if request.data else {}
        model_base = data.get('model_base', 'gemma3:27b-it-qat')
        
        manager = bibbia.BibbiaManager(BIBBIA_WORK_DIR)
        modelfile_path = manager.save_modelfile()
        
        if modelfile_path:
            # Leggi il contenuto per mostrarlo all'utente
            with open(modelfile_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return jsonify({
                "success": True,
                "path": modelfile_path,
                "content": content,
                "message": f"MODELFILE generato: {modelfile_path}"
            })
        else:
            return jsonify({"success": False, "error": "Errore generazione MODELFILE"}), 500
    except Exception as e:
        logging.error(f"Errore generazione MODELFILE: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/bibbia/extract', methods=['POST'])
def bibbia_extract():
    """Estrae automaticamente personaggi e entità dal romanzo."""
    try:
        data = request.get_json(force=True)
        file_path = data.get('file_path', '')
        
        if not file_path:
            return jsonify({"success": False, "error": "file_path richiesto"}), 400
        
        # Costruisci path assoluto
        if not os.path.isabs(file_path):
            file_path = os.path.join(BIBBIA_WORK_DIR, file_path)
        
        manager = bibbia.BibbiaManager(BIBBIA_WORK_DIR)
        extracted = manager.extract_bibbia_from_novel(file_path)
        
        if extracted:
            return jsonify({
                "success": True,
                "data": extracted
            })
        else:
            return jsonify({"success": False, "error": "Nessun dato estratto"}), 404
    except Exception as e:
        logging.error(f"Errore estrazione BIBBIA: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/bibbia/add-synopsis', methods=['POST'])
def bibbia_add_synopsis():
    """Aggiunge un riassunto di capitolo alla Cronaca."""
    try:
        data = request.get_json(force=True)
        capitolo = data.get('capitolo', 1)
        riassunto = data.get('riassunto', '')
        
        if not riassunto:
            return jsonify({"success": False, "error": "riassunto richiesto"}), 400
        
        manager = bibbia.BibbiaManager(BIBBIA_WORK_DIR)
        
        if manager.add_sinossi(capitolo, riassunto):
            # Ricostruisci anche il video MEMVID
            manager.build_memory_video()
            return jsonify({
                "success": True,
                "message": f"Riassunto capitolo {capitolo} aggiunto."
            })
        else:
            return jsonify({"success": False, "error": "Errore aggiunta sinossi"}), 500
    except Exception as e:
        logging.error(f"Errore aggiunta sinossi: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/bibbia/build-prompt', methods=['POST'])
def bibbia_build_prompt():
    """Assembla il prompt narrativo completo con i 3 livelli."""
    try:
        data = request.get_json(force=True) if request.data else {}
        novel_path = data.get('novel_path', '')
        include_sinossi = data.get('include_sinossi', True)
        last_n = data.get('last_n_chapters', 4)
        
        if novel_path and not os.path.isabs(novel_path):
            novel_path = os.path.join(BIBBIA_WORK_DIR, novel_path)
        
        manager = bibbia.BibbiaManager(BIBBIA_WORK_DIR)
        prompt = manager.build_narrative_prompt(
            novel_path=novel_path if novel_path else None,
            include_sinossi=include_sinossi,
            last_n_chapters=last_n
        )
        
        return jsonify({
            "success": True,
            "prompt": prompt,
            "tokens": manager.count_tokens_estimate(prompt)
        })
    except Exception as e:
        logging.error(f"Errore build prompt: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    logging.info("Kuzco-Server in fase di avvio...")
    app.run(debug=True, host='0.0.0.0', port=5000)

