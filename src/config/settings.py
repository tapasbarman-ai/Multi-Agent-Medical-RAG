import os
from dotenv import load_dotenv

load_dotenv()

EMBED_MODEL = os.getenv("EMBED_MODEL")
DATASET_NAME = os.getenv("DATASET_NAME")
FAISS_DB_PATH = os.getenv("FAISS_DB_PATH")
if FAISS_DB_PATH and not os.path.isabs(FAISS_DB_PATH):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    FAISS_DB_PATH = os.path.abspath(os.path.join(project_root, FAISS_DB_PATH))
