import io
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from .models import Note


def notes_to_dataframe(notes: list[Note]) -> pd.DataFrame:
    rows = [
        {
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "tags": ", ".join(t.name for t in n.tags),
            "created_at": n.created_at,
            "updated_at": n.updated_at,
        }
        for n in notes
    ]
    return pd.DataFrame(rows)


def export_notes_csv(notes: list[Note]) -> bytes:
    df = notes_to_dataframe(notes)
    return df.to_csv(index=False).encode("utf-8-sig")


def export_notes_excel(notes: list[Note]) -> bytes:
    df = notes_to_dataframe(notes)

    # Excel не понимает timezone-aware даты — убираем таймзону
    for col in ("created_at", "updated_at"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
            # df[col] = pd.to_datetime(df[col], utc=True).dt.tz_convert("Europe/Moscow").dt.tz_localize(None)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="notes")
    return buf.getvalue()


def tag_statistics(notes: list[Note]) -> list[dict]:
    """Сколько заметок на каждый тег + сколько слов в среднем."""
    rows = []
    for n in notes:
        words = len(n.content.split()) if n.content else 0
        if not n.tags:
            rows.append({"tag": "(без тега)", "words": words})
        else:
            for t in n.tags:
                rows.append({"tag": t.name, "words": words})

    if not rows:
        return []

    df = pd.DataFrame(rows)
    agg = (
        df.groupby("tag")
        .agg(notes_count=("tag", "size"), avg_words=("words", "mean"))
        .reset_index()
        .sort_values("notes_count", ascending=False)
    )
    agg["avg_words"] = agg["avg_words"].round(1)
    return agg.to_dict(orient="records")