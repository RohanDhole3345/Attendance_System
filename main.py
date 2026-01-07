import os
import shutil
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from deepface import DeepFace

# Import your finalized database objects
from database import SessionLocal, engine, Base, Student, AttendanceLog, ClassroomSetting, get_db

# Sync the database
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Pro-Grade Multi-Classroom Attendance")

# Directory Setup
for path in ["uploads/references", "uploads/temp"]:
    os.makedirs(path, exist_ok=True)

# ---------------------------
# TEACHER / ADMIN ENDPOINTS
# ---------------------------

@app.post("/teacher/add-classroom")
def add_classroom(name: str, max_lat: float, min_lat: float, max_lon: float, min_lon: float, db: Session = Depends(get_db)):
    # Create a new classroom entry
    new_room = ClassroomSetting(
        name=name, 
        max_lat=max_lat, 
        min_lat=min_lat, 
        max_lon=max_lon, 
        min_lon=min_lon
    )
    db.add(new_room)
    db.commit()
    return {"message": f"Classroom '{name}' created successfully!"}

# THE FILTERING FEATURE: Get logs for a specific classroom only
@app.get("/teacher/view-attendance/{room_name}")
def view_attendance_by_room(room_name: str, db: Session = Depends(get_db)):
    logs = db.query(AttendanceLog).filter(AttendanceLog.classroom_name == room_name).all()
    return logs

# ---------------------------
# STUDENT ENDPOINTS
# ---------------------------

@app.get("/student/get-classrooms")
def get_classrooms(db: Session = Depends(get_db)):
    # This feeds the dropdown list on the student's phone
    classrooms = db.query(ClassroomSetting).all() # Fetch the full objects
    return classrooms

@app.post("/student/mark-attendance")
async def mark_attendance(
    student_id: str = Form(...), 
    classroom_id: int = Form(...), # ID from the dropdown
    latitude: float = Form(...), 
    longitude: float = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 1. Fetch classroom details
    rect = db.query(ClassroomSetting).filter(ClassroomSetting.id == classroom_id).first()
    if not rect:
        return {"attendance": "Error", "reason": "Classroom not found"}

    # 2. GPS Boundary Check
    if not (rect.min_lat <= latitude <= rect.max_lat and rect.min_lon <= longitude <= rect.max_lon):
        return {"attendance": "Rejected", "reason": f"You are not inside {rect.name}"}

    # 3. 1-Hour Duplicate Check
    last_hour = datetime.now() - timedelta(hours=1)
    if db.query(AttendanceLog).filter(AttendanceLog.student_id == student_id, AttendanceLog.timestamp >= last_hour).first():
        return {"attendance": "Rejected", "reason": "Attendance already marked for this hour"}

    # 4. Face Recognition
    db_student = db.query(Student).filter(Student.id == student_id).first()
    ref_path = f"uploads/references/{student_id}.jpg"

    # --- CASE A: ENROLLMENT ---
    if not db_student:
        with open(ref_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        new_student = Student(id=student_id, name=student_id, reference_image_path=ref_path)
        try:
            db.add(new_student)
            db.commit()
            db.refresh(new_student)
            
            # Save the log with the classroom name!
            new_log = AttendanceLog(student_id=student_id, status="Enrolled", classroom_name=rect.name)
            db.add(new_log)
            db.commit()
            return {"attendance": "Marked", "status": "Enrolled", "classroom": rect.name}
        except Exception as e:
            db.rollback()
            return {"attendance": "Error", "reason": str(e)}

    # --- CASE B: VERIFICATION ---
    else:
        temp_path = f"uploads/temp/{student_id}_temp.jpg"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        try:
            result = DeepFace.verify(img1_path=ref_path, img2_path=temp_path, enforce_detection=False)
            if os.path.exists(temp_path): os.remove(temp_path)

            if result["verified"]:
                # Record present status with classroom name
                new_log = AttendanceLog(student_id=student_id, status="Present", classroom_name=rect.name)
                db.add(new_log)
                db.commit()
                return {"attendance": "Marked", "status": "Present", "classroom": rect.name}
            return {"attendance": "Rejected", "reason": "Face does not match"}
        except Exception as e:
            if os.path.exists(temp_path): os.remove(temp_path)
            return {"attendance": "Error", "reason": "AI Verification failed"}