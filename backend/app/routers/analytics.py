from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import models
from ..auth import get_current_user, get_db

router = APIRouter()


@router.get("/metrics/{project_id}")
def list_metrics(project_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    membership = (
        db.query(models.Membership)
        .filter(models.Membership.organization_id == project.organization_id, models.Membership.user_id == user.id)
        .first()
    )
    if not membership:
        return {"metrics": []}
    metrics = db.query(models.Metric).filter(models.Metric.project_id == project_id).all()
    if not metrics:
        # seed mock metrics
        for label, value in [("views", 1200), ("likes", 240), ("shares", 32)]:
            db.add(models.Metric(organization_id=project.organization_id, project_id=project_id, metric=label, value=value))
        db.commit()
        metrics = db.query(models.Metric).filter(models.Metric.project_id == project_id).all()
    return {"metrics": [ {"metric": m.metric, "value": m.value, "created_at": m.created_at} for m in metrics]}
