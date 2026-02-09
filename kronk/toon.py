def to_toon(text_or_data):
    """
    Converte dati o testo semplice nel formato TOON (Token-Oriented Object Notation).
    Rimuove ridondanze, parentesi e virgolette per risparmiare token.
    """
    if isinstance(text_or_data, str):
        # Se è testo semplice, lo formattiamo come un blocco di memoria
        lines = text_or_data.strip().split('\n')
        toon_lines = ["@ memory_source"]
        for line in lines:
            if line.strip():
                toon_lines.append(f"  + {line.strip()}")
        return '\n'.join(toon_lines)
    
    if isinstance(text_or_data, dict):
        toon_lines = []
        for key, value in text_or_data.items():
            toon_lines.append(f"{key}: {value}")
        return '\n'.join(toon_lines)
    
    return str(text_or_data)

def parse_memory_to_toon(text):
    """
    Tenta di dare una struttura a un testo libero per TOON.
    Esempio: "Mi chiamo Raffaele" -> "subject: user, name: Raffaele"
    """
    # Per ora usiamo una logica semplice di riga, in futuro Kronk stesso
    # potrebbe generare output già in TOON.
    return f"- data: {text.strip()}"


# ==================== FUNZIONI BIBBIA ====================

def to_bibbia_toon(section_name, data):
    """
    Converte dati strutturati in formato TOON per BIBBIA.
    
    Args:
        section_name: Nome sezione (es. "PROTAGONISTI", "MONDO")
        data: Lista di dict o dict singolo
    
    Returns:
        Stringa in formato TOON
    """
    lines = [f"@ {section_name}"]
    
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                # Prima chiave come identificatore
                first_key = list(item.keys())[0]
                lines.append(f"  + {first_key}: {item[first_key]}")
                # Altre chiavi come attributi
                for key, value in list(item.items())[1:]:
                    lines.append(f"    | {key}: {value}")
            else:
                lines.append(f"  + {item}")
    elif isinstance(data, dict):
        for key, value in data.items():
            lines.append(f"  + {key}: {value}")
    
    return '\n'.join(lines)

def parse_bibbia_section(content, section_name):
    """
    Estrae una sezione specifica da un file BIBBIA.toon.
    
    Args:
        content: Contenuto completo del file TOON
        section_name: Nome sezione da estrarre (es. "PROTAGONISTI")
    
    Returns:
        Lista di dict con i dati della sezione
    """
    import re
    
    # Trova la sezione
    pattern = rf'@ {section_name}\s*(.*?)(?=\n@ |\Z)'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        return []
    
    section_content = match.group(1)
    items = []
    current_item = None
    
    for line in section_content.split('\n'):
        line = line.rstrip()
        
        # Nuovo item principale
        if line.strip().startswith('+'):
            if current_item:
                items.append(current_item)
            # Parse: "+ nome: valore"
            item_content = line.strip()[2:].strip()
            if ':' in item_content:
                key, value = item_content.split(':', 1)
                current_item = {'id': key.strip(), 'descrizione': value.strip()}
            else:
                current_item = {'id': item_content}
        
        # Attributo dell'item corrente
        elif line.strip().startswith('|') and current_item:
            attr_content = line.strip()[1:].strip()
            if ':' in attr_content:
                key, value = attr_content.split(':', 1)
                current_item[key.strip()] = value.strip()
    
    if current_item:
        items.append(current_item)
    
    return items

def generate_sinossi_toon(capitolo_num, titolo, riassunto):
    """
    Genera entry TOON per un riassunto di capitolo.
    
    Args:
        capitolo_num: Numero del capitolo
        titolo: Titolo del capitolo
        riassunto: Testo del riassunto (può essere multiriga)
    
    Returns:
        Stringa TOON formattata
    """
    lines = [f"@ cap_{capitolo_num}"]
    lines.append(f"  + titolo: {titolo}")
    
    for line in riassunto.strip().split('\n'):
        if line.strip():
            lines.append(f"  + {line.strip()}")
    
    return '\n'.join(lines)

