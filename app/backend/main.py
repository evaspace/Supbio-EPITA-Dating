"""Backend for Campus Connect.

Run locally with: uvicorn backend.main:app --reload
Production requires SMTP, PostgreSQL, HTTPS and an independent safety review.
"""
import asyncio
import hashlib
import io
import hmac
import json
import os
import re
import secrets
import ssl
import smtplib
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, event, or_, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
SCHOOLS = {"EPITA": "epita.fr", "SupBiotech": "supbiotech.fr", "ESME": "esme.fr", "ISG": "isg.fr", "IPSA": "ipsa.fr"}
School = Literal["EPITA", "SupBiotech", "ESME", "ISG", "IPSA"]
GENDERS = {"Femme", "Homme", "Non-binaire", "Autre", "Non précisé"}
CITIES = {"Paris", "Lyon", "Rennes", "Strasbourg", "Toulouse", "Autre"}
UTC = timezone.utc

def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)

def uid() -> str:
    return uuid4().hex

def years_old(day: date) -> int:
    today = date.today()
    return today.year - day.year - ((today.month, today.day) < (day.month, day.day))

def password_digest(secret: str, value: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(35))
    school: Mapped[str] = mapped_column(String(30), index=True)
    city: Mapped[str] = mapped_column(String(30), default="Lyon")
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(30), default="Non précisé")
    bio: Mapped[str] = mapped_column(Text, default="")
    interests: Mapped[str] = mapped_column(Text, default="[]")
    preferences: Mapped[str] = mapped_column(Text, default='{"schools":["EPITA","SupBiotech","ESME","ISG","IPSA"],"genders":["Femme","Homme","Non-binaire","Autre","Non précisé"],"age_min":18,"age_max":40,"city":"Toutes"}')
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class OTP(Base):
    __tablename__ = "otp_challenges"
    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    issued_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    tries: Mapped[int] = mapped_column(Integer, default=0)

class SessionToken(Base):
    __tablename__ = "sessions"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

