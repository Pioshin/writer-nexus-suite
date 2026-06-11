import os
import memory

# Setup
root = os.path.abspath("./sandbox")
if not os.path.exists(root): os.makedirs(root)

mem = memory.MemoryManager(root)

print("Test 1: Store")
res = mem.store("Mio nome: Raffaele. Ruolo: Proprietario.")
print(f"Result: {res}")

print("\nTest 2: Search")
results = mem.search("Come mi chiamo?")
print(f"Search Results: {results}")

print("\nFiles in sandbox:")
print(os.listdir(root))
