import requests
import json

BASE_URL = "http://127.0.0.1:8008"

def test_glossary_refinement():
    print("Testing /refine_glossary endpoint...")
    
    # Raw candidates (some real, some fake, some common words)
    raw_terms = [
        {"term": "Lightsaber", "context": "Jedi weapon"},
        {"term": "Tattooine", "context": "Desert planet"}, # Should be rejected as Place (ideally)
        {"term": "Droid", "context": "Mechanical being"},
        {"term": "Table", "context": "Wooden furniture"}, # Should be rejected as Common
        {"term": "Luke", "context": "Hero"}, # Should be rejected as Person
        {"term": "Hyperdrive", "context": "FTL engine"},
        {"term": "Midi-chlorians", "context": "Microscopic lifeforms"}
    ]
    
    try:
        response = requests.post(f"{BASE_URL}/refine_glossary", json={"glossary": raw_terms})
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            glossary = data.get("glossary", [])
            print(f"Refined Glossary ({len(glossary)} items):")
            print(json.dumps(glossary, indent=2))
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    test_glossary_refinement()