class Swipe(Base):
    __tablename__ = "swipes"
    __table_args__ = (UniqueConstraint("actor_id", "target_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    actor_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(6))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("user_a_id", "user_b_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_a_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    user_b_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    match_id: Mapped[str] = mapped_column(String(32), ForeignKey("matches.id", ondelete="CASCADE"))
    sender_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Photo(Base):
    __tablename__ = "photos"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    file_name: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = (UniqueConstraint("actor_id", "target_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    actor_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    reporter_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    status: Mapped[str] = mapped_column(String(20), default="open")

class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

class PhotoOrder(BaseModel):
    photo_ids: list[str] = Field(min_length=1, max_length=6)

class ModerationAction(BaseModel):
    status: Literal["approved", "rejected"]

class ReportAction(BaseModel):
    status: Literal["open", "reviewed", "dismissed"]

class AccountAction(BaseModel):
    approved: bool

class RequestCode(BaseModel):
    email: str = Field(min_length=6, max_length=255)
    school: School

    @field_validator("email")
    @classmethod
    def email_format(cls, v: str) -> str:
        return v.strip().lower()

class VerifyCode(BaseModel):
    email: str
    code: str = Field(pattern=r"^\d{6}$")
    school: School
    name: str = Field(min_length=2, max_length=35)
    birthday: date
    city: str = Field(default="Lyon", max_length=30)
    gender: str = Field(default="Non précisé", max_length=30)
    adult_consent: bool

class EditProfile(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=35)
    bio: str | None = Field(default=None, max_length=450)
    city: str | None = None
    gender: str | None = None
    interests: list[str] | None = Field(default=None, max_length=12)
    visible: bool | None = None

class Preferences(BaseModel):
    schools: list[School] = Field(min_length=1)
    genders: list[str] = Field(min_length=1)
    age_min: int = Field(ge=18, le=99)
    age_max: int = Field(ge=18, le=99)
    city: str = Field(default="Toutes", max_length=30)

class SwipeIn(BaseModel):
    target_id: str
    action: Literal["like", "pass"]

class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)

class ReportIn(BaseModel):
    target_id: str
    reason: str = Field(min_length=5, max_length=200)

class BlockIn(BaseModel):
    target_id: str


def create_app(database_url: str | None = None, dev_otp: bool | None = None) -> FastAPI:
    production = os.getenv("APP_ENV", "development").lower() == "production"
    app = FastAPI(title="Campus Connect API", version="1.0.0", docs_url=None if production else "/api/docs", openapi_url=None if production else "/api/openapi.json")
    db_url = database_url or os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'campus.db'}")
    engine = create_engine(db_url, connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {}, pool_pre_ping=True)
    if db_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def sqlite_foreign_keys(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    # Initial schema for a fresh database; use a reviewed migration before upgrades.
    from . import jeudi as jeudi_layer  # registers the Jeudi tables on Base
    Base.metadata.create_all(engine)
    LocalSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    live_sockets: dict[str, set[WebSocket]] = {}
    app.state.engine = engine
    app.state.local_session = LocalSession
    app.state.dev_otp = dev_otp if dev_otp is not None else os.getenv("DEV_OTP", "false").lower() == "true"
    if production and app.state.dev_otp:
        raise RuntimeError("DEV_OTP interdit en production")
    secret = os.getenv("AUTH_SECRET")
    if production and (not secret or len(secret) < 48):
        raise RuntimeError("AUTH_SECRET doit contenir au moins 48 caracteres en production")
    if not secret:
        secret = secrets.token_hex(32)
    app.state.auth_secret = secret
    media_dir = Path(os.getenv("MEDIA_DIR", str(ROOT / "private_uploads"))).resolve()
    media_dir.mkdir(parents=True, exist_ok=True)
    cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    app.state.cookie_secure = cookie_secure
    if production and not cookie_secure:
        raise RuntimeError("COOKIE_SECURE=true requis en production")
    approval_required = os.getenv("REQUIRE_ACCOUNT_APPROVAL", "true" if production else "false").lower() == "true"
    admin_emails = {x.strip().lower() for x in os.getenv("ADMIN_EMAILS", "").split(",") if x.strip()}
    if production and not admin_emails:
        raise RuntimeError("ADMIN_EMAILS requis pour la moderation en production")
    if production and not os.getenv("SITE_ORIGIN", "").startswith("https://"):
        raise RuntimeError("SITE_ORIGIN HTTPS requis en production")
    if production:
        from starlette.middleware.trustedhost import TrustedHostMiddleware
        from urllib.parse import urlparse
        domain = urlparse(os.getenv("SITE_ORIGIN", "")).hostname
        if not domain:
            raise RuntimeError("Nom de domaine invalide")
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=[domain, "127.0.0.1", "localhost"])
    if production and not os.getenv("SMTP_HOST"):
        raise RuntimeError("SMTP_HOST requis en production")

    def db():
        with LocalSession() as session:
            yield session

    def own_user(request: Request, conn: Annotated[Session, Depends(db)]) -> User:
        raw = request.cookies.get("campus_session")
        if not raw or len(raw) < 40:
            raise HTTPException(401, "Connexion requise")
        digest = password_digest(secret, raw)
        record = conn.get(SessionToken, digest)
        if not record or record.expires_at <= now():
            raise HTTPException(401, "Session expirée")
        user = conn.get(User, record.user_id)
        if not user or user.suspended or user.age < 18:
            raise HTTPException(403, "Compte inaccessible")
        if approval_required and not user.approved and request.url.path not in {"/api/me", "/api/auth/logout", "/api/account/export", "/api/account"} and not request.url.path.startswith("/api/admin/"):
            raise HTTPException(403, "Compte en attente de validation par la moderation")
        return user

    AuthUser = Annotated[User, Depends(own_user)]
    Db = Annotated[Session, Depends(db)]
    ctx = SimpleNamespace(AuthUser=AuthUser, Db=Db, LocalSession=LocalSession, media_dir=media_dir, production=production, root=ROOT)

    def limit_ip(conn: Session, request: Request, category: str, max_count: int, window_seconds: int):
        # The reverse proxy must overwrite X-Real-IP and the API must not be directly reachable.
        ip = request.headers.get("x-real-ip", "") if os.getenv("TRUST_PROXY_IP") == "true" else ""
        if not ip:
            ip = request.client.host if request.client else "unknown"
        bucket_key = password_digest(secret, f"{category}:{ip}")
        row = conn.get(RateBucket, bucket_key, with_for_update=True)
        t = now()
        if row is None:
            row = RateBucket(key=bucket_key, count=0, expires_at=t + timedelta(seconds=window_seconds))
            conn.add(row)
        if row.expires_at < t:
            row.count = 0
            row.expires_at = t + timedelta(seconds=window_seconds)
        if row.count >= max_count:
            conn.commit()
            raise HTTPException(429, "Trop de requetes. Reessayez plus tard")
        row.count += 1
        conn.commit()

    @app.middleware("http")
    async def same_origin_write(request: Request, call_next):
        # When authenticated by cookies, enforce same-origin writes. This protects against CSRF.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            allowed = os.getenv("SITE_ORIGIN", str(request.base_url).rstrip("/"))
            if origin and origin.rstrip("/") != allowed.rstrip("/"):
                return Response(status_code=403, content="Origine non autorisee")
            if request.url.path.startswith("/api/") and request.headers.get("x-campus-request") != "1":
                return Response(status_code=403, content="En-tete de protection requis")
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' ws: wss:; font-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith('/api/') else "no-cache"
        if production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    def represent(user: User, private: bool = False) -> dict:
        data = {"id": user.id, "name": user.name, "school": user.school,
                "city": user.city, "age": user.age, "gender": user.gender,
                "bio": user.bio, "interests": json.loads(user.interests)}
        if private:
            data.update(email=user.email, preferences=json.loads(user.preferences), visible=user.visible,
                        adult_verification="self_declared_only", approved=user.approved, pending_approval=approval_required and not user.approved, is_admin=user.email in admin_emails)
        return data

    def with_photos(conn: Session, data: dict, private: bool = False) -> dict:
        photos = conn.scalars(select(Photo).where(Photo.owner_id == data["id"]).order_by(Photo.position, Photo.created_at)).all()
        data["photos"] = [{"id": p.id, "url": f"/api/photos/{p.id}", "status": p.status}
                          for p in photos if private or p.status == "approved"]
        return data

    ctx.represent, ctx.with_photos = represent, with_photos

    def is_blocked(conn: Session, a: str, b: str) -> bool:
        return conn.scalar(select(Block.id).where(or_((Block.actor_id == a) & (Block.target_id == b),
                                                     (Block.actor_id == b) & (Block.target_id == a))).limit(1)) is not None

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "beta", "live_accounts": True}

    @app.post("/api/auth/request-code")
    def request_code(payload: RequestCode, request: Request, conn: Db):
        limit_ip(conn, request, "request-otp", 12, 15 * 60)
        email = payload.email
        if not re.fullmatch(r"[^@\s]+@" + re.escape(SCHOOLS[payload.school]), email):
            raise HTTPException(422, "Adresse de l'école invalide")
        existing = conn.get(OTP, email)
        t = now()
        if existing and (t-existing.issued_at).total_seconds() < 60:
            raise HTTPException(429, "Veuillez attendre une minute avant un nouveau code")
        code = f"{secrets.randbelow(1000000):06d}"
        dev_ok = app.state.dev_otp and request.client and request.client.host in {"127.0.0.1", "::1", "localhost", "testclient"}
        if not dev_ok:
            smtp_host = os.getenv("SMTP_HOST")
            if not smtp_host:
                raise HTTPException(503, "Envoi d'email non configuré")
            msg = EmailMessage()
            msg["From"] = os.getenv("SMTP_FROM", "noreply@localhost")
            msg["To"] = email
            msg["Subject"] = "Votre code Campus Connect"
            msg.set_content(f"Votre code est {code}. Il expire dans 10 minutes. Ne le partagez pas.")
            try:
                with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "587")), timeout=8) as smtp:
                    smtp.starttls(context=ssl.create_default_context())
                    if os.getenv("SMTP_USER"):
                        smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD", ""))
                    smtp.send_message(msg)
            except (OSError, smtplib.SMTPException):
                raise HTTPException(503, "Service email temporairement indisponible")
        record = existing or OTP(email=email, code_hash="", issued_at=t, expires_at=t)
        record.code_hash = password_digest(secret, email + ":" + code)
        record.issued_at = t
        record.expires_at = t + timedelta(minutes=10)
        record.tries = 0
        conn.add(record)
        conn.commit()
        result = {"message": "Si l'adresse est valide, un code a été préparé.", "expires_in": 600}
        if dev_ok:
            result["local_demo_code"] = code  # Local-only simulation, never expose in production.
        return result

    @app.post("/api/auth/verify-code")
    def verify(payload: VerifyCode, response: Response, request: Request, conn: Db):
        limit_ip(conn, request, "verify-otp", 30, 15 * 60)
        email = payload.email.strip().lower()
        if not re.fullmatch(r"[^@\s]+@" + re.escape(SCHOOLS[payload.school]), email):
            raise HTTPException(422, "Email et école incompatibles")
        if years_old(payload.birthday) < 18 or years_old(payload.birthday) > 100 or not payload.adult_consent:
            raise HTTPException(403, "Application réservée aux adultes de 18 ans et plus")
        challenge = conn.get(OTP, email)
        if not challenge or challenge.expires_at < now() or challenge.tries >= 5:
            raise HTTPException(400, "Code invalide ou expiré")
        challenge.tries += 1
        if not hmac.compare_digest(challenge.code_hash, password_digest(secret, email + ":" + payload.code)):
            conn.commit()
            raise HTTPException(400, "Code invalide ou expiré")
        clean_name = payload.name.strip()
        if len(clean_name) < 2:
            raise HTTPException(422, "Prénom invalide")
        user = conn.scalar(select(User).where(User.email == email))
        if not user:
            user = User(email=email, name=clean_name, age=years_old(payload.birthday), school=payload.school,
                        approved=(not approval_required or email in admin_emails),
                        city=payload.city if payload.city in CITIES else "Autre",
                        gender=payload.gender if payload.gender in GENDERS else "Non précisé")
            conn.add(user)
            conn.flush()
        if user.suspended:
            raise HTTPException(403, "Compte suspendu")
        conn.delete(challenge)
        token = secrets.token_urlsafe(48)
        conn.add(SessionToken(digest=password_digest(secret, token), user_id=user.id, expires_at=now()+timedelta(days=7)))
        conn.commit()
        response.set_cookie("campus_session", token, max_age=7*86400, httponly=True,
                            secure=cookie_secure, samesite="strict", path="/")
        return {"user": with_photos(conn, represent(user, True), private=True), "notice": "Age declare uniquement : validation adulte manuelle requise avant acces si activee"}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response, conn: Db):
        raw = request.cookies.get("campus_session")
        if raw:
            record = conn.get(SessionToken, password_digest(secret, raw))
            if record:
                conn.delete(record)
                conn.commit()
        response.delete_cookie("campus_session", path="/")
        return {"ok": True}

    @app.get("/api/me")
    def me(user: AuthUser):
        with LocalSession() as conn:
            return with_photos(conn, represent(user, True), private=True)

    @app.patch("/api/me")
    def edit_me(payload: EditProfile, user: AuthUser, conn: Db):
        for key, val in payload.model_dump(exclude_unset=True).items():
            if val is None:
                raise HTTPException(422, "Champ vide ou non valide")
            if key == "name":
                val = val.strip()
                if len(val) < 2:
                    raise HTTPException(422, "Prénom invalide")
            if key == "interests":
                if any(not t.strip() or len(t) > 65 for t in val):
                    raise HTTPException(422, "Centres d’intérêt non valides")
                user.interests = json.dumps(list(dict.fromkeys(t.strip() for t in val)), ensure_ascii=False)
            elif key == "city":
                if val not in CITIES:
                    raise HTTPException(422, "Campus inconnu")
                user.city = val
            elif key == "gender":
                if val not in GENDERS:
                    raise HTTPException(422, "Genre invalide")
                user.gender = val
            else:
                setattr(user, key, val)
        conn.commit()
        return with_photos(conn, represent(user, True), private=True)

    @app.put("/api/me/preferences")
    def set_preferences(payload: Preferences, user: AuthUser, conn: Db):
        if payload.age_min > payload.age_max or any(g not in GENDERS for g in payload.genders):
            raise HTTPException(422, "Filtres incorrects")
        if payload.city not in CITIES | {"Toutes"}:
            raise HTTPException(422, "Ville incorrecte")
        user.preferences = payload.model_dump_json()
        conn.commit()
        return {"preferences": json.loads(user.preferences)}

    @app.get("/api/interests")
    def get_interests():
        path = ROOT / "data" / "interests.json"
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/discover")
    def discover(user: AuthUser, conn: Db):
        if not user.visible:
            return {"profiles": []}
        pref = json.loads(user.preferences)
        seen = set(conn.scalars(select(Swipe.target_id).where(Swipe.actor_id == user.id)))
        seen.add(user.id)
        blocks = set(conn.scalars(select(Block.target_id).where(Block.actor_id == user.id)))
        blocks |= set(conn.scalars(select(Block.actor_id).where(Block.target_id == user.id)))
        q = select(User).where(User.id.not_in(seen | blocks), User.suspended.is_(False), User.approved.is_(True), User.visible.is_(True),
                               User.school.in_(pref["schools"]), User.gender.in_(pref["genders"]),
                               User.age.between(pref["age_min"], pref["age_max"]))
        if pref["city"] != "Toutes":
            q = q.where(User.city == pref["city"])
        candidates = conn.scalars(q.limit(150)).all()
        my_interests = set(json.loads(user.interests))
        eligible = []
        for target in candidates:
            reciprocal = json.loads(target.preferences)
            if user.school not in reciprocal["schools"] or user.gender not in reciprocal["genders"]:
                continue
            if not reciprocal["age_min"] <= user.age <= reciprocal["age_max"]:
                continue
            if reciprocal["city"] not in {"Toutes", user.city}:
                continue
            if not (jeudi_layer.intents_of(conn, user.id) & jeudi_layer.intents_of(conn, target.id)):
                continue
            other_interests = set(json.loads(target.interests))
            common = sorted(my_interests & other_interests)
            eligible.append({**ctx.decorate(conn, with_photos(conn, represent(target)), False), "shared_interests": common,
                             "_gap": abs(jeudi_layer.elo_of(conn, user.id) - jeudi_layer.elo_of(conn, target.id))})
        eligible.sort(key=lambda p: (-len(p["shared_interests"]), p.pop("_gap"), p["id"]))
        for p in eligible:
            p.pop("_gap", None)
        return {"profiles": eligible[:30]}

    @app.post("/api/swipes")
    def swipe(payload: SwipeIn, user: AuthUser, conn: Db):
        if payload.target_id == user.id:
            raise HTTPException(422, "Impossible de se liker soi-même")
        target = conn.get(User, payload.target_id)
        if not target or not target.visible or target.suspended or not target.approved or not user.visible or is_blocked(conn, user.id, target.id):
            raise HTTPException(404, "Profil indisponible")
        own_pref = json.loads(user.preferences)
        their_pref = json.loads(target.preferences)
        if (target.school not in own_pref["schools"] or target.gender not in own_pref["genders"] or
            not own_pref["age_min"] <= target.age <= own_pref["age_max"] or
            own_pref["city"] not in {"Toutes", target.city} or
            user.school not in their_pref["schools"] or user.gender not in their_pref["genders"] or
            not their_pref["age_min"] <= user.age <= their_pref["age_max"] or
            their_pref["city"] not in {"Toutes", user.city}):
            raise HTTPException(404, "Profil indisponible")
        exists = conn.scalar(select(Swipe).where(Swipe.actor_id == user.id, Swipe.target_id == target.id))
        if exists:
            raise HTTPException(409, "Profil déjà évalué")
        conn.add(Swipe(actor_id=user.id, target_id=target.id, action=payload.action))
        jeudi_layer.on_swipe(conn, user, target, payload.action)
        match_id = None
        if payload.action == "like":
            reverse = conn.scalar(select(Swipe).where(Swipe.actor_id == target.id, Swipe.target_id == user.id, Swipe.action == "like"))
            if reverse:
                a, b = sorted([user.id, target.id])
                match = conn.scalar(select(Match).where(Match.user_a_id == a, Match.user_b_id == b))
                if not match:
                    match = Match(user_a_id=a, user_b_id=b)
                    conn.add(match)
                    conn.flush()
                match_id = match.id
        conn.commit()
        return {"ok": True, "matched": bool(match_id), "match_id": match_id}

    @app.get("/api/likes-received")
    def likes_received(user: AuthUser, conn: Db):
        likes = conn.scalars(select(Swipe).where(Swipe.target_id == user.id, Swipe.action == "like")).all()
        sent = set(conn.scalars(select(Swipe.target_id).where(Swipe.actor_id == user.id)))
        return {"profiles": [ctx.decorate(conn, with_photos(conn, represent(u)), False) for l in likes if l.actor_id not in sent and not is_blocked(conn, user.id, l.actor_id)
                             if (u := conn.get(User, l.actor_id)) and u.visible and not u.suspended]}

    @app.get("/api/matches")
    def matches(user: AuthUser, conn: Db):
        res = []
        for match in conn.scalars(select(Match).where(or_(Match.user_a_id == user.id, Match.user_b_id == user.id)).order_by(Match.created_at.desc())):
            other_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
            if is_blocked(conn, user.id, other_id):
                continue
            target = conn.get(User, other_id)
            if not target or target.suspended or (approval_required and not target.approved):
                continue
            last = conn.scalar(select(Message).where(Message.match_id == match.id).order_by(Message.created_at.desc(), Message.id.desc()).limit(1))
            res.append({"id": match.id, "profile": ctx.decorate(conn, with_photos(conn, represent(target)), True),
                        "last_message": last.body if last else None, "created_at": match.created_at.isoformat()})
        return {"matches": res}

    def get_match(conn: Session, match_id: str, user_id: str) -> Match:
        match = conn.get(Match, match_id)
        if not match or user_id not in {match.user_a_id, match.user_b_id} or is_blocked(conn, match.user_a_id, match.user_b_id):
            raise HTTPException(404, "Conversation inaccessible")
        counterpart = conn.get(User, match.user_b_id if user_id == match.user_a_id else match.user_a_id)
        if not counterpart or counterpart.suspended:
            raise HTTPException(404, "Conversation inaccessible")
        return match

    @app.get("/api/matches/{match_id}/messages")
    def messages(match_id: str, user: AuthUser, conn: Db):
        get_match(conn, match_id, user.id)
        rows = conn.scalars(select(Message).where(Message.match_id == match_id).order_by(Message.created_at.asc(), Message.id.asc()).limit(200)).all()
        return {"messages": [{"id": m.id, "mine": m.sender_id == user.id,
                               "body": m.body, "time": m.created_at.isoformat()} for m in rows]}

    @app.post("/api/matches/{match_id}/messages")
    async def send_message(match_id: str, payload: MessageIn, user: AuthUser, conn: Db):
        get_match(conn, match_id, user.id)
        body = payload.body.strip()
        if not body:
            raise HTTPException(422, "Message vide")
        recent = conn.scalar(select(Message.created_at).where(Message.sender_id == user.id).order_by(Message.created_at.desc()).limit(1))
        if recent and now() - recent < timedelta(seconds=1):
            raise HTTPException(429, "Envoi trop rapide")
        msg = Message(match_id=match_id, sender_id=user.id, body=body)
        conn.add(msg)
        conn.commit()
        payload = {"type": "new-message", "match_id": match_id, "message_id": msg.id}
        # WebSockets only announce a change; full message is re-read via the authorized API.
        for socket in tuple(live_sockets.get(match_id, ())):
            try:
                await socket.send_json(payload)
            except Exception:
                live_sockets.get(match_id, set()).discard(socket)
        return {"id": msg.id, "body": msg.body, "mine": True, "time": msg.created_at.isoformat()}

    @app.websocket("/api/ws/matches/{match_id}")
    async def ws_messages(websocket: WebSocket, match_id: str):
        origin = websocket.headers.get("origin")
        expected = os.getenv("SITE_ORIGIN") or ("https://" if websocket.url.scheme == "wss" else "http://") + websocket.headers.get("host", "")
        if not origin or origin.rstrip("/") != expected.rstrip("/"):
            await websocket.close(code=1008)
            return
        token = websocket.cookies.get("campus_session", "")
        with LocalSession() as check:
            record = check.get(SessionToken, password_digest(secret, token)) if len(token) >= 40 else None
            user = check.get(User, record.user_id) if record and record.expires_at > now() else None
            if not user or user.suspended or user.age < 18 or (approval_required and not user.approved):
                await websocket.close(code=1008)
                return
            try:
                get_match(check, match_id, user.id)
            except HTTPException:
                await websocket.close(code=1008)
                return
        await websocket.accept()
        live_sockets.setdefault(match_id, set()).add(websocket)
        try:
            while True:
                incoming = await websocket.receive_text()
                if incoming == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass
        finally:
            live_sockets.get(match_id, set()).discard(websocket)

    @app.delete("/api/matches/{match_id}")
    def unmatch(match_id: str, user: AuthUser, conn: Db):
        match = get_match(conn, match_id, user.id)
        conn.delete(match)
        conn.commit()
        return {"ok": True}

    @app.post("/api/blocks")
    def block(payload: BlockIn, user: AuthUser, conn: Db):
        if payload.target_id == user.id or not conn.get(User, payload.target_id):
            raise HTTPException(404, "Profil introuvable")
        if not conn.scalar(select(Block).where(Block.actor_id == user.id, Block.target_id == payload.target_id)):
            conn.add(Block(actor_id=user.id, target_id=payload.target_id))
        a, b = sorted((user.id, payload.target_id))
        match = conn.scalar(select(Match).where(Match.user_a_id == a, Match.user_b_id == b))
        if match:
            conn.delete(match)
        conn.commit()
        return {"ok": True}

    @app.post("/api/reports")
    def report(payload: ReportIn, user: AuthUser, conn: Db):
        if payload.target_id == user.id or not conn.get(User, payload.target_id):
            raise HTTPException(404, "Profil introuvable")
        conn.add(Report(reporter_id=user.id, target_id=payload.target_id, reason=payload.reason.strip()))
        conn.commit()
        return {"ok": True, "status": "recorded_for_review"}

    @app.post("/api/me/photos")
    async def upload_photo(user: AuthUser, conn: Db, photo: UploadFile = File(...)):
        if photo.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(415, "Format autorisé : JPEG, PNG ou WebP")
        current = conn.scalars(select(Photo).where(Photo.owner_id == user.id)).all()
        if len(current) >= 6:
            raise HTTPException(422, "Maximum 6 photos")
        raw = await photo.read(5 * 1024 * 1024 + 1)
        if not raw or len(raw) > 5 * 1024 * 1024:
            raise HTTPException(413, "Photo limitée à 5 Mo")
        try:
            with Image.open(io.BytesIO(raw)) as source:
                if source.width * source.height > 20_000_000:
                    raise ValueError("Image trop grande")
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((1280, 1280))
                result_id = uid()
                name = result_id + ".webp"
                image.save(media_dir / name, "WEBP", quality=82, method=5)
        except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError):
            raise HTTPException(422, "Fichier image invalide")
        item = Photo(id=result_id, owner_id=user.id, file_name=name, status="pending", position=len(current))
        conn.add(item)
        conn.commit()
        return {"id": result_id, "url": f"/api/photos/{result_id}", "status": "pending",
                "notice": "Photo privée en attente de validation avant affichage aux autres comptes"}

    @app.patch("/api/me/photos/order")
    def reorder_photos(payload: PhotoOrder, user: AuthUser, conn: Db):
        photos = conn.scalars(select(Photo).where(Photo.owner_id == user.id)).all()
        expected = {p.id for p in photos}
        if len(payload.photo_ids) != len(expected) or set(payload.photo_ids) != expected:
            raise HTTPException(422, "Precisez tous vos identifiants de photos, sans doublon")
        positions = {id_: i for i, id_ in enumerate(payload.photo_ids)}
        for photo in photos:
            photo.position = positions[photo.id]
        conn.commit()
        return {"photos": with_photos(conn, represent(user, True), private=True)["photos"]}

    @app.get("/api/photos/{photo_id}")
    def read_photo(photo_id: str, user: AuthUser, conn: Db):
        item = conn.get(Photo, photo_id)
        if not item:
            raise HTTPException(404, "Photo introuvable")
        owner = conn.get(User, item.owner_id)
        if not owner or is_blocked(conn, user.id, owner.id):
            raise HTTPException(404, "Photo indisponible")
        if item.owner_id != user.id and (item.status != "approved" or not owner.visible or owner.suspended):
            raise HTTPException(404, "Photo en attente de validation")
        if item.owner_id != user.id:
            x, y = sorted((user.id, owner.id))
            if not conn.scalar(select(Match.id).where(Match.user_a_id == x, Match.user_b_id == y)):
                raise HTTPException(404, "Photo visible seulement après un match")
        filename = media_dir / item.file_name  # generated UUID filename, not user input
        if not filename.exists():
            raise HTTPException(404, "Photo introuvable")
        return FileResponse(filename, media_type="image/webp", headers={"Cache-Control": "private, no-store"})

    @app.delete("/api/me/photos/{photo_id}")
    def delete_photo(photo_id: str, user: AuthUser, conn: Db):
        item = conn.get(Photo, photo_id)
        if not item or item.owner_id != user.id:
            raise HTTPException(404, "Photo introuvable")
        filename = media_dir / item.file_name
        conn.delete(item)
        conn.commit()
        filename.unlink(missing_ok=True)
        return {"ok": True}

    @app.get("/api/account/export")
    def export_account(user: AuthUser, conn: Db):
        swipes = conn.scalars(select(Swipe).where(Swipe.actor_id == user.id)).all()
        messages = conn.scalars(select(Message).where(Message.sender_id == user.id)).all()
        return {"profile": with_photos(conn, represent(user, True), private=True),
                "swipes": [{"target_id": s.target_id, "action": s.action} for s in swipes],
                "messages": [{"body": m.body, "sent_at": m.created_at.isoformat()} for m in messages]}

    @app.delete("/api/account")
    def delete_account(user: AuthUser, response: Response, conn: Db):
        # SQL FKs cascade most rows, but rows pointing to account as target must also cascade.
        pictures = [media_dir / x.file_name for x in conn.scalars(select(Photo).where(Photo.owner_id == user.id))]
        own_style = conn.get(jeudi_layer.UserStyle, user.id)
        if own_style and own_style.drawing_file:
            pictures.append(media_dir / own_style.drawing_file)
        conn.delete(user)
        conn.commit()
        for file in pictures:
            file.unlink(missing_ok=True)
        response.delete_cookie("campus_session", path="/")
        return {"ok": True}

    def admin_only(user: AuthUser):
        if user.email not in admin_emails:
            raise HTTPException(403, "Acces moderation interdit")
        return user

    Admin = Annotated[User, Depends(admin_only)]
    ctx.Admin = Admin

    @app.get("/api/admin/queue")
    def admin_queue(admin: Admin, conn: Db):
        photos = conn.scalars(select(Photo).where(Photo.status == "pending").order_by(Photo.created_at).limit(100)).all()
        reports = conn.scalars(select(Report).where(Report.status == "open").order_by(Report.created_at).limit(100)).all()
        approvals = conn.scalars(select(User).where(User.approved.is_(False)).order_by(User.created_at).limit(100)).all()
        return {"photos": [{"id": p.id, "owner_id": p.owner_id, "status": p.status} for p in photos],
                "reports": [{"id": r.id, "reporter_id": r.reporter_id, "target_id": r.target_id, "reason": r.reason} for r in reports],
                "accounts": [{"id": u.id, "name": u.name, "school": u.school, "email": u.email, "age_declared": u.age, "approved": u.approved} for u in approvals]}

    @app.get("/api/admin/photos/{photo_id}")
    def admin_photo(photo_id: str, admin: Admin, conn: Db):
        item = conn.get(Photo, photo_id)
        if not item:
            raise HTTPException(404, "Photo introuvable")
        path = media_dir / item.file_name
        if not path.is_file():
            raise HTTPException(404, "Photo absente")
        return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "private, no-store"})

    @app.patch("/api/admin/photos/{photo_id}")
    def moderate_photo(photo_id: str, payload: ModerationAction, admin: Admin, conn: Db):
        photo = conn.get(Photo, photo_id)
        if not photo:
            raise HTTPException(404, "Photo introuvable")
        if payload.status == "rejected":
            path = media_dir / photo.file_name
            conn.delete(photo)
            conn.commit()
            path.unlink(missing_ok=True)
            return {"ok": True, "status": "rejected"}
        photo.status = "approved"
        conn.commit()
        return {"ok": True, "status": "approved"}

    @app.patch("/api/admin/reports/{report_id}")
    def moderate_report(report_id: str, payload: ReportAction, admin: Admin, conn: Db):
        row = conn.get(Report, report_id)
        if not row:
            raise HTTPException(404, "Signalement introuvable")
        row.status = payload.status
        conn.commit()
        return {"ok": True}

    @app.patch("/api/admin/accounts/{user_id}")
    def moderate_account(user_id: str, payload: AccountAction, admin: Admin, conn: Db):
        row = conn.get(User, user_id)
        if not row:
            raise HTTPException(404, "Compte introuvable")
        row.approved = payload.approved
        conn.commit()
        return {"ok": True}

    ctx.is_blocked = is_blocked
    jeudi_layer.install(app, ctx)

    # Mount the existing polished PWA after API routes to keep all endpoints accessible.
    app.mount("/", StaticFiles(directory=str(ROOT / "public"), html=True), name="frontend")
    return app

app = create_app()
