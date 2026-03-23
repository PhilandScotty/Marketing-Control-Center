"""AI Chat routes — slide-out panel with conversation history."""
import asyncio
import json
import logging
from datetime import date, datetime

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Project, ChatConversation, ChatMessage, ChatRole,
    AIInsight, Task, TaskStatus, TaskPriority,
)
from app.ai.engine import chat_completion, is_configured
from app.ai.tools import execute_tool

logger = logging.getLogger("mcc.routes.chat")

router = APIRouter(prefix="/chat")
templates = Jinja2Templates(directory="app/templates")


@router.get("/panel")
def chat_panel(request: Request, db: Session = Depends(get_db)):
    """Render the chat panel content."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("<div class='p-4 text-mcc-muted'>No project loaded</div>")

    conversations = db.query(ChatConversation).filter_by(
        project_id=project.id
    ).order_by(ChatConversation.updated_at.desc()).limit(20).all()

    return templates.TemplateResponse("partials/chat_panel.html", {
        "request": request,
        "conversations": conversations,
        "ai_configured": is_configured(),
    })


@router.post("/conversations/new")
def new_conversation(request: Request, db: Session = Depends(get_db)):
    """Create a new chat conversation."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("")

    conv = ChatConversation(
        project_id=project.id,
        title="New Chat",
    )
    db.add(conv)
    db.commit()

    return templates.TemplateResponse("partials/chat_messages.html", {
        "request": request,
        "conversation": conv,
        "messages": [],
        "ai_configured": is_configured(),
    })


@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: int, request: Request, db: Session = Depends(get_db)):
    """Load a conversation's messages."""
    conv = db.get(ChatConversation, conv_id)
    if not conv:
        return HTMLResponse("")

    messages = db.query(ChatMessage).filter_by(
        conversation_id=conv_id
    ).order_by(ChatMessage.created_at.asc()).all()

    return templates.TemplateResponse("partials/chat_messages.html", {
        "request": request,
        "conversation": conv,
        "messages": messages,
        "ai_configured": is_configured(),
    })


@router.post("/send")
async def send_message(
    request: Request,
    db: Session = Depends(get_db),
    conversation_id: int = Form(...),
    message: str = Form(...),
    page_context: str = Form(""),
):
    """Send a message and get AI response."""
    conv = db.get(ChatConversation, conversation_id)
    if not conv:
        return HTMLResponse("<div class='text-red-400'>Conversation not found</div>")

    # Save user message
    user_msg = ChatMessage(
        conversation_id=conv.id,
        role=ChatRole.user,
        content=message,
        context_snapshot={"page": page_context} if page_context else None,
    )
    db.add(user_msg)
    db.commit()

    # Update conversation title from first message
    msg_count = db.query(ChatMessage).filter_by(conversation_id=conv.id).count()
    if msg_count == 1:
        conv.title = message[:60] + ("..." if len(message) > 60 else "")
        db.commit()

    if not is_configured():
        assistant_msg = ChatMessage(
            conversation_id=conv.id,
            role=ChatRole.assistant,
            content="AI features require ANTHROPIC_API_KEY. Set it in your environment to enable chat.",
        )
        db.add(assistant_msg)
        db.commit()
        return _render_new_messages(request, db, conv.id, [user_msg, assistant_msg])

    try:
        # Build message history for API
        all_messages = db.query(ChatMessage).filter_by(
            conversation_id=conv.id
        ).order_by(ChatMessage.created_at.asc()).all()

        api_messages = []
        for m in all_messages:
            if m.role == ChatRole.system:
                continue
            api_messages.append({"role": m.role.value, "content": m.content})

        # Call AI
        response = await chat_completion(api_messages, page_context=page_context)

        # Handle tool use loop
        tool_calls_log = []
        tool_results_log = []
        max_tool_rounds = 5
        rounds = 0

        while rounds < max_tool_rounds:
            content_blocks = response.get("content", [])
            stop_reason = response.get("stop_reason", "end_turn")

            if stop_reason != "tool_use":
                break

            # Process tool calls
            tool_use_blocks = [b for b in content_blocks if b.get("type") == "tool_use"]
            if not tool_use_blocks:
                break

            # Add assistant response with tool use to message history
            api_messages.append({"role": "assistant", "content": content_blocks})

            # Execute tools and build results
            tool_result_content = []
            for tool_block in tool_use_blocks:
                tool_name = tool_block["name"]
                tool_input = tool_block["input"]
                tool_id = tool_block["id"]

                result_str = execute_tool(tool_name, tool_input)
                tool_calls_log.append({"name": tool_name, "input": tool_input})
                tool_results_log.append({"name": tool_name, "result": result_str[:500]})

                tool_result_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result_str,
                })

            api_messages.append({"role": "user", "content": tool_result_content})

            # Call AI again with tool results
            response = await chat_completion(api_messages, page_context=page_context)
            rounds += 1

        # Extract final text response
        final_content = response.get("content", [])
        text_parts = [b["text"] for b in final_content if b.get("type") == "text"]
        assistant_text = "\n".join(text_parts) if text_parts else "I couldn't generate a response."

    except Exception as e:
        logger.exception(f"AI chat error in conversation {conv.id}: {e}")
        assistant_text = f"AI error: {e}"
        tool_calls_log = []
        tool_results_log = []

    # Save assistant message
    assistant_msg = ChatMessage(
        conversation_id=conv.id,
        role=ChatRole.assistant,
        content=assistant_text,
        tool_calls=tool_calls_log if tool_calls_log else None,
        tool_results=tool_results_log if tool_results_log else None,
    )
    db.add(assistant_msg)
    conv.updated_at = datetime.utcnow()
    db.commit()

    return _render_new_messages(request, db, conv.id, [user_msg, assistant_msg])


