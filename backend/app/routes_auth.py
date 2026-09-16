from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, UserOut, Token
from app.auth import hash_password, verify_password, create_access_token
from app.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email is already registered")

    new_user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        password_hash=hash_password(user_in.password),
        # role defaults to 'user' — admins are promoted manually, never self-registered
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the profile of whoever's token is being used — a quick way to test auth is working."""
    return current_user


@router.get("/admin-only")
def admin_only_check(current_user: User = Depends(require_admin)):
    """
    Demo route to prove role enforcement works. Any logged-in user can hit
    /auth/me, but only an admin can successfully hit this one — a regular
    user gets a 403 Forbidden.
    """
    return {"message": f"Welcome, admin {current_user.full_name}. Role check passed."}