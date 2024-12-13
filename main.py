"""Модуль демонстрирует работу с базой данных через SQLAlchemy."""


from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, DeclarativeBase, Session
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

# Настройки подключения к PostgreSQL
DATABASE_URL = "postgresql://postgres:12345@localhost:5432/LAB9"

# Создание движка SQLAlchemy
engine = create_engine(DATABASE_URL)

# Базовый класс для моделей
class Base(DeclarativeBase):
    """Базовый класс для всех моделей данных, которые будут использовать SQLAlchemy."""


# Определение таблицы Users
class User(Base):
    """Модель данных для пользователей. В этой таблице хранятся данные
    о пользователях, такие как их имя пользователя, email и пароль."""
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    posts = relationship("Post", back_populates="user", cascade="all, delete")

# Определение таблицы Posts
class Post(Base):
    """Модель данных для постов. В этой таблице хранятся посты пользователей,
    включая заголовок, контент и ссылку на пользователя."""
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    user = relationship("User", back_populates="posts")

# Создание таблиц в базе данных
Base.metadata.create_all(bind=engine)

# Создание сессии для работы с базой данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Функция для получения сессии базы данных.
    Используется для передачи сессии в зависимости в FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI приложение
app = FastAPI()

# Схемы Pydantic для запросов и ответов
class UserCreate(BaseModel):
    """Схема для создания нового пользователя.
    Используется для полученияданных пользователя из запроса."""
    username: str
    email: str
    password: str

class PostCreate(BaseModel):
    """Схема для создания нового поста. Используется для получения данных поста из запроса."""
    title: str
    content: str
    user_id: int

class UserResponse(BaseModel):
    """Схема для представления данных пользователя в ответах API."""
    id: int
    username: str
    email: str

    class Config:
        """Этот класс позволяет работать с объектами SQLAlchemy, как с обычными Python объектами"""
        from_attributes = True

class PostResponse(BaseModel):
    """Схема для представления данных поста в ответах API."""
    id: int
    title: str
    content: str
    user: UserResponse

    class Config:
        """Этот класс позволяет работать с объектами SQLAlchemy, как с обычными Python объектами"""
        from_attributes = True

app = FastAPI(docs_url="/docs")

@app.get("/")
def read_root():
    """Базовый маршрут"""
    return {"message": "Hello, World!"}

# CRUD операции для пользователей
@app.post("/users/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Создает нового пользователя. Проверяет уникальность username
    и email перед добавлением в базу данных."""
    # Проверка уникальности username и email
    if db.query(User).filter((User.username == user.username) | (User.email == user.email)).first():
        raise HTTPException(status_code=400,
                            detail="User with this username or email already exists")
    db_user = User(username=user.username, email=user.email, password=user.password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/", response_model=list[UserResponse])
def get_users(db: Session = Depends(get_db)):
    """Извлекает всех пользователей из базы данных."""
    return db.query(User).all()

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Извлекает информацию о пользователе по его id."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Удаляет пользователя по его id из базы данных, а также все связанные с ним посты."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(db_user)
    db.commit()
    return {"message": "User deleted"}

# Обновление email пользователя
@app.post("/users/", response_model=UserResponse)
def change_user_email(user_id: int, email: str, db: Session = Depends(get_db)):
    """Изменяет email у пользователя, находя его по id."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Проверяем, не занят ли email другим пользователем
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email is already taken")

    db_user.email = email
    db.commit()
    db.refresh(db_user)
    return db_user

# Обновление content поста
@app.put("/posts/{post_id}", response_model=PostResponse)
def update_post_content(post_id: int, content: str, db: Session = Depends(get_db)):
    """Обновляет content поста по его id."""
    db_post = db.query(Post).filter(Post.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")

    db_post.content = content
    db.commit()
    db.refresh(db_post)
    return db_post

# CRUD операции для постов
@app.post("/posts/", response_model=PostResponse)
def create_post(post: PostCreate, db: Session = Depends(get_db)):
    """Создает новый пост. Проверяет, существует ли
    пользователь с данным id, перед добавлением поста."""
    db_user = db.query(User).filter(User.id == post.user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db_post = Post(title=post.title, content=post.content, user_id=post.user_id)
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

@app.get("/posts/", response_model=list[PostResponse])
def get_posts(db: Session = Depends(get_db)):
    """Извлекает все посты из базы данных, включая информацию
    о пользователе, который создал каждый пост."""
    return db.query(Post).all()

@app.get("/posts/{post_id}", response_model=PostResponse)
def get_post(post_id: int, db: Session = Depends(get_db)):
    """Извлекает пост по его id, включая информацию о пользователе, который его создал."""
    db_post = db.query(Post).filter(Post.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    return db_post

@app.delete("/posts/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db)):
    """Удаляет пост по его id из базы данных."""
    db_post = db.query(Post).filter(Post.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(db_post)
    db.commit()
    return {"message": "Post deleted"}
