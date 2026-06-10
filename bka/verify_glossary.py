
import sys
import os

# Add paths
sys.path.append("/home/pioshin/AI/Projects/P_NOOS/ADAM-suite/bka")
sys.path.append("/home/pioshin/AI/Projects/P_NOOS/ADAM-suite/bka/backend")

from backend.nlp_engine import nlp_engine
from backend import toon

text = """
Nel sistema di Ephemera, i Guardiani della Luce combattono contro i temibili Xylophagi.
La Principessa Kenla usa il suo Chromatron per difendersi.
Gli Xylophagi sono creature di legno vivente.
Il Chromatron è un'arma laser.
Ephemera è una galassia lontana.
Hector Starborn non sa usare il Chromatron.
Gli Xylophagi mangiano i mobili.
"""

print("--- TESTING GLOSSARY EXTRACTION ---")
# Ephemera = LOC (Entity) -> Should NOT be in glossary if extracted as entity?
# Xylophagi = Neologism, capitalized -> Should be in glossary
# Chromatron = Neologism, capitalized -> Should be in glossary
# Guardiani = Capitalized -> Maybe?
# Kenla = PER -> Should be entity

# Mock entities (since we don't know what spacy will find without running it)
# But let's run it.
glossary = nlp_engine.extract_glossary_terms(text)
print("EXTRACTED GLOSSARY:")
for item in glossary:
    print(item)

print("\n--- TESTING TOON FORMAT ---")
toon_output = toon.to_bibbia_format([], [], glossary=glossary)
print(toon_output['dna'])