def _render_new_messages(request, db, conv_id, new_messages):
    """Render just the new messages as HTML."""
    return templates.TemplateResponse("partials/chat_new_messages.html", {
        "request": request,
        "messages": new_messages,
    })


@router.post("/quick-action")
async def quick_action(
    request: Request,
    db: Session = Depends(get_db),
    action: str = Form(...),
):
    """Handle quick action buttons (Morning briefing, What needs attention, etc.)."""
    project = db.query(Project).filter_by(slug="grindlab").first()
    if not project:
        return HTMLResponse("")

    # Create a new conversation for the quick action
    conv = ChatConversation(
        project_id=project.id,
        title=action,
    )
    db.add(conv)
    db.commit()

    prompts = {
        "Morning briefing": "Give me a morning briefing. What's the status of everything? What should I focus on today? Use the tools to get current data.",
        "What needs attention?": "What needs my attention right now? Check for overdue tasks, stale automations, anomalies, and anything urgent. Use the tools to check current state.",
        "Weekly summary": "Give me a full weekly summary. How did we do? What's the execution score? What shipped? What's behind? Use the tools to get all the data.",
        "Strategy export": "Generate a strategy export for my Claude strategy session. Use the generate_strategy_export tool.",
        "Export for Claude": "Generate a strategy export for my Claude strategy session. Use the generate_strategy_export tool.",
    }

    message_text = prompts.get(action, f"Help me with: {action}")

    # Save user message
    user_msg = ChatMessage(
        conversation_id=conv.id,
        role=ChatRole.user,
        content=message_text,
    )
    db.add(user_msg)
    db.commit()

    if not is_configured():
        assistant_msg = ChatMessage(
            conversation_id=conv.id,
            role=ChatRole.assistant,
            content="AI features require ANTHROPIC_API_KEY. Set it in your environment to enable chat.",
        )
        db.add(assistant_msg)
        db.commit()

        messages = [user_msg, assistant_msg]
        return templates.TemplateResponse("partials/chat_messages.html", {
            "request": request,
            "conversation": conv,
            "messages": messages,
            "ai_configured": is_configured(),
        })

    # Call AI with tool use
    try:
        api_messages = [{"role": "user", "content": message_text}]
        response = await chat_completion(api_messages)

        # Handle tool use loop
        tool_calls_log = []
        tool_results_log = []
        max_rounds = 5
        rounds = 0

        while rounds < max_rounds:
            content_blocks = response.get("content", [])
            stop_reason = response.get("stop_reason", "end_turn")

            if stop_reason != "tool_use":
                break

            tool_use_blocks = [b for b in content_blocks if b.get("type") == "tool_use"]
            if not tool_use_blocks:
                break

            api_messages.append({"role": "assistant", "content": content_blocks})

            tool_result_content = []
            for tool_block in tool_use_blocks:
                result_str = execute_tool(tool_block["name"], tool_block["input"])
                tool_calls_log.append({"name": tool_block["name"], "input": tool_block["input"]})
                tool_results_log.append({"name": tool_block["name"], "result": result_str[:500]})
                tool_result_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block["id"],
                    "content": result_str,
                })

            api_messages.append({"role": "user", "content": tool_result_content})
            response = await chat_completion(api_messages)
            rounds += 1

        final_content = response.get("content", [])
        text_parts = [b["text"] for b in final_content if b.get("type") == "text"]
        assistant_text = "\n".join(text_parts) if text_parts else "I couldn't generate a response."

    except Exception as e:
        logger.exception(f"AI quick-action error ({action}): {e}")
        assistant_text = f"AI error: {e}"
        tool_calls_log = []
        tool_results_log = []

    assistant_msg = ChatMessage(
        conversation_id=conv.id,
        role=ChatRole.assistant,
        content=assistant_text,
        tool_calls=tool_calls_log if tool_calls_log else None,
        tool_results=tool_results_log if tool_results_log else None,
    )
    db.add(assistant_msg)
    db.commit()

    messages = [user_msg, assistant_msg]
    return templates.TemplateResponse("partials/chat_messages.html", {
        "request": request,
        "conversation": conv,
        "messages": messages,
        "ai_configured": is_configured(),
    })


# --- Insight to Task ---

@router.post("/insight-to-task/{insight_id}")
def insight_to_task(insight_id: int, db: Session = Depends(get_db)):
    """Create a task from an AI insight's action item."""
    insight = db.get(AIInsight, insight_id)
    if not insight:
        return HTMLResponse("<span class='text-red-400'>Insight not found</span>")

    task = Task(
        project_id=insight.project_id,
        title=f"[AI] {insight.title[:150]}",
        description=insight.body,
        status=TaskStatus.backlog,
        priority=TaskPriority.high if insight.severity.value in ("urgent", "critical") else TaskPriority.medium,
    )
    db.add(task)
    insight.acknowledged = True
    db.commit()

    return HTMLResponse(
        f'<span class="text-mcc-success text-xs">Task #{task.id} created</span>'
    )
