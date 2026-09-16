"""Test model download via HF mirror."""
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from sentence_transformers import SentenceTransformer

print("Loading BAAI/bge-small-zh-v1.5 via hf-mirror.com...")
model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
print(f"Model loaded OK, dim={model.get_sentence_embedding_dimension()}")

# Quick test encode
test_text = "测试一下中文嵌入"
emb = model.encode([test_text])
print(f"Encoding shape: {emb.shape}")
print("OK!")
