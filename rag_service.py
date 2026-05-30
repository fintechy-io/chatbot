from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from langchain_nomic.embeddings import NomicEmbeddings
from langchain_core.documents import Document
from config import settings
import openai
import time

DISCLAIMER = """

---
**Disclaimer and Note:** In case of supply of multiple goods and services, the final rate applicable would depend on whether the supply of goods can be considered as composite or mixed. If you would like to know more about whether the goods and services in question are composite and mixed supply please look at relevant case laws and section 8, read with section 2(30) and 2(74) of the Central Goods and Services Act, 2017. Alternatively you can also refer to our explainer blog.

*This information is provided for general guidance only and should not be construed as legal or tax advice. Please consult a qualified GST professional for advice specific to your situation.*
"""

class RAGService:
    def __init__(self):
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index_name = settings.PINECONE_INDEX_NAME

        # Initialize Nomic embeddings. nomic-embed-text uses 768 dimensions by default
        self.embeddings = NomicEmbeddings(
            model="nomic-embed-text-v1.5",
            nomic_api_key=settings.NOMIC_API_KEY
        )

        self.ensure_index_exists()
        self.vector_store = PineconeVectorStore(
            index_name=self.index_name,
            embedding=self.embeddings,
            pinecone_api_key=settings.PINECONE_API_KEY
        )

        # Initialize DeepSeek client
        self.llm_client = openai.OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_API_BASE
        )

    def ensure_index_exists(self):
        if self.index_name not in self.pc.list_indexes().names():
            self.pc.create_index(
                name=self.index_name,
                dimension=768,  # Nomic text v1.5 dimension
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region=settings.PINECONE_ENV
                )
            )
            # wait for index to be initialized
            while not self.pc.describe_index(self.index_name).status['ready']:
                time.sleep(1)

    def delete_source(self, source_name: str):
        """
        Delete all vectors previously ingested from a given source file.
        This ensures that re-uploading a file replaces old data.
        """
        try:
            index = self.pc.Index(self.index_name)
            # Query for vectors with matching source metadata and delete them
            results = index.query(
                vector=[0.0] * 768,
                top_k=10000,
                filter={"source": {"$eq": source_name}},
                include_metadata=True
            )
            ids_to_delete = [match["id"] for match in results.get("matches", [])]
            if ids_to_delete:
                index.delete(ids=ids_to_delete)
                print(f"Deleted {len(ids_to_delete)} old vectors for source: {source_name}")
        except Exception as e:
            print(f"Warning: Could not delete old vectors for {source_name}: {e}")

    def _split_into_chunks(self, text: str, max_chars: int = 6000) -> list:
        """
        Split text into chunks that respect Pinecone's 40KB metadata size limit.
        First splits by double newline (paragraphs), then further splits any
        oversized paragraphs using a sliding window.
        """
        raw_chunks = [c.strip() for c in text.split('\n\n') if len(c.strip()) > 20]
        final_chunks = []
        for chunk in raw_chunks:
            if len(chunk) <= max_chars:
                final_chunks.append(chunk)
            else:
                # Further split by single newline
                sub_chunks = [c.strip() for c in chunk.split('\n') if len(c.strip()) > 20]
                current = ""
                for sub in sub_chunks:
                    if len(current) + len(sub) + 1 <= max_chars:
                        current = (current + "\n" + sub).strip()
                    else:
                        if current:
                            final_chunks.append(current)
                        # If single line still too big, hard-split it
                        while len(sub) > max_chars:
                            final_chunks.append(sub[:max_chars])
                            sub = sub[max_chars:]
                        current = sub
                if current:
                    final_chunks.append(current)
        return final_chunks

    def ingest_text(self, text: str, metadata: dict = None):
        """
        Ingests extracted text. Deletes old data from the same source first,
        then re-ingests. This ensures latest data is always preferred.
        """
        if metadata is None:
            metadata = {}

        # Delete old vectors for this source to avoid stale/duplicate data
        if "source" in metadata:
            self.delete_source(metadata["source"])

        # Chunk safely within Pinecone's 40KB metadata size limit
        chunks = self._split_into_chunks(text)

        if not chunks:
            return 0

        # Add upload timestamp so retriever can rank newer data higher
        import datetime
        ts = datetime.datetime.utcnow().isoformat()
        documents = [
            Document(page_content=chunk, metadata={**metadata, "ingested_at": ts})
            for chunk in chunks
        ]
        self.vector_store.add_documents(documents)
        return len(documents)

    def _generate_query_variants(self, question: str) -> list:
        """
        Use DeepSeek to generate 4 alternative phrasings of the user's question.
        This ensures retrieval works regardless of how the question is worded.
        """
        prompt = f"""You are a GST expert. Generate 4 different ways to search for the answer to this question in a GST rate database.
Each variant should focus on different aspects: HSN code lookup, rate lookup, product category lookup, and keyword variation.

Original question: {question}

Return ONLY the 4 search queries, one per line, no numbering, no explanation."""

        try:
            response = self.llm_client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            variants = [line.strip() for line in response.choices[0].message.content.strip().split('\n') if line.strip()]
            return variants[:4]  # cap at 4
        except Exception:
            return []  # fallback: just use original question

    def query(self, question: str) -> str:
        """
        Multi-Query Retrieval: generates alternative phrasings, retrieves
        chunks for all of them, deduplicates, then generates a single answer.
        This makes the system robust to how the question is phrased.
        """
        # 1. Generate query variants
        variants = self._generate_query_variants(question)
        all_queries = [question] + variants

        # 2. Retrieve chunks for every query variant
        retriever = self.vector_store.as_retriever(search_kwargs={"k": 6})
        seen_content = set()
        unique_docs = []

        for q in all_queries:
            try:
                docs = retriever.invoke(q)
                for doc in docs:
                    # Deduplicate by content fingerprint
                    fingerprint = doc.page_content[:100]
                    if fingerprint not in seen_content:
                        seen_content.add(fingerprint)
                        unique_docs.append(doc)
            except Exception:
                continue

        # Cap at top 15 unique chunks to avoid token overflow
        unique_docs = unique_docs[:15]

        # ---------------------------------------------------------
        # PRINT STATEMENT FOR CONSOLE VERIFICATION
        # ---------------------------------------------------------
        print("\n" + "="*50)
        print(f"DEBUG: Retrieved {len(unique_docs)} chunks for question: '{question}'")
        print("Variants generated by DeepSeek:", variants)
        for idx, doc in enumerate(unique_docs):
            print(f"\n--- CHUNK {idx + 1} ---")
            print(doc.page_content)
        print("="*50 + "\n")

        if not unique_docs:
            return "I could not find any relevant information in the uploaded documents." + DISCLAIMER

        context = "\n\n---\n\n".join([doc.page_content for doc in unique_docs])

        # 3. Generate answer with rich context
        prompt = f"""You are a highly accurate GST (Goods & Services Tax) assistant. You have been given comprehensive context extracted from official GST rate documents.

Context (multiple relevant sections):
{context}

Question: {question}

Instructions:
- Search ALL sections of the context carefully before answering.
- Answer accurately. Include the HSN/SAC code and exact GST rate (CGST, SGST, IGST) where available.
- If the exact product is not found, look for the closest matching category or parent heading.
- Format your answer clearly with bold for rates and HSN codes.
- Do NOT quote the raw context or add sections like "Relevant Context Entry". Just give the final answer.
- If you genuinely cannot find the answer in any section of the context, say so clearly.
- Do NOT add any disclaimer yourself; one will be appended automatically."""

        response = self.llm_client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": "You are a precise GST rate lookup assistant. Always check all provided context sections before concluding the answer is not available."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )

        answer = response.choices[0].message.content

        # Always append the mandatory disclaimer
        return answer + DISCLAIMER



