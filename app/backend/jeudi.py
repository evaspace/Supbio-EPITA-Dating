"""Jeudi layer: weekly drop, meeting slots, reliability, profile style, drawings, stats.

Kept in its own module and its own tables so the base (auth, swipes, matches, photos,
moderation) stays untouched. `install(app, ctx)` is called from backend.main.create_app.
"""
import io
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func, or_, select
from sqlalchemy.orm import Mapped, mapped_column

from .main import Base, Match, User, now, uid

PARIS = ZoneInfo("Europe/Paris")
UTC = timezone.utc
INTENTS = ("dating", "amis", "binome")
FONTS = ("dm-sans", "bricolage", "fraunces", "caveat", "baloo", "playfair", "anton")
BLOCKS = ("bio", "interests", "status", "hook")
LAPIN_SUSPENSION_DAYS = 7
CHECKIN_OPENS = timedelta(minutes=60)
CHECKIN_DEADLINE = timedelta(minutes=30)
VALIDATE_FROM = timedelta(minutes=10)
VALIDATE_UNTIL = timedelta(minutes=30)
ELO_K = 32


class UserStyle(Base):
    __tablename__ = "user_styles"
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    intents: Mapped[str] = mapped_column(Text, default="[]")
    promo: Mapped[str] = mapped_column(String(20), default="")
    accent: Mapped[str] = mapped_column(String(7), default="#b8336a")
    ground: Mapped[str] = mapped_column(String(7), default="#fdf2f7")
    font: Mapped[str] = mapped_column(String(20), default="dm-sans")
    emoji: Mapped[str] = mapped_column(String(16), default="")
    status: Mapped[str] = mapped_column(String(80), default="")
    hook: Mapped[str] = mapped_column(String(120), default="")
    highlights: Mapped[str] = mapped_column(Text, default="[]")
    blocks: Mapped[str] = mapped_column(Text, default=json.dumps(list(BLOCKS)))
    drawing_file: Mapped[str | None] = mapped_column(String(60), nullable=True)
    elo: Mapped[float] = mapped_column(Float, default=1000.0)
    meetings: Mapped[int] = mapped_column(Integer, default=0)
    lapins: Mapped[int] = mapped_column(Integer, default=0)
    banned_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    match_id: Mapped[str] = mapped_column(String(32), ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    proposer_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    venue_id: Mapped[str] = mapped_column(String(30), index=True)
    activity: Mapped[str] = mapped_column(String(40))
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(12), default="proposed")  # proposed confirmed cancelled done lapin
    a_checkin: Mapped[bool] = mapped_column(Boolean, default=False)
    b_checkin: Mapped[bool] = mapped_column(Boolean, default=False)
    a_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    b_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    a_again: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    b_again: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    settled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class StyleIn(BaseModel):
    intents: list[Literal["dating", "amis", "binome"]] = Field(min_length=1, max_length=3)
    promo: str = Field(default="", max_length=20)
    accent: str
    ground: str
    font: Literal["dm-sans", "bricolage", "fraunces", "caveat", "baloo", "playfair", "anton"] = "dm-sans"
    emoji: str = Field(default="", max_length=16)
    status: str = Field(default="", max_length=80)
    hook: str = Field(default="", max_length=120)
    highlights: list[str] = Field(default_factory=list, max_length=3)
    blocks: list[Literal["bio", "interests", "status", "hook"]] = Field(default_factory=lambda: list(BLOCKS))

    @field_validator("accent", "ground")
    @classmethod
    def hex_colour(cls, v: str) -> str:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            raise ValueError("Couleur #RRGGBB attendue")
        return v.lower()


class BookingIn(BaseModel):
    match_id: str
    offer_id: str = Field(max_length=80)


class ValidateIn(BaseModel):
    code: str = Field(min_length=3, max_length=12)


class FeedbackIn(BaseModel):
    again: bool


