from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import User, Note, Tag
from .security import hash_password


# --- Users ---
def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def create_user(db: Session, username: str, password: str) -> User:
    user = User(username=username, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --- Tags ---
def get_or_create_tags(db: Session, names: list[str]) -> list[Tag]:
    result: list[Tag] = []
    for raw in names:
        name = raw.strip().lower()
        if not name:
            continue
        tag = db.scalar(select(Tag).where(Tag.name == name))
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        result.append(tag)
    return result


# --- Notes ---
def list_notes(
    db: Session,
    owner_id: int,
    tag: str | None = None,
    search: str | None = None,
) -> list[Note]:
    stmt = select(Note).where(Note.owner_id == owner_id)
    if tag:
        stmt = stmt.join(Note.tags).where(Tag.name == tag.lower())
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(Note.title.ilike(like) | Note.content.ilike(like))
    stmt = stmt.order_by(Note.updated_at.desc())
    return list(db.scalars(stmt).unique())


def get_note(db: Session, note_id: int, owner_id: int) -> Note | None:
    return db.scalar(select(Note).where(Note.id == note_id, Note.owner_id == owner_id))


def create_note(
    db: Session, owner_id: int, title: str, content: str, tags: list[str]
) -> Note:
    note = Note(
        owner_id=owner_id,
        title=title,
        content=content,
        tags=get_or_create_tags(db, tags),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def update_note(db: Session, note: Note, **fields) -> Note:
    if "tags" in fields and fields["tags"] is not None:
        note.tags = get_or_create_tags(db, fields.pop("tags"))
    for key, value in fields.items():
        if value is not None:
            setattr(note, key, value)
    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, note: Note) -> None:
    db.delete(note)
    db.commit()


def all_tags(db: Session, owner_id: int) -> list[Tag]:
    stmt = (
        select(Tag)
        .join(Tag.notes)
        .where(Note.owner_id == owner_id)
        .distinct()
        .order_by(Tag.name)
    )
    return list(db.scalars(stmt))