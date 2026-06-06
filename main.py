from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
import yaml
import os
from typing import Optional
from datetime import date
from zkteco_utils import ZKTecoAttendance

# Define the security scheme for Swagger UI
api_key_header = APIKeyHeader(name="x-auth-header", auto_error=False)

# Add it as a global dependency so Swagger UI knows about it
app = FastAPI(dependencies=[Depends(api_key_header)])

CONFIG_FILE = "config.yaml"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise HTTPException(status_code=404, detail="Configuration file not found")
    
    with open(CONFIG_FILE, "r") as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError:
            raise HTTPException(status_code=500, detail="Error parsing YAML file")

def load_devices():
    config = load_config()
    return config.get("devices", [])

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Bypass auth for OpenAPI docs
    if request.url.path in ["/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)
        
    config = load_config()
    expected_token = config.get("x_auth_header")
    
    # Check if the header matches
    if expected_token and request.headers.get("x-auth-header") != expected_token:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        
    return await call_next(request)

@app.get("/devices")
def get_devices():
    return load_devices()

@app.get("/devices/{device_id}/users")
def get_device_users(device_id: str):
    devices = load_devices()
    device_info = next((d for d in devices if d.get("id") == device_id), None)
    
    if not device_info:
        raise HTTPException(status_code=404, detail="Device not found")
    
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
    device_info = next((d for d in devices if d.get("id") == device_id), None)
    
    if not device_info:
        raise HTTPException(status_code=404, detail="Device not found")
    
    zk = ZKTecoAttendance(ip_address=device_info["ip"], port=device_info.get("port", 4370))
    
    try:
        zk.connect()
        return zk.get_attendance(start_date=start_date, end_date=end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        zk.disconnect()