def contrast(a: str, b: str) -> float:
    def lum(h: str) -> float:
        rgb = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def drop_window(at: datetime, force_open: bool = False) -> dict:
    """Thursday window in Paris time. `at` is naive UTC."""
    start_h = int(os.getenv("DROP_START_HOUR", "18"))
    end_h = int(os.getenv("DROP_END_HOUR", "22"))
    local = at.replace(tzinfo=UTC).astimezone(PARIS)
    thursday = local.date() + timedelta(days=(3 - local.weekday()) % 7)
    opens = datetime.combine(thursday, datetime.min.time(), PARIS).replace(hour=start_h)
    closes = opens.replace(hour=end_h)
    if local >= closes:
        opens += timedelta(days=7)
        closes += timedelta(days=7)
    is_open = opens <= local < closes
    return {"open": is_open or force_open, "opens_at": opens.astimezone(UTC).replace(tzinfo=None),
            "closes_at": closes.astimezone(UTC).replace(tzinfo=None), "week": opens.date().isoformat()}


def offer_times(venue: dict, window: dict) -> list[datetime]:
    """Slots of the seven days that follow the drop night, naive UTC."""
    opens = window["opens_at"].replace(tzinfo=UTC).astimezone(PARIS)
    out = []
    for day in range(1, 7):
        d = (opens + timedelta(days=day)).date()
        if d.weekday() not in venue.get("days", [0, 1, 2, 3, 4]):
            continue
        for hhmm in venue["times"]:
            h, m = map(int, hhmm.split(":"))
            out.append(datetime.combine(d, datetime.min.time(), PARIS).replace(hour=h, minute=m).astimezone(UTC).replace(tzinfo=None))
    return out


def iso(d: datetime | None) -> str | None:
    return d.isoformat() + "Z" if d else None


