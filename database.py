from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, ForeignKey # Added ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

# Database Connection
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:Rohan%402004@localhost/attendance_system"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Database Models ---

class Student(Base):
    __tablename__ = "students"
    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100))
    reference_image_path = Column(String(255))

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    id = Column(Integer, primary_key=True, index=True)
    # This now works because ForeignKey is imported
    student_id = Column(String(50), ForeignKey("students.id")) 
    status = Column(String(50))
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

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()