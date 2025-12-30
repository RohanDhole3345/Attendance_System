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
# ---------------------------
class ClassroomLocation(BaseModel):
    latitude: float
    longitude: float
    radius: float   # meters

class StudentLocation(BaseModel):
    student_id: int
    latitude: float
    longitude: float

