import os
import time

# Default sandbox root if nothing is specified
DEFAULT_SANDBOX_DIR = os.path.abspath("./sandbox")

def get_sandbox_path(requested_path):
    """Risolve il path richiesto o usa il default."""
    if not requested_path:
        return DEFAULT_SANDBOX_DIR
    path = os.path.abspath(requested_path)
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except:
            return DEFAULT_SANDBOX_DIR # Fallback se non riesce a creare
    return path

def is_safe_path(filename, sandbox_root):
    """Il Cerbero digitale: controlla che non si esca dal recinto."""
    try:
        target = os.path.abspath(os.path.join(sandbox_root, filename))
        return os.path.commonprefix([target, sandbox_root]) == sandbox_root
    except:
        return False

def read_file(filename, sandbox_root):
    if not is_safe_path(filename, sandbox_root):
        return "⚠️ Errore: Tentativo di accesso fuori dalla sandbox bloccato."
    try:
        filepath = os.path.join(sandbox_root, filename)
        if not os.path.exists(filepath):
            return f"⚠️ Errore: Il file {filename} non esiste."
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Errore lettura: {str(e)}"

def write_file(filename, content, sandbox_root):
    if not is_safe_path(filename, sandbox_root):
        return "⚠️ Errore: Tentativo di scrittura fuori dalla sandbox bloccato."
    try:
        filepath = os.path.join(sandbox_root, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"✅ Successo: File {filename} salvato."
    except Exception as e:
        return f"Errore scrittura: {str(e)}"


def list_files(sandbox_root):
    try:
        if not os.path.exists(sandbox_root):
            return []
        items = os.listdir(sandbox_root)
        detailed_files = []
        for item in sorted(items):
            path = os.path.join(sandbox_root, item)
            if os.path.isfile(path):
                mtime = os.path.getmtime(path)
                mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
                detailed_files.append({"name": item, "display": f"{item} (Modificato: {mtime_str})"})
            else:
                detailed_files.append({"name": item, "display": f"{item}/ (Directory)"})
        return detailed_files
    except:
        return []
