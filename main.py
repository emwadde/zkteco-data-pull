from fastapi import FastAPI, HTTPException, Query
import yaml
import os
from typing import Optional
from datetime import date
from zkteco_utils import ZKTecoAttendance

app = FastAPI()

CONFIG_FILE = "devices.yaml"

def load_devices():
    if not os.path.exists(CONFIG_FILE):
        raise HTTPException(status_code=404, detail="Configuration file not found")
    
    with open(CONFIG_FILE, "r") as file:
        try:
            data = yaml.safe_load(file)
            return data.get("devices", {})
        except yaml.YAMLError:
            raise HTTPException(status_code=500, detail="Error parsing YAML file")

@app.get("/devices")
def get_devices():
    return load_devices()

@app.get("/devices/{device_id}/users")
def get_device_users(device_id: str):
    devices = load_devices()
    print(f"Loaded devices: {devices}")
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device_info = devices[device_id]
    zk = ZKTecoAttendance(ip_address=device_info["ip"], port=device_info.get("port", 4370))
    
    try:
        zk.connect()
        return zk.get_users()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        zk.disconnect()

@app.get("/devices/{device_id}/attendance")
def get_device_attendance(
    device_id: str, 
    start_date: Optional[date] = Query(None, description="Start date in YYYY-MM-DD format"), 
    end_date: Optional[date] = Query(None, description="End date in YYYY-MM-DD format")
):
    devices = load_devices()
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device_info = devices[device_id]
    zk = ZKTecoAttendance(ip_address=device_info["ip"], port=device_info.get("port", 4370))
    
    try:
        zk.connect()
        # The utility class handles datetime/date conversions automatically
        return zk.get_attendance(start_date=start_date, end_date=end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        zk.disconnect()

# Run using: uvicorn main:app --reload