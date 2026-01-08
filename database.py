from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

# Database Connection (Ensure your password and DB name match your MySQL setup)
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:Rohan%402004@localhost/attendance_system"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Database Models ---

class Student(Base):
    __tablename__ = "students"
    # student_id will act as the "Roll No"
    id = Column(String(50), primary_key=True, index=True) 
    name = Column(String(100))
    # This will store the password (initially set to the Roll No)
    password = Column(String(100)) 
    reference_image_path = Column(String(255))

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(50), ForeignKey("students.id")) 
    status = Column(String(50))
    # Stores the classroom name (e.g., 'math01') for the teacher's dashboard filter
    classroom_name = Column(String(100)) 
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class ClassroomSetting(Base):
    __tablename__ = "classroom_settings"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False) 
    max_lat = Column(Float)
    min_lat = Column(Float)
    max_lon = Column(Float)
    min_lon = Column(Float)

class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True)
    password = Column(String(100))

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()