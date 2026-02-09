import os
from memvid import MemvidRetriever

root = os.path.abspath("./sandbox")
video = os.path.join(root, "agent_memory.mp4")
index = os.path.join(root, "agent_memory.json")

if not os.path.exists(video) or not os.path.exists(index):
    print("Files missing")
else:
    print(f"Testing retriever with video={video} and index={index}")
    retriever = MemvidRetriever(video, index)
    results = retriever.search("Come mi chiamo?", top_k=3)
    print(f"Results: {results}")
