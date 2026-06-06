from fastapi import FastAPI, HTTPException, Query, Request, Depends, Form, Response
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.security import APIKeyHeader
import yaml
import os
from typing import Optional
from datetime import date
from pydantic import BaseModel
from zkteco_utils import ZKTecoAttendance

api_key_header = APIKeyHeader(name="x-auth-token", auto_error=False)
app = FastAPI(dependencies=[Depends(api_key_header)])

CONFIG_FILE = "config.yaml"

class SetUserRequest(BaseModel):
    uid: int
    user_id: str = "2"
    name: str
    privilege: int = 0
    password: str = ""
    group_id: str = ""
    card: int = 0

def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise HTTPException(status_code=404, detail="Configuration file not found")
    with open(CONFIG_FILE, "r") as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError:
            raise HTTPException(status_code=500, detail="Error parsing YAML file")

def load_devices():
    return load_config().get("devices", [])

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path in ["/docs", "/openapi.json", "/redoc", "/ui/login"]:
        return await call_next(request)
        
    config = load_config()
    expected_token = config.get("x_auth_token")
    
    if expected_token:
        provided_token = request.headers.get("x-auth-token") or request.cookies.get("x-auth-token")
        if provided_token != expected_token:
            if request.url.path.startswith("/ui/"):
                return RedirectResponse(url="/ui/login", status_code=302)
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            
    return await call_next(request)

