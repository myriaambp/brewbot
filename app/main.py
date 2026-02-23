import os
from dotenv import load_dotenv
load_dotenv()

import uuid

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from litellm import completion
from pydantic import BaseModel

from app.backstop import check_input, check_output
from app.prompt import SYSTEM_PROMPT

# --- Config ---
MODEL = "vertex_ai/gemini-2.0-flash-lite"

# --- Session Management ---
# Each session stores a list of messages in OpenAI format:
# [
#     {"role": "system", "content": "..."},
#     {"role": "user", "content": "Hello!"},
#     {"role": "assistant", "content": "Hi there!"},
#     ...
# ]
sessions: dict[str, list[dict]] = {}


# --- LLM Call ---
def generate_response(messages: list[dict]) -> str:
    """Generate a response using LiteLLM with Gemini on Vertex AI."""
    response = completion(
        model=MODEL,
        messages=messages,
        temperature=0.4,
        max_tokens=512,
    )
    return response.choices[0].message.content


# --- FastAPI App ---
app = FastAPI(title="BrewBot", description="Specialty coffee Q&A chatbot")


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


@app.get("/")
def index():
    return FileResponse("app/static/index.html")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())

    # Initialize session with system prompt
    if session_id not in sessions:
        sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # --- Backstop: check input BEFORE LLM ---
    backstop_response = check_input(request.message)
    if backstop_response:
        # Still log to history for continuity
        sessions[session_id].append({"role": "user", "content": request.message})
        sessions[session_id].append({"role": "assistant", "content": backstop_response})
        return ChatResponse(response=backstop_response, session_id=session_id)

    # Add user message
    sessions[session_id].append({"role": "user", "content": request.message})

    # Generate LLM response
    response_text = generate_response(sessions[session_id])

    # --- Backstop: check output AFTER LLM ---
    corrected = check_output(response_text, request.message)
    if corrected:
        response_text = corrected

    # Add assistant response to history
    sessions[session_id].append({"role": "assistant", "content": response_text})

    return ChatResponse(response=response_text, session_id=session_id)


@app.post("/clear")
def clear(session_id: str | None = None):
    if session_id and session_id in sessions:
        del sessions[session_id]
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
