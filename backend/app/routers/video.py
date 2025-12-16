from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas
from ..auth import get_current_user, get_db
from ..services.orchestrator import Orchestrator
from ..services.usage import enforce_quota, log_usage, QuotaExceeded

router = APIRouter()
orchestrator = Orchestrator()


def _get_project(project_id: str, db: Session, user: models.User) -> models.Project:
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    membership = (
        db.query(models.Membership)
        .filter(models.Membership.organization_id == project.organization_id, models.Membership.user_id == user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return project


@router.post("/generate/{project_id}/{plan_id}", response_model=schemas.VideoAssetOut)
def generate_assets(project_id: str, plan_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    project = _get_project(project_id, db, user)
    plan = db.query(models.Plan).filter(models.Plan.id == plan_id, models.Plan.project_id == project_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    try:
        enforce_quota(db, project.organization_id, metric="video_generation")
    except QuotaExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    asset = orchestrator.generate_assets(db, project, plan)
    plan.status = "assets_generated"
    db.commit()
    log_usage(db, project.organization_id, metric="video_generation")
    return asset


@router.post("/publish/{asset_id}")
def publish_now(asset_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    asset = db.query(models.VideoAsset).filter(models.VideoAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    project = db.query(models.Project).filter(models.Project.id == asset.project_id).first()
    _ = _get_project(project.id, db, user)
    result = orchestrator.publish_now(asset)
    asset.status = "published"
    db.commit()
    log_usage(db, project.organization_id, metric="publish")
    return {"result": result}
