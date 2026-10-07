from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.src import crud, analytics, web_auth
from app.src.database import Base, engine
from app.src.models import User
from app.src.security import create_access_token, verify_password
from app.src.config import settings
from app.src.markdown_render import render_markdown

BASE_DIR = Path(__file__).resolve().parent
PREFIX = settings.APP_PREFIX

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Knowledge Base", version="1.1.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

# Статика монтируется с префиксом, чтобы URL /wiki/static/... работал
app.mount(f"{PREFIX}/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["APP_PREFIX"] = PREFIX

COOKIE_NAME = web_auth.COOKIE_NAME
COOKIE_MAX_AGE = 60 * 60  # 1 час

@app.get("/health")
def health():
    return {"status": "ok"}


# ============================================================
#  Web UI (HTML, cookie-сессия) — всё под префиксом /wiki
# ============================================================

router = APIRouter(prefix=PREFIX, include_in_schema=False)


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path=PREFIX or "/",
    )


@router.get("/", include_in_schema=False, name="root")
def root(request: Request, user: User | None = Depends(web_auth.get_current_user_optional)):
    if user:
        return RedirectResponse(request.url_for("page_notes"), status_code=303)
    return RedirectResponse(request.url_for("page_login"), status_code=303)


@router.get("/login", response_class=HTMLResponse, name="page_login")
def page_login(
    request: Request,
    user: User | None = Depends(web_auth.get_current_user_optional),
):
    if user:
        return RedirectResponse(request.url_for("page_notes"), status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "user": None})


@router.post("/login", response_class=HTMLResponse, name="page_login_post")
def page_login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(web_auth.get_db),
):
    user = crud.get_user_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "user": None, "error": "Неверный логин или пароль"},
            status_code=400,
        )
    response = RedirectResponse(request.url_for("page_notes"), status_code=303)
    _set_auth_cookie(response, create_access_token(user.id))
    return response


@router.get("/register", response_class=HTMLResponse, name="page_register")
def page_register(
    request: Request,
    user: User | None = Depends(web_auth.get_current_user_optional),
):
    if user:
        return RedirectResponse(request.url_for("page_notes"), status_code=303)
    return templates.TemplateResponse("register.html", {"request": request, "user": None})


@router.post("/register", response_class=HTMLResponse, name="page_register_post")
def page_register_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(web_auth.get_db),
):
    if crud.get_user_by_username(db, username):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "user": None, "error": "Логин уже занят"},
            status_code=400,
        )
    user = crud.create_user(db, username, password)
    response = RedirectResponse(request.url_for("page_notes"), status_code=303)
    _set_auth_cookie(response, create_access_token(user.id))
    return response


@router.get("/web/logout", include_in_schema=False, name="page_logout")
def page_logout(request: Request):
    response = RedirectResponse(request.url_for("page_login"), status_code=303)
    response.delete_cookie(COOKIE_NAME, path=PREFIX or "/")
    return response


@router.get("/notes", response_class=HTMLResponse, include_in_schema=False, name="page_notes")
def page_notes(
    request: Request,
    tag: str | None = Query(None),
    author: str | None = Query(None),        # ← НОВОЕ
    search: str | None = Query(None),
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    notes = crud.list_notes(db, tag=tag, author=author, search=search)
    all_tags = crud.all_tags(db)
    all_authors = crud.all_authors(db)       # ← НОВОЕ
    return templates.TemplateResponse(
        "notes_list.html",
        {
            "request": request,
            "user": user,
            "notes": notes,
            "all_tags": all_tags,
            "all_authors": all_authors,      # ← НОВОЕ
            "tag": tag,
            "author": author,                # ← НОВОЕ
            "search": search,
        },
    )


@router.get("/notes/new", response_class=HTMLResponse, include_in_schema=False, name="page_note_new")
def page_note_new(
    request: Request,
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    return templates.TemplateResponse(
        "note_form.html",
        {"request": request, "user": user, "note": None},
    )


@router.post("/notes/new", response_class=HTMLResponse, include_in_schema=False, name="page_note_new_post")
def page_note_new_post(
    request: Request,
    title: str = Form(...),
    content: str = Form(""),
    tags: str = Form(""),
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    note = crud.create_note(db, user.id, title, content, tag_list)   # owner_id = user.id
    return RedirectResponse(
        request.url_for("page_note_view", note_id=note.id), status_code=303
    )


@router.get("/notes/{note_id}", response_class=HTMLResponse, include_in_schema=False, name="page_note_view")
def page_note_view(
    request: Request,
    note_id: int,
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    note = crud.get_note(db, note_id)                        # ← без user.id
    if not note:
        raise HTTPException(404, "Заметка не найдена")
    return templates.TemplateResponse(
        "note_view.html",
        {
            "request": request,
            "user": user,
            "note": note,
            "content_html": render_markdown(note.content),
            "is_owner": note.owner_id == user.id,            # ← для шаблона
        },
    )


@router.get("/notes/{note_id}/edit", response_class=HTMLResponse, include_in_schema=False, name="page_note_edit")
def page_note_edit(
    request: Request,
    note_id: int,
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    note = crud.get_note(db, note_id)
    if not note:
        raise HTTPException(404, "Заметка не найдена")
    if note.owner_id != user.id:
        raise HTTPException(403, "Это чужая заметка — редактировать нельзя")
    return templates.TemplateResponse(
        "note_form.html",
        {"request": request, "user": user, "note": note},
    )


@router.post("/notes/{note_id}/edit", response_class=HTMLResponse, include_in_schema=False, name="page_note_edit_post")
def page_note_edit_post(
    request: Request,
    note_id: int,
    title: str = Form(...),
    content: str = Form(""),
    tags: str = Form(""),
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    note = crud.get_note(db, note_id)
    if not note:
        raise HTTPException(404, "Заметка не найдена")
    if note.owner_id != user.id:
        raise HTTPException(403, "Это чужая заметка — редактировать нельзя")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    crud.update_note(db, note, title=title, content=content, tags=tag_list)
    return RedirectResponse(request.url_for("page_note_view", note_id=note.id), status_code=303)


@router.post("/notes/{note_id}/delete", include_in_schema=False, name="page_note_delete")
def page_note_delete(
    request: Request,
    note_id: int,
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    note = crud.get_note(db, note_id)
    if not note:
        raise HTTPException(404, "Заметка не найдена")
    if note.owner_id != user.id:
        raise HTTPException(403, "Это чужая заметка — удалять нельзя")
    crud.delete_note(db, note)
    return RedirectResponse(request.url_for("page_notes"), status_code=303)


@router.get("/export/csv", include_in_schema=False, name="page_export_csv")
def page_export_csv(
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    notes = crud.list_notes(db)
    data = analytics.export_notes_csv(notes)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=notes.csv"},
    )


@router.get("/export/xlsx", include_in_schema=False, name="page_export_xlsx")
def page_export_xlsx(
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    notes = crud.list_notes(db)
    data = analytics.export_notes_excel(notes)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=notes.xlsx"},
    )


@router.get("/analytics/tags", response_class=HTMLResponse, include_in_schema=False, name="page_tags_stats")
def page_tags_stats(
    request: Request,
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    notes = crud.list_notes(db)
    stats = analytics.tag_statistics(notes)
    return templates.TemplateResponse(
        "tags_stats.html",
        {"request": request, "user": user, "stats": stats},
    )


@router.get("/favicon.ico", include_in_schema=False, name="favicon")
def favicon(request: Request):
    return RedirectResponse(
        request.url_for("static", path="favicon.ico"), status_code=301
    )


# Подключаем роутер к приложению
app.include_router(router)
