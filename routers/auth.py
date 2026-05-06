from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from pydantic import BaseModel
from database import get_db
from config import settings
from auth_utils import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


class Token(BaseModel):
    access_token: str
    token_type: str
    username: str


async def get_current_admin(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = get_db()
    docs = list(db.collection('admin_users').where('username', '==', username).limit(1).stream())
    if not docs:
        raise HTTPException(status_code=401, detail="User not found")
    return docs[0].to_dict()


@router.post("/token", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    db = get_db()
    docs = list(db.collection('admin_users').where('username', '==', form.username).limit(1).stream())
    if not docs:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    user = docs[0].to_dict()
    if not verify_password(form.password, user['hashed_password']):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token({"sub": user['username']})
    return Token(access_token=token, token_type="bearer", username=user['username'])


@router.get("/me")
async def get_me(admin=Depends(get_current_admin)):
    return {"username": admin['username'], "email": admin.get('email', '')}
