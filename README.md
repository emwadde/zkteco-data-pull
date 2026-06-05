# ZKTeco Attendance System

A Python-based data pull tool for ZKTeco biometric devices. This application provides a developer-friendly API to retrieve and manage attendance records from ZKTeco devices.

## Features

- Connect to ZKTeco devices over network
- Get attendance records with user names
- Group check-in and check-out times
- Calculate duration between check-in and check-out
- Filter records by date range

### For Developers
1. Clone the repository and create virtual env:
   ```bash
   git clone https://github.com/emwadde/zkteco-attendance-system.git
   cd zkteco-attendance-system
   uv venv
   ```

2. Install required packages:
   ```bash
   uv pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main.py
   ```

## Usage

1. Enter the Device details in devices.yaml
2. run main.py

