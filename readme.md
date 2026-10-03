# Wiki

Веб-приложение для заметок с тегами, поиском и аналитикой на FastAPI.

## Возможности

- Регистрация и авторизация пользователей
- CRUD для заметок
- Теги и фильтрация по ним
- Статистика по тегам и заметкам
- Серверный рендеринг через Jinja2
- REST API на FastAPI

## Стек

- **Python** 3.11+
- **FastAPI** — веб-фреймворк
- **Uvicorn** — ASGI-сервер
- **SQLAlchemy** — ORM
- **Jinja2** — шаблоны
- **Pydantic** — валидация схем
- **Passlib / bcrypt** — хеширование паролей
- **SQLite** (по умолчанию) / PostgreSQL

## Структура проекта
wiki/
├── app/
│ ├── main.py # точка входа FastAPI
│ ├── serjotools/ # бизнес-логика
│ │ ├── analytics.py
│ │ ├── config.py
│ │ ├── crud.py
│ │ ├── database.py
│ │ ├── dependencies.py
│ │ ├── models.py
│ │ ├── schemas.py
│ │ ├── security.py
│ │ └── web_auth.py
│ ├── static/ # CSS/JS
│ │ └── style.css
│ └── templates/ # Jinja2-шаблоны
│ ├── base.html
│ ├── login.html
│ ├── note_form.html
│ ├── note_view.html
│ ├── notes_list.html
│ ├── register.html
│ └── tags_stats.html
├── .env # локальные переменные (не коммитится)
├── .env.example # шаблон переменных окружения
├── .gitignore
├── .vscode/
│ └── launch.json # конфигурация отладки
├── README.md
└── requirements.txt


## Установка

1. Клонировать репозиторий

```bash
git clone https://github.com/imserjo/wiki.git
cd wiki

2. Создать и активировать виртуальное окружение
Windows (PowerShell):

powershell
python -m venv .venv
.venv\Scripts\activate
Linux / macOS:

bash
python3 -m venv .venv
source .venv/bin/activate

3. Установить зависимости
bash
pip install -r requirements.txt

4. Настроить переменные окружения
Скопируйте .env.example в .env и заполните значения:
