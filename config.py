import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
    PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east-1")
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "image-rag-index")
    
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    
    NOMIC_API_KEY = os.getenv("NOMIC_API_KEY", "")
    UNSTRUCTURED_API_KEY = os.getenv("UNSTRUCTURED_API_KEY", "")
    UNSTRUCTURED_API_URL = os.getenv("UNSTRUCTURED_API_URL", "")
    
settings = Settings()
