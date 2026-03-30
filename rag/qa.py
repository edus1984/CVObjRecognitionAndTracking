from langchain.chains import RetrievalQA
from rag.retriever import get_retriever


def get_qa(llm):
    retriever = get_retriever()

    return RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever
    )