def install(app, ctx):
    AuthUser, Db, Admin, LocalSession = ctx.AuthUser, ctx.Db, ctx.Admin, ctx.LocalSession
    media_dir, production = ctx.media_dir, ctx.production
    force_open = os.getenv("DROP_FORCE_OPEN", "false").lower() == "true"
    if production and force_open:
        raise RuntimeError("DROP_FORCE_OPEN interdit en production")
    stats_min = int(os.getenv("STATS_MIN_GROUP", "10"))
    venues = json.loads((ctx.root / "data" / "venues.json").read_text(encoding="utf-8"))["venues"]
    venue_by_id = {v["id"]: v for v in venues}

    def style_of(conn, user_id: str, create: bool = False) -> UserStyle | None:
        row = conn.get(UserStyle, user_id)
        if row is None and create:
            row = UserStyle(user_id=user_id)
            conn.add(row)
            conn.flush()
        return row

    def public_style(row: UserStyle | None) -> dict:
        if row is None:
            return {"configured": False, "intents": [], "accent": "#b8336a", "ground": "#fdf2f7", "font": "dm-sans",
                    "emoji": "", "status": "", "hook": "", "highlights": [], "blocks": list(BLOCKS), "promo": "", "drawing": None}
        return {"configured": bool(json.loads(row.intents)), "intents": json.loads(row.intents), "promo": row.promo,
                "accent": row.accent, "ground": row.ground, "font": row.font, "emoji": row.emoji, "status": row.status,
                "hook": row.hook, "highlights": json.loads(row.highlights), "blocks": json.loads(row.blocks),
                "drawing": f"/api/drawings/{row.user_id}" if row.drawing_file else None}

    def decorate(conn, data: dict, with_private_photos: bool) -> dict:
        data["style"] = public_style(conn.get(UserStyle, data["id"]))
        if not with_private_photos:
            data["photos"] = []
        return data

    ctx.decorate = decorate
    ctx.style_of = style_of

    def matched(conn, a: str, b: str) -> bool:
        x, y = sorted((a, b))
        return conn.scalar(select(Match.id).where(Match.user_a_id == x, Match.user_b_id == y)) is not None

    def settle(conn):
        """Lazy sweep: auto-cancel missed check-ins, score meetings and no-shows."""
        t = now()
        rows = conn.scalars(select(Booking).where(Booking.settled.is_(False), Booking.status.in_(("proposed", "confirmed")))).all()
        for b in rows:
            if b.status == "proposed" and t >= b.starts_at - CHECKIN_DEADLINE:
                b.status, b.settled = "cancelled", True
            elif b.status == "confirmed" and t < b.starts_at + VALIDATE_UNTIL and not (b.a_checkin and b.b_checkin) and t >= b.starts_at - CHECKIN_DEADLINE:
                b.status, b.settled = "cancelled", True
            elif b.status == "confirmed" and t >= b.starts_at + VALIDATE_UNTIL:
                match = conn.get(Match, b.match_id)
                ua, ub = (match.user_a_id, match.user_b_id) if match else (None, None)
                if b.a_valid and b.b_valid:
                    b.status = "done"
                    for u in (ua, ub):
                        if u:
                            style_of(conn, u, True).meetings += 1
                else:
                    b.status = "lapin" if (b.a_checkin or b.b_checkin) else "cancelled"
                    for flag, u in ((b.a_valid, ua), (b.b_valid, ub)):
                        if u and not flag and b.status == "lapin":
                            s = style_of(conn, u, True)
                            s.lapins += 1
                            if s.lapins % 2 == 0:
                                s.banned_until = t + timedelta(days=LAPIN_SUSPENSION_DAYS)
                b.settled = True
        conn.commit()

    def reliability(s: UserStyle | None):
        if not s or s.meetings + s.lapins == 0:
            return None
        return round(100 * s.meetings / (s.meetings + s.lapins))

    def view_booking(conn, b: Booking, me: str) -> dict:
        match = conn.get(Match, b.match_id)
        mine_is_a = match.user_a_id == me
        other = conn.get(User, match.user_b_id if mine_is_a else match.user_a_id)
        v = venue_by_id.get(b.venue_id, {"name": b.venue_id})
        t = now()
        my_check, their_check = (b.a_checkin, b.b_checkin) if mine_is_a else (b.b_checkin, b.a_checkin)
        my_valid, their_valid = (b.a_valid, b.b_valid) if mine_is_a else (b.b_valid, b.a_valid)
        my_again = b.a_again if mine_is_a else b.b_again
        confirmed = b.status == "confirmed"
        return {
            "id": b.id, "status": b.status, "activity": b.activity, "venue": v["name"], "venue_id": b.venue_id,
            "starts_at": iso(b.starts_at), "proposed_by_me": b.proposer_id == me,
            "other": decorate(conn, ctx.with_photos(conn, ctx.represent(other)), True) if other else None,
            "my_checkin": my_check, "their_checkin": their_check, "my_valid": my_valid, "their_valid": their_valid,
            "can_accept": b.status == "proposed" and b.proposer_id != me,
            "can_checkin": confirmed and not my_check and b.starts_at - CHECKIN_OPENS <= t < b.starts_at - CHECKIN_DEADLINE,
            "can_validate": confirmed and my_check and not my_valid and b.starts_at - VALIDATE_FROM <= t < b.starts_at + VALIDATE_UNTIL,
            "can_feedback": b.status == "done" and my_again is None, "my_again": my_again,
            "checkin_opens_at": iso(b.starts_at - CHECKIN_OPENS), "checkin_deadline": iso(b.starts_at - CHECKIN_DEADLINE),
        }

    @app.get("/api/drop")
    def drop(user: AuthUser, conn: Db):
        w = drop_window(now(), force_open)
        out = {"open": w["open"], "opens_at": iso(w["opens_at"]), "closes_at": iso(w["closes_at"]), "week": w["week"], "server_now": iso(now()), "offers": []}
        s = style_of(conn, user.id)
        out["banned_until"] = iso(s.banned_until) if s and s.banned_until and s.banned_until > now() else None
        if w["open"]:
            taken: dict[tuple, int] = {}
            for b in conn.scalars(select(Booking).where(Booking.status.in_(("proposed", "confirmed")), Booking.starts_at > now())):
                taken[(b.venue_id, b.starts_at)] = taken.get((b.venue_id, b.starts_at), 0) + 1
            for v in venues:
                for start in offer_times(v, w):
                    left = v["capacity"] - taken.get((v["id"], start), 0)
                    out["offers"].append({"id": f"{v['id']}|{start.isoformat()}", "venue": v["name"], "venue_id": v["id"], "activity": v["activity"],
                                          "starts_at": iso(start), "left": left})
            out["offers"].sort(key=lambda o: o["starts_at"])
        return out

    @app.get("/api/bookings")
    def bookings(user: AuthUser, conn: Db):
        settle(conn)
        rows = conn.scalars(select(Booking).join(Match, Match.id == Booking.match_id)
                            .where(or_(Match.user_a_id == user.id, Match.user_b_id == user.id))
                            .order_by(Booking.starts_at.desc()).limit(50)).all()
        s = style_of(conn, user.id)
        return {"bookings": [view_booking(conn, b, user.id) for b in rows],
                "me": {"meetings": s.meetings if s else 0, "lapins": s.lapins if s else 0, "reliability": reliability(s),
                       "banned_until": iso(s.banned_until) if s and s.banned_until and s.banned_until > now() else None}}

    def load_booking(conn, booking_id: str, user_id: str) -> Booking:
        b = conn.get(Booking, booking_id)
        match = conn.get(Match, b.match_id) if b else None
        if not b or not match or user_id not in (match.user_a_id, match.user_b_id):
            raise HTTPException(404, "Créneau introuvable")
        return b

    @app.post("/api/bookings")
    def propose(payload: BookingIn, user: AuthUser, conn: Db):
        settle(conn)
        w = drop_window(now(), force_open)
        if not w["open"]:
            raise HTTPException(409, "Le drop est fermé. Prochaine ouverture le jeudi à 18 h")
        s = style_of(conn, user.id)
        if s and s.banned_until and s.banned_until > now():
            raise HTTPException(403, "Réservation suspendue après deux lapins")
        match = conn.get(Match, payload.match_id)
        if not match or user.id not in (match.user_a_id, match.user_b_id) or ctx.is_blocked(conn, match.user_a_id, match.user_b_id):
            raise HTTPException(404, "Match introuvable")
        try:
            venue_id, when = payload.offer_id.split("|", 1)
            start = datetime.fromisoformat(when)
        except ValueError:
            raise HTTPException(422, "Créneau invalide")
        v = venue_by_id.get(venue_id)
        if not v or start not in offer_times(v, w):
            raise HTTPException(422, "Ce créneau n'est pas proposé cette semaine")
        if conn.scalar(select(Booking.id).where(Booking.match_id == match.id, Booking.status.in_(("proposed", "confirmed")))):
            raise HTTPException(409, "Un créneau est déjà en cours pour ce match")
        used = conn.scalar(select(func.count()).select_from(Booking).where(Booking.venue_id == venue_id, Booking.starts_at == start, Booking.status.in_(("proposed", "confirmed"))))
        if used >= v["capacity"]:
            raise HTTPException(409, "Plus de place sur ce créneau")
        b = Booking(match_id=match.id, proposer_id=user.id, venue_id=venue_id, activity=v["activity"], starts_at=start)
        conn.add(b)
        conn.commit()
        return view_booking(conn, b, user.id)

    @app.post("/api/bookings/{booking_id}/accept")
    def accept(booking_id: str, user: AuthUser, conn: Db):
        settle(conn)
        b = load_booking(conn, booking_id, user.id)
        if b.status != "proposed" or b.proposer_id == user.id:
            raise HTTPException(409, "Rien à accepter")
        s = style_of(conn, user.id)
        if s and s.banned_until and s.banned_until > now():
            raise HTTPException(403, "Réservation suspendue après deux lapins")
        b.status = "confirmed"
        conn.commit()
        return view_booking(conn, b, user.id)

    @app.post("/api/bookings/{booking_id}/cancel")
    def cancel(booking_id: str, user: AuthUser, conn: Db):
        settle(conn)
        b = load_booking(conn, booking_id, user.id)
        if b.status not in ("proposed", "confirmed") or now() >= b.starts_at - CHECKIN_OPENS:
            raise HTTPException(409, "Annulation impossible à moins d'une heure du créneau")
        b.status, b.settled = "cancelled", True
        conn.commit()
        return view_booking(conn, b, user.id)

    def side(conn, b: Booking, user_id: str) -> str:
        return "a" if conn.get(Match, b.match_id).user_a_id == user_id else "b"

    @app.post("/api/bookings/{booking_id}/checkin")
    def checkin(booking_id: str, user: AuthUser, conn: Db):
        settle(conn)
        b = load_booking(conn, booking_id, user.id)
        t = now()
        if b.status != "confirmed" or not (b.starts_at - CHECKIN_OPENS <= t < b.starts_at - CHECKIN_DEADLINE):
            raise HTTPException(409, "Le check-in ouvre une heure avant et ferme 30 minutes avant")
        setattr(b, side(conn, b, user.id) + "_checkin", True)
        conn.commit()
        return view_booking(conn, b, user.id)

    @app.post("/api/bookings/{booking_id}/validate")
    def validate(booking_id: str, payload: ValidateIn, user: AuthUser, conn: Db):
        settle(conn)
        b = load_booking(conn, booking_id, user.id)
        t = now()
        sd = side(conn, b, user.id)
        if b.status != "confirmed" or not getattr(b, sd + "_checkin") or not (b.starts_at - VALIDATE_FROM <= t < b.starts_at + VALIDATE_UNTIL):
            raise HTTPException(409, "Validation possible après le check-in, de 10 minutes avant à 30 minutes après l'heure")
        if payload.code.strip().upper() != venue_by_id[b.venue_id]["code"].upper():
            raise HTTPException(422, "Code du lieu incorrect")
        setattr(b, sd + "_valid", True)
        conn.commit()
        return view_booking(conn, b, user.id)

    @app.post("/api/bookings/{booking_id}/feedback")
    def feedback(booking_id: str, payload: FeedbackIn, user: AuthUser, conn: Db):
        settle(conn)
        b = load_booking(conn, booking_id, user.id)
        if b.status != "done":
            raise HTTPException(409, "Retour possible après une rencontre validée")
        setattr(b, side(conn, b, user.id) + "_again", payload.again)
        conn.commit()
        return view_booking(conn, b, user.id)

    # ---- style and drawing -------------------------------------------------
    @app.get("/api/me/style")
    def get_style(user: AuthUser, conn: Db):
        return public_style(conn.get(UserStyle, user.id))

    @app.put("/api/me/style")
    def put_style(payload: StyleIn, user: AuthUser, conn: Db):
        if contrast(payload.accent, payload.ground) < 3:
            raise HTTPException(422, "Contraste trop faible entre l'accent et le fond")
        if any(not h.strip() or len(h) > 65 for h in payload.highlights):
            raise HTTPException(422, "Intérêt phare invalide")
        own = set(json.loads(user.interests))
        if any(h not in own for h in payload.highlights):
            raise HTTPException(422, "Les intérêts phares doivent faire partie de tes intérêts")
        s = style_of(conn, user.id, True)
        s.intents = json.dumps(list(dict.fromkeys(payload.intents)))
        s.promo, s.accent, s.ground, s.font = payload.promo.strip(), payload.accent, payload.ground, payload.font
        s.emoji, s.status, s.hook = payload.emoji.strip(), payload.status.strip(), payload.hook.strip()
        s.highlights = json.dumps(payload.highlights, ensure_ascii=False)
        s.blocks = json.dumps(list(dict.fromkeys(payload.blocks)))
        conn.commit()
        return public_style(s)

    @app.post("/api/me/drawing")
    async def upload_drawing(user: AuthUser, conn: Db, drawing: UploadFile = File(...)):
        if drawing.content_type not in {"image/png", "image/webp", "image/jpeg"}:
            raise HTTPException(415, "Format autorisé : PNG, WebP ou JPEG")
        raw = await drawing.read(1024 * 1024 + 1)
        if not raw or len(raw) > 1024 * 1024:
            raise HTTPException(413, "Dessin limité à 1 Mo")
        try:
            with Image.open(io.BytesIO(raw)) as src:
                if src.width * src.height > 4_000_000:
                    raise ValueError("Image trop grande")
                rgba = src.convert("RGBA")
                flat = Image.new("RGB", rgba.size, (255, 255, 255))
                flat.paste(rgba, mask=rgba.getchannel("A"))
                flat.thumbnail((640, 640))
                name = "draw_" + uid() + ".webp"
                flat.save(media_dir / name, "WEBP", quality=85, method=5)
        except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError):
            raise HTTPException(422, "Fichier image invalide")
        s = style_of(conn, user.id, True)
        old, s.drawing_file = s.drawing_file, name
        conn.commit()
        if old:
            (media_dir / old).unlink(missing_ok=True)
        return {"drawing": f"/api/drawings/{user.id}"}

    @app.delete("/api/me/drawing")
    def delete_drawing(user: AuthUser, conn: Db):
        s = conn.get(UserStyle, user.id)
        if s and s.drawing_file:
            (media_dir / s.drawing_file).unlink(missing_ok=True)
            s.drawing_file = None
            conn.commit()
        return {"ok": True}

    @app.get("/api/drawings/{user_id}")
    def read_drawing(user_id: str, user: AuthUser, conn: Db):
        s = conn.get(UserStyle, user_id)
        if not s or not s.drawing_file or ctx.is_blocked(conn, user.id, user_id):
            raise HTTPException(404, "Dessin introuvable")
        path = media_dir / s.drawing_file
        if not path.is_file():
            raise HTTPException(404, "Dessin introuvable")
        return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "private, max-age=60"})

    @app.delete("/api/admin/drawings/{user_id}")
    def admin_drawing(user_id: str, admin: Admin, conn: Db):
        s = conn.get(UserStyle, user_id)
        if s and s.drawing_file:
            (media_dir / s.drawing_file).unlink(missing_ok=True)
            s.drawing_file = None
            conn.commit()
        return {"ok": True}

    # ---- stats: aggregates only, hidden under the anonymity threshold ------
    @app.get("/api/stats")
    def stats(user: AuthUser, conn: Db):
        settle(conn)
        people = conn.execute(select(User.school, User.city, func.count()).where(User.approved.is_(True), User.suspended.is_(False)).group_by(User.school, User.city)).all()
        meetings = conn.execute(select(User.school, User.city, func.coalesce(func.sum(UserStyle.meetings), 0), func.coalesce(func.sum(UserStyle.lapins), 0))
                                .join(UserStyle, UserStyle.user_id == User.id).group_by(User.school, User.city)).all()
        by_school: dict[str, dict] = {}
        for school, city, n in people:
            g = by_school.setdefault(school, {"label": school, "members": 0, "meetings": 0, "lapins": 0})
            g["members"] += n
        for school, city, m, l in meetings:
            g = by_school.setdefault(school, {"label": school, "members": 0, "meetings": 0, "lapins": 0})
            g["meetings"] += int(m)
            g["lapins"] += int(l)
        ranking, hidden = [], 0
        for g in by_school.values():
            if g["members"] < stats_min:
                hidden += 1
                continue
            # counted per participant: a validated meeting counts for both people
            ranking.append({"label": g["label"], "members": g["members"], "meetings": g["meetings"],
                            "reliability": round(100 * g["meetings"] / (g["meetings"] + g["lapins"])) if g["meetings"] + g["lapins"] else None})
        ranking.sort(key=lambda r: (-r["meetings"], r["label"]))
        s = conn.get(UserStyle, user.id)
        return {"threshold": stats_min, "ranking": ranking, "hidden_groups": hidden,
                "me": {"meetings": s.meetings if s else 0, "lapins": s.lapins if s else 0, "reliability": reliability(s)}}

    @app.get("/api/venues")
    def list_venues(user: AuthUser):
        return {"venues": [{k: v[k] for k in ("id", "name", "activity")} for v in venues]}


def on_swipe(conn, actor: User, target: User, action: str):
    """Elo: a like received is a win against the swiper, a pass a loss. Internal only."""
    a = conn.get(UserStyle, actor.id) or UserStyle(user_id=actor.id)
    t = conn.get(UserStyle, target.id) or UserStyle(user_id=target.id)
    for s in (a, t):
        if s.elo is None:
            s.elo = 1000.0
        conn.add(s)
    expected = 1 / (1 + 10 ** ((a.elo - t.elo) / 400))
    score = 1.0 if action == "like" else 0.0
    t.elo += ELO_K * (score - (1 - expected))
    a.elo += ELO_K * ((1 - score) - expected) * 0.25


def intents_of(conn, user_id: str) -> set:
    row = conn.get(UserStyle, user_id)
    got = set(json.loads(row.intents)) if row else set()
    return got or {"dating"}


def elo_of(conn, user_id: str) -> float:
    row = conn.get(UserStyle, user_id)
    return row.elo if row and row.elo is not None else 1000.0
