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

## Установка

1. Клонировать репозиторий

```bash
git clone https://github.com/imserjo/wiki.git
cd wiki
```

1. a) Обновить репозиторий до актуальной версии
```bash
cd wiki
git pull
```


2. Создать и активировать виртуальное окружение
Windows (PowerShell):

```bash
python -m venv .venv
.venv\Scripts\activate
```
Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Установить зависимости
```bash
pip install -r requirements.txt
```

4. Настроить переменные окружения
```
Скопируйте .env.example в .env и заполните значения:
```

5. Запуск приложения из папки wiki
```bash
python -m uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
```
