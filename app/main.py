from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import (
    Depends, FastAPI, Form, HTTPException, Query, Request, status,
)
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from fastapi.responses import StreamingResponse   # добавьте в шапку импортов


from app.serjotools import crud, schemas, analytics, web_auth
from app.serjotools.database import Base, engine
from app.serjotools.dependencies import get_db, get_current_user
from app.serjotools.models import User
from app.serjotools.security import create_access_token, verify_password

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Knowledge Base", version="1.1.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

COOKIE_NAME = web_auth.COOKIE_NAME
COOKIE_MAX_AGE = 60 * 60  # 1 час


# ============================================================
#  JSON API (всё под /api, требует Bearer-токен)
# ============================================================

@app.post("/api/auth/register", response_model=schemas.UserOut, status_code=201)
def api_register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    if crud.get_user_by_username(db, data.username):
        raise HTTPException(status_code=400, detail="Логин уже занят")
    return crud.create_user(db, data.username, data.password)


@app.post("/api/auth/login", response_model=schemas.Token)
def api_login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_username(db, form.username)
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")
    return schemas.Token(access_token=create_access_token(user.id))


@app.get("/api/auth/me", response_model=schemas.UserOut)
def api_me(current: User = Depends(get_current_user)):
    return current


@app.get("/api/notes", response_model=list[schemas.NoteOut])
def api_list_notes(
    tag: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    return crud.list_notes(db, current.id, tag=tag, search=search)


@app.post("/api/notes", response_model=schemas.NoteOut, status_code=201)
def api_create_note(
    data: schemas.NoteCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    return crud.create_note(db, current.id, data.title, data.content, data.tags)


@app.get("/api/notes/{note_id}", response_model=schemas.NoteOut)
def api_get_note(
    note_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    note = crud.get_note(db, note_id, current.id)
    if not note:
        raise HTTPException(404, "Заметка не найдена")
    return note


@app.patch("/api/notes/{note_id}", response_model=schemas.NoteOut)
def api_update_note(
    note_id: int,
    data: schemas.NoteUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    note = crud.get_note(db, note_id, current.id)
    if not note:
        raise HTTPException(404, "Заметка не найдена")
    return crud.update_note(db, note, **data.model_dump(exclude_unset=True))


@app.delete("/api/notes/{note_id}", status_code=204)
def api_delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    note = crud.get_note(db, note_id, current.id)
    if not note:
        raise HTTPException(404, "Заметка не найдена")
    crud.delete_note(db, note)
    return Response(status_code=204)


@app.get("/api/tags", response_model=list[schemas.TagOut])
def api_tags(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    return crud.all_tags(db, current.id)


@app.get("/api/analytics/tags")
def api_tags_stats(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    notes = crud.list_notes(db, current.id)
    return analytics.tag_statistics(notes)


@app.get("/api/export/csv")
def api_export_csv(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    notes = crud.list_notes(db, current.id)
    data = analytics.export_notes_csv(notes)
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=notes.csv"},
    )


@app.get("/api/export/xlsx")
def api_export_xlsx(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    notes = crud.list_notes(db, current.id)
    data = analytics.export_notes_excel(notes)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=notes.xlsx"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


# ============================================================
#  Web UI (HTML, cookie-сессия)
# ============================================================

def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )


@app.get("/", include_in_schema=False)
def root(user: User | None = Depends(web_auth.get_current_user_optional)):
    if user:
        return RedirectResponse("/notes", status_code=303)
    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def page_login(
    request: Request,
    user: User | None = Depends(web_auth.get_current_user_optional),
):
    if user:
        return RedirectResponse("/notes", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "user": None})


@app.post("/login", response_class=HTMLResponse)
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
    response = RedirectResponse("/notes", status_code=303)
    _set_auth_cookie(response, create_access_token(user.id))
    return response


@app.get("/register", response_class=HTMLResponse)
def page_register(
    request: Request,
    user: User | None = Depends(web_auth.get_current_user_optional),
):
    if user:
        return RedirectResponse("/notes", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request, "user": None})


@app.post("/register", response_class=HTMLResponse)
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
    response = RedirectResponse("/notes", status_code=303)
    _set_auth_cookie(response, create_access_token(user.id))
    return response


@app.get("/web/logout", include_in_schema=False)
def page_logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@app.get("/notes", response_class=HTMLResponse, include_in_schema=False)
def page_notes(
    request: Request,
    tag: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    notes = crud.list_notes(db, user.id, tag=tag, search=search)
    all_tags = crud.all_tags(db, user.id)
    return templates.TemplateResponse(
        "notes_list.html",
        {
            "request": request,
            "user": user,
            "notes": notes,
            "all_tags": all_tags,
            "tag": tag,
            "search": search,
        },
    )


@app.get("/notes/new", response_class=HTMLResponse, include_in_schema=False)
def page_note_new(
    request: Request,
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    return templates.TemplateResponse(
        "note_form.html",
        {"request": request, "user": user, "note": None},
    )


@app.post("/notes/new", response_class=HTMLResponse, include_in_schema=False)
def page_note_new_post(
    request: Request,
    title: str = Form(...),
    content: str = Form(""),
    tags: str = Form(""),
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    note = crud.create_note(db, user.id, title, content, tag_list)
    return RedirectResponse(f"/notes/{note.id}", status_code=303)


@app.get("/notes/{note_id}", response_class=HTMLResponse, include_in_schema=False)
def page_note_view(
    request: Request,
    note_id: int,
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    note = crud.get_note(db, note_id, user.id)
    if not note:
        raise HTTPException(404, "Заметка не найдена")
    return templates.TemplateResponse(
        "note_view.html",
        {"request": request, "user": user, "note": note},
    )


@app.get("/notes/{note_id}/edit", response_class=HTMLResponse, include_in_schema=False)
def page_note_edit(
    request: Request,
    note_id: int,
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    note = crud.get_note(db, note_id, user.id)
    if not note:
        raise HTTPException(404, "Заметка не найдена")
    return templates.TemplateResponse(
        "note_form.html",
        {"request": request, "user": user, "note": note},
    )


@app.post("/notes/{note_id}/edit", response_class=HTMLResponse, include_in_schema=False)
def page_note_edit_post(
    request: Request,
    note_id: int,
    title: str = Form(...),
    content: str = Form(""),
    tags: str = Form(""),
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    note = crud.get_note(db, note_id, user.id)
    if not note:
        raise HTTPException(404, "Заметка не найдена")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    crud.update_note(db, note, title=title, content=content, tags=tag_list)
    return RedirectResponse(f"/notes/{note.id}", status_code=303)


@app.post("/notes/{note_id}/delete", include_in_schema=False)
def page_note_delete(
    note_id: int,
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    note = crud.get_note(db, note_id, user.id)
    if not note:
        raise HTTPException(404, "Заметка не найдена")
    crud.delete_note(db, note)
    return RedirectResponse("/notes", status_code=303)


@app.get("/export/csv", include_in_schema=False)
def page_export_csv(
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    notes = crud.list_notes(db, user.id)
    data = analytics.export_notes_csv(notes)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=notes.csv"},
    )


@app.get("/export/xlsx", include_in_schema=False)
def page_export_xlsx(
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    notes = crud.list_notes(db, user.id)
    data = analytics.export_notes_excel(notes)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=notes.xlsx"},
    )


@app.get("/analytics/tags", response_class=HTMLResponse, include_in_schema=False)
def page_tags_stats(
    request: Request,
    db: Session = Depends(web_auth.get_db),
    user: User = Depends(web_auth.get_current_user_from_cookie),
):
    notes = crud.list_notes(db, user.id)
    stats = analytics.tag_statistics(notes)
    return templates.TemplateResponse(
        "tags_stats.html",
        {"request": request, "user": user, "stats": stats},
    )

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse("/static/favicon.ico", status_code=301)
