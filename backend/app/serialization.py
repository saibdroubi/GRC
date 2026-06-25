"""Turn service-layer return values (ORM models, dicts of them, UUIDs,
datetimes) into plain JSON-able structures — used wherever results need to
cross a boundary that isn't a Pydantic response_model, namely chat tool
results."""

import datetime
import uuid


def to_jsonable(obj):
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (uuid.UUID,)):
        return str(obj)
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if hasattr(obj, "__table__"):
        return {
            column.name: to_jsonable(getattr(obj, column.name))
            for column in obj.__table__.columns
        }
    return obj
