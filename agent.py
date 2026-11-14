import json
import re
from google.adk.agents import Agent, SequentialAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
from google.genai import Client, types


def build_weekly_ai_pipeline(user_api_key: str) -> SequentialAgent:
    """Builds an isolated ADK pipeline using strictly the end-user's Gemini API key."""
    user_client = Client(api_key=user_api_key)

    # High-limit lightweight model for search & synthesis
    scout_model = Gemini(model="gemini-2.5-flash-lite", client=user_client)
    # Smarter model called ONLY ONCE per week for final ranking
    curator_model = Gemini(model="gemini-2.5-flash", client=user_client)

    scout_agent = Agent(
        name="ai_weekly_scout",
        model=scout_model,
        instruction=(
            "You are an expert AI research analyst. Use Google Search to find the 6 most important "
            "AI model releases, open-source tools, frameworks, or research breakthroughs from the past 7 days. "
            "Focus strictly on credible primary sources (official AI labs, GitHub trending, Hugging Face, arXiv). "
            "List each item clearly with: Title, Source Name, Source URL, and a concise 2-sentence technical summary."
        ),
        tools=[google_search],
        output_key="raw_weekly_news"
    )

    curator_agent = Agent(
        name="weekend_digest_curator",
        model=curator_model,
        instruction=(
            "Analyze the discovered AI news below:\n{raw_weekly_news}\n\n"
            "Select the #1 most impactful release for SATURDAY and the #2 most impactful release for SUNDAY. "
            "Return ONLY valid raw JSON (no markdown fences, no commentary) matching this exact structure:\n"
            "{\n"
            '  "saturday": {\n'
            '    "title": "Name of Top #1 Release",\n'
            '    "category": "Model / Tool / Research",\n'
            '    "source_url": "https://...",\n'
            '    "summary": "Clear 2-3 sentence explanation of what it is.",\n'
            '    "why_it_matters": "Concrete impact for developers and builders.",\n'
            '    "quick_start": "1 actionable tip or command to try it today."\n'
            "  },\n"
            '  "sunday": {\n'
            '    "title": "Name of Runner-Up #2 Release",\n'
            '    "category": "Model / Tool / Research",\n'
            '    "source_url": "https://...",\n'
            '    "summary": "Clear 2-3 sentence explanation of what it is.",\n'
            '    "why_it_matters": "Concrete impact for developers and builders.",\n'
            '    "quick_start": "1 actionable tip or command to try it today."\n'
            "  }\n"
            "}"
        ),
        output_key="curated_json"
    )

    return SequentialAgent(
        name="weekly_ai_digest_pipeline",
        sub_agents=[scout_agent, curator_agent]
    )


def _extract_json(text: str) -> dict:
    """Safely extracts JSON even if the model wraps it in markdown backticks."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)


async def run_digest_for_user(user_email: str, user_api_key: str) -> dict:
    """Executes the ADK pipeline for a single user and returns {'saturday': {...}, 'sunday': {...}}."""
    pipeline = build_weekly_ai_pipeline(user_api_key)
    session_service = InMemorySessionService()
    runner = Runner(agent=pipeline, app_name="ai_weekend_digest", session_service=session_service)

    session = await session_service.create_session(app_name="ai_weekend_digest", user_id=user_email)
    prompt = types.Content(
        role="user",
        parts=[types.Part(text="Find this week's top AI breakthroughs and curate the #1 Saturday and #2 Sunday picks.")]
    )

    final_text = ""
    async for event in runner.run_async(user_id=user_email, session_id=session.id, new_message=prompt):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text

    if not final_text:
        raise RuntimeError("ADK pipeline returned an empty response.")

    return _extract_json(final_text)