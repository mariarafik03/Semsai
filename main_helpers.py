
from langchain_ollama import ChatOllama

import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI

load_dotenv() 


#openai_model = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)



ollama_model = ChatOllama(
    model="qwen2.5:7b", temperature=0.3)

def ask_ollama(prompt: str) -> str:
    response = ollama_model.invoke(prompt)
    return response.content.strip()

"""def ask_openai(prompt: str) -> str:
    response = openai_model.invoke(prompt)
    return response.content.strip()"""

