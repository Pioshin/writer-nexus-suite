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
    return f"- data: {text.strip()}"


# ==================== FUNZIONI BOOKANALYZER ====================

def characters_to_toon(characters):
    """
    Converte lista personaggi in formato TOON per BIBBIA.
    
    Args:
        characters: Lista di dict con name e role
    
    Returns:
        Stringa in formato TOON
    """
    lines = ["@ PROTAGONISTI"]
    
    for char in characters:
        name = char.get('name', 'Unknown')
        role = char.get('role', '')
        lines.append(f"  + {name}: {role}")
    
    return '\n'.join(lines)

def world_to_toon(world_elements):
    """
    Converte world building elements in formato TOON.
    Raggruppa per categoria.
    """
    categories = {}
    
    for elem in world_elements:
        cat = elem.get('category', 'Unknown')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(elem)
    
    lines = []
    for cat, items in categories.items():
        lines.append(f"@ {cat.upper()}")
        for item in items:
            name = item.get('name', 'Unknown')
            context = item.get('context', item.get('raw_type', ''))
            lines.append(f"  + {name}: {context[:80]}")
    
    return '\n'.join(lines)

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
    """
    import re
    
    pattern = rf'@ {section_name}\s*(.*?)(?=\n@ |\Z)'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        return []
    
    section_content = match.group(1)
    items = []
    current_item = None
    
    for line in section_content.split('\n'):
        line = line.rstrip()
        
        if line.strip().startswith('+'):
            if current_item:
                items.append(current_item)
            item_content = line.strip()[2:].strip()
            if ':' in item_content:
                key, value = item_content.split(':', 1)
                current_item = {'id': key.strip(), 'descrizione': value.strip()}
            else:
                current_item = {'id': item_content}
        
        elif line.strip().startswith('|') and current_item:
            attr_content = line.strip()[1:].strip()
            if ':' in attr_content:
                key, value = attr_content.split(':', 1)
                current_item[key.strip()] = value.strip()
    
    if current_item:
        items.append(current_item)
    
    return items

def generate_synopsis_toon(post_num, riassunto):
    """
    Genera entry TOON per un riassunto di POST.
    """
    lines = [f"@ POST_{post_num}"]
    
    for line in riassunto.strip().split('\n'):
        if line.strip():
            lines.append(f"  + {line.strip()}")
    
    return '\n'.join(lines)


def to_bibbia_format(characters, world_elements, synopses=None, title=""):
    """
    Genera contenuto TOON completo formattato per BIBBIA.
    """
    sections = []
    
    if title:
        sections.append(f"# BIBBIA - {title}")
        sections.append("")
    
    # PERSONAGGI
    if characters:
        sections.append("@ PERSONAGGI")
        for char in characters:
            name = char.get('name', 'Unknown')
            slug = name.split()[0].lower() # Simple slug: first name lowercase
            role = char.get('role', 'ruolo sconosciuto')
            # Format: + slug: Full Name
            sections.append(f"  + {slug}: {name}")
            sections.append(f"    | ruol: {role}")
            # Context/Description if available? usually in 'context' or merged desc
            if 'context' in char:
                 sections.append(f"    | desc: {char['context'][:100]}")
        sections.append("")
    
    # World elements per categoria
    if world_elements:
        categories = {}
        for elem in world_elements:
            cat = elem.get('category', 'Unknown')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(elem)
        
        # MAPPING
        # Place -> @ LUOGHI
        # System/Group -> @ SOCIETA
        # Object/Myth -> @ OGGETTI
        # Unknown -> @ ALTRO
        
        cat_map = {
            'Place': 'LUOGHI',
            'Geography': 'LUOGHI', 
            'System': 'SOCIETA',
            'Culture': 'SOCIETA',
            'System/Group': 'SOCIETA', 
            'Object': 'OGGETTI',
            'Object/Myth': 'OGGETTI',
            'History': 'SOCIETA',
            'Unknown': 'ALTRO'
        }
        
        # Group by MAPPED categories
        mapped_content = {}
        for cat, items in categories.items():
            mapped_cat = cat_map.get(cat, 'ALTRO')
            if mapped_cat not in mapped_content:
                mapped_content[mapped_cat] = []
            mapped_content[mapped_cat].extend(items)

        for section, items in mapped_content.items():
            sections.append(f"@ {section}")
            for item in items:
                name = item.get('name', 'Unknown')
                slug = name.replace(" ", "_").lower()[:20]
                context = item.get('context', item.get('raw_type', ''))
                
                sections.append(f"  + {slug}: {name}")
                sections.append(f"    | desc: {context}")
            sections.append("")
    
    # Synopses
    if synopses:
        sections.append("@ CRONACA")
        for syn in synopses:
            post_num = syn.get('post_number', 0)
            syn_title = syn.get('title', '')
            summary = syn.get('summary', '')
            sections.append(f"  + post_{post_num}: {syn_title}")
            if summary:
                sections.append(f"    | riassunto: {summary}")
        sections.append("")
    
    return '\n'.join(sections)
