"""
BIBBIA - Sistema di Gestione Contesto Narrativo a 3 Livelli
============================================================
Implementa la "Strategia del Cursore Narrativo":
- Livello 1 (DNA): Personaggi, regole mondo -> MODELFILE (~500 token)
- Livello 2 (Cronaca): Riassunti capitoli compressi (~3-4k token)
- Livello 3 (Fronte Attivo): Ultimi N capitoli integrali (~8-10k token)
"""

import os
import re
import json
import logging
from datetime import datetime

import toon
import memory

class BibbiaManager:
    """Gestisce i 3 livelli della strategia narrativa."""
    
    def __init__(self, work_dir):
        self.work_dir = work_dir
        self.bibbia_file = os.path.join(work_dir, "BIBBIA.toon")
        self.sinossi_file = os.path.join(work_dir, "SINOSSI_MASTER.toon")
        self.memory_file = os.path.join(work_dir, "bibbia_memory.mp4")
        self.index_file = os.path.join(work_dir, "bibbia_memory.json")
        
    # ==================== LIVELLO 1: DNA ====================
    
    def load_dna(self):
        """Carica il DNA del mondo dalla BIBBIA."""
        if not os.path.exists(self.bibbia_file):
            return self._get_default_dna()
        
        try:
            with open(self.bibbia_file, 'r', encoding='utf-8') as f:
                content = f.read()
            # Estrai solo le sezioni DNA (MONDO, RAZZE, PROTAGONISTI, ecc.)
            return content
        except Exception as e:
            logging.error(f"Errore caricamento BIBBIA: {e}")
            return self._get_default_dna()
    
    def save_dna(self, dna_content):
        """Salva il DNA del mondo nella BIBBIA."""
        try:
            with open(self.bibbia_file, 'w', encoding='utf-8') as f:
                f.write(dna_content)
            return True
        except Exception as e:
            logging.error(f"Errore salvataggio BIBBIA: {e}")
            return False
    
    def _get_default_dna(self):
        """Restituisce un template DNA vuoto."""
        return """@ MONDO
  + galassia: [nome galassia]
  + pianeta_principale: [nome pianeta]
  + governo: [tipo governo]
  + tecnologia: [tecnologie chiave]
  + tono: [stile narrativo]

@ RAZZE
  + [razza_1]: [descrizione]
  + [razza_2]: [descrizione]

@ PROTAGONISTI
  + [nome]: [ruolo]
    | razza: [razza]
    | tratti: [personalità]
    | arco: [evoluzione personaggio]

@ PERSONAGGI_PRINCIPALI
  + [nome]: [ruolo]
    | razza: [razza]
    | tratti: [personalità]

@ REGOLE_NARRATIVE
  + [regola_1]: [descrizione]
  + [regola_2]: [descrizione]
"""

    def generate_modelfile_content(self, model_base="gemma3:12b"):
        """Genera il contenuto del MODELFILE per Ollama con il DNA."""
        dna = self.load_dna()
        
        modelfile = f'''FROM {model_base}

SYSTEM """
Sei "Adam", un assistente di scrittura creativa specializzato nel romanzo "Galactic Powder Ephemera".

=== BIBBIA DEL MONDO ===
{dna}

=== ISTRUZIONI ===
- Mantieni coerenza con i personaggi e le loro caratteristiche
- Rispetta il tono: fusione rigore Asimov + demenziale Adams + riferimenti anni '80
- Le razze sono: Umanidi, Spaziali (+ 3 future da svelare)
- I protagonisti sono: Hector, Sheila, Kenla, Darwin
- Usa umorismo con digressioni, battute meta e riferimenti pop
"""

PARAMETER temperature 0.8
PARAMETER top_p 0.9
PARAMETER num_ctx 32768
'''
        return modelfile
    
    def save_modelfile(self, output_path=None):
        """Salva il MODELFILE per Ollama."""
        if output_path is None:
            output_path = os.path.join(self.work_dir, "Adam.modelfile")
        
        content = self.generate_modelfile_content()
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return output_path
        except Exception as e:
            logging.error(f"Errore salvataggio MODELFILE: {e}")
            return None

    # ==================== LIVELLO 2: CRONACA ====================
    
    def load_sinossi(self):
        """Carica tutti i riassunti dei capitoli."""
        if not os.path.exists(self.sinossi_file):
            return []
        
        try:
            with open(self.sinossi_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse del formato TOON per sinossi
            chapters = []
            current_chapter = None
            
            for line in content.split('\n'):
                if line.startswith('@ cap_'):
                    if current_chapter:
                        chapters.append(current_chapter)
                    # Estrai numero capitolo
                    match = re.match(r'@ cap_(\d+)', line)
                    num = int(match.group(1)) if match else len(chapters) + 1
                    current_chapter = {'numero': num, 'contenuto': []}
                elif line.strip().startswith('+') and current_chapter:
                    current_chapter['contenuto'].append(line.strip()[2:])
            
            if current_chapter:
                chapters.append(current_chapter)
            
            return chapters
        except Exception as e:
            logging.error(f"Errore caricamento sinossi: {e}")
            return []
    
    def add_sinossi(self, capitolo_num, riassunto):
        """Aggiunge un riassunto di capitolo alla cronaca."""
        toon_entry = f"\n@ cap_{capitolo_num}\n"
        for line in riassunto.strip().split('\n'):
            if line.strip():
                toon_entry += f"  + {line.strip()}\n"
        
        try:
            with open(self.sinossi_file, 'a', encoding='utf-8') as f:
                f.write(toon_entry)
            return True
        except Exception as e:
            logging.error(f"Errore aggiunta sinossi: {e}")
            return False
    
    def get_sinossi_text(self):
        """Restituisce la sinossi come testo formattato per il prompt."""
        if not os.path.exists(self.sinossi_file):
            return ""
        
        try:
            with open(self.sinossi_file, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return ""

    # ==================== LIVELLO 3: FRONTE ATTIVO ====================
    
    def extract_chapters_from_novel(self, novel_path):
        """Estrae i capitoli (POST) dal romanzo."""
        if not os.path.exists(novel_path):
            return []
        
        try:
            with open(novel_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Trova tutti i POST
            chapters = []
            pattern = r'\*\*POST (\d+):(.*?)\*\*\s*(.*?)(?=\*\*POST \d+:|$)'
            matches = re.findall(pattern, content, re.DOTALL)
            
            for match in matches:
                chapters.append({
                    'numero': int(match[0]),
                    'titolo': match[1].strip(),
                    'contenuto': match[2].strip()
                })
            
            return chapters
        except Exception as e:
            logging.error(f"Errore estrazione capitoli: {e}")
            return []
    
    def get_last_n_chapters(self, novel_path, n=4):
        """Restituisce gli ultimi N capitoli integrali."""
        chapters = self.extract_chapters_from_novel(novel_path)
        if not chapters:
            return ""
        
        last_chapters = chapters[-n:]
        result = ""
        for ch in last_chapters:
            result += f"\n=== CAPITOLO {ch['numero']}: {ch['titolo']} ===\n"
            result += ch['contenuto'] + "\n"
        
        return result

    # ==================== ASSEMBLAGGIO PROMPT ====================
    
    def build_narrative_prompt(self, novel_path=None, include_sinossi=True, last_n_chapters=4):
        """
        Assembla il prompt completo con i 3 livelli.
        Questo va incollato all'inizio della conversazione con Adam.
        """
        parts = []
        
        # Livello 1: DNA (già nel MODELFILE, ma lo includiamo anche qui per contesto)
        # parts.append("=== CONTESTO NARRATIVO ===\n")
        
        # Livello 2: Cronaca
        if include_sinossi:
            sinossi = self.get_sinossi_text()
            if sinossi.strip():
                parts.append("=== STORIA FINORA (MEMORIZZA) ===\n")
                parts.append(sinossi)
                parts.append("\n")
        
        # Livello 3: Fronte Attivo
        if novel_path and os.path.exists(novel_path):
            last_chapters = self.get_last_n_chapters(novel_path, last_n_chapters)
            if last_chapters.strip():
                parts.append(f"=== ULTIMI {last_n_chapters} CAPITOLI (RIFERIMENTO STILISTICO) ===\n")
                parts.append(last_chapters)
        
        return ''.join(parts)
    
    def count_tokens_estimate(self, text):
        """Stima approssimativa dei token (1 token ≈ 4 caratteri)."""
        return len(text) // 4

    # ==================== ESTRAZIONE AUTOMATICA ====================
    
    def extract_bibbia_from_novel(self, novel_path):
        """
        Analizza il romanzo ed estrae personaggi, luoghi, oggetti.
        Restituisce un dict con le informazioni estratte.
        """
        if not os.path.exists(novel_path):
            return None
        
        try:
            with open(novel_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            extracted = {
                'personaggi': [],
                'luoghi': [],
                'oggetti': [],
                'organizzazioni': []
            }
            
            # Pattern comuni per nomi propri (maiuscoli)
            # Personaggi noti dal testo
            known_chars = [
                ('Hector Starborn', 'umanide', 'tecnico help desk, protagonista'),
                ('Darwin', 'spaziale', 'scienziato TERRA'),
                ('Kenla Quilah', 'spaziale', 'comandante 3G'),
                ('Joyl Cond-Horr', 'spaziale', 'pilota 3G'),
                ('Souvenir', 'robot', 'robot 3G'),
                ('Sheila Evening', 'umanide', 'pianeta Malaffare'),
                ('Nikola Galilei', 'umanide', 'professore TECO'),
                ('Hal Seldon', 'umanide', 'Triumvirato'),
                ('Asimov Kress', 'umanide', 'Triumvirato'),
                ('Ripley Foster', 'umanide', 'Triumvirato'),
                ('Generale Harlan', 'spaziale', 'generale Aleph'),
            ]
            
            for name, race, role in known_chars:
                if name in content:
                    extracted['personaggi'].append({
                        'nome': name,
                        'razza': race,
                        'ruolo': role
                    })
            
            # Luoghi
            known_places = [
                ('Terrax', 'pianeta principale umanidi'),
                ('Aleph', 'pianeta spaziali'),
                ('Ephemera', 'galassia'),
                ('New Xanadu', 'metropoli'),
                ('TECO', 'laboratorio temporale'),
                ('Celestial Voyager', 'nave crociera'),
                ('Mach5000', 'nave squadra 3G'),
                ('Stazione Orus', 'stazione culinaria'),
            ]
            
            for place, desc in known_places:
                if place in content:
                    extracted['luoghi'].append({
                        'nome': place,
                        'descrizione': desc
                    })
            
            return extracted
        except Exception as e:
            logging.error(f"Errore estrazione BIBBIA: {e}")
            return None

    # ==================== INTEGRAZIONE MEMVID ====================
    
    def build_memory_video(self):
        """Costruisce il video MEMVID con BIBBIA + Sinossi."""
        try:
            from memvid import MemvidEncoder
            
            encoder = MemvidEncoder()
            
            # Aggiungi DNA
            dna = self.load_dna()
            if dna.strip():
                encoder.add_text(f"DNA DEL MONDO:\n{dna}")
            
            # Aggiungi Sinossi
            sinossi = self.get_sinossi_text()
            if sinossi.strip():
                encoder.add_text(f"CRONACA CAPITOLI:\n{sinossi}")
            
            # Costruisci video
            encoder.build_video(self.memory_file, self.index_file, show_progress=False)
            
            return True
        except Exception as e:
            logging.error(f"Errore costruzione video MEMVID: {e}")
            return False
