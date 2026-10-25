import hashlib, os, binascii
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from pymongo import ReturnDocument

from ..database import db, users
from ..gamification.engine import BASE_AVATARS, GamificationEngine
from ..models.user import LoginRequest, RegisterRequest, UpdateProfileRequest

# The project covers Grade 6 only. The grade field is kept on every user and
# lesson so another grade can be added later without a schema change.
GRADES = [6]
LANGUAGES = ["en", "te", "hi"]

router = APIRouter(prefix="/auth", tags=["Authentication"])

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return binascii.hexlify(salt).decode() + ":" + binascii.hexlify(digest).decode()

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":")
        salt = binascii.unhexlify(salt_hex)
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
        return binascii.hexlify(check).decode() == digest_hex
    except Exception:
        return False

def public_user(doc):
    return {"id": str(doc["_id"]), "username": doc["username"], "grade": doc["grade"],
            "language": doc["language"], "avatar": doc.get("avatar"),
            "role": doc.get("role", "student")}

@router.post("/register")
def register(req: RegisterRequest):
    if req.grade not in GRADES:
        raise HTTPException(400, "Only Grade 6 is available")
    if req.language not in LANGUAGES:
        raise HTTPException(400, "Unsupported language")
    if users.find_one({"username": req.username}):
        raise HTTPException(409, "Username already exists")
    doc = {"username": req.username, "password_hash": hash_password(req.password),
           "grade": req.grade, "language": req.language, "points": 0,
           "role": "student",
           "avatar": req.avatar if req.avatar in BASE_AVATARS else None}
    result = users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return {"message":"Registration successful", "user":public_user(doc)}

@router.post("/login")
def login(req: LoginRequest):
    doc = users.find_one({"username": req.username})
    if not doc or not verify_password(req.password, doc["password_hash"]):
        raise HTTPException(401, "Invalid username or password")
    return {"message":"Login successful", "user":public_user(doc)}


@router.patch("/profile/{user_id}")
def update_profile(user_id: str, req: UpdateProfileRequest):
    """
    Change a student's grade or preferred language after registration.

    Both were fixed at sign-up originally, which left a student who picked the
    wrong one with no way to correct it - and, because lessons are filtered by
    language, an empty Lessons page they could not explain.
    """
    changes = {}

    if req.grade is not None:
        if req.grade not in GRADES:
            raise HTTPException(400, "Only Grade 6 is available")
        changes["grade"] = req.grade

    if req.language is not None:
        if req.language not in LANGUAGES:
            raise HTTPException(400, "Unsupported language")
        changes["language"] = req.language

    try:
        object_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(400, "Invalid user id")

    if req.avatar is not None:
        # Reward avatars unlock with levels, so check the student has earned it.
        allowed = GamificationEngine(db).profile(user_id)["avatars"]
        if req.avatar not in allowed:
            raise HTTPException(403, "That avatar has not been unlocked yet")
        changes["avatar"] = req.avatar

    if not changes:
        raise HTTPException(400, "Nothing to update")

    result = users.find_one_and_update(
        {"_id": object_id},
        {"$set": changes},
        return_document=ReturnDocument.AFTER,
    )
    if result is None:
        raise HTTPException(404, "User not found")

    return {"message": "Profile updated", "user": public_user(result)}
