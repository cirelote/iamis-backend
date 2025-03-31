# iamis-backend

**iamis-backend** is a robust IoT dashboard backend service built with FastAPI, SQLAlchemy, and MQTT integration. It is designed to collect, store, and expose sensor data from IoT devices in real time while providing a customizable dashboard layout for visualizing the data.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

---

## Overview

The **iamis-backend** project serves as the backend component of an IoT dashboard application. It is responsible for:
- Receiving sensor data via MQTT.
- Storing sensor data in a relational database (SQLite by default).
- Exposing RESTful API endpoints to retrieve sensor data.
- Managing a customizable dashboard layout stored in a local JSON file.

This solution leverages FastAPI for high-performance API development and SQLAlchemy as the ORM for seamless database interactions.

---

## Features

- **Real-Time MQTT Integration:** Subscribes to an MQTT topic to process sensor data as it is published.
- **RESTful API Endpoints:** Provides endpoints for health-check, sensor data CRUD operations, and dashboard layout management.
- **Database Support:** Uses SQLAlchemy to interact with a relational database. SQLite is used by default with support for Write-Ahead Logging (WAL) for improved performance.
- **Configurable Dashboard Layout:** Reads from and writes to a `layout.json` file to manage the front-end dashboard configuration.
- **CORS Middleware:** Supports multiple origins, making it easy to integrate with front-end applications hosted on different domains.
- **Threaded MQTT Client:** Runs the MQTT client in a separate daemon thread ensuring non-blocking API operations.
- **Custom Exception Handling:** Implements custom error responses for better API reliability.

---

## Prerequisites

- **Python 3.8+**  
- **pip** – Python package installer

**Required Python Packages:**

- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `paho-mqtt`
- `python-dotenv`
- `pydantic`

Install the required packages using pip:

```bash
pip install -r requirements.txt
```

---

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/cirelote/iamis-backend.git
   cd iamis-backend
   ```

2. **Create a Virtual Environment (Optional but Recommended):**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**

   Create a `.env` file in the project root and define the necessary environment variables (see [Configuration](#configuration) below).

5. **Initialize the Database:**

   The application will automatically create the SQLite database file (if it does not exist) and set up the necessary tables on the first run.

---

## Configuration

The application uses environment variables for configuration. Create a `.env` file in the project root with entries similar to the following:

```dotenv
# Database configuration
DATABASE_URL=sqlite:///./iot_dashboard.db

# MQTT Broker configuration
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_TOPIC=sensor/data

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:3000
```

**Environment Variables:**

- **DATABASE_URL:**  
  The URL for the database connection. The default is set to a local SQLite file (`iot_dashboard.db`). For other databases (e.g., PostgreSQL), update the URL accordingly.

- **MQTT_BROKER:**  
  The hostname or IP address of the MQTT broker.

- **MQTT_PORT:**  
  The port on which the MQTT broker is running (default is `1883`).

- **MQTT_TOPIC:**  
  The topic to subscribe to for sensor data (default is `sensor/data`).

- **ALLOWED_ORIGINS:**  
  A comma-separated list of origins that are permitted to access the API (default is `http://localhost:3000`).

---

## Running the Application

1. **Start the Backend Server:**

   You can run the application using guvicorn. From the project root, execute:

   ```bash
   gunicorn src.main:app -c gunicorn_conf.py
   ```

2. **MQTT Client:**

   The MQTT client is initialized in a separate daemon thread as soon as the application starts. It will attempt to connect to the MQTT broker and subscribe to the specified topic. Sensor data messages received via MQTT will be automatically stored in the database.

---

## API Endpoints

### Health Check

- **Endpoint:** `GET /health-check/`
- **Description:** Returns the health status of the API and the connection status of the MQTT client.
- **Response Example:**

  ```json
  {
    "status": "Healthy",
    "mqtt_connected": true
  }
  ```

### Sensor Data

#### Create Sensor Data

- **Endpoint:** `POST /sensor-data/`
- **Description:** Insert a new sensor data record into the database.
- **Request Body Example:**

  ```json
  {
    "sensor_type": "temperature",
    "value": 22.5,
    "unit": "°C"
  }
  ```

- **Response Example:**

  ```json
  {
    "id": 1,
    "sensor_type": "temperature",
    "value": 22.5,
    "unit": "°C",
    "timestamp": "2025-03-31T12:34:56.789Z"
  }
  ```

#### Retrieve Sensor Data

- **Endpoint:** `GET /sensor-data/{sensor_type}/`
- **Description:** Retrieve sensor data for a given sensor type with pagination.
- **Query Parameters:**
  - `page`: Page number (default is 1)
  - `limit`: Number of records per page (default is 20)
- **Response Example:**

  ```json
  [
    {
      "id": 1,
      "sensor_type": "temperature",
      "value": 22.5,
      "unit": "°C",
      "timestamp": "2025-03-31T12:34:56.789Z"
    },
    ...
  ]
  ```

### Dashboard Layout

#### Get Dashboard Layout

- **Endpoint:** `GET /api/layout`
- **Description:** Retrieves the current dashboard layout configuration stored in `layout.json`.
- **Response Example:**

  ```json
  {
    "tiles": [
      {
        "id": "tile-1",
        "title": "Temperature Sensor",
        "sensorType": "temperature",
        "layout": { "i": "tile-1", "x": 0, "y": 0, "w": 4, "h": 3 }
      }
    ]
  }
  ```

#### Save Dashboard Layout

- **Endpoint:** `POST /api/layout`
- **Description:** Saves a new dashboard layout configuration.
- **Request Body Example:**

  ```json
  {
    "tiles": [
      {
        "id": "tile-1",
        "title": "Temperature Sensor",
        "sensorType": "temperature",
        "layout": { "i": "tile-1", "x": 0, "y": 0, "w": 4, "h": 3 }
      }
    ]
  }
  ```

- **Response Example:**

  ```json
  {
    "status": "ok",
    "savedTiles": 1
  }
  ```

---

## Project Structure

```
iamis-backend/
├── src/
│   └── main.py
├── .gitignore
├── LICENSE
├── README.md
└── gunicorn_conf.py
```

- **main.py:**  
  Contains the core logic for initializing the FastAPI app, setting up the MQTT client, handling database operations, and defining the API endpoints.

- **layout.json:**  
  Stores the dashboard layout. The application reads from and writes to this file via API endpoints.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Contact

For questions or feedback, please contact:

- **Project Maintainer:** [Bohdan Lutsenko](mailto:bohdan.lutsen.co@gmail.com)
- **GitHub:** [cirelote](https://github.com/cirelote)
