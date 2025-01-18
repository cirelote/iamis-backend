# main.py
from datetime import datetime
import os
import json
import threading
from typing import Any, Dict, List

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError, Field
import paho.mqtt.client as mqtt
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv
import sqlite3

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./iot_dashboard.db")

# If using a sqlite file, let's parse the file path from DATABASE_URL
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        open(db_path, 'a').close()  # ensure the file exists

    # Enable WAL mode:
    try:
        # open a direct connection using python's sqlite3 to enable WAL
        with sqlite3.connect(db_path) as wal_conn:
            wal_conn.execute("PRAGMA journal_mode=WAL;")
            wal_conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception as e:
        print("Could not enable WAL mode:", e)
        
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensor/data")

# Multi-origin for production readiness:
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# Database setup
Base = declarative_base()
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Models -------------------------------------------------------------------
class SensorData(Base):
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, index=True)
    sensor_type = Column(String, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class SettingsDB(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    temperature_threshold = Column(Integer, default=30)
    humidity_threshold = Column(Integer, default=70)

Base.metadata.create_all(bind=engine)

# --- Pydantic Schemas ---------------------------------------------------------
class SensorDataCreate(BaseModel):
    sensor_type: str
    value: float
    unit: str

class SensorDataResponse(SensorDataCreate):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class SettingsIn(BaseModel):
    temperatureThreshold: int = Field(..., alias="temperatureThreshold")
    humidityThreshold: int = Field(..., alias="humidityThreshold")

class SettingsOut(BaseModel):
    temperatureThreshold: int
    humidityThreshold: int

# For partial updates (PATCH):
class SettingsPatch(BaseModel):
    temperatureThreshold: int | None = Field(None, alias="temperatureThreshold")
    humidityThreshold: int | None = Field(None, alias="humidityThreshold")

# --- Database Dependency ------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- FastAPI App -------------------------------------------------------------
app = FastAPI(title="IoT Dashboard Backend", version="1.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MQTT Setup ---------------------------------------------------------------
mqtt_client = mqtt.Client()
mqtt_client_connected = False

def on_connect(client, userdata, flags, rc):
    global mqtt_client_connected
    mqtt_client_connected = (rc == 0)
    print(f"Connected to MQTT broker with code {rc}")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    print(f"Received message on topic {msg.topic}: {msg.payload.decode()}")
    try:
        payload = json.loads(msg.payload.decode())
        sensor_data = SensorDataCreate(**payload)
        
        # Use a separate short-lived session:
        db = SessionLocal()  # no sharing with the main thread
        db_sensor_data = SensorData(
            sensor_type=sensor_data.sensor_type,
            value=sensor_data.value,
            unit=sensor_data.unit,
        )
        db.add(db_sensor_data)
        db.commit()
        db.close()
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"Error processing message: {e}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

def start_mqtt():
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_forever()

mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
mqtt_thread.start()

# --- Routes -------------------------------------------------------------------
# Health-check: includes MQTT status
@app.get("/health-check/")
def health_check():
    return {
        "status": "Healthy",
        "mqtt_connected": mqtt_client_connected
    }

# Settings
@app.get("/api/settings", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    # We only expect one row for settings, so let's fetch or create a default
    record = db.query(SettingsDB).first()
    if not record:
        record = SettingsDB()
        db.add(record)
        db.commit()
        db.refresh(record)
    return SettingsOut(
        temperatureThreshold=record.temperature_threshold,
        humidityThreshold=record.humidity_threshold
    )

@app.patch("/api/settings", response_model=SettingsOut)
def patch_settings(body: SettingsPatch, db: Session = Depends(get_db)):
    record = db.query(SettingsDB).first()
    if not record:
        record = SettingsDB()
        db.add(record)
        db.commit()
        db.refresh(record)

    # Update only present fields
    if body.temperatureThreshold is not None:
        record.temperature_threshold = body.temperatureThreshold
    if body.humidityThreshold is not None:
        record.humidity_threshold = body.humidityThreshold

    db.commit()
    db.refresh(record)
    return SettingsOut(
        temperatureThreshold=record.temperature_threshold,
        humidityThreshold=record.humidity_threshold
    )

# -----------------------------
# Layout Persistence
# For example, we store in layout.json. Adjust to store in DB if you prefer.
# -----------------------------
LAYOUT_FILE_PATH = "layout.json"

class TileLayout(BaseModel):
    id: str
    title: str
    sensorType: str
    layout: Dict[str, Any]  # {i, x, y, w, h, etc.}
    # data not stored here; we only store config

class DashboardLayout(BaseModel):
    tiles: List[TileLayout]

def load_layout_from_file():
    if not os.path.exists(LAYOUT_FILE_PATH):
        return {"tiles": []}
    with open(LAYOUT_FILE_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data
        except json.JSONDecodeError:
            return {"tiles": []}

def save_layout_to_file(layout_data):
    with open(LAYOUT_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(layout_data, f, indent=2)

@app.get("/api/layout")
def get_layout():
    """ Return the saved dashboard layout from layout.json """
    return load_layout_from_file()

@app.post("/api/layout")
def save_layout(layout: DashboardLayout):
    """ Save the entire dashboard layout """
    layout_dict = layout.dict()
    save_layout_to_file(layout_dict)
    return {"status": "ok", "savedTiles": len(layout_dict["tiles"])}

# Sensor data
@app.post("/sensor-data/", response_model=SensorDataResponse, status_code=201)
def create_sensor_data(sensor_data: SensorDataCreate, db: Session = Depends(get_db)):
    db_sensor_data = SensorData(**sensor_data.dict())
    db.add(db_sensor_data)
    db.commit()
    db.refresh(db_sensor_data)
    return db_sensor_data

@app.get("/sensor-data/{sensor_type}/", response_model=list[SensorDataResponse])
def get_sensor_data(
    sensor_type: str,
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    if page < 1 or limit < 1:
        raise HTTPException(status_code=400, detail="Invalid pagination params.")
    query = db.query(SensorData).filter(SensorData.sensor_type == sensor_type)
    total = query.count()
    data = query.order_by(SensorData.timestamp.desc()) \
                .offset((page - 1) * limit) \
                .limit(limit) \
                .all()
    if not data:
        return []
    return data

# Custom exception handler
@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    return {"detail": exc.detail, "status_code": exc.status_code}
