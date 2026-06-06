from zk import ZK, const
import pandas as pd
from datetime import datetime, time

class ZKTecoAttendance:
    def __init__(self, ip_address, port=4370, timeout=5, password=0):
        self.ip_address = ip_address
        self.port = port
        self.timeout = timeout
        self.password = password
        self.zk = ZK(self.ip_address, port=self.port, timeout=self.timeout, password=self.password)
        self.conn = None
        self.users = {}

    def connect(self):
        try:
            self.conn = self.zk.connect()
            self._cache_users()
        except Exception as e:
            raise ConnectionError(f"Error connecting to device {self.ip_address}: {str(e)}")

    def disconnect(self):
        if self.conn:
            self.conn.disconnect()
            self.conn = None
            self.users = {}

    def _cache_users(self):
        """Internal method to cache users for attendance mapping"""
        if self.conn:
            users = self.conn.get_users()
            self.users = {user.user_id: user.name for user in users}

    def get_users(self):
        """Returns a list of all users on the device"""
        if not self.conn:
            raise ConnectionError("Not connected to device.")
        
        users = self.conn.get_users()
        return [
            {
                "uid": user.uid,
                "user_id": user.user_id,
                "name": user.name,
                "privilege": user.privilege,
                "password": user.password
            }
            for user in users
        ]
    
    def set_user(self, uid=None, name='', privilege=0, password='', group_id='', user_id='', card=0):
        """
        create or update user by uid

        :param name: name ot the user
        :param privilege: check the const.py for reference
        :param password: int password
        :param group_id: group ID
        :param user_id: your own user ID
        :param card: card
        :return: bool
        """
        if not self.conn:
            raise ConnectionError("Not connected to device.")
        try:
            self.conn.set_user(uid=uid, name=name, privilege=0, password=password, group_id=group_id, card=card)
            return True
        except Exception as e:
            print ("Process terminate : {}".format(e))
            return False

    def get_attendance_status(self, punch):
        punch_map = {0: "Check In", 1: "Check Out"}
        return punch_map.get(punch, f"Unknown Punch ({punch})")

    def get_attendance(self, start_date=None, end_date=None):
        """Returns attendance records as a list of dictionaries for the API"""
        if not self.conn:
            raise ConnectionError("Not connected to device.")
            
        attendance = self.conn.get_attendance()
        if not attendance:
            return []

        if start_date and not isinstance(start_date, datetime):
            start_date = datetime.combine(start_date, time.min)
        if end_date and not isinstance(end_date, datetime):
            end_date = datetime.combine(end_date, time.max)

        raw_records = []
        for att in attendance:
            dt = att.timestamp
            if start_date and end_date and not (start_date <= dt <= end_date):
                continue
                
            raw_records.append({
                'user_id': att.user_id,
                'user_name': self.users.get(att.user_id, "Unknown"),
                'timestamp': dt,
                'punch': att.punch
            })

        df = pd.DataFrame(raw_records)
        if df.empty:
            return []

        df = df.sort_values(['user_id', 'timestamp'])
        grouped_records = []
        current_user, current_date, check_in, check_out = None, None, None, None

        for _, row in df.iterrows():
            user_id, user_name, timestamp, punch = row['user_id'], row['user_name'], row['timestamp'], row['punch']
            date = timestamp.date()

            if current_user != user_id or current_date != date:
                if current_user is not None and check_in is not None:
                    grouped_records.append({
                        'user_id': current_user,
                        'user_name': current_user_name,
                        'date': current_date,
                        'check_in': check_in,
                        'check_out': check_out
                    })
                current_user, current_user_name, current_date = user_id, user_name, date
                check_in, check_out = None, None

            if punch == 0:
                check_in = timestamp
            elif punch == 1:
                check_out = timestamp

        if current_user is not None and check_in is not None:
            grouped_records.append({
                'user_id': current_user,
                'user_name': current_user_name,
                'date': current_date,
                'check_in': check_in,
                'check_out': check_out
            })

        result_df = pd.DataFrame(grouped_records)
        if not result_df.empty:
            result_df['duration_hours'] = result_df.apply(
                lambda row: round((row['check_out'] - row['check_in']).total_seconds() / 3600, 2) 
                if pd.notnull(row['check_out']) else None, axis=1
            )
            
            # Convert NaT and NaN to None for clean JSON serialization in FastAPI
            result_df = result_df.replace({pd.NaT: None, float('nan'): None})

        return result_df.to_dict(orient='records')