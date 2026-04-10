# Project AURA - Advanced FastAPI Backend
# INCLUDES FULL LOGIN & REGISTRATION, Daily Check-ins, and Weekly Plan Generator

import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict
import uvicorn
import os
import time
from passlib.context import CryptContext

# --- DATABASE SETUP ---
DB_FILE = "aura_wellness.db"

def init_db():
    if not os.path.exists(DB_FILE):
        print(f"Database not found. Initializing from 'database.sql'...")
        time.sleep(1)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        with open("database.sql", "r") as f:
            cursor.executescript(f.read())
        conn.commit()
        conn.close()
        print("Database initialized successfully.")

# --- SECURITY ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Pydantic Models ---
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

# NEW: Model for the login form
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class DailyCheckIn(BaseModel):
    physical_score: int; nutritional_score: int; mental_score: int; intellectual_score: int;
    social_score: int; habitual_score: int; financial_score: int; environmental_score: int
    notes: Optional[str] = None

class WeeklyPlan(BaseModel):
    title: str
    focus_area: str
    plan: Dict[str, List[str]]

class DashboardData(BaseModel):
    username: str
    checkin_history: List[dict]
    weekly_plan: WeeklyPlan

# --- AI Plan Generation Logic (remains the same) ---
def generate_weekly_plan(latest_checkin: dict) -> WeeklyPlan:
    if not latest_checkin:
        return WeeklyPlan(title="Your First Week!", focus_area="Foundation", plan={"Monday": ["Complete your first check-in!"], "Tuesday": [], "Wednesday": [], "Thursday": [], "Friday": [], "Saturday": [], "Sunday": []})
    scores = {key: latest_checkin[key] for key in latest_checkin if key.endswith('_score')}
    focus_key = min(scores, key=scores.get)
    focus_area = focus_key.replace('_score', '').capitalize()
    plans = {
        "Physical": {"title": "1-Week Physical Wellness Kickstart", "plan": {"Monday": ["30 min brisk walk"], "Tuesday": ["15 min stretching"], "Wednesday": ["Rest"], "Thursday": ["30 min brisk walk"], "Friday": ["15 min bodyweight exercises"], "Saturday": ["Active recovery"], "Sunday": ["Rest"]}},
        "Nutritional": {"title": "1-Week Mindful Eating Challenge", "plan": {"Monday": ["Drink 8 glasses of water"], "Tuesday": ["Add a vegetable to every meal"], "Wednesday": ["Plan tomorrow's meals"], "Thursday": ["Drink 8 glasses of water"], "Friday": ["Try a new healthy recipe"], "Saturday": ["Avoid sugary drinks"], "Sunday": ["Eat without screen time"]}},
        "Mental": {"title": "1-Week Mental Clarity Plan", "plan": {"Monday": ["5 min guided meditation"], "Tuesday": ["Journal for 10 mins"], "Wednesday": ["Practice deep breathing"], "Thursday": ["Listen to calming music"], "Friday": ["Walk without your phone"], "Saturday": ["Connect with a friend"], "Sunday": ["Plan the week ahead"]}}
    }
    selected_plan = plans.get(focus_area, plans["Mental"])
    return WeeklyPlan(title=selected_plan["title"], focus_area=focus_area, plan=selected_plan["plan"])

# --- FastAPI Application ---
app = FastAPI(title="Project AURA API", version="5.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup_event():
    init_db()

# --- API ENDPOINTS ---

# NEW: Fully functional registration endpoint
@app.post("/api/v4/register")
async def register_user(user: UserCreate):
    hashed_password = pwd_context.hash(user.password)
    user_id = f"user-{user.username.lower().replace(' ', '')}-{str(int(time.time()))[-4:]}"
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (id, username, email, password_hash) VALUES (?, ?, ?, ?)",
                       (user_id, user.username, user.email, hashed_password))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Email is already registered.")
    finally:
        conn.close()
    return {"message": "User created successfully!", "user_id": user_id, "username": user.username}

# NEW: Fully functional login endpoint
@app.post("/api/v4/login")
async def login_user(form_data: UserLogin):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (form_data.email,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="Incorrect email or password.")

    if not pwd_context.verify(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password.")
        
    return {"message": "Login successful!", "user_id": user["id"], "username": user["username"]}


@app.post("/api/v4/checkin/{user_id}")
async def submit_daily_checkin(user_id: str, checkin_data: DailyCheckIn):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO daily_checkins (user_id, checkin_date, physical_score, nutritional_score, mental_score, intellectual_score, social_score, habitual_score, financial_score, environmental_score, notes)
            VALUES (?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, checkin_data.physical_score, checkin_data.nutritional_score, checkin_data.mental_score, checkin_data.intellectual_score,
              checkin_data.social_score, checkin_data.habitual_score, checkin_data.financial_score, checkin_data.environmental_score, checkin_data.notes))
        conn.commit()
    finally:
        conn.close()
    return {"message": "Daily check-in saved successfully."}

@app.get("/api/v4/dashboard/{user_id}", response_model=DashboardData)
async def get_dashboard_data(user_id: str):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if not user: raise HTTPException(status_code=404, detail="User not found")

        cursor.execute("SELECT * FROM daily_checkins WHERE user_id = ? ORDER BY checkin_date ASC", (user_id,))
        checkins = [dict(row) for row in cursor.fetchall()]
        
        latest_checkin = checkins[-1] if checkins else None
        weekly_plan = generate_weekly_plan(latest_checkin)

        return DashboardData(username=user["username"], checkin_history=checkins, weekly_plan=weekly_plan)
    finally:
        conn.close()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
