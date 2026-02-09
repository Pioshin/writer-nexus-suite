import spacy

class NLPEngine:
    def __init__(self, model="it_core_news_sm"):
        print(f"Loading spaCy model: {model}...")
        try:
            self.nlp = spacy.load(model)
        except OSError:
            print(f"Model {model} not found. downloading...")
            from spacy.cli import download
            download(model)
            self.nlp = spacy.load(model)
        print("Model loaded.")

    def extract_characters(self, text):
        """
        Extracts characters (PER entities) and attempts to identify roles.
        Returns a list of dicts: {'name': str, 'role': str}
        """
        doc = self.nlp(text)
        characters = {}
        
        # Custom deny list for common false positives in manuscripts/scripts
        deny_list = {
            "capitolo", "parte", "trama", "indice", "introduzione", "conclusione", 
            "appunti", "personaggi", "presenti", "scena", "titolo", "autore",
            "hub", "bug", "software", "gamma", "raggi", "ghiaccio", "salsa",
            "cacciavite", "macchie", "giorni", "incidenti", "tante", "gentili",
            "potremmo", "scoperta", "specializzazione", "esseri", "superiori",
            "ritrovamento", "tema", "po'", "deponi"
        }

        # 1. basic NER extraction
        for ent in doc.ents:
            if ent.label_ == "PER":
                name = ent.text.strip()
                lower_name = name.lower()
                
                # --- STRICT FILTERS ---

                # 1. Length Check
                if len(name) < 3 or len(name) > 40:
                    continue
                
                # 2. Deny List Check (substring match for safety)
                if any(denied in lower_name.split() for denied in deny_list):
                    continue

                # 3. Stopword Check (Spacy's built-in)
                if self.nlp.vocab[lower_name].is_stop:
                    continue
                
                # 4. Content Check
                if not any(c.isalpha() for c in name): # Must have letters
                    continue
                if "\n" in name: # No newlines in names
                    continue
                    
                # 5. Part-Of-Speech Verification (Crucial for "Macchie", "Potremmo")
                # We require that at least ONE token in the entity is a Proper Noun (PROPN)
                # AND that it doesn't contain Verbs or plain Nouns as the ONLY content.
                has_propn = any(token.pos_ == "PROPN" for token in ent)
                is_mostly_common = all(token.pos_ in ["NOUN", "VERB", "ADJ", "ADV", "DET"] for token in ent)
                
                # Exception: "Hector 'Noone" might have punctuation, that's fine.
                # But "Macchie" (NOUN) should be skipped. "Potremmo" (VERB/AUX) should be skipped.
                if not has_propn or is_mostly_common:
                     continue
                     
                # 6. Capitalization Check (Heuristic)
                # True names usually start with uppercase. Spacy catches capitalized words as entities too easily.
                if not name[0].isupper():
                    continue

                # --- END FILTERS ---

                if name not in characters:
                    characters[name] = {"count": 1, "context": []}
                else:
                    characters[name]["count"] += 1

                # Save sentence context for role inference (limit to first 3 occurrences)
                if len(characters[name]["context"]) < 3:
                     # Clean and truncate context
                     cleaned_sent = ent.sent.text.strip().replace('\n', ' ')
                     characters[name]["context"].append(cleaned_sent[:200])

        results = []
        for name, data in characters.items():
            role = "Unknown"
            # Naive heuristic based on frequency
            if data["count"] > 10:
                role = "Main Character?"
            elif data["count"] > 3:
                role = "Secondary Character?"
            else:
                role = "Minor Character?"

            results.append({"name": name, "role": role, "context": " ".join(data["context"])})

        return results

    def extract_world_elements(self, text):
        """
        Extracts world building elements: LOC, GPE (Places), ORG (Systems/Groups), MISC (Myths/Objects).
        Returns a list of dicts: {'name': str, 'type': str, 'context': str}
        """
        doc = self.nlp(text)
        world_elements = {}
        
        # Extended deny list for world elements
        deny_list = {
            "capitolo", "parte", "trama", "indice", "introduzione", "conclusione",
            "nord", "sud", "est", "ovest", "destra", "sinistra", "lato",
            "giorno", "notte", "mattina", "sera", "oggi", "domani",
            "via", "piazza", "corso", "vicolo" # Too generic without proper name
        }

        target_labels = {"LOC", "GPE", "ORG", "PROD", "EVENT", "MISC", "WORK_OF_ART"}
        
        for ent in doc.ents:
            if ent.label_ in target_labels:
                name = ent.text.strip()
                lower_name = name.lower()
                
                # --- FILTERS ---
                if len(name) < 3 or len(name) > 60: continue
                if any(denied == lower_name for denied in deny_list): continue
                if self.nlp.vocab[lower_name].is_stop: continue
                if not any(c.isalpha() for c in name): continue
                if "\n" in name: continue
                
                # Heuristic: mostly common words check
                if all(token.pos_ in ["VERB", "ADJ", "ADV", "DET", "ADP"] for token in ent):
                     continue

                if name not in world_elements:
                    world_elements[name] = {
                        "count": 1, 
                        "type": ent.label_, # Use spaCy label initially
                        "context": []
                    }
                else:
                    world_elements[name]["count"] += 1
                
                # Context capture
                if len(world_elements[name]["context"]) < 3:
                     cleaned_sent = ent.sent.text.strip().replace('\n', ' ')
                     world_elements[name]["context"].append(cleaned_sent[:200])

        results = []
        for name, data in world_elements.items():
            # Initial categorization mapping
            category = "Unknown"
            if data["type"] in ["LOC", "GPE"]:
                category = "Place"
            elif data["type"] == "ORG":
                category = "System/Group"
            else:
                category = "Object/Myth"

            results.append({
                "name": name, 
                "category": category, 
                "raw_type": data["type"],
                "context": " ".join(data["context"])
            })

        return results

nlp_engine = NLPEngine()
