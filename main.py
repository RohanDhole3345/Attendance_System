from fastapi import FastAPI
from pydantic import BaseModel
import math
from datetime import datetime, timedelta

app = FastAPI(title="Location Based Attendance Backend")

# Root API

@app.get("/")
def root():
    return {"message": "Location Based Attendance Backend Running"}

# DB later

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
    longitude: float #capicitor

# ---------------------------
# Haversine Distance Formula

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  #Earth radius in meters

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