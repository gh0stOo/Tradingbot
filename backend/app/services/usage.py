from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .. import models

MONTHLY_QUOTA = 120  # example posts per org


class QuotaExceeded(Exception):
    pass


def log_usage(db: Session, organization_id: str, metric: str, amount: int = 1):
    entry = models.UsageLedger(organization_id=organization_id, metric=metric, amount=amount)
    db.add(entry)
    db.commit()
    return entry


def enforce_quota(db: Session, organization_id: str, metric: str, limit: int = MONTHLY_QUOTA):
    start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = (
        db.query(models.UsageLedger)
        .filter(models.UsageLedger.organization_id == organization_id, models.UsageLedger.metric == metric, models.UsageLedger.created_at >= start)
        .count()
    )
    if total >= limit:
        raise QuotaExceeded(f"Quota exceeded for {metric}")
