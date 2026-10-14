from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
import os

from app.models.db import get_db, User, AuthToken, UserRole, Course, TAAssignment, CourseEnrollment

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/verify")
async def verify_token(token: str, response: Response, db: Session = Depends(get_db)):
    auth_token = db.query(AuthToken).filter(
        AuthToken.token == token,
        AuthToken.used == False,
        AuthToken.expires_at > datetime.utcnow()
    ).first()

    if not auth_token:
        return RedirectResponse(url="/login?message=Invalid+or+expired+token", status_code=302)

    auth_token.used = True
    db.commit()

    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=86400
    )
    return response


@router.post("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session_token")
    if token:
        auth_token = db.query(AuthToken).filter(AuthToken.token == token).first()
        if auth_token:
            db.delete(auth_token)
            db.commit()
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session_token")
    return response


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    auth_token = db.query(AuthToken).filter(
        AuthToken.token == token,
        AuthToken.used == True,
        AuthToken.expires_at > datetime.utcnow()
    ).first()

    if not auth_token:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return auth_token.user


def require_role(role: UserRole):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role != role:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker
