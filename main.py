from fastapi import FastAPI
from pydantic import BaseModel
import math
from datetime import datetime, timedelta

app = FastAPI(title="Location Based Attendance Backend")

# ---------------------------
# Root API
@app.get("/")
def root():
    return {"message": "Location Based Attendance Backend Running"}

# ---------------------------
# In-memory storage (DB later)
# ---------------------------
classroom_location = {
    "lat": None,
    "lon": None,
    "radius": None
}

attendance_records = []

# ---------------------------
# Request Models
class ClassroomLocation(BaseModel):
    latitude: float
    longitude: float
    radius: float   # meters

class StudentLocation(BaseModel):
    student_id: int
    latitude: float
    longitude: float

# ---------------------------
# Haversine Distance Formula-
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ---------------------------
# Admin API – Set Classroom Location
@app.post("/set-classroom-location")
def set_classroom_location(data: ClassroomLocation):
    classroom_location["lat"] = data.latitude
    classroom_location["lon"] = data.longitude
    classroom_location["radius"] = data.radius

    return {
        "message": "Classroom location set successfully",
        "classroom_location": classroom_location
    }

# ---------------------------
# Student API–Mark Attendance(Once per Hour Only)
@app.post("/mark-attendance")
def mark_attendance(data: StudentLocation):

    if classroom_location["lat"] is None:
        return {"error": "Classroom location not set by admin"}

    # Distance check
    distance = haversine(
        data.latitude,
        data.longitude,
        classroom_location["lat"],
        classroom_location["lon"]
    )

    if distance > classroom_location["radius"]:
        return {
            "attendance": "Rejected",
            "reason": "Outside classroom",
            "distance": round(distance, 2)
        }

    now = datetime.now()

    # One attendance per hr logic
    for record in attendance_records:
        if record["student_id"] == data.student_id:
            if now - record["timestamp"] < timedelta(hours=1):
                return {
                    "attendance": "Rejected",
                    "reason": "Attendance already marked within last hour"
                }

    # Mark attendance
    attendance_records.append({
        "student_id": data.student_id,
        "timestamp": now,
        "status": "Present"
    })

    return {
        "attendance": "Marked",
        "status": "Present",
        "distance": round(distance, 2),
        "time": now.strftime("%Y-%m-%d %H:%M:%S")
    }
