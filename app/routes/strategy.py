"""Strategy builder — AI-guided conversation across 7 topics, saves ProjectStrategy."""
from datetime import date, datetime

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Project, ProjectStrategy, StrategySection,
    ChatConversation, ChatMessage, ChatRole,
)
from app.ai.engine import is_configured

router = APIRouter(prefix="/strategy")
templates = Jinja2Templates(directory="app/templates")

SECTION_ORDER = [
    StrategySection.product,
    StrategySection.customer,
    StrategySection.competitors,
    StrategySection.messaging,
    StrategySection.voice,
    StrategySection.pillars,
    StrategySection.budget,
]

SECTION_META = {
    StrategySection.product: {
        "label": "Product Definition",
        "description": "What is the product? What problem does it solve? What makes it unique?",
        "ai_prompt": "Help me define the product positioning for my marketing strategy. Ask me about the product, its target market, unique value proposition, and key differentiators.",
    },
    StrategySection.customer: {
        "label": "Customer Profile",
        "description": "Who is your ideal customer? What are their pain points and desires?",
        "ai_prompt": "Help me build a detailed customer profile. Ask about demographics, psychographics, pain points, goals, and buying behavior.",
    },
    StrategySection.competitors: {
        "label": "Competitive Landscape",
        "description": "Who are your competitors? How do you differentiate?",
        "ai_prompt": "Help me analyze the competitive landscape. Ask about direct/indirect competitors, their strengths, weaknesses, and our differentiation strategy.",
    },
    StrategySection.messaging: {
        "label": "Messaging Framework",
        "description": "Core messages, value props, taglines, and positioning statements.",
        "ai_prompt": "Help me build a messaging framework. Let's define the core value proposition, key messages for different audiences, and a positioning statement.",
    },
    StrategySection.voice: {
        "label": "Brand Voice",
        "description": "Tone, personality, dos and don'ts for communications.",
        "ai_prompt": "Help me define the brand voice. Ask about personality traits, tone examples, words to use vs avoid, and communication style.",
    },
    StrategySection.pillars: {
        "label": "Content Pillars",
        "description": "Core themes and topics that drive your content strategy.",
        "ai_prompt": "Help me define content pillars. Ask about core topics, audience interests, expertise areas, and content formats.",
    },
    StrategySection.budget: {
        "label": "Budget Strategy",
        "description": "How marketing budget is allocated across channels and activities.",
        "ai_prompt": "Help me plan the marketing budget strategy. Ask about total budget, channel priorities, expected CAC, and investment timeline.",
    },
}


@router.get("/")
def strategy_view(request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return templates.TemplateResponse("strategy.html", {
            "request": request, "project": None,
            "current_page": "strategy", "today": date.today(),
        })

    sections = []
    for sec in SECTION_ORDER:
        strategy = db.query(ProjectStrategy).filter_by(
            project_id=project.id, section=sec
        ).first()
        meta = SECTION_META[sec]
        sections.append({
            "section": sec,
            "label": meta["label"],
            "description": meta["description"],
            "strategy": strategy,
            "has_content": bool(strategy and strategy.content),
        })

    return templates.TemplateResponse("strategy.html", {
        "request": request,
        "project": project,
        "sections": sections,
        "ai_configured": is_configured(),
        "current_page": "strategy",
        "today": date.today(),
    })


@router.get("/section/{section_name}")
def strategy_section(section_name: str, request: Request, db: Session = Depends(get_db)):
    """View/edit a single strategy section."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("")

    try:
        sec = StrategySection(section_name)
    except ValueError:
        return HTMLResponse("<div class='text-red-400'>Invalid section</div>")

    strategy = db.query(ProjectStrategy).filter_by(
        project_id=project.id, section=sec
    ).first()

    meta = SECTION_META[sec]

    return templates.TemplateResponse("partials/strategy_section.html", {
        "request": request,
        "project": project,
        "section": sec,
        "meta": meta,
        "strategy": strategy,
        "ai_configured": is_configured(),
    })


@router.post("/section/{section_name}/save")
def save_strategy_section(
    section_name: str,
    request: Request,
    db: Session = Depends(get_db),
    content: str = Form(""),
):
    """Save strategy section content."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("")

    try:
        sec = StrategySection(section_name)
    except ValueError:
        return HTMLResponse("<div class='text-red-400'>Invalid section</div>")

    strategy = db.query(ProjectStrategy).filter_by(
        project_id=project.id, section=sec
    ).first()

    if strategy:
        strategy.content = content
        strategy.updated_at = datetime.utcnow()
    else:
        strategy = ProjectStrategy(
            project_id=project.id,
            section=sec,
            content=content,
        )
        db.add(strategy)

    db.commit()

    return HTMLResponse(
        '<span class="text-mcc-success text-xs">Saved</span>'
    )


@router.post("/section/{section_name}/start-ai")
def start_ai_conversation(
    section_name: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Start an AI-guided conversation for a strategy section."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("")

    try:
        sec = StrategySection(section_name)
    except ValueError:
        return HTMLResponse("")

    meta = SECTION_META[sec]

    # Create a chat conversation linked to this strategy section
    conv = ChatConversation(
        project_id=project.id,
        title=f"Strategy: {meta['label']}",
    )
    db.add(conv)
    db.commit()

    # Link it to the strategy
    strategy = db.query(ProjectStrategy).filter_by(
        project_id=project.id, section=sec
    ).first()
    if strategy:
        strategy.ai_conversation_id = conv.id
    else:
        strategy = ProjectStrategy(
            project_id=project.id,
            section=sec,
            content="",
            ai_conversation_id=conv.id,
        )
        db.add(strategy)
    db.commit()

    # Add initial AI prompt as user message
    msg = ChatMessage(
        conversation_id=conv.id,
        role=ChatRole.user,
        content=meta["ai_prompt"],
    )
    db.add(msg)
    db.commit()

    # Redirect to chat with this conversation
    return HTMLResponse(
        f'<script>'
        f'document.getElementById("ai-chat-panel").classList.remove("hidden");'
        f'htmx.ajax("GET", "/chat/conversations/{conv.id}", '
        f'{{target: "#chat-body", swap: "innerHTML"}});'
        f'</script>'
    )
