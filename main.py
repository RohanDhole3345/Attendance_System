import os
import shutil
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from deepface import DeepFace

# Import your finalized database objects
from database import SessionLocal, engine, Base, Student, AttendanceLog, ClassroomSetting, Admin, get_db

# Sync the database
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Powered Attendance With Loaction Validation📍& Selfi Verification🤳 ")

# Directory Setup
for path in ["uploads/references", "uploads/temp"]:
    os.makedirs(path, exist_ok=True)

# >>----------AUTHENTICATION ENDPOINTS----------<<

@app.post("/login/student")
def login_student(student_id: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(Student).filter(Student.id == student_id).first()
    if not user or user.password != password:
        throw_auth_error()
    return {"message": "Success", "role": "student", "name": user.name}

@app.post("/login/teacher")
def login_teacher(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin or admin.password != password:
        throw_auth_error()
    return {"message": "Success", "role": "teacher"}

@app.post("/teacher/register")
def register_teacher(
    username: str = Form(...), 
    password: str = Form(...), 
    master_key: str = Form(...), # NEW: Master Key required
    db: Session = Depends(get_db)
):
    # BOOM: Updated security key
    IF_MASTER_KEY_RIGHT = "SECRET_CODE_2026" 
    
    if master_key != IF_MASTER_KEY_RIGHT:
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid Master Key")

    # Check if admin already exists
    if db.query(Admin).filter(Admin.username == username).first():
        return {"message": "Error", "reason": "Username already exists"}

    new_admin = Admin(username=username, password=password)
    db.add(new_admin)
    db.commit()
    return {"message": "Admin registered successfully"}

# >>----------FORGOT PASSWORD ENDPOINTS----------<<

@app.post("/student/forgot-password")
def student_forgot_password(student_id: str = Form(...), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return {"message": "Error", "reason": "Roll No not found"}
    # Reset password back to Roll No
    student.password = student_id 
    db.commit()
    return {"message": "Success", "detail": "Password reset to Roll No"}

@app.post("/teacher/forgot-password")
def teacher_forgot_password(username: str = Form(...), recovery_key: str = Form(...), new_password: str = Form(...), db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == username).first()
    # Using BOOM123 as the recovery key for teachers
    if recovery_key == "BOOM123" and admin:
        admin.password = new_password
        db.commit()
        return {"message": "Success"}
    return {"message": "Error", "reason": "Invalid key or username"}


# >>----------TEACHER / ADMIN ENDPOINTS----------<<

@app.post("/teacher/add-classroom")
def add_classroom(name: str, max_lat: float, min_lat: float, max_lon: float, min_lon: float, db: Session = Depends(get_db)):
    new_room = ClassroomSetting(
        name=name, max_lat=max_lat, min_lat=min_lat, max_lon=max_lon, min_lon=min_lon
    )
    db.add(new_room)
    db.commit()
    return {"message": f"Classroom '{name}' created successfully!"}

@app.get("/teacher/view-attendance/{room_name}")
def view_attendance_by_room(room_name: str, db: Session = Depends(get_db)):
    logs = db.query(AttendanceLog).filter(AttendanceLog.classroom_name == room_name).all()
    return logs

# >>----------STUDENT ENDPOINTS----------<<

@app.get("/student/get-classrooms")
def get_classrooms(db: Session = Depends(get_db)):
    classrooms = db.query(ClassroomSetting).all()
    return classrooms

@app.post("/student/mark-attendance")
async def mark_attendance(
    student_id: str = Form(...), 
    classroom_id: int = Form(...),
    latitude: float = Form(...), 
    longitude: float = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    rect = db.query(ClassroomSetting).filter(ClassroomSetting.id == classroom_id).first()
    if not rect: return {"attendance": "Error", "reason": "Classroom not found"}

    if not (rect.min_lat <= latitude <= rect.max_lat and rect.min_lon <= longitude <= rect.max_lon):
        return {"attendance": "Rejected", "reason": f"You are not inside {rect.name}"}

    last_hour = datetime.now() - timedelta(hours=1)
    if db.query(AttendanceLog).filter(AttendanceLog.student_id == student_id, AttendanceLog.timestamp >= last_hour).first():
        return {"attendance": "Rejected", "reason": "Attendance already marked for this hour"}

    db_student = db.query(Student).filter(Student.id == student_id).first()
    ref_path = f"uploads/references/{student_id}.jpg"

    # --- CASE A: ENROLLMENT ---
    if not db_student:
        with open(ref_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Setting password equal to student_id
        new_student = Student(id=student_id, name=student_id, password=student_id, reference_image_path=ref_path)
        try:
            db.add(new_student)
            db.commit()
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
                new_log = AttendanceLog(student_id=student_id, status="Present", classroom_name=rect.name)
                db.add(new_log)
                db.commit()
                return {"attendance": "Marked", "status": "Present", "classroom": rect.name}
            return {"attendance": "Rejected", "reason": "Face does not match"}
        except Exception as e:
            if os.path.exists(temp_path): os.remove(temp_path)
            return {"attendance": "Error", "reason": "AI Verification failed"}

def throw_auth_error():
    raise HTTPException(status_code=401, detail="Invalid credentials")