@app.get("/ui/login", response_class=HTMLResponse, include_in_schema=False)
def login_page():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="bg-gray-100 flex items-center justify-center h-screen px-4">
        <form method="post" action="/ui/login" class="bg-white p-6 sm:p-8 rounded-lg shadow-md w-full max-w-sm border border-gray-200">
            <h2 class="text-2xl font-bold mb-6 text-gray-800 text-center">API Login</h2>
            <input type="password" name="token" placeholder="Enter x-auth-token" required 
                   class="w-full px-4 py-2 border rounded-md mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"/>
            <button type="submit" class="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700 transition">Login</button>
        </form>
    </body>
    </html>
    """

@app.post("/ui/login", include_in_schema=False)
def login_submit(response: Response, token: str = Form(...)):
    config = load_config()
    expected_token = config.get("x_auth_token")
    
    if token == expected_token:
        res = RedirectResponse(url="/ui/devices", status_code=302)
        res.set_cookie(key="x-auth-token", value=token, httponly=True, samesite="lax", max_age=86400)
        return res
        
    return HTMLResponse("Invalid token. <a href='/ui/login' class='text-blue-500 underline'>Try again</a>", status_code=401)

@app.get("/ui/devices", response_class=HTMLResponse, include_in_schema=False)
def devices_page():
    devices = load_devices()
    rows = ""
    for d in devices:
        rows += f"""
        <tr class="border-b border-gray-200 hover:bg-gray-50">
            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{d.get('id')}</td>
            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{d.get('name')}</td>
            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{d.get('ip')}</td>
            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{d.get('port', 4370)}</td>
            <td class="px-4 py-3 whitespace-nowrap text-sm font-medium">
                <a href="/ui/devices/{d.get('id')}/users" class="text-blue-600 hover:text-blue-900 mr-3">Users</a>
                <a href="/ui/devices/{d.get('id')}/logs" class="text-blue-600 hover:text-blue-900">Logs</a>
            </td>
        </tr>
        """
        
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Devices</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="bg-gray-50 p-4 sm:p-8">
        <div class="max-w-5xl mx-auto">
            <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
                <h1 class="text-2xl sm:text-3xl font-bold text-gray-800">Connected Devices</h1>
                <a href="/docs" class="bg-gray-800 text-white px-4 py-2 rounded shadow hover:bg-gray-700 text-sm sm:text-base whitespace-nowrap">Swagger API</a>
            </div>
            <div class="bg-white shadow-md rounded-lg overflow-x-auto border border-gray-200">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP Address</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Port</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        {rows}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/ui/devices/{device_id}/users", response_class=HTMLResponse, include_in_schema=False)
def device_users_page(device_id: str):
    devices = load_devices()
    device_info = next((d for d in devices if d.get("id") == device_id), None)
    
    if not device_info:
        return HTMLResponse("<div style='padding:2rem'>Device not found</div>", status_code=404)

    zk = ZKTecoAttendance(ip_address=device_info["ip"], port=device_info.get("port", 4370))
    try:
        zk.connect()
        users = zk.get_users()
    except Exception as e:
        return HTMLResponse(f"<div style='padding:2rem'>Error connecting to device: {str(e)}</div>", status_code=500)
    finally:
        zk.disconnect()

    rows = ""
    for u in users:
        rows += f"""
        <tr class="border-b border-gray-200 hover:bg-gray-50">
            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{u.get('uid')}</td>
            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{u.get('user_id')}</td>
            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900 font-medium">{u.get('name') or 'N/A'}</td>
            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{u.get('privilege')}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Users - {device_info.get('name')}</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="bg-gray-50 p-4 sm:p-8">
        <div class="max-w-5xl mx-auto">
            <div class="mb-4">
                <a href="/ui/devices" class="text-blue-600 hover:underline">&larr; Back to Devices</a>
            </div>
            <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
                <h1 class="text-2xl sm:text-3xl font-bold text-gray-800">Users: {device_info.get('name')}</h1>
                <a href="/ui/devices/{device_id}/set-user" class="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 transition font-medium">+ Add/Edit User</a>
            </div>
            <div class="bg-white shadow-md rounded-lg overflow-x-auto border border-gray-200">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">UID</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User ID</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Privilege</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        {rows}
                    </tbody>
                </table>
            </div>
                <script>document.getElementById('loading').classList.add('hidden');</script>
    </body>
    </html>
    """

@app.get("/ui/devices/{device_id}/set-user", response_class=HTMLResponse, include_in_schema=False)
def set_device_user_page(device_id: str):
    devices = load_devices()
    device_info = next((d for d in devices if d.get("id") == device_id), None)
    
    if not device_info:
        return HTMLResponse("<div style='padding:2rem'>Device not found</div>", status_code=404)

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Set User - {device_info.get('name')}</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="bg-gray-50 p-4 sm:p-8">
        <div class="max-w-2xl mx-auto">
            <div class="mb-4">
                <a href="/ui/devices/{device_id}/users" class="text-blue-600 hover:underline">&larr; Back to Users</a>
            </div>
            <h1 class="text-2xl sm:text-3xl font-bold text-gray-800 mb-6">Set User: {device_info.get('name')}</h1>

            <div id="alert" class="hidden p-4 mb-4 rounded-md"></div>

            <form id="setUserForm" class="bg-white p-6 rounded-lg shadow-md border border-gray-200">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">UID (Internal ID)</label>
                        <input type="number" name="uid" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">User ID (Display)</label>
                        <input type="text" name="user_id" value="2" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Name</label>
                        <input type="text" name="name" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Password</label>
                        <input type="text" name="password" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Privilege</label>
                        <select name="privilege" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 bg-white">
                            <option value="0">User</option>
                            <option value="14">Admin</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Card Number</label>
                        <input type="number" name="card" value="0" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Group ID</label>
                        <input type="text" name="group_id" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2">
                    </div>
                </div>
                <button type="submit" class="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700 transition font-medium">Save User</button>
            </form>
        </div>
        <script>
            document.getElementById('setUserForm').addEventListener('submit', async (e) => {{
                e.preventDefault();
                const btn = e.target.querySelector('button');
                btn.disabled = true;
                btn.innerText = 'Saving...';
                
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData.entries());
                
                // Typecasting to match Pydantic model
                data.uid = parseInt(data.uid) || 0;
                data.privilege = parseInt(data.privilege) || 0;
                data.card = parseInt(data.card) || 0;
                if(!data.user_id) data.user_id = '2';

                const alertBox = document.getElementById('alert');
                alertBox.className = 'hidden p-4 mb-4 rounded-md';

                try {{
                    const response = await fetch(`/devices/{device_id}/set-user`, {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify(data)
                    }});

                    if (!response.ok) {{
                        const err = await response.json();
                        throw new Error(err.detail || 'Failed to save user');
                    }}

                    alertBox.className = 'p-4 mb-4 rounded-md bg-green-100 text-green-700';
                    alertBox.innerText = 'User saved successfully!';
                }} catch (error) {{
                    alertBox.className = 'p-4 mb-4 rounded-md bg-red-100 text-red-700';
                    alertBox.innerText = error.message;
                }} finally {{
                    btn.disabled = false;
                    btn.innerText = 'Save User';
                }}
            }});
        </script>
    </body>
    </html>
    """

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

@app.post("/devices/{device_id}/set-user")
def set_device_user(device_id: str, user: SetUserRequest):
    devices = load_devices()
    device_info = next((d for d in devices if d.get("id") == device_id), None)
    
    if not device_info:
        raise HTTPException(status_code=404, detail="Device not found")
    
    zk = ZKTecoAttendance(ip_address=device_info["ip"], port=device_info.get("port", 4370))
    try:
        zk.connect()
        success = zk.set_user(
            uid=user.uid,
            name=user.name,
            privilege=user.privilege,
            password=user.password,
            group_id=user.group_id,
            user_id=user.user_id,
            card=user.card
        )
        if success:
            return {"status": "success", "message": f"User {user.uid} saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save user via ZKTeco connection")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        zk.disconnect()