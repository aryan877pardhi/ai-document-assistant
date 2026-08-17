import os
from dotenv import load_dotenv 
from groq import Groq
load_dotenv()
print("API KEY FOUND:", os.getenv("GROQ_API_KEY")is not None)
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


def create_llm():
    client = Groq(
        api_key=os.getenv("GROQ_API_KEY")
    )

    return client
def rewrite_question(client, question, chat_history):

    if not chat_history:
        return question

    history_text = ""

    for chat in chat_history:
        history_text += f"""
User: {chat['question']}
Assistant: {chat['answer']}
"""

    prompt = f"""
You are a question rewriting assistant.

Your task is to rewrite the user's latest question into a
standalone question using the conversation history.

Conversation history:
{history_text}

Latest question:
{question}

Rules:
1. Resolve pronouns like "it", "there", "he", "she", "that", etc.
2. Use information from the conversation history.
3. Do not answer the question.
4. Return ONLY the rewritten question.
5. If the question is already clear, return it unchanged.
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip()
    
def generate_answer(client, question, context):

    prompt = f"""
You are an AI Document Assistant.

Your job is to answer the user's question using ONLY the information
provided in the PDF context below.

PDF CONTEXT:
{context}

USER QUESTION:
{question}

RULES:
1. Use only the PDF context to answer.
2. Do not use your own knowledge.
3. Do not guess or invent information.
4. If the answer is not clearly present in the PDF context, say:
   "I couldn't find this information in the PDF."
5. Keep the answer clear and concise.
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b", 
          messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    return response.choices[0].message.content
   
    
def load_pdf(file_path):
    loader = PyPDFLoader(file_path)
    documents = loader.load()
    
    return documents 
def split_documents(documents):
  text_splitter = RecursiveCharacterTextSplitter(
      chunk_size = 500,
      chunk_overlap=50
      
  )    
  chunks = text_splitter.split_documents(documents)
  return chunks
def create_embeddings():
    embeddings = HuggingFaceEmbeddings(
        model_name ="sentence-transformers/all-MiniLM-L6-v2"
        
    ) 
    return embeddings
def create_vector_store(chunks,embeddings):
   vector_store = FAISS.from_documents(
    chunks, 
    embeddings 
   )
   return vector_store  