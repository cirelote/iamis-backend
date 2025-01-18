from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime
import os
from dotenv import load_dotenv
import threading
import paho.mqtt.client as mqtt

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./iamis-db.db")
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime
import os
from dotenv import load_dotenv
import threading
import paho.mqtt.client as mqtt

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./iot_dashboard.db")
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensor/data")

# Database setup
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Define database models
class SensorData(Base):
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, index=True)
    sensor_type = Column(String, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Create database tables
Base.metadata.create_all(bind=engine)

# Pydantic models
class SensorDataCreate(BaseModel):
    sensor_type: str
    value: float
    unit: str

class SensorDataResponse(SensorDataCreate):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize FastAPI app
app = FastAPI(title="IoT Dashboard Backend", version="1.0.0")


app.add_middleware(
    CORSMiddleware,
    # Frontend origin
    allow_origins=os.getenv("FRONTEND_URL", "http://localhost:3000"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Settings API
class Settings(BaseModel):
    temperatureThreshold: int
    humidityThreshold: int

@app.post("/api/settings")
async def update_settings(settings: Settings):
    try:
        # Save settings to a database or a file
        return {"message": "Settings updated successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update settings.")


# Sensor data API
@app.post("/sensor-data/", response_model=SensorDataResponse, status_code=201)
def create_sensor_data(sensor_data: SensorDataCreate, db: Session = Depends(get_db)):
    db_sensor_data = SensorData(**sensor_data.dict())
    db.add(db_sensor_data)
    db.commit()
    db.refresh(db_sensor_data)
    return db_sensor_data

@app.get("/sensor-data/{sensor_type}/", response_model=list[SensorDataResponse])
def get_sensor_data(sensor_type: str, db: Session = Depends(get_db)):
    data = db.query(SensorData).filter(SensorData.sensor_type == sensor_type).all()
    if not data:
        raise HTTPException(status_code=404, detail="Sensor data not found")
    return data

@app.get("/health-check/", status_code=200)
def health_check():
    return {"status": "Healthy"}

# Custom exception handler
@app.exception_handler(HTTPException)
def http_exception_handler(request, exc: HTTPException):
    return {"detail": exc.detail, "status_code": exc.status_code}

# MQTT client setup
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    client.subscribe(MQTT_TOPIC)


def on_message(client, userdata, msg):
    print(f"Received message on topic {msg.topic}: {msg.payload.decode()}")
    try:
        # Parse the message
        payload = eval(msg.payload.decode())  # Ensure the payload is sanitized in production
        sensor_data = SensorDataCreate(**payload)

        # Save to database
        db = SessionLocal()
        db_sensor_data = SensorData(**sensor_data.dict())
        db.add(db_sensor_data)
        db.commit()
        db.close()
    except Exception as e:
        print(f"Error processing message: {e}")

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Start MQTT client in a separate thread
def start_mqtt():
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_forever()

mqtt_thread = threading.Thread(target=start_mqtt)
mqtt_thread.daemon = True
mqtt_thread.start()

# Run FastAPI
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
