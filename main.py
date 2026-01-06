import os
import shutil
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from deepface import DeepFace

# Import your database connection and models
from database import SessionLocal, engine, Base, Student, AttendanceLog, ClassroomSetting, get_db

# Initialize Database Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Pro-Grade Face & GPS Attendance System")

# ---------------------------
# Directory Setup (Windows Robust)
# ---------------------------
REFERENCE_DIR = "uploads/references"
TEMP_DIR = "uploads/temp"

for path in [REFERENCE_DIR, TEMP_DIR]:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

# ---------------------------
# Teacher API
# ---------------------------

@app.post("/teacher/set-rectangle")
def set_rectangle(max_lat: float, min_lat: float, max_lon: float, min_lon: float, db: Session = Depends(get_db)):
    setting = db.query(ClassroomSetting).filter(ClassroomSetting.id == 1).first()
    if not setting:
        setting = ClassroomSetting(id=1)
        db.add(setting)
    
    setting.max_lat = max_lat
    setting.min_lat = min_lat
    setting.max_lon = max_lon
    setting.min_lon = min_lon
    
    db.commit()
    return {"message": "Classroom rectangle saved to Database", "rectangle": [max_lat, min_lat, max_lon, min_lon]}

@app.get("/teacher/view-attendance")
def view_attendance(db: Session = Depends(get_db)):
    return db.query(AttendanceLog).all()

# ---------------------------
# Student API – Mark Attendance
# ---------------------------

@app.post("/student/mark-attendance")
async def mark_attendance(
    student_id: str = Form(...), 
    latitude: float = Form(...), 
    longitude: float = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 1. Fetch Classroom boundaries from DB
    rect = db.query(ClassroomSetting).filter(ClassroomSetting.id == 1).first()
    if not rect or rect.min_lat is None:
        return {"attendance": "Error", "reason": "Classroom rectangle not set by teacher"}

    # 2. GPS Validation
    is_inside = (rect.min_lat <= latitude <= rect.max_lat and 
                 rect.min_lon <= longitude <= rect.max_lon)
    
    if not is_inside:
        return {"attendance": "Rejected", "reason": "Outside classroom boundary"}

    # 3. Check for Duplicate Attendance (Last 1 Hour)
    last_hour = datetime.now() - timedelta(hours=1)
    existing_record = db.query(AttendanceLog).filter(
        AttendanceLog.student_id == student_id,
        AttendanceLog.timestamp >= last_hour
    ).first()

    if existing_record:
        return {"attendance": "Rejected", "reason": "Already marked within the last hour"}

    # 4. Face Recognition Logic
    db_student = db.query(Student).filter(Student.id == student_id).first()
    ref_path = os.path.join(REFERENCE_DIR, f"{student_id}.jpg")

    # --- CASE A: ENROLLMENT (First Time) ---
    if not db_student:
        # 1. Save the file
        with open(ref_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 2. Create the Student record ONLY
        new_student = Student(
            id=student_id, 
            name=student_id, 
            reference_image_path=ref_path
        )
        
        try:
            db.add(new_student)
            db.commit() # <--- COMMIT 1: Save the student first!
            db.refresh(new_student)
            
            # 3. NOW create the log (Foreign Key will now succeed)
            new_log = AttendanceLog(student_id=student_id, status="Present (Enrolled)")
            db.add(new_log)
            db.commit() # <--- COMMIT 2: Save the attendance log
            
            return {"attendance": "Marked", "status": "Enrolled", "message": "Success"}
        except Exception as e:
            db.rollback()
            return {"attendance": "Error", "reason": f"Database Error: {str(e)}"}

    # --- CASE B: VERIFICATION (Returning Student) ---
    else:
        temp_path = os.path.join(TEMP_DIR, f"{student_id}_temp.jpg")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        try:
            result = DeepFace.verify(
                img1_path=str(db_student.reference_image_path), 
                img2_path=temp_path, 
                model_name="VGG-Face",
                enforce_detection=False 
            )
            
            if os.path.exists(temp_path):
                os.remove(temp_path)

            if result["verified"]:
                new_log = AttendanceLog(student_id=student_id, status="Present (Verified)")
                db.add(new_log)
                db.commit()
                return {"attendance": "Marked", "status": "Present", "distance": result["distance"]}
            else:
                return {"attendance": "Rejected", "reason": "Face does not match reference"}

        except Exception as e:
            if os.path.exists(temp_path): os.remove(temp_path)
            print(f"DeepFace Error: {e}")
            return {"attendance": "Error", "reason": "Verification failed. Ensure your face is visible."}