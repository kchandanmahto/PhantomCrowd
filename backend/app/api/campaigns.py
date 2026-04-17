import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db, async_session
from app.models.campaign import Campaign, CampaignEntity, SimAction
from app.services.knowledge.graph_builder import GraphBuilder
from app.services.knowledge.file_parser import save_and_parse_upload
from app.services.knowledge.ontology_generator import generate_ontology
from app.services.knowledge.graph_updater import update_graph_with_actions
from app.services.simulation_v2.profile_generator import generate_profiles
from app.services.simulation_v2.config_generator import generate_sim_config
from app.services.simulation_v2.engine import (
    run_simulation, get_simulation_state, cleanup_simulation_state, Action,
)
from app.services.report.report_agent import generate_report, interview_agent
from app.services.controversy_detector import detect_controversy, build_controversy_context
from app.core.events import publish

router = APIRouter(prefix="/v2/campaigns", tags=["campaigns-v2"])


# --- Schemas ---

class CampaignCreate(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    content_type: str = "social_post"
    context_text: str | None = None
    audience_config: dict | None = None
    language: str = "en"
    llm_agents: int = Field(default=10, ge=3, le=100)
    rule_agents: int = Field(default=50, ge=0, le=2000)
    sim_rounds: int = Field(default=5, ge=1, le=50)


class CampaignOut(BaseModel):
    id: str
    title: str
    content: str
    content_type: str
    status: str
    language: str
    llm_agents: int
    rule_agents: int
    sim_rounds: int
    viral_score: float | None
    summary: str | None
    report: dict | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class GraphOut(BaseModel):
    nodes: list[dict]
    edges: list[dict]
    stats: dict


class SimStatusOut(BaseModel):
    campaign_id: str
    status: str
    current_round: int
    total_rounds: int
    actions_count: int


class InterviewRequest(BaseModel):
    agent_name: str
    question: str


# --- Background tasks ---

async def _update_campaign(campaign_id: str, **fields) -> None:
    """Update campaign fields with a short-lived session and retry on lock."""
    for attempt in range(3):
        try:
            async with async_session() as db:
                campaign = await db.get(Campaign, campaign_id)
                if not campaign:
                    return
                for k, v in fields.items():
                    setattr(campaign, k, v)
                await db.commit()
                return
        except Exception as e:
            logger.warning("_update_campaign attempt %d failed: %s", attempt + 1, e)
            await asyncio.sleep(1)
    logger.error("_update_campaign failed after 3 attempts for %s", campaign_id)



async def _get_campaign_data(campaign_id: str) -> dict | None:
    """Read campaign data with a short-lived session."""
    async with async_session() as db:
        campaign = await db.get(Campaign, campaign_id)
        if not campaign:
            return None
        return {
            "content": campaign.content,
            "content_type": campaign.content_type,
            "context_text": campaign.context_text,
            "audience_config": campaign.audience_config,
            "language": campaign.language,
            "llm_agents": campaign.llm_agents,
            "rule_agents": campaign.rule_agents,
            "sim_rounds": campaign.sim_rounds,
            "graph_dir": campaign.graph_dir,
        }


async def _run_campaign_pipeline(campaign_id: str):
    """Full pipeline: build graph → generate profiles → simulate → report."""
    data = await _get_campaign_data(campaign_id)
    if not data:
        return

    try:
        # Step 1: Build knowledge graph
        await _update_campaign(campaign_id, status="graph_building")
        await publish(campaign_id, "status", {"status": "graph_building"})

        builder = GraphBuilder(campaign_id)
        await builder.initialize()
        graph_data = await builder.build_graph(data["content"], data["context_text"])

        # Save entities to DB
        async with async_session() as db:
            for node in graph_data["nodes"]:
                entity = CampaignEntity(
                    campaign_id=campaign_id,
                    name=node["id"],
                    entity_type=node.get("type"),
                    description=node.get("description"),
                )
                db.add(entity)
            await db.commit()

        await _update_campaign(campaign_id, status="graph_ready", graph_dir=builder.working_dir)
        await publish(campaign_id, "status", {
            "status": "graph_ready",
            "graph_stats": graph_data["stats"],
        })

        # Get graph context + entity list for agents
        graph_context = await builder.query(
            f"Summarize all key entities and relationships about: {data['content'][:200]}",
            mode="hybrid",
        )
        if not graph_context:
            graph_context = "No additional context available."

        graph_entities = builder.get_entities()

        # Step 1.5: Generate ontology (for metadata)
        try:
            ontology = await generate_ontology(
                data["content"],
                data["context_text"] or "",
                "marketing audience simulation",
            )
            logger.info("[%s] Ontology generated", campaign_id[:8])
        except Exception:
            logger.warning("[%s] Ontology generation failed, skipping", campaign_id[:8], exc_info=True)
            ontology = None

        # Step 2: Generate profiles (graph-grounded)
        logger.info("[%s] Starting profile generation", campaign_id[:8])
        await _update_campaign(campaign_id, status="generating_profiles")
        await publish(campaign_id, "status", {"status": "generating_profiles"})

        llm_profiles, rule_profiles = await generate_profiles(
            content=data["content"],
            graph_context=graph_context,
            llm_count=data["llm_agents"],
            rule_count=data["rule_agents"],
            audience_config=data["audience_config"],
            language=data["language"],
            graph_entities=graph_entities,
        )

        # Step 2.5: Auto-generate simulation config
        try:
            sim_config = await generate_sim_config(
                content=data["content"],
                entity_count=graph_data["stats"]["nodes"],
                edge_count=graph_data["stats"]["edges"],
                key_entities=[e["label"] for e in graph_entities[:10]],
                language=data["language"],
            )
        except Exception:
            sim_config = None

        # Step 2.7: Controversy Detection (pre-scan)
        controversy = await detect_controversy(
            content=data["content"],
            content_type=data["content_type"],
            language=data["language"],
            context=data["context_text"] or "",
        )
        logger.info(
            "Controversy detection result: has=%s risk=%s penalty=%s",
            controversy.get("has_controversy"),
            controversy.get("overall_risk"),
            controversy.get("total_score_penalty"),
        )
        controversy_context = build_controversy_context(controversy)
        if controversy_context:
            graph_context = graph_context + "\n" + controversy_context

        # Step 3: Run simulation
        await _update_campaign(campaign_id, status="simulating")
        await publish(campaign_id, "status", {"status": "simulating"})

        actions = await run_simulation(
            campaign_id=campaign_id,
            content=data["content"],
            graph_context=graph_context,
            llm_profiles=llm_profiles,
            rule_profiles=rule_profiles,
            num_rounds=data["sim_rounds"],
        )

        # Save actions to DB
        async with async_session() as db:
            for action in actions:
                sa = SimAction(
                    campaign_id=campaign_id,
                    round_num=action.round_num,
                    agent_name=action.agent_name,
                    agent_profile=action.agent_profile,
                    action_type=action.action_type,
                    content=(action.content or "").encode("utf-8", errors="replace").decode("utf-8"),
                    target_agent=action.target_agent,
                    target_content=(action.target_content or "").encode("utf-8", errors="replace").decode("utf-8"),
                    sentiment=action.sentiment,
                    sentiment_score=action.sentiment_score,
                )
                db.add(sa)
            await db.commit()

        # Step 3.5: Feedback loop — update graph with simulation results
        if data["graph_dir"]:
            try:
                update_graph_with_actions(data["graph_dir"], actions)
            except Exception:
                pass

        # Step 4: Generate report
        await _update_campaign(campaign_id, status="reporting")
        await publish(campaign_id, "status", {"status": "reporting"})

        report = await generate_report(
            content=data["content"],
            actions=actions,
            graph_context=graph_context,
            language=data["language"],
        )

        # Apply controversy penalty to viral score
        raw_score = report.get("viral_score", 50)
        penalty = controversy.get("total_score_penalty", 0)
        if penalty > 0:
            report["viral_score"] = max(5, raw_score - penalty)
            report["controversy"] = controversy
            logger.info("Applied controversy penalty: %s -> %s (-%s)", raw_score, report["viral_score"], penalty)
        else:
            logger.info("No controversy penalty (raw score: %s)", raw_score)

        await _update_campaign(
            campaign_id,
            status="completed",
            viral_score=report.get("viral_score"),
            summary=report.get("summary"),
            report=report,
            completed_at=datetime.utcnow(),
        )
        await publish(campaign_id, "status", {
            "status": "completed",
            "viral_score": report.get("viral_score"),
        })

    except Exception as e:
        logger.exception("Campaign pipeline failed for %s", campaign_id)
        await _update_campaign(campaign_id, status="failed", summary=str(e)[:500])
        await publish(campaign_id, "status", {
            "status": "failed", "error": str(e)[:200],
        })
    finally:
        cleanup_simulation_state(campaign_id)


# Keep references to background tasks so they don't get garbage collected
_background_tasks: set[asyncio.Task] = set()


# --- Routes ---

@router.post("/", response_model=CampaignOut)
async def create_campaign(req: CampaignCreate, db: AsyncSession = Depends(get_db)):
    campaign = Campaign(
        title=req.title,
        content=req.content,
        content_type=req.content_type,
        context_text=req.context_text,
        audience_config=req.audience_config,
        language=req.language,
        llm_agents=req.llm_agents,
        rule_agents=req.rule_agents,
        sim_rounds=req.sim_rounds,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    # Start pipeline in background — must keep reference to prevent GC
    task = asyncio.create_task(_run_campaign_pipeline(campaign.id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return campaign


@router.get("/", response_model=list[CampaignOut])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    return result.scalars().all()


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.get("/{campaign_id}/graph", response_model=GraphOut)
async def get_graph(campaign_id: str, db: AsyncSession = Depends(get_db)):
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if not campaign.graph_dir:
        raise HTTPException(status_code=400, detail="Graph not built yet")

    builder = GraphBuilder(campaign_id)
    return builder.get_graph_data()


@router.get("/{campaign_id}/simulation/status", response_model=SimStatusOut)
async def get_sim_status(campaign_id: str):
    state = get_simulation_state(campaign_id)
    return SimStatusOut(
        campaign_id=campaign_id,
        status=state.get("status", "unknown"),
        current_round=state.get("current_round", 0),
        total_rounds=state.get("total_rounds", 0),
        actions_count=state.get("actions_count", 0),
    )


@router.get("/{campaign_id}/actions")
async def get_actions(
    campaign_id: str,
    round_num: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(SimAction).where(SimAction.campaign_id == campaign_id)
    if round_num:
        query = query.where(SimAction.round_num == round_num)
    query = query.order_by(SimAction.round_num, SimAction.created_at)
    result = await db.execute(query)
    actions = result.scalars().all()
    return [
        {
            "round": a.round_num,
            "agent": a.agent_name,
            "profile": a.agent_profile,
            "action": a.action_type,
            "content": a.content,
            "target": a.target_agent,
            "sentiment": a.sentiment,
            "score": a.sentiment_score,
        }
        for a in actions
    ]


@router.get("/{campaign_id}/report")
async def get_report(campaign_id: str, db: AsyncSession = Depends(get_db)):
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if not campaign.report:
        raise HTTPException(status_code=400, detail="Report not generated yet")
    return campaign.report


@router.post("/{campaign_id}/interview")
async def do_interview(
    campaign_id: str,
    req: InterviewRequest,
    db: AsyncSession = Depends(get_db),
):
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Get actions for this campaign
    result = await db.execute(
        select(SimAction).where(SimAction.campaign_id == campaign_id)
    )
    db_actions = result.scalars().all()
    actions = [
        Action(
            round_num=a.round_num,
            agent_name=a.agent_name,
            agent_profile=a.agent_profile or {},
            action_type=a.action_type,
            content=a.content or "",
            sentiment=a.sentiment or "neutral",
            sentiment_score=a.sentiment_score or 0,
        )
        for a in db_actions
    ]

    response = await interview_agent(
        agent_name=req.agent_name,
        question=req.question,
        actions=actions,
        content=campaign.content,
    )
    return {"agent": req.agent_name, "response": response}


@router.post("/{campaign_id}/upload")
async def upload_context_file(
    campaign_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file (PDF, MD, TXT) as additional context for the campaign."""
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    allowed_ext = {".pdf", ".md", ".markdown", ".txt", ".text", ".csv"}
    ext = "." + (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Supported: {allowed_ext}")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    text = await save_and_parse_upload(file.filename or "upload.txt", content)

    # Append to existing context
    if campaign.context_text:
        campaign.context_text += f"\n\n--- Uploaded: {file.filename} ---\n\n{text}"
    else:
        campaign.context_text = text

    await db.commit()

    return {
        "filename": file.filename,
        "chars": len(text),
        "preview": text[:500],
    }
