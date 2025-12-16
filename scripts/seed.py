from backend.app.db import SessionLocal
from backend.app import models
from backend.app.auth import hash_password
from backend.app.config import get_settings
from datetime import date, timedelta


def main():
    settings = get_settings()
    db = SessionLocal()
    demo_user = db.query(models.User).filter(models.User.email == "demo@codex.local").first()
    if not demo_user:
        demo_user = models.User(email="demo@codex.local", hashed_password=hash_password(settings.demo_password))
        db.add(demo_user)
    org = db.query(models.Organization).filter(models.Organization.name == "Demo Org").first()
    if not org:
        org = models.Organization(name="Demo Org", autopilot_enabled=True)
        db.add(org)
        db.flush()
        db.add(models.Membership(user_id=demo_user.id, organization_id=org.id, role="owner"))
    project = db.query(models.Project).filter(models.Project.name == "Demo Project").first()
    if not project:
        project = models.Project(name="Demo Project", organization_id=org.id, autopilot_enabled=True)
        db.add(project)
    db.commit()
    # generate plan slots
    start = date.today()
    for day in range(30):
        for slot in range(1, 4):
            existing = (
                db.query(models.Plan)
                .filter(models.Plan.project_id == project.id, models.Plan.slot_date == start + timedelta(days=day), models.Plan.slot_index == slot)
                .first()
            )
            if existing:
                continue
            db.add(models.Plan(project_id=project.id, slot_date=start + timedelta(days=day), slot_index=slot, status="scheduled"))
    db.commit()
    print("Seeded demo data")


if __name__ == "__main__":
    main()
