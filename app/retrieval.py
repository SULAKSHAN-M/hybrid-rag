import threading
from app.core import bm25, fuse

class Retrieval:
    def __init__(self, root):
        self.root=root
        self.lock=threading.RLock()
        self.client=None
        self.encoder=None
        self.reranker=None

    def collection(self, owner):
        if self.client is None:
            import chromadb
            self.client=chromadb.PersistentClient(path=str(self.root/'private-vectors'))
        return self.client.get_or_create_collection('ws_'+owner, metadata={'hnsw:space':'cosine'},embedding_function=None)

    def models(self):
        if self.encoder is None:
            from sentence_transformers import SentenceTransformer, CrossEncoder
            self.encoder=SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            self.reranker=CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

    def add(self,owner,doc,folder,passages,progress):
        with self.lock:
            progress('loading models',50)
            self.models()
            col=self.collection(owner)
            for start in range(0,len(passages),64):
                batch=passages[start:start+64]
                progress('embedding',50+int(40*start/len(passages)))
                texts=[p['text'] for p in batch]
                vectors=self.encoder.encode(texts,normalize_embeddings=True).tolist()
                col.add(ids=[p['id'] for p in batch],documents=texts,embeddings=vectors,metadatas=[{'document_id':doc,'folder':folder} for p in batch])
            progress('indexing',95)

    def delete(self,owner,doc):
        with self.lock:
            self.collection(owner).delete(where={'document_id':doc})

    def search(self,owner,folder,query,limit=5):
        with self.lock:
            col=self.collection(owner)
            where={'folder':folder} if folder else None
            rows=col.get(where=where,include=['documents'])
            if not rows['ids']:
                return []
            self.models()
            vec=self.encoder.encode([query],normalize_embeddings=True).tolist()
            dense=col.query(query_embeddings=vec,where=where,n_results=min(20,len(rows['ids'])),include=['distances'])['ids'][0]
            scores=bm25(query,rows['documents'])
            sparse=[rows['ids'][i] for i in sorted(range(len(scores)),key=lambda i:-scores[i]) if scores[i]>0][:20]
            candidates=fuse(dense,sparse)[:20]
            lookup=dict(zip(rows['ids'],rows['documents']))
            # Identity activation preserves logits for the configured relevance threshold.
            import torch
            relevance=self.reranker.predict([(query,lookup[k]) for k in candidates],activation_fn=torch.nn.Identity()).tolist()
            return sorted(zip(candidates,relevance),key=lambda item:-item[1])[:limit]
