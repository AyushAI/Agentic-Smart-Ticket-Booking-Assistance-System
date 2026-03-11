import logging
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# if HuggingFace is slow or offline,
# it will crash the entire app on startup. Wrapped in try/except with a fallback.
try:
    vector_db = FAISS.from_texts(
        ["User prefers cheapest travel"],
        embedding=embeddings,
    )
except Exception as e:
    logger.error("Failed to initialise FAISS vector store: %s", e)
    vector_db = None

conversation_history: list[str] = []


def store_conversation(user_message: str) -> None:
    """Persist a user message to in-memory history and the vector store."""
    conversation_history.append(user_message)
    if vector_db is not None:
        try:
            vector_db.add_texts([user_message])
        except Exception as e:
            logger.warning("Could not store message in vector DB: %s", e)


def retrieve_memory(query: str) -> list[str]:
    """
    Return the most relevant past conversation snippets for the given query.
    Falls back to an empty list if the vector DB is unavailable.
    """
    if vector_db is None:
        return []
    try:
        docs = vector_db.similarity_search(query, k=3)   #limit k to avoid returning too much noise
        return [d.page_content for d in docs]
    except Exception as e:
        logger.warning("Memory retrieval failed: %s", e)
        return []