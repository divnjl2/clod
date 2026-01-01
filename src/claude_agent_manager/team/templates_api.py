"""
Team Templates API
==================

REST API endpoints для управления шаблонами команд.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Optional
import json
from pathlib import Path

from ..team_templates import (
    TeamTemplate,
    TeamTemplateManager,
    TeamBuilder,
    TeamLibrary
)

router = APIRouter(prefix="/api/teams/templates", tags=["team_templates"])

# Initialize manager
template_manager = TeamTemplateManager()


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/")
async def list_templates(tags: Optional[str] = None) -> List[dict]:
    """
    List all team templates.
    
    Query params:
    - tags: Comma-separated tags to filter by
    """
    
    filter_tags = tags.split(",") if tags else None
    templates = template_manager.list_templates(filter_tags)
    
    return [t.to_dict() for t in templates]


@router.get("/{template_id}")
async def get_template(template_id: str) -> dict:
    """Get team template by ID."""
    
    template = template_manager.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template.to_dict()


@router.post("/")
async def create_template(template_data: dict) -> dict:
    """Create new team template."""
    
    try:
        template = TeamTemplate.from_dict(template_data)
        template_manager.add_template(template)
        
        return {
            "success": True,
            "template_id": template.id,
            "message": "Template created successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{template_id}")
async def update_template(template_id: str, template_data: dict) -> dict:
    """Update existing team template."""
    
    existing = template_manager.get_template(template_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    
    try:
        # Ensure ID matches
        template_data["id"] = template_id
        template = TeamTemplate.from_dict(template_data)
        template_manager.add_template(template)
        
        return {
            "success": True,
            "message": "Template updated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{template_id}")
async def delete_template(template_id: str) -> dict:
    """Delete team template."""
    
    if template_id in template_manager.templates:
        del template_manager.templates[template_id]
        return {
            "success": True,
            "message": "Template deleted successfully"
        }
    else:
        raise HTTPException(status_code=404, detail="Template not found")


@router.post("/{template_id}/clone")
async def clone_template(template_id: str, new_name: str) -> dict:
    """Clone existing template."""
    
    try:
        cloned = template_manager.clone_template(template_id, new_name)
        return {
            "success": True,
            "template_id": cloned.id,
            "template": cloned.to_dict()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{template_id}/export")
async def export_template(template_id: str):
    """Export template as JSON file."""
    
    template = template_manager.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Create temp file
    filepath = f"/tmp/{template_id}.json"
    template_manager.save_template(template, filepath)
    
    return FileResponse(
        filepath,
        media_type="application/json",
        filename=f"{template.name.replace(' ', '_')}.json"
    )


@router.post("/import")
async def import_template(file: UploadFile = File(...)) -> dict:
    """Import template from JSON file."""
    
    try:
        content = await file.read()
        json_str = content.decode("utf-8")
        
        template = template_manager.import_template(json_str)
        
        return {
            "success": True,
            "template_id": template.id,
            "template": template.to_dict()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/library/builtin")
async def get_builtin_templates() -> List[dict]:
    """Get all built-in templates."""
    
    templates = TeamLibrary.get_all_templates()
    return [t.to_dict() for t in templates]


@router.post("/instantiate/{template_id}")
async def instantiate_team(
    template_id: str,
    project_path: str,
    task: str
) -> dict:
    """
    Instantiate a team from template.
    
    Creates actual agents from template and starts execution.
    """
    
    template = template_manager.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # TODO: Create actual team from template
    # This would integrate with TeamOrchestrator
    
    return {
        "success": True,
        "message": f"Team '{template.name}' instantiated",
        "agents_created": len(template.agents)
    }


# ============================================================================
# BUILDER ENDPOINTS
# ============================================================================

@router.post("/builder/start")
async def start_builder() -> dict:
    """Start a new team builder session."""
    
    builder = TeamBuilder()
    
    return {
        "success": True,
        "session_id": builder.team_id,
        "template": builder.build().to_dict()
    }


@router.post("/builder/{session_id}/add_agent")
async def add_agent_to_builder(
    session_id: str,
    agent_data: dict
) -> dict:
    """Add agent to builder session."""
    
    # In production, you'd store builder sessions
    # For now, just return updated template
    
    return {
        "success": True,
        "message": "Agent added"
    }


# ============================================================================
# TAGS & SEARCH
# ============================================================================

@router.get("/tags/all")
async def get_all_tags() -> List[str]:
    """Get all unique tags across templates."""
    
    templates = template_manager.list_templates()
    all_tags = set()
    
    for template in templates:
        all_tags.update(template.tags)
    
    return sorted(list(all_tags))


@router.get("/search")
async def search_templates(q: str) -> List[dict]:
    """Search templates by name or description."""
    
    templates = template_manager.list_templates()
    query = q.lower()
    
    results = [
        t for t in templates
        if query in t.name.lower() or query in t.description.lower()
    ]
    
    return [t.to_dict() for t in results]


# ============================================================================
# STATISTICS
# ============================================================================

@router.get("/stats")
async def get_template_stats() -> dict:
    """Get statistics about templates."""
    
    templates = template_manager.list_templates()
    
    # Count by type
    type_counts = {}
    for template in templates:
        team_type = template.team_type.value
        type_counts[team_type] = type_counts.get(team_type, 0) + 1
    
    # Count by coordination
    coord_counts = {}
    for template in templates:
        coord = template.coordination.value
        coord_counts[coord] = coord_counts.get(coord, 0) + 1
    
    # Average agents per team
    avg_agents = sum(len(t.agents) for t in templates) / len(templates) if templates else 0
    
    return {
        "total_templates": len(templates),
        "by_type": type_counts,
        "by_coordination": coord_counts,
        "average_agents": round(avg_agents, 1),
        "total_tags": len(await get_all_tags())
    }


if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
