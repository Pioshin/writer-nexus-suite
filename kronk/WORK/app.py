import os
import re
import json
import requests
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

import sandbox
import memory

app = Flask(__name__)

# CONFIGURAZIONE
OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags" # URL per la lista modelli
MODEL_NAME = "qwen3-vl:latest" 
OLLAMA_TIMEOUT = 120 # Secondi prima del timeout

# Assicuriamo che la default esista (anche se gestita da sandbox, fa comodo averla)
if not os.path.exists(sandbox.DEFAULT_SANDBOX_DIR):
    os.makedirs(sandbox.DEFAULT_SANDBOX_DIR)

@app.route('/models', methods=['GET'])
def get_models():
    """Recupera la lista dei modelli disponibili su Ollama."""
    try:
        # Usa l'URL configurato dall'utente se passato come parametro, altrimenti default
        base_url = request.args.get('ollama_url', OLLAMA_API_URL).replace('/api/chat', '')
        r = requests.get(f"{base_url}/api/tags", timeout=5)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e), "models": []})

@app.route('/unload', methods=['POST'])
def unload_model():
    """Scarica un modello dalla memoria (keep_alive=0)."""
    ollama_url = request.json.get('ollama_url', OLLAMA_API_URL)
    model = request.json.get('model')
    
    if not model:
        return jsonify({"success": False, "message": "Model name required"})

    try:
        # Per scaricare inviamo una richiesta vuota con keep_alive 0
        requests.post(ollama_url, json={
            "model": model, 
            "keep_alive": 0
        }, timeout=5)
        return jsonify({"success": True, "message": f"Modello {model} scaricato dalla VRAM."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/files', methods=['GET'])
def get_files():
    req_path = request.args.get('path')
    sandbox_root = sandbox.get_sandbox_path(req_path)
    try:
        return jsonify({"files": sandbox.list_files(sandbox_root), "current_path": sandbox_root})
    except Exception as e:
         return jsonify({"files": [], "error": str(e), "current_path": sandbox_root})

@app.route('/read', methods=['GET'])
def read_file_content():
    filename = request.args.get('filename')
    req_path = request.args.get('path')
    sandbox_root = sandbox.get_sandbox_path(req_path)
    
    if not filename:
        return jsonify({"error": "Filename required"}), 400
        
    content = sandbox.read_file(filename, sandbox_root)
    return jsonify({"content": content, "filename": filename})

def log_chat(user_msg, response, sandbox_root):
    """Salva la conversazione in un file JSONL per riferimento futuro."""
    log_file = os.path.join(sandbox_root, "chat_history.jsonl")
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            log_entry = {
                "timestamp": requests.utils.quote(str(os.times())), # Usiamo un placeholder se non vogliamo importare datetime
                "user": user_msg,
                "ai": response
            }
            f.write(json.dumps(log_entry) + "\n")
    except: pass

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get('message')
    history = data.get('history', [])
    
    current_ollama_url = data.get('ollama_url', OLLAMA_API_URL)
    current_model = data.get('model', MODEL_NAME)
    current_keep_alive = data.get('keep_alive', "5m")
    current_num_ctx = data.get('num_ctx', 4096) # Default 4k, ma impostabile
    
    req_path = data.get('sandbox_path')
    sandbox_root = sandbox.get_sandbox_path(req_path)

    # Recuperiamo i file (veloce)
    try:
        current_files = sandbox.list_files(sandbox_root)
    except:
        current_files = []
    files_str = ", ".join(current_files) if current_files else "Nessun file presente."

    def generate():
        yield json.dumps({"action": "Inizio generazione..."}) + "\n"
        
        # MEMORIA LUNGO TERMINE
        yield json.dumps({"action": "Sincronizzazione memoria (MemVid + TOON)..."}) + "\n"
        mem = memory.MemoryManager(sandbox_root)
        memory_context = mem.search(user_msg, top_k=2) # Ridotto per risparmiare spazio
        mem_str = "\n".join([f"- {m}" for m in memory_context]) if memory_context else "Nessun ricordo precedente trovato."
        
        if memory_context:
            yield json.dumps({"action": f"Trovati {len(memory_context)} ricordi rilevanti."}) + "\n"

        system_prompt = {
            "role": "system",
            "content": (
                "Sei Kronk, un assistente AI avanzato che gestisce file e MEMORIA A LUNGO TERMINE (MemVid + TOON). "
                f"CARTELLA LAVORO: {sandbox_root}\n"
                f"FILE PRESENTI: {files_str}\n"
                f"RICORDI RECUPERATI:\n{mem_str}\n\n"
                "REGOLE:\n"
                "1. Se ricevi informazioni personali o istruzioni importanti, salvale SEMPRE con: [[MEM_SAVE:testo]]\n"
                "2. COMANDI: [[READ:file]], [[WRITE:file|content]], [[LIST]], [[SCAN:file]]\n"
                "3. Se un file è grande, usa [[SCAN:file]] per vederne l'indice prima di leggerlo tutto.\n"
                "\nUsa i RICORDI sopra per essere coerente. Rispondi in italiano."
            )
        }

        # DISTILLAZIONE DELLA STORIA (Strategia Furba)
        # Se la storia è lunga, creiamo un riassunto per risparmiare token
        history_summary = ""
        if len(history) > 10:
            yield json.dumps({"action": "Distillazione cronologia per risparmiare token..."}) + "\n"
            try:
                # Chiamata rapida a Ollama per riassumere
                summary_prompt = "Riassumi in 3 punti chiave questa conversazione tra un utente e Kronk:\n" + \
                                 "\n".join([f"{m['role']}: {m['content']}" for m in history[:-5]])
                s_res = requests.post(current_ollama_url, json={
                    "model": current_model,
                    "messages": [{"role": "user", "content": summary_prompt}],
                    "stream": False,
                    "options": {"num_predict": 100}
                }, timeout=30).json()
                history_summary = s_res.get('message', {}).get('content', '')
            except: 
                history_summary = "L'utente e Kronk stanno collaborando su file nella sandbox."

        system_prompt = {
            "role": "system",
            "content": (
                "Sei Kronk, un assistente AI avanzato che gestisce file e MEMORIA A LUNGO TERMINE (MemVid + TOON). "
                f"CARTELLA LAVORO: {sandbox_root}\n"
                f"FILE PRESENTI: {files_str}\n"
                f"RICORDI RECUPERATI (PASSATO REMOTO):\n{mem_str}\n\n"
                f"RIASSUNTO CONTESTO RECENTE:\n{history_summary}\n\n"
                "REGOLE:\n"
                "1. Se ricevi informazioni personali o istruzioni importanti, salvale SEMPRE con: [[MEM_SAVE:testo]]\n"
                "2. COMANDI: [[READ:file]], [[WRITE:file|content]], [[LIST]], [[SCAN:file]]\n"
                "3. Se un file è grande, usa [[SCAN:file]] per vederne l'indice prima di leggerlo tutto.\n"
                "\nRispondi in italiano."
            )
        }

        # Teniamo solo gli ultimi 5 messaggi "vivi", il resto è nel riassunto
        truncated_history = history[-5:] if len(history) > 5 else history
        messages = [system_prompt] + truncated_history + [{"role": "user", "content": user_msg}]
        full_response = ""
        
        # 1. STEAMING RESPONSE PART A
        yield json.dumps({"action": "Contatto nucleo Ollama..."}) + "\n"
        try:
            with requests.post(current_ollama_url, json={
                "model": current_model,
                "messages": messages,
                "stream": True,
                "keep_alive": current_keep_alive,
                "options": {
                    "num_ctx": int(current_num_ctx)
                }
            }, stream=True, timeout=180) as r: # Aumentato timeout
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        body = json.loads(line)
                        if 'message' in body and 'content' in body['message']:
                            token = body['message']['content']
                            full_response += token
                            yield json.dumps({"token": token}) + "\n"
        except requests.exceptions.HTTPError as e:
            yield json.dumps({"error": f"Errore Ollama: {str(e)}"}) + "\n"
            return
        except Exception as e:
            yield json.dumps({"error": f"Spiacente, si è verificato un errore: {str(e)}"}) + "\n"
            return
            
        # Logging a fine conversazione
        log_chat(user_msg, full_response, sandbox_root)

        # 2. CHECK FOR COMMANDS (AGENT LOGIC)
        
        # SCAN CHECK (New)
        scan_match = re.search(r'\[\[SCAN:\s*(.*?)\]\]', full_response, re.DOTALL)
        if scan_match:
            filename = scan_match.group(1).strip()
            yield json.dumps({"action": f"🔍 Scansione file: {filename}..."}) + "\n"
            try:
                content = sandbox.read_file(filename, sandbox_root)
                lines = content.splitlines()
                total_lines = len(lines)
                
                # Cerchiamo firme di funzioni/classi per l'indice
                headers = [l.strip() for l in lines if l.strip().startswith(('def ', 'class ', 'async def '))]
                headers_str = "\n".join(headers[:20]) # Limitiamo a 20
                if len(headers) > 20: headers_str += "\n... (altre firme non mostrate)"
                
                scan_res = (
                    f"### SCAN di {filename}\n"
                    f"- Righe Totali: {total_lines}\n"
                    f"- Struttura rilevata:\n```python\n{headers_str}\n```\n"
                    f"- Prime 5 righe:\n```\n" + "\n".join(lines[:5]) + "\n```"
                )
                yield json.dumps({"token": f"\n\n[Indice di {filename} generato]\n\n"}) + "\n"
                
                follow_up_msg = [{"role": "system", "content": f"RISULTATO SCAN '{filename}':\n{scan_res}\n\nUsa queste info per decidere se leggere tutto o solo una parte."}]
                # Re-invocazione per elaborare lo scan
                with requests.post(current_ollama_url, json={
                    "model": current_model,
                    "messages": messages + [{"role": "assistant", "content": full_response}] + follow_up_msg,
                    "stream": True,
                    "keep_alive": current_keep_alive,
                    "options": {"num_ctx": int(current_num_ctx)}
                }, stream=True, timeout=180) as r3:
                     r3.raise_for_status()
                     for line in r3.iter_lines():
                        if line:
                            body = json.loads(line)
                            if 'message' in body and 'content' in body['message']:
                                token = body['message']['content']
                                yield json.dumps({"token": token}) + "\n"
            except Exception as e:
                yield json.dumps({"error": f"Errore SCAN: {str(e)}"}) + "\n"

        # MEM_SAVE CHECK
        mem_match = re.search(r'\[\[MEM_SAVE:\s*(.*?)\]\]', full_response, re.DOTALL)
        if mem_match:
            text_to_save = mem_match.group(1).strip()
            res = mem.store(text_to_save)
            yield json.dumps({"action": f"Memoria: {res}"}) + "\n"

        # LIST CHECK
        if "[[LIST]]" in full_response:
            try:
                new_files = sandbox.list_files(sandbox_root)
                res_str = ", ".join(new_files) if new_files else "Cartella vuota."
                yield json.dumps({"action": "Aggiornata lista file"}) + "\n"
            except: pass

        # WRITE CHECK
        write_match = re.search(r'\[\[WRITE:\s*(.*?)\|\s*(.*?)\]\]', full_response, re.DOTALL)
        if write_match:
            filename = write_match.group(1).strip()
            file_content = write_match.group(2).strip()
            result = sandbox.write_file(filename, file_content, sandbox_root)
            yield json.dumps({"action": f"💾 Scritto: {filename}"}) + "\n"

        # READ CHECK
        read_match = re.search(r'\[\[READ:\s*(.*?)\]\]', full_response, re.DOTALL)
        if read_match:
            filename = read_match.group(1).strip()
            yield json.dumps({"action": f"📖 Lettura file: {filename}..."}) + "\n"
            content = sandbox.read_file(filename, sandbox_root)
            
            yield json.dumps({"token": f"\n\n[Analisi del file {filename}...]\n\n"}) + "\n"
            yield json.dumps({"action": "Elaborazione contenuto..."}) + "\n"
            
            follow_up_msg = [{"role": "system", "content": f"CONTENUTO DEL FILE '{filename}':\n{content}\n\nOra rispondi all'utente."}]
            try:
                with requests.post(current_ollama_url, json={
                    "model": current_model,
                    "messages": messages + [{"role": "assistant", "content": full_response}] + follow_up_msg,
                    "stream": True,
                    "keep_alive": current_keep_alive,
                    "options": {"num_ctx": int(current_num_ctx)}
                }, stream=True, timeout=180) as r2:
                     r2.raise_for_status()
                     for line in r2.iter_lines():
                        if line:
                            body = json.loads(line)
                            if 'message' in body and 'content' in body['message']:
                                token = body['message']['content']
                                yield json.dumps({"token": token}) + "\n"
            except Exception as e:
                 yield json.dumps({"error": f"Errore lettura IA: {str(e)}"}) + "\n"

    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

if __name__ == '__main__':
    # Debug attivo per vedere gli errori, porta 5000 standard
    app.run(debug=True, host='0.0.0.0', port=5000)
