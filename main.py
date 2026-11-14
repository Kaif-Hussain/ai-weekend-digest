from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from google.genai import Client

from database import init_db, upsert_subscriber, delete_subscriber, save_sunday_cache
from agent import run_digest_for_user
from mailer import send_weekend_email
from scheduler import start_scheduler, run_saturday_dispatch, run_sunday_dispatch


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(title="AI Weekend Digest (BYOK)", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


class UserCredentials(BaseModel):
    email: EmailStr
    api_key: str


class UnsubscribeRequest(BaseModel):
    email: EmailStr


def verify_gemini_key(api_key: str):
    """Performs a zero-token metadata check to verify the user's Gemini API key."""
    try:
        client = Client(api_key=api_key.strip())
        next(iter(client.models.list()))
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid Gemini API key. Please check your key in Google AI Studio."
        )


@app.get("/")
async def serve_ui():
    return FileResponse("static/index.html")


@app.post("/api/subscribe")
async def subscribe(payload: UserCredentials):
    verify_gemini_key(payload.api_key)
    upsert_subscriber(payload.email, payload.api_key.strip())
    return {
        "status": "subscribed",
        "message": f"Connected! {payload.email} will receive Pick #1 on Saturday and Pick #2 on Sunday."
    }


@app.post("/api/preview")
async def preview_digest(payload: UserCredentials):
    """Runs the ADK pipeline immediately with the user's own key and shows the results in UI."""
    verify_gemini_key(payload.api_key)
    try:
        digest = await run_digest_for_user(payload.email, payload.api_key.strip())
        return {"status": "ok", "digest": digest}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ADK Agent Error: {str(e)}")


@app.post("/api/test-email-now")
async def test_email_now(payload: UserCredentials):
    """Test endpoint: immediately runs the ADK agent, sends Saturday #1 email, and caches Sunday #2."""
    verify_gemini_key(payload.api_key)
    upsert_subscriber(payload.email, payload.api_key.strip())
    try:
        digest = await run_digest_for_user(payload.email, payload.api_key.strip())
        send_weekend_email(payload.email, "SATURDAY", "#1 TOP PICK OF THE WEEK", digest["saturday"])
        save_sunday_cache(payload.email, digest["sunday"])
        return {
            "status": "sent",
            "message": f"Saturday #1 email sent to {payload.email}! Sunday #2 cached in DB.",
            "digest": digest
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test Dispatch Error: {str(e)}")


@app.post("/api/unsubscribe")
async def unsubscribe(payload: UnsubscribeRequest):
    removed = delete_subscriber(payload.email)
    if not removed:
        raise HTTPException(status_code=404, detail="Email not found in subscriber list.")
    return {"status": "deleted", "message": "Your email and encrypted API key have been permanently wiped."}