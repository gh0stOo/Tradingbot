from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas
from ..auth import get_current_user, get_db

router = APIRouter()


def ensure_org_access(db: Session, org_id: str, user: models.User):
    membership = db.query(models.Membership).filter(
        models.Membership.organization_id == org_id, models.Membership.user_id == user.id
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of organization")


@router.post("/{org_id}", response_model=schemas.ProjectOut)
def create_project(org_id: str, payload: schemas.ProjectCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_org_access(db, org_id, user)
    project = models.Project(organization_id=org_id, name=payload.name, autopilot_enabled=payload.autopilot_enabled)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{org_id}", response_model=list[schemas.ProjectOut])
def list_projects(org_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_org_access(db, org_id, user)
    return db.query(models.Project).filter(models.Project.organization_id == org_id).all()
