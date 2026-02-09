# 🤖 Kronk - AI Expert Text Analyst

> **"Un assistente locale con memoria fotografica e capacità di analisi profonda."**

Kronk è un'interfaccia avanzata per modelli LLM locali (via Ollama) progettata per l'analisi di testi, la scrittura creativa e la gestione di conoscenze a lungo termine. A differenza delle chat standard, Kronk possiede una **memoria persistente** e strumenti specifici per interagire con il file system.

![Kronk UI Demo](https://via.placeholder.com/800x450.png?text=Kronk+UI+Preview) <!-- Sostituisci con uno screenshot reale -->

---

## 🚀 Quick Start (Per iniziare subito)

Segui questi passaggi per avere Kronk operativo in meno di 5 minuti.

### 1. Prerequisiti
Assicurati di avere installato:
*   [**Ollama**](https://ollama.com/) (per il cervello dell'AI).
*   **Python 3.10+** (per l'interfaccia).
*   **FFmpeg** (necessario per il sistema di memoria video).

### 2. Scegli il tuo Cervello (Modello LLM)
Kronk è agnostico al modello: **puoi usare quello che preferisci!**
1.  Vai su [ollama.com/library](https://ollama.com/library) e scegli un modello (es. `llama3`, `mistral`, `gemma`, `mixtral`, ecc.).
2.  Scaricalo col comando:
    ```bash
    ollama pull <nome-modello>  # es. ollama pull llama3:8b
    ```
3.  Una volta avviato Kronk, vai nelle **Impostazioni (⚙️)** e scrivi il nome del modello scelto.

### 3. Modello per la Memoria (Embedding)
Per far funzionare la memoria a lungo termine offline, serve un modello di *embedding* specifico. Consigliamo questo (ha le dimensioni corrette per il nostro sistema patchato):
```bash
ollama pull embeddinggemma
```
*(Se vuoi usarne altri come `nomic-embed-text`, dovrai modificare `memory.py` per adattare le dimensioni).*

### 4. Installazione
Scarica questo repository e installa le dipendenze Python:

```bash
git clone https://github.com/tuo-user/kronk.git
cd kronk
pip install -r requirements.txt
```

> **Nota:** Se `memvid` non è disponibile come pacchetto pubblico, assicurati di copiare la cartella `memvid` nella directory del progetto o installala manualmente.

### 4. Avvio
Lancia l'applicazione:

```bash
python3 app.py
```
Apri il browser su: `http://localhost:5000`

---

## ✨ Funzionalità Chiave

*   **💬 Multi-Chat & Auto-Titling**: Gestione sessioni multiple con salvataggio automatico e titoli generati dall'AI.
*   **🧠 Memoria a Lungo Termine (MemVid + TOON)**: Kronk ricorda fatti e conversazioni passate salvandoli in un formato video compresso (QR Code) che viene indicizzato localmente.
*   **📂 File System Sandbox**:
    *   `[[READ:nomefile]]`: Legge il contenuto di un file.
    *   `[[WRITE:nomefile|contenuto]]`: Scrive o crea file.
    *   `[[SCAN:nomefile]]`: Analizza la struttura di un file senza leggerlo tutto.
    *   `[[LIST]]`: Elenca i file nella cartella di lavoro.
*   **🔒 Privacy Totale**: Tutto gira in locale. Nessun dato viene inviato a cloud esterni (nemmeno per gli embedding).

---

## 🔧 Dettagli Tecnici (Deep Dive)

Questa sezione spiega come funziona la magia "sotto il cofano".

### Architettura
*   **Backend**: Flask (Python). Gestisce le chiamate API a Ollama, il file system e la memoria.
*   **Frontend**: HTML5 + Vanilla JS + TailwindCSS (via CDN o locale). Interfaccia reattiva con supporto Markdown e Syntax Highlighting.
*   **Database**: JSONL per la chat history, MP4 + FAISS per la memoria vettoriale.

### Il Sistema di Memoria (Offline & Patchato)
Kronk utilizza una versione custom della libreria `memvid` per memorizzare informazioni.

1.  **Embedding Locale**: Di default, librerie come `sentence-transformers` chiamano HuggingFace per scaricare modelli. Per garantire il funzionamento offline e la privacy, abbiamo "patchato" il sistema (`memory.py`) per usare **Ollama** come motore di embedding (tramite l'endpoint `/api/embeddings`).
2.  **TOON (Token-Oriented Object Notation)**: Prima di essere memorizzati, i testi vengono compressi in un formato essenziale chiamato TOON, che rimuove ridondanze linguistiche mantenendo il significato semantico.
3.  **Storage Ibrido**:
    *   **Vettoriale (FAISS)**: Per la ricerca semantica veloce ("Cosa mi piace mangiare?").
    *   **Video (MP4)**: I dati grezzi sono codificati in QR code all'interno di un file video `.mp4`. Questo permette un backup robusto e portabile della memoria.

### Configurazione Avanzata
Puoi modificare i parametri principali direttamente dalla UI (icona Ingranaggio ⚙️) o editando `app.py`:

*   `num_ctx`: Dimensione finestra di contesto (default: **32768**). Aumentalo se hai molta VRAM per analizzare libri interi.
*   `OLLAMA_API_URL`: L'indirizzo del server Ollama (default: `http://localhost:11434/api/chat`).

---

## 🛠 Troubleshooting

**Errore "Model not found" nei log:**
Assicurati di aver scaricato il modello di embedding specificato in `memory.py` (default: `embeddinggemma`).
```bash
ollama pull embeddinggemma
```

**Il browser non apre la pagina:**
Verifica che la porta 5000 non sia occupata. Puoi cambiarla in `app.py` alla fine del file:
```python
app.run(debug=True, port=8080) # Esempio change port
```
