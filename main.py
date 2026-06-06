from fastapi import FastAPI, HTTPException, Query, Request, Depends, Form, Response
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.security import APIKeyHeader
import yaml
import os
from typing import Optional
from datetime import date
from zkteco_utils import ZKTecoAttendance

api_key_header = APIKeyHeader(name="x-auth-token", auto_error=False)
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

@app.get("/ui/login", response_class=HTMLResponse)
def login_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="bg-gray-100 flex items-center justify-center h-screen">
        <form method="post" action="/ui/login" class="bg-white p-8 rounded-lg shadow-md w-96">
            <h2 class="text-2xl font-bold mb-6 text-gray-800">API Login</h2>
            <input type="password" name="token" placeholder="Enter x-auth-token" required 
                   class="w-full px-4 py-2 border rounded-md mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"/>
            <button type="submit" class="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700 transition">Login</button>
        </form>
    </body>
    </html>
    """

@app.post("/ui/login")
def login_submit(response: Response, token: str = Form(...)):
    config = load_config()
    expected_token = config.get("x_auth_token")
    
    if token == expected_token:
        res = RedirectResponse(url="/ui/devices", status_code=302)
        res.set_cookie(key="x-auth-token", value=token, httponly=True, samesite="lax", max_age=86400)
        return res
        
    return HTMLResponse("Invalid token. <a href='/ui/login' class='text-blue-500 underline'>Try again</a>", status_code=401)

@app.get("/ui/devices", response_class=HTMLResponse)
def devices_page():
    devices = load_devices()
    rows = ""
    for d in devices:
        rows += f"""
        <tr class="border-b border-gray-200 hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{d.get('id')}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{d.get('name')}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{d.get('ip')}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{d.get('port', 4370)}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <a href="/ui/devices/{d.get('id')}/users" class="text-blue-600 hover:text-blue-900 mr-3">Users</a>
                <a href="/ui/devices/{d.get('id')}/logs" class="text-blue-600 hover:text-blue-900">Logs</a>
            </td>
        </tr>
        """
        
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Devices</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="bg-gray-50 p-8">
        <div class="max-w-5xl mx-auto">
            <div class="flex justify-between items-center mb-6">
                <h1 class="text-3xl font-bold text-gray-800">Connected Devices</h1>
                <a href="/docs" class="bg-gray-800 text-white px-4 py-2 rounded shadow hover:bg-gray-700">Swagger API</a>
            </div>
            <div class="bg-white shadow-md rounded-lg overflow-hidden border border-gray-200">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP Address</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Port</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
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

@app.get("/ui/devices/{device_id}/users", response_class=HTMLResponse)
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
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{u.get('uid')}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{u.get('user_id')}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">{u.get('name') or 'N/A'}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{u.get('privilege')}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Users - {device_info.get('name')}</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="bg-gray-50 p-8">
        <div class="max-w-5xl mx-auto">
            <div class="mb-4">
                <a href="/ui/devices" class="text-blue-600 hover:underline">&larr; Back to Devices</a>
            </div>
            <h1 class="text-3xl font-bold text-gray-800 mb-6">Users on {device_info.get('name')}</h1>
            <div class="bg-white shadow-md rounded-lg overflow-hidden border border-gray-200">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">UID</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User ID</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Privilege</th>
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

@app.get("/ui/devices/{device_id}/logs", response_class=HTMLResponse)
def device_logs_page(device_id: str):
    devices = load_devices()
    device_info = next((d for d in devices if d.get("id") == device_id), None)
    
    if not device_info:
        return HTMLResponse("<div style='padding:2rem'>Device not found</div>", status_code=404)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Logs - {device_info.get('name')}</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="bg-gray-50 p-8">
        <div class="max-w-6xl mx-auto">
            <div class="mb-4">
                <a href="/ui/devices" class="text-blue-600 hover:underline">&larr; Back to Devices</a>
            </div>
            <h1 class="text-3xl font-bold text-gray-800 mb-6">Attendance Logs: {device_info.get('name')}</h1>
            
            <div class="bg-white p-4 rounded-lg shadow-md border border-gray-200 mb-6 flex flex-wrap gap-4 items-end">
                <div>
                    <label class="block text-sm font-medium text-gray-700">From Date</label>
                    <input type="date" id="from_date" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-blue-500 focus:border-blue-500">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700">To Date</label>
                    <input type="date" id="to_date" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-blue-500 focus:border-blue-500">
                </div>
                <button id="fetch_btn" class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition">Fetch Logs</button>
            </div>

            <div id="loading" class="hidden text-blue-600 mb-4 font-medium">Fetching data from device...</div>
            <div id="error" class="hidden text-red-600 mb-4 font-medium"></div>

            <div class="bg-white shadow-md rounded-lg overflow-hidden border border-gray-200 hidden" id="table_container">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User ID</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Check In</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Check Out</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Hours</th>
                        </tr>
                    </thead>
                    <tbody id="logs_body" class="bg-white divide-y divide-gray-200">
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            document.getElementById('fetch_btn').addEventListener('click', async () => {{
                const fromDate = document.getElementById('from_date').value;
                const toDate = document.getElementById('to_date').value;
                
                let url = `/devices/{device_id}/attendance?`;
                if (fromDate) url += `start_date=${{fromDate}}&`;
                if (toDate) url += `end_date=${{toDate}}`;

                document.getElementById('loading').classList.remove('hidden');
                document.getElementById('error').classList.add('hidden');
                document.getElementById('table_container').classList.add('hidden');
                const tbody = document.getElementById('logs_body');
                tbody.innerHTML = '';

                try {{
                    const response = await fetch(url);
                    if (!response.ok) {{
                        const err = await response.json();
                        throw new Error(err.detail || `HTTP error! status: ${{response.status}}`);
                    }}
                    
                    const data = await response.json();
                    
                    if (data.length === 0) {{
                        document.getElementById('error').innerText = 'No records found for the selected date range.';
                        document.getElementById('error').classList.remove('hidden');
                    }} else {{
                        data.forEach(row => {{
                            const checkInStr = row.check_in ? new Date(row.check_in).toLocaleTimeString([], {{hour: '2-digit', minute:'2-digit'}}) : '-';
                            const checkOutStr = row.check_out ? new Date(row.check_out).toLocaleTimeString([], {{hour: '2-digit', minute:'2-digit'}}) : '-';
                            
                            const tr = document.createElement('tr');
                            tr.className = 'hover:bg-gray-50';
                            tr.innerHTML = `
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${{row.user_id}}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${{row.user_name}}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${{row.date || '-'}}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-green-600 font-medium">${{checkInStr}}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-red-600 font-medium">${{checkOutStr}}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${{row.duration_hours || '-'}}</td>
                            `;
                            tbody.appendChild(tr);
                        }});
                        document.getElementById('table_container').classList.remove('hidden');
                    }}
                }} catch (e) {{
                    document.getElementById('error').innerText = 'Error: ' + e.message;
                    document.getElementById('error').classList.remove('hidden');
                }} finally {{
                    document.getElementById('loading').classList.add('hidden');
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