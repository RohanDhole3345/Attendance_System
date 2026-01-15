import os
import shutil
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from deepface import DeepFace
from fastapi.responses import FileResponse

# Import your database objects 
from database import SessionLocal, engine, Base, Student, AttendanceLog, ClassroomSetting, Admin, get_db

# Initialize FastAPI
app = FastAPI(title="AI Powered Attendance System📍🤳")

# >>---------- CORS SECURITY BRIDGE ----------<<
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# >>---------- PAGE ROUTING ----------<<

@app.get("/")
@app.get("/login")
@app.get("/login.html")
def get_login():
    return FileResponse("login.html")

@app.get("/admin")
def get_admin_page():
    return FileResponse("admin.html")

@app.get("/student")
def get_student_page():
    return FileResponse("student.html")

# Sync the database
Base.metadata.create_all(bind=engine)

# Directory Setup
for path in ["uploads/references", "uploads/temp"]:
    os.makedirs(path, exist_ok=True)

# Helper Function
def throw_auth_error():
    raise HTTPException(status_code=401, detail="Invalid credentials")

# >>---------- AUTHENTICATION ENDPOINTS ----------<<

@app.post("/login/student")
def login_student(student_id: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(Student).filter(Student.id == student_id).first()
    
    # Auto-Enroll Logic: If student doesn't exist, create them
    if not user:
        new_student = Student(
            id=student_id, 
            name=student_id, 
            password=password, 
            reference_image_path=f"uploads/references/{student_id}.jpg"
        )
        db.add(new_student)
        db.commit()
        return {"message": "Success", "role": "student", "name": student_id, "status": "New Student Created"}
    
    if user.password != password:
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
    master_key: str = Form(...), 
    db: Session = Depends(get_db)
):
    # As per your requirement: "Reset123" or "R2026"
    if master_key not in ["R2026", "Reset123"]:
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid Master Key")

    if db.query(Admin).filter(Admin.username == username).first():
        return {"message": "Error", "reason": "Username already exists"}

    new_admin = Admin(username=username, password=password)
    db.add(new_admin)
    db.commit()
    return {"message": "Admin registered successfully"}

# >>---------- FORGOT PASSWORD LOGIC ----------<<

@app.post("/student/forgot-password")
def student_forgot_password(student_id: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(Student).filter(Student.id == student_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student ID not found")
    user.password = student_id 
    db.commit()
    return {"message": "Success", "new_password": student_id}

@app.post("/teacher/forgot-password")
def teacher_forgot_password(
    username: str = Form(...), 
    secret_key: str = Form(...), 
    new_password: str = Form(...), 
    db: Session = Depends(get_db)
):
    if secret_key != "Reset123":
        raise HTTPException(status_code=403, detail="Invalid Secret Key")
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    admin.password = new_password
    db.commit()
    return {"message": "Success"}

# >>---------- TEACHER / ADMIN ENDPOINTS ----------<<

@app.post("/teacher/add-classroom")
def add_classroom(name: str, min_lat: float, max_lat: float, min_lon: float, max_lon: float, db: Session = Depends(get_db)):
    new_room = ClassroomSetting(name=name, min_lat=min_lat, max_lat=max_lat, min_lon=min_lon, max_lon=max_lon)
    db.add(new_room)
    db.commit()
    return {"message": f"Classroom '{name}' created successfully!"}

@app.get("/teacher/view-attendance/{room_name}")
def view_attendance_by_room(room_name: str, db: Session = Depends(get_db)):
    logs = db.query(AttendanceLog).filter(AttendanceLog.classroom_name == room_name).all()
    formatted_logs = []
    for log in logs:
        formatted_logs.append({
            "student_id": log.student_id,
            "status": log.status,
            "classroom_name": log.classroom_name,
            "timestamp": log.timestamp.strftime("%b-%d-%Y %I:%M %p") 
        })
    return formatted_logs

# >>---------- STUDENT ATTENDANCE LOGIC ----------<<

@app.get("/student/get-classrooms")
def get_classrooms(db: Session = Depends(get_db)):
    return db.query(ClassroomSetting).all()

@app.post("/student/mark-attendance")
async def mark_attendance(
    student_id: str = Form(...), 
    classroom_id: str = Form(...),
    latitude: float = Form(...), 
    longitude: float = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    rect = db.query(ClassroomSetting).filter(ClassroomSetting.id == classroom_id).first()
    if not rect: return {"attendance": "Error", "reason": "Classroom not found"}

    # Geofence Validation
    actual_min_lat, actual_max_lat = sorted([rect.min_lat, rect.max_lat])
    actual_min_lon, actual_max_lon = sorted([rect.min_lon, rect.max_lon])
    BUFFER = 0.00005
    if not ((actual_min_lat - BUFFER) <= latitude <= (actual_max_lat + BUFFER) and 
            (actual_min_lon - BUFFER) <= longitude <= (actual_max_lon + BUFFER)):
        return {"attendance": "Rejected", "reason": f"Outside {rect.name} boundary"}

    # IST Time Handling
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    time_threshold = ist_now - timedelta(hours=1)
    
    duplicate = db.query(AttendanceLog).filter(
        AttendanceLog.student_id == student_id,
        AttendanceLog.timestamp >= time_threshold
    ).first()

    if duplicate:
        return {"attendance": "Rejected", "reason": "Already marked recently"}

    db_student = db.query(Student).filter(Student.id == student_id).first()
    ref_path = f"uploads/references/{student_id}.jpg"

    # ENROLLMENT FIX (Save student first, then log)
    if not db_student:
        with open(ref_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        new_student = Student(id=student_id, name=student_id, password=student_id, reference_image_path=ref_path)
        db.add(new_student)
        db.commit() # Save student to satisfy Foreign Key
        
        db.add(AttendanceLog(student_id=student_id, status="Enrolled", classroom_name=rect.name, timestamp=ist_now))
        db.commit()
        return {"attendance": "Marked", "status": "Enrolled"}

    # AI FACE VERIFICATION
    else:
        temp_path = f"uploads/temp/{student_id}_temp.jpg"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        try:
            result = DeepFace.verify(img1_path=ref_path, img2_path=temp_path, enforce_detection=False)
            if os.path.exists(temp_path): os.remove(temp_path)
            
            if result["verified"]:
                db.add(AttendanceLog(student_id=student_id, status="Present", classroom_name=rect.name, timestamp=ist_now))
                db.commit()
                return {"attendance": "Marked", "status": "Present"}
            return {"attendance": "Rejected", "reason": "Face mismatch"}
        except:
            if os.path.exists(temp_path): os.remove(temp_path)
            return {"attendance": "Error", "reason": "AI Failed"}