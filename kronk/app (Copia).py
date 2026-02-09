import os
import re
import json
import requests
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

import sandbox

app = Flask(__name__)

# CONFIGURAZIONE
OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags" # URL per la lista modelli
MODEL_NAME = "llama3" 
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

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get('message')
    history = data.get('history', [])
    
    current_ollama_url = data.get('ollama_url', OLLAMA_API_URL)
    current_model = data.get('model', MODEL_NAME)
    current_keep_alive = data.get('keep_alive', "5m")
    
    req_path = data.get('sandbox_path')
    sandbox_root = sandbox.get_sandbox_path(req_path)

    # Recuperiamo i file per darli in pasto all'IA nel prompt
    try:
        current_files = sandbox.list_files(sandbox_root)
    except:
        current_files = []
    
    files_str = ", ".join(current_files) if current_files else "Nessun file presente."

    system_prompt = {
        "role": "system",
        "content": (
            "Sei un assistente AI avanzato con capacità di gestire file. "
            f"OPERI NELLA CARTELLA: {sandbox_root}\n"
            f"FILE ATTUALMENTE PRESENTI: {files_str}\n"
            "Hai i seguenti POTERI SPECIALI (usali ESATTAMENTE come descritto):\n"
            "1. LEGGERE: [[READ:nomefile.txt]]\n"
            "2. SCRIVERE: [[WRITE:nomefile.txt|contenuto del file]]\n"
            "3. ELENCARE: [[LIST]]\n"
            "\nIMPORTANTE:\n"
            "- Scrivi i comandi come TESTO PURO, non dentro blocchi di codice markdown.\n"
            "- Se l'utente ti chiede di creare un file con i messaggi precedenti, FALLO usando [[WRITE:...]].\n"
            "- Non dire che non puoi vedere i file, perché l'elenco ti è stato fornito sopra."
        )
    }

    messages = [system_prompt] + history + [{"role": "user", "content": user_msg}]

    def generate():
        yield json.dumps({"action": "Inizio generazione..."}) + "\n"
        full_response = ""
        
        # 1. STEAMING RESPONSE PART A
        try:
            with requests.post(current_ollama_url, json={
                "model": current_model,
                "messages": messages,
                "stream": True,
                "keep_alive": current_keep_alive
            }, stream=True, timeout=OLLAMA_TIMEOUT) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        body = json.loads(line)
                        if 'message' in body and 'content' in body['message']:
                            token = body['message']['content']
                            full_response += token
                            yield json.dumps({"token": token}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"
            return

        # 2. CHECK FOR COMMANDS (AGENT LOGIC)
        # Analizziamo full_response accumulata
        
        # LIST CHECK
        if "[[LIST]]" in full_response:
            try:
                new_files = sandbox.list_files(sandbox_root)
                res_str = ", ".join(new_files) if new_files else "Cartella vuota."
                yield json.dumps({"action": "Aggiornata lista file"}) + "\n"
                yield json.dumps({"token": f"\n\n[Sistema: Elenco file aggiornato: {res_str}]\n\n"}) + "\n"
                # Chiamata di follow-up per far sapere all'IA cosa ha trovato
                follow_up = [{"role": "system", "content": f"Elenco aggiornato dei file: {res_str}"}]
                # ... (streaming r2 come per il READ) ...
            except: pass

        # WRITE CHECK
        write_match = re.search(r'\[\[WRITE:\s*(.*?)\|\s*(.*?)\]\]', full_response, re.DOTALL)
        if write_match:
            filename = write_match.group(1).strip()
            file_content = write_match.group(2).strip()
            result = sandbox.write_file(filename, file_content, sandbox_root)
            yield json.dumps({"action": f"Scritto: {filename} ({result})"}) + "\n"
            # Non serve chiamare Ollama di nuovo, abbiamo finito l'azione. 
            # Potremmo voler nascondere il comando brutto dal testo mostrato all'utente?
            # Con lo streaming è difficile "cancellare" ciò che è già stato mandato.
            # L'utente vedrà il comando, poi vedrà l'azione di conferma. È accettabile.

        # READ CHECK
        read_match = re.search(r'\[\[READ:\s*(.*?)\]\]', full_response, re.DOTALL)
        if read_match:
            filename = read_match.group(1).strip()
            content = sandbox.read_file(filename, sandbox_root)
            yield json.dumps({"action": f"Letto: {filename}"}) + "\n"
            
            # Start Round 2: Feed content back to Ollama
            yield json.dumps({"token": f"\n\n[Lettura completata. Analisi di {filename}...]\n\n"}) + "\n"
            
            follow_up_msg = [{"role": "system", "content": f"CONTENUTO DEL FILE '{filename}':\n{content}\n\nOra rispondi all'utente basandoti su questo."}]
            
            try:
                with requests.post(current_ollama_url, json={
                    "model": current_model,
                    "messages": messages + [{"role": "assistant", "content": full_response}] + follow_up_msg,
                    "stream": True,
                    "keep_alive": current_keep_alive
                }, stream=True, timeout=OLLAMA_TIMEOUT) as r2:
                     r2.raise_for_status()
                     for line in r2.iter_lines():
                        if line:
                            body = json.loads(line)
                            if 'message' in body and 'content' in body['message']:
                                token = body['message']['content']
                                yield json.dumps({"token": token}) + "\n"
            except Exception as e:
                 yield json.dumps({"error": f"Errore fase 2: {str(e)}"}) + "\n"

    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

if __name__ == '__main__':
    # Debug attivo per vedere gli errori, porta 5000 standard
    app.run(debug=True, host='0.0.0.0', port=5000)
