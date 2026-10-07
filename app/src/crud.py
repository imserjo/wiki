from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

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
    tag: str | None = None,
    author: str | None = None,          # ← НОВОЕ
    search: str | None = None,
) -> list[Note]:
    """Все заметки всех пользователей, с фильтрами и предзагрузкой связей."""
    stmt = (
        select(Note)
        .options(joinedload(Note.owner), joinedload(Note.tags))
    )
    if tag:
        stmt = stmt.join(Note.tags).where(Tag.name == tag.lower())
    if author:
        stmt = stmt.join(Note.owner).where(User.username == author)   # ← НОВОЕ
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(Note.title.ilike(like) | Note.content.ilike(like))
    stmt = stmt.order_by(Note.updated_at.desc())
    return list(db.scalars(stmt).unique())


def get_note(db: Session, note_id: int) -> Note | None:
    """Любая заметка по id — без привязки к владельцу."""
    return db.scalar(
        select(Note)
        .options(joinedload(Note.owner), joinedload(Note.tags))
        .where(Note.id == note_id)
    )


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


def all_tags(db: Session) -> list[Tag]:
    """Все теги, которые есть в системе (используются хоть где-то)."""
    stmt = select(Tag).join(Tag.notes).distinct().order_by(Tag.name)
    return list(db.scalars(stmt))


def all_authors(db: Session) -> list[User]:
    """Список пользователей, у которых есть хотя бы одна заметка."""
    stmt = (
        select(User)
        .join(User.notes)
        .distinct()
        .order_by(User.username)
    )
    return list(db.scalars(stmt))


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user_by_oauth(db: Session, provider: str, oauth_id: str) -> User | None:
    return db.scalar(
        select(User).where(
            User.auth_provider == provider,
            User.oauth_id == oauth_id,
        )
    )


def create_user(
    db: Session,
    username: str,
    email: str,
    password: str | None = None,
    auth_provider: str = "local",
    oauth_id: str | None = None,
) -> User:
    user = User(
        username=username,
        email=email.lower(),
        hashed_password=hash_password(password) if password else None,
        auth_provider=auth_provider,
        oauth_id=oauth_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
