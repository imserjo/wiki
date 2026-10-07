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
from app.src.security import create_access_token, verify_password, generate_reset_token, verify_reset_token, hash_password
from app.src.email_utils import send_password_reset_email
    
from app.src.config import settings
from app.src.markdown_render import render_markdown

from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware


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

# SessionMiddleware нужен Authlib для хранения state между запросами
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


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
    email: str = Form(...),                 # ← было username
    password: str = Form(...),
    db: Session = Depends(web_auth.get_db),
):
    user = crud.get_user_by_email(db, email)   # ← ищем по email
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "user": None, "error": "Неверный email или пароль"},
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
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(web_auth.get_db),
):
    if crud.get_user_by_username(db, username):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "user": None, "error": "Ник уже занят"},
            status_code=400,
        )
    if crud.get_user_by_email(db, email):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "user": None, "error": "Email уже зарегистрирован"},
            status_code=400,
        )
    user = crud.create_user(db, username, email, password)
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


@router.get("/forgot-password", response_class=HTMLResponse, include_in_schema=False, name="page_forgot_password")
def page_forgot_password(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request, "user": None})


@router.post("/forgot-password", response_class=HTMLResponse, include_in_schema=False, name="page_forgot_password_post")
def page_forgot_password_post(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(web_auth.get_db),
):
    user = crud.get_user_by_email(db, email)
    
    # ВАЖНО: не раскрываем, существует ли email
    # Всегда показываем одинаковое сообщение
    if user:
        token = generate_reset_token(user.email)
        reset_url = f"{settings.APP_BASE_URL}{PREFIX}/reset-password/{token}"
        try:
            send_password_reset_email(user.email, reset_url)
        except Exception:
            pass  # логируем, но не показываем пользователю
    
    return templates.TemplateResponse(
        "forgot_password.html",
        {
            "request": request,
            "user": None,
            "message": "Если этот email зарегистрирован, мы отправили ссылку для сброса пароля.",
        },
    )


@router.get("/reset-password/{token}", response_class=HTMLResponse, include_in_schema=False, name="page_reset_password")
def page_reset_password(request: Request, token: str):
    email = verify_reset_token(token)
    if not email:
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "user": None, "error": "Ссылка недействительна или истекла."},
            status_code=400,
        )
    return templates.TemplateResponse(
        "reset_password.html",
        {"request": request, "user": None, "token": token},
    )


@router.post("/reset-password/{token}", response_class=HTMLResponse, include_in_schema=False, name="page_reset_password_post")
def page_reset_password_post(
    request: Request,
    token: str,
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(web_auth.get_db),
):
    email = verify_reset_token(token)
    if not email:
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "user": None, "error": "Ссылка недействительна или истекла."},
            status_code=400,
        )
    
    if password != password_confirm:
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "user": None, "token": token, "error": "Пароли не совпадают."},
            status_code=400,
        )
    
    if len(password) < 6:
        return templates.TemplateResponse(
            "reset_password.html",
            {"request": request, "user": None, "token": token, "error": "Пароль должен быть минимум 6 символов."},
            status_code=400,
        )
    
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    
    user.hashed_password = hash_password(password)
    db.commit()
    
    return RedirectResponse(request.url_for("page_login"), status_code=303)


@router.get("/auth/google/login", include_in_schema=False, name="google_login")
async def google_login(request: Request):
    redirect_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback", include_in_schema=False, name="google_callback")
async def google_callback(
    request: Request,
    db: Session = Depends(web_auth.get_db),
):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return RedirectResponse(request.url_for("page_login"), status_code=303)
    
    userinfo = token.get("userinfo")
    if not userinfo or not userinfo.get("email"):
        return RedirectResponse(request.url_for("page_login"), status_code=303)
    
    email = userinfo["email"].lower()
    oauth_id = userinfo["sub"]  # уникальный ID Google
    name = userinfo.get("name", email.split("@")[0])
    
    # Ищем по oauth_id, потом по email
    user = crud.get_user_by_oauth(db, "google", oauth_id)
    if not user:
        user = crud.get_user_by_email(db, email)
        if user:
            # Существующий email — привязываем Google
            user.auth_provider = "google"
            user.oauth_id = oauth_id
            db.commit()
        else:
            # Новый пользователь
            # username из email, с обработкой коллизий
            base_username = email.split("@")[0][:64]
            username = base_username
            counter = 1
            while crud.get_user_by_username(db, username):
                username = f"{base_username}{counter}"
                counter += 1
            
            user = crud.create_user(
                db, username, email,
                password=None,
                auth_provider="google",
                oauth_id=oauth_id,
            )
    
    # Выдаём свой JWT (как при обычном логине)
    response = RedirectResponse(request.url_for("page_notes"), status_code=303)
    _set_auth_cookie(response, create_access_token(user.id))
    return response


# Подключаем роутер к приложению
app.include_router(router)
