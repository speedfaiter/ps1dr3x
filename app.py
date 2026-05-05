"""Kids' nutrition app — kid view (capture + challenge) and manager gallery."""
import json
import secrets
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, abort, redirect, render_template, request, send_from_directory,
    url_for,
)

import food_vision
from challenges import POWERS, today_power_index
from db import get_conn, init_db

STORAGE_DIR = Path(__file__).parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

with app.app_context():
    init_db()


def _get_kid(kid_id):
    conn = get_conn()
    kid = conn.execute("SELECT * FROM kids WHERE id=?", (kid_id,)).fetchone()
    if not kid:
        abort(404)
    return kid, conn


@app.route("/")
def home():
    conn = get_conn()
    kids = conn.execute("SELECT * FROM kids ORDER BY display_name").fetchall()
    return render_template("home.html", kids=kids)


@app.route("/kid/<kid_id>")
def kid_view(kid_id):
    kid, conn = _get_kid(kid_id)
    today_idx = today_power_index()
    completed = conn.execute(
        "SELECT 1 FROM challenge_completions "
        "WHERE kid_id=? AND day_of_week=? AND completed_on=date('now','localtime')",
        (kid_id, today_idx),
    ).fetchone() is not None
    meals = conn.execute(
        "SELECT * FROM meals WHERE kid_id=? ORDER BY eaten_at DESC LIMIT 10",
        (kid_id,),
    ).fetchall()
    return render_template(
        "kid.html", kid=kid, power=POWERS[today_idx], completed=completed, meals=meals,
    )


@app.route("/kid/<kid_id>/meal", methods=["POST"])
def kid_upload(kid_id):
    kid, conn = _get_kid(kid_id)
    photo = request.files.get("photo")
    if not photo or not photo.filename:
        abort(400, "no photo uploaded")

    ext = Path(photo.filename).suffix.lower() or ".jpg"
    if ext not in ALLOWED_EXTS:
        abort(400, f"unsupported file type: {ext}")

    kid_dir = STORAGE_DIR / kid_id
    kid_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{datetime.utcnow():%Y%m%d_%H%M%S}_{secrets.token_hex(4)}{ext}"
    rel_path = f"{kid_id}/{fname}"
    photo.save(STORAGE_DIR / rel_path)

    try:
        analysis = food_vision.analyze(str(STORAGE_DIR / rel_path))
        ai_error = None
    except Exception as e:
        analysis = {}
        ai_error = f"{type(e).__name__}: {e}"

    cur = conn.execute(
        """INSERT INTO meals(
            kid_id, photo_path, hunger_level, mood_before,
            is_food, dish_name_he, dish_name_en, ingredients_json,
            estimated_grams, traffic_light, energy_stars, confidence, notes, ai_error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            kid_id, rel_path,
            request.form.get("hunger", type=int),
            request.form.get("mood"),
            analysis.get("is_food"),
            analysis.get("dish_name_he"),
            analysis.get("dish_name_en"),
            json.dumps(analysis.get("ingredients", []), ensure_ascii=False)
                if analysis else None,
            analysis.get("estimated_grams"),
            analysis.get("traffic_light"),
            analysis.get("energy_stars"),
            analysis.get("confidence"),
            analysis.get("notes"),
            ai_error,
        ),
    )
    conn.commit()
    return redirect(url_for("kid_meal", kid_id=kid_id, meal_id=cur.lastrowid))


@app.route("/kid/<kid_id>/meal/<int:meal_id>")
def kid_meal(kid_id, meal_id):
    kid, conn = _get_kid(kid_id)
    meal = conn.execute(
        "SELECT * FROM meals WHERE id=? AND kid_id=?", (meal_id, kid_id),
    ).fetchone()
    if not meal:
        abort(404)
    ingredients = json.loads(meal["ingredients_json"]) if meal["ingredients_json"] else []
    return render_template("kid_meal.html", kid=kid, meal=meal, ingredients=ingredients)


@app.route("/kid/<kid_id>/challenge", methods=["POST"])
def mark_challenge(kid_id):
    kid, conn = _get_kid(kid_id)
    try:
        conn.execute(
            "INSERT INTO challenge_completions(kid_id, day_of_week) VALUES(?, ?)",
            (kid_id, today_power_index()),
        )
        conn.commit()
    except Exception:
        pass  # already completed today
    return redirect(url_for("kid_view", kid_id=kid_id))


@app.route("/manager")
def manager_view():
    conn = get_conn()
    kids = conn.execute("SELECT * FROM kids ORDER BY display_name").fetchall()
    meals = conn.execute(
        """SELECT m.*, k.display_name AS kid_name
           FROM meals m JOIN kids k ON m.kid_id = k.id
           ORDER BY m.eaten_at DESC LIMIT 50""",
    ).fetchall()
    return render_template("manager.html", kids=kids, meals=meals)


@app.route("/storage/<path:rel_path>")
def serve_photo(rel_path):
    return send_from_directory(STORAGE_DIR, rel_path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
