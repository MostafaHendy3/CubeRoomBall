import csv
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import ConnectionError, Timeout, RequestException
import time   
import numpy as np
import json
from PyQt5.QtGui import QMovie,QPainter, QColor, QFont,QFontDatabase ,QImage, QPixmap,QPen, QPainterPath , QPolygonF, QBrush, QRadialGradient, QLinearGradient
from PyQt5.QtCore import QTimer,Qt, pyqtSignal, pyqtSlot ,QThread , QTime,QSize,QRectF,QPointF, QUrl
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget ,QGridLayout,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QTableWidget,QTableWidgetItem,QHeaderView,QFrame
import math 
import requests , os ,time
import random

from PyQt5 import QtCore, QtGui, QtWidgets
import paho.mqtt.client as mqtt
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent


import sys

# Import our new API and configuration system
from api.game_api import GameAPI
from config import config
from utils.logger import get_logger

# Import serial communication module (ST1Scale for weighing scale)
from typing import Any, Dict
import serial as pyserial
import re

# Setup logging
logger = get_logger(__name__)

# Load configuration
game_config = config.settings.game

# Initialize global variables
final_screen_timer_idle = game_config.final_screen_timer
count = 0
TimerValue = game_config.timer_value
global scaled
scaled = 1
scored = 0
list_players_name = []
list_players_score = [0,0,0,0,0]
list_players_id = []
list_top5_TheCage = []
RemainingTime = 0
teamName = ""
homeOpened = False

# Global variable to control number of balls in the cube widget
# This can be updated from anywhere in the code to change the number of balls
# Example: cube_balls_count = 5  # Will show 5 balls in the cube
cube_balls_count = 0

# Global variable to track if serial communication is being used for scoring
# Used for logging purposes to distinguish between serial and non-serial scores
serial_scoring_active = False

import numpy as np
gamefinished = False
gameStarted = False
firstDetected = False

response = None


def set_cube_balls_count(count):
    """
    Helper function to set the number of balls in the cube widget.
    
    Args:
        count (int): Number of balls to display (0-10 recommended)
    
    Example:
        set_cube_balls_count(5)  # Shows 5 balls in the cube
    """
    global cube_balls_count
    cube_balls_count = max(0, min(15, count))  # Clamp between 0 and 15
    print(f"Cube balls count set to: {cube_balls_count}")


class ST1ScaleThread(QThread):
    """
    Threaded ST1 Weighing Scale class that combines serial communication and threading
    to prevent blocking the main UI thread while providing continuous scale monitoring.
    """
    # Qt signals for thread communication
    scale_data_received = pyqtSignal(dict)  # Emitted when new scale data is received
    score_updated = pyqtSignal(int)  # Emitted when score is updated
    connection_status_changed = pyqtSignal(bool)  # Emitted when connection status changes
    error_occurred = pyqtSignal(str)  # Emitted when an error occurs
    
    def __init__(self, port: str, baudrate: int = 9600, timeout: int = 1, data_format: int = 2):
        super().__init__()
        self.port_name = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.data_format = data_format
        self.running = False
        self.is_connected = False
        
        # Communication parameters from the manual 
        self.serial_connection = pyserial.Serial()
        self.serial_connection.port = self.port_name
        self.serial_connection.baudrate = self.baudrate
        self.serial_connection.bytesize = pyserial.EIGHTBITS
        self.serial_connection.parity = pyserial.PARITY_NONE
        self.serial_connection.stopbits = pyserial.STOPBITS_ONE
        self.serial_connection.timeout = self.timeout

    def connect(self) -> bool:
        """
        Opens the serial port connection to the scale.
        
        Returns:
            bool: True if connection is successful, False otherwise.
        """
        if self.is_connected:
            print("Already connected.")
            return True
        try:
            self.serial_connection.open()
            self.is_connected = True
            print(f"Successfully connected to scale on {self.port_name}.")
            return True
        except pyserial.SerialException as e:
            print(f"Error: Could not connect to {self.port_name}. Details: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Closes the serial port connection."""
        if self.is_connected and self.serial_connection.is_open:
            self.serial_connection.close()
            self.is_connected = False
            print("Disconnected from scale.")

    def reconnect(self, max_attempts: int = 3) -> bool:
        """
        Reconnect to the scale with retry mechanism.
        
        Args:
            max_attempts (int): Maximum number of reconnection attempts
            
        Returns:
            bool: True if reconnection successful, False otherwise
        """
        print(f"Attempting to reconnect to scale on {self.port_name}...")
        
        # First disconnect if connected
        if self.is_connected:
            self.disconnect()
        
        # Try to reconnect multiple times
        for attempt in range(max_attempts):
            print(f"Reconnection attempt {attempt + 1}/{max_attempts}")
            
            if attempt > 0:
                time.sleep(2)  # Wait 2 seconds between attempts
            
            if self.connect():
                print(f"Successfully reconnected to scale on attempt {attempt + 1}")
                return True
        
        print(f"Failed to reconnect after {max_attempts} attempts")
        return False

    def read_raw_line(self) -> str | None:
        """
        Reads a single raw line of data from the scale.
        Each data transmission is terminated by CR LF.
        
        Returns:
            str | None: The decoded string line, or None if no data is read.
        """
        if not self.is_connected:
            print("Not connected. Please call connect() first.")
            return None
        try:
            line_bytes = self.serial_connection.readline()
            if line_bytes:
                return line_bytes.decode('ascii').strip()
            return "" # Return empty string on timeout
        except pyserial.SerialException as e:
            print(f"Serial communication error: {e}")
            self.disconnect()
            return None

    def _parse_format1(self, line: str) -> dict:
        """Parses Format 1 data. Example: "ST, GS, + 1.000kg" """
        data = {'format': 1, 'raw': line, 'parsed_data': None}
        try:
            parts = line.split(',')
            if len(parts) >= 3:
                status_code = parts[0].strip()
                weight_type_code = parts[1].strip()
                weight_info = ','.join(parts[2:]).strip()
                
                match = re.search(r'([+\-])\s*(\d+\.\d+)\s*(\w+)', weight_info)
                if match:
                    sign = match.group(1)
                    number = match.group(2)
                    unit = match.group(3)
                    value = float(sign + number)
                else:
                    value, unit = None, None

                data['parsed_data'] = {
                    'status_code': status_code,
                    'status': {"ST": "Stable", "US": "Unstable", "OL": "Overload"}.get(status_code, "Unknown"),
                    'weight_type_code': weight_type_code,
                    'weight_type': {"GS": "Gross weight", "NT": "Net weight"}.get(weight_type_code, "Unknown"),
                    'value': value,
                    'unit': unit
                }
        except Exception as e:
            data['error'] = str(e)
        return data

    def _parse_format2(self, line: str) -> dict:
        """Parses Format 2 data. Example: "+ 1.000kg" """
        data = {'format': 2, 'raw': line, 'parsed_data': None}
        try:
            match = re.search(r'([+\-])\s*(\d+\.\d+)\s*(\w+)', line)
            if match:
                sign = match.group(1)
                number = match.group(2)
                unit = match.group(3)
                value = float(sign + number)
                data['parsed_data'] = {
                    'value': value,
                    'unit': unit
                }
        except Exception as e:
            data['error'] = str(e)
        return data
        
    def _parse_format3(self, line: str) -> dict:
        """Parses Format 3 data (multi-line format)"""
        data = {'format': 3, 'raw': line, 'parsed_data': None, 'line_type': 'unknown'}
        try:
            line = line.strip()
            if "S/N" in line and "WT" in line:
                data['line_type'] = 'header'
            elif "TOTAL" in line:
                data['line_type'] = 'total_header'
            else:
                parts = re.split(r'\s+', line)
                if len(parts) == 2:
                    if parts[0].isdigit() and re.match(r'^\d+(\.\d+)?$', parts[1]):
                        data['line_type'] = 'data_or_total_value'
                        data['parsed_data'] = {
                            'column1': int(parts[0]),
                            'column2': float(parts[1])
                        }
        except Exception as e:
            data['error'] = str(e)
        return data

    def _parse_format4(self, line: str) -> dict:
        """Parses Format 4 data (ticket format)"""
        data = {'format': 4, 'raw': line, 'parsed_data': None, 'line_type': 'unknown'}
        try:
            line_upper = line.upper().strip()
            if line_upper.startswith("TICKET NO."):
                data['line_type'] = 'ticket_number'
                data['parsed_data'] = {'ticket_no': int(re.search(r'\d+', line).group())}
            elif line_upper.startswith("G"):
                data['line_type'] = 'gross_weight'
                match = re.search(r'(\d+\.\d+)\s*(\w+)', line)
                data['parsed_data'] = {'value': float(match.group(1)), 'unit': match.group(2)} if match else {}
            elif line_upper.startswith("T") and "TOTAL" not in line_upper:
                data['line_type'] = 'tare_weight'
                match = re.search(r'(\d+\.\d+)\s*(\w+)', line)
                data['parsed_data'] = {'value': float(match.group(1)), 'unit': match.group(2)} if match else {}
            elif line_upper.startswith("N"):
                data['line_type'] = 'net_weight'
                match = re.search(r'(\d+\.\d+)\s*(\w+)', line)
                data['parsed_data'] = {'value': float(match.group(1)), 'unit': match.group(2)} if match else {}
            # ... other format 4 parsing logic
        except Exception as e:
            data['error'] = str(e)
        return data
        
    def read_parsed_data(self, data_format: int = None) -> dict | None:
        """
        Reads a line from the scale and parses it based on the specified format.
        
        Args:
            data_format (int): The format number (1, 2, 3, or 4). Uses instance default if None.

        Returns:
            dict | None: A dictionary containing the parsed data, or None on error.
        """
        if data_format is None:
            data_format = self.data_format
            
        line = self.read_raw_line()
        if line is None:
            return None # Error reading
        if line == "":
            return {} # Timeout, no data
            
        if data_format == 1:
            return self._parse_format1(line)
        elif data_format == 2:
            return self._parse_format2(line)
        elif data_format == 3:
            return self._parse_format3(line)
        elif data_format == 4:
            return self._parse_format4(line)
        else:
            print(f"Error: Unknown data format '{data_format}'.")
            return {'raw': line, 'error': f'Unknown format {data_format}'}
    
    def connect_for_game(self) -> bool:
        """Connect to ST1 scale for game start with logging"""
        try:
            if self.connect():
                logger.info(" ST1Scale thread connected")
                self.connection_status_changed.emit(True)
                return True
            else:
                logger.warning("️ ST1Scale thread connection failed")
                self.connection_status_changed.emit(False)
                return False
        except Exception as e:
            logger.error(f" ST1Scale thread connection error: {e}")
            self.error_occurred.emit(f"Connection error: {e}")
            return False
    
    def disconnect_for_game(self) -> bool:
        """Disconnect from ST1 scale for game end with logging"""
        try:
            self.disconnect()
            logger.info(" ST1Scale thread disconnected")
            self.connection_status_changed.emit(False)
            return True
        except Exception as e:
            logger.error(f" ST1Scale thread disconnection error: {e}")
            self.error_occurred.emit(f"Disconnection error: {e}")
            return False
    
    def get_status(self) -> dict:
        """Get current ST1 scale connection status"""
        return {
            'connected': self.is_connected,
            'enabled': True,
            'port': self.port_name,
            'baudrate': self.baudrate
        }
    
    def start_monitoring(self):
        """Start the monitoring thread"""
        self.running = True
        self.start()
    
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.running = False
        self.quit()
        self.wait()
    
    def run(self):
        """Main thread loop - continuously monitor the scale"""
        logger.info("ST1Scale monitoring thread started")
        
        while self.running:
            try:
                if self.is_connected:
                    # Read data from scale
                    scale_data = self.read_parsed_data(self.data_format)
                    
                    if scale_data and 'parsed_data' in scale_data and scale_data['parsed_data']:
                        parsed_data = scale_data['parsed_data']
                        
                        # Emit the raw scale data
                        self.scale_data_received.emit(scale_data)
                        
                        # Extract value and emit score
                        value = None
                        if 'value' in parsed_data:
                            value = parsed_data['value']
                        elif 'column2' in parsed_data:  # Format 3
                            value = parsed_data['column2']
                        
                        if value is not None:
                            score = int(abs(value))
                            self.score_updated.emit(score)
                
                # Sleep for a short time to prevent excessive CPU usage
                self.msleep(200)  # 200ms = 5 readings per second
                
            except Exception as e:
                self.error_occurred.emit(f"Monitoring error: {e}")
                logger.error(f" ST1Scale monitoring error: {e}")
                # Try to reconnect on error
                if self.running:
                    self.msleep(1000)  # Wait 1 second before retry
                    try:
                        if self.reconnect(max_attempts=1):
                            self.connection_status_changed.emit(True)
                        else:
                            self.connection_status_changed.emit(False)
                    except:
                        pass
        
        logger.info("ST1Scale monitoring thread stopped")


# ST1Scale functionality is now integrated into ST1ScaleThread class above


class CubeAndBallWidget(QWidget):
    """3D Cube and Ball Widget for integration into Active Screen"""
    
    def __init__(self, width=400, height=300, parent=None):
        super().__init__(parent)
        self.custom_width = width
        self.custom_height = height
        self.init_ui()
        self.init_game()
        
    def init_ui(self):
        """Initialize the UI components."""
        self.setFixedSize(self.custom_width, self.custom_height)
        self.setStyleSheet("background-color: rgba(30, 30, 50, 180);")
        
        # Set up the timer for game loop
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_game)
        self.timer.start(16)  # ~60 FPS (1000ms / 60 ≈ 16ms)
        
    def init_game(self):
        """Initialize game constants and variables."""
        # Screen setup
        self.WIDTH, self.HEIGHT = self.custom_width, self.custom_height
        
        # 3D Projection Settings - scale based on widget size
        self.FOV = min(self.WIDTH, self.HEIGHT) * 0.5
        self.CENTER_X, self.CENTER_Y = self.WIDTH // 2, self.HEIGHT // 2
        
        # Cube Settings - scale based on widget size  
        self.BOX_SIZE = min(self.WIDTH, self.HEIGHT) * 1.5  # Increased from 0.6 to 0.8
        self.BOX_MIN = -self.BOX_SIZE // 2
        self.BOX_MAX = self.BOX_SIZE // 2
        
        # Ball Settings - scale based on widget size
        self.BALL_RADIUS = min(self.WIDTH, self.HEIGHT) * 0.1  # Increased from 0.03 to 0.05
        self.GRAVITY = 0.2
        self.DAMPING = 0.8
        
        # Cube vertices
        self.cube_vertices = [
            [self.BOX_MIN, self.BOX_MIN, self.BOX_MIN],
            [self.BOX_MAX, self.BOX_MIN, self.BOX_MIN],
            [self.BOX_MAX, self.BOX_MAX, self.BOX_MIN],
            [self.BOX_MIN, self.BOX_MAX, self.BOX_MIN],
            [self.BOX_MIN, self.BOX_MIN, self.BOX_MAX],
            [self.BOX_MAX, self.BOX_MIN, self.BOX_MAX],
            [self.BOX_MAX, self.BOX_MAX, self.BOX_MAX],
            [self.BOX_MIN, self.BOX_MAX, self.BOX_MAX],
        ]
        
        # Cube edges
        self.cube_edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),
            (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7)
        ]
        
        # Cube faces - BASKET: 4 sides + top, NO BOTTOM (open from top where Y=BOX_MIN)
        self.cube_faces = [
            # Front face
            ([0, 1, 2, 3], QColor(60, 120, 200, 120)),  # Blue - more transparent
            # Back face  
            ([4, 7, 6, 5], QColor(120, 60, 200, 120)),  # Purple
            # Left face
            ([0, 3, 7, 4], QColor(200, 60, 120, 120)),  # Red
            # Right face
            ([1, 5, 6, 2], QColor(60, 200, 120, 120)),  # Green
            # Top face (at Y=BOX_MAX, visually bottom)
            ([3, 2, 6, 7], QColor(200, 200, 60, 120)),  # Yellow
            # NO BOTTOM FACE - basket is open from top (Y=BOX_MIN)
        ]
        
        # Game state
        self.balls = []
        self.angle = math.radians(45)  # Rotate 45° around Y-axis for better side view
        self.rotation_speed = 0.01  # Slow auto-rotation for cool effect
        self.auto_rotate = True  # Enable/disable auto rotation
        
    def update_balls_count(self, target_count):
        """Update the number of balls to match the global variable"""
        global cube_balls_count
        current_count = len(self.balls)
        
        if target_count > current_count:
            # Add balls
            for _ in range(target_count - current_count):
                self.balls.append(Ball(self))
        elif target_count < current_count:
            # Remove balls
            self.balls = self.balls[:target_count]
    
    def rotateY(self, x, y, z, angle):
        """Rotate point around Y axis."""
        cosA, sinA = math.cos(angle), math.sin(angle)
        return x * cosA + z * sinA, y, -x * sinA + z * cosA
    
    def project_point(self, x, y, z):
        """Project 3D point into 2D with perspective."""
        scale = self.FOV / (self.FOV + z + self.BOX_SIZE * 1.5)
        sx = int(self.CENTER_X + x * scale)
        sy = int(self.CENTER_Y + y * scale)
        return sx, sy
    
    def update_game(self):
        """Update game state and repaint."""
        global cube_balls_count
        
        # Update ball count based on global variable
        self.update_balls_count(cube_balls_count)
        
        # Update balls
        for ball in self.balls:
            ball.update(self.balls)
        
        # Auto-rotate the cube for cool effect
        if self.auto_rotate:
            self.angle += self.rotation_speed
        
        # Trigger repaint
        self.update()
    
    def paintEvent(self, event):
        """Handle paint events."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Render with cube priority over balls
        rotated_vertices = [self.rotateY(x, y, z, self.angle) for (x, y, z) in self.cube_vertices]
        projected_vertices = [self.project_point(x, y, z) for (x, y, z) in rotated_vertices]
        
        # First: Render all balls (furthest to closest)
        sorted_balls = sorted(self.balls, key=lambda b: self.rotateY(b.x, b.y, b.z, self.angle)[2], reverse=True)
        for ball in sorted_balls:
            ball.draw(painter, self.angle)
        
        # Second: Render cube faces (back to front) - this ensures cube is on top
        face_depths = []
        for face_data in self.cube_faces:
            vertices_indices, color = face_data
            avg_z = sum(rotated_vertices[i][2] for i in vertices_indices) / 4
            face_depths.append((avg_z, face_data))
        
        # Sort faces by depth (furthest first)
        face_depths.sort(key=lambda x: x[0], reverse=True)
        
        # Render faces from back to front
        for depth, face_data in face_depths:
            self.draw_cube_face(painter, face_data, rotated_vertices, projected_vertices)
        
        # Third: Draw cube edges on top for definition
        self.draw_cube_edges(painter, projected_vertices)
        
        painter.end()
    
    def draw_cube_face(self, painter, face_data, rotated_vertices, projected_vertices):
        """Draw a single cube face with lighting effects."""
        vertices_indices, base_color = face_data
        base_color = QColor(255, 255, 255, 80)  # Very transparent white blurry
        # Create polygon for the face
        polygon = QPolygonF()
        face_center_x, face_center_y = 0, 0
        
        for i in vertices_indices:
            x, y = projected_vertices[i]
            polygon.append(QPointF(x, y))
            face_center_x += x
            face_center_y += y
        
        face_center_x /= 4
        face_center_y /= 4
        
        # Calculate depth for lighting
        depth = sum(rotated_vertices[i][2] for i in vertices_indices) / 4
        
        # Create gradient for 3D lighting effect
        gradient = QLinearGradient(
            face_center_x - 25, face_center_y - 25,
            face_center_x + 25, face_center_y + 25
        )
        
        # Calculate lighting based on face normal and depth
        light_intensity = max(0.3, min(1.0, (depth + self.BOX_SIZE) / (self.BOX_SIZE * 2)))
        
        # Create lighter and darker versions of the base color
        light_color = QColor(
            min(255, int(base_color.red() * light_intensity * 1.3)),
            min(255, int(base_color.green() * light_intensity * 1.3)),
            min(255, int(base_color.blue() * light_intensity * 1.3)),
            base_color.alpha()
        )
        dark_color = QColor(
            int(base_color.red() * light_intensity * 0.7),
            int(base_color.green() * light_intensity * 0.7),
            int(base_color.blue() * light_intensity * 0.7),
            base_color.alpha()
        )
        
        gradient.setColorAt(0.0, light_color)
        gradient.setColorAt(0.5, base_color)
        gradient.setColorAt(1.0, dark_color)
        
        # Draw the face
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1))  # Subtle white edges
        painter.drawPolygon(polygon)
    
    def draw_cube_edges(self, painter, projected_vertices):
        """Draw cube edges and corner points."""
        # Draw highlighted edges for better definition
        edge_pen = QPen(QColor(255, 255, 255, 100), 1)
        painter.setPen(edge_pen)
        painter.setBrush(Qt.NoBrush)
        
        # Draw only the most visible edges
        visible_edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 4), (1, 5), (2, 6), (3, 7)]
        for edge in visible_edges:
            start_point = QPointF(projected_vertices[edge[0]][0], projected_vertices[edge[0]][1])
            end_point = QPointF(projected_vertices[edge[1]][0], projected_vertices[edge[1]][1])
            painter.drawLine(start_point, end_point)


class Ball:
    """Ball class for the 3D cube widget"""
    
    def __init__(self, widget):
        self.widget = widget
        # Spawn balls above the open top (smaller Y = higher visually)
        self.x = random.uniform(widget.BOX_MIN * 0.7, widget.BOX_MAX * 0.7)
        self.y = widget.BOX_MIN - random.uniform(50, 100)  # Above the open top
        self.z = random.uniform(widget.BOX_MIN * 0.7, widget.BOX_MAX * 0.7)
        self.vx = random.uniform(-0.5, 0.5)  # Small horizontal drift
        self.vy = random.uniform(1, 3)  # Positive velocity = downward in PyQt
        self.vz = random.uniform(-0.5, 0.5)  # Small depth drift
        self.radius = widget.BALL_RADIUS
    
    def update(self, balls):
        """Update ball position and handle collisions."""
        # Gravity
        self.vy += self.widget.GRAVITY
        
        # Move
        self.x += self.vx
        self.y += self.vy
        self.z += self.vz
        
        # Basket collision system with margins
        margin = max(self.radius * 0.3, 4)
        
        # X-axis (left/right walls)
        if self.x - self.radius <= self.widget.BOX_MIN + margin:
            self.x = self.widget.BOX_MIN + self.radius + margin
            self.vx *= -self.widget.DAMPING
        elif self.x + self.radius >= self.widget.BOX_MAX - margin:
            self.x = self.widget.BOX_MAX - self.radius - margin
            self.vx *= -self.widget.DAMPING
            
        # Y-axis - corrected for open top basket
        # NO TOP COLLISION (Y=BOX_MIN) - basket is open from above
        # ONLY BOTTOM collision (Y=BOX_MAX) - basket floor
        if self.y + self.radius >= self.widget.BOX_MAX - margin:
            self.y = self.widget.BOX_MAX - self.radius - margin
            self.vy *= -self.widget.DAMPING
            
        # Z-axis (front/back walls)
        if self.z - self.radius <= self.widget.BOX_MIN + margin:
            self.z = self.widget.BOX_MIN + self.radius + margin
            self.vz *= -self.widget.DAMPING
        elif self.z + self.radius >= self.widget.BOX_MAX - margin:
            self.z = self.widget.BOX_MAX - self.radius - margin
            self.vz *= -self.widget.DAMPING
        
        # Safety zone to keep balls within bounds
        safety_zone = max(self.radius * 0.5, 5)
        self.x = max(self.widget.BOX_MIN + self.radius + safety_zone, 
                    min(self.widget.BOX_MAX - self.radius - safety_zone, self.x))
        self.z = max(self.widget.BOX_MIN + self.radius + safety_zone, 
                    min(self.widget.BOX_MAX - self.radius - safety_zone, self.z))
        # Y is only clamped at bottom (basket floor)
        if self.y + self.radius > self.widget.BOX_MAX - safety_zone:
            self.y = self.widget.BOX_MAX - self.radius - safety_zone
        
        # Ball-ball collision
        for other in balls:
            if other is not self:
                dx, dy, dz = other.x - self.x, other.y - self.y, other.z - self.z
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                if dist < self.radius + other.radius and dist > 0:
                    overlap = 0.5 * (self.radius + other.radius - dist)
                    nx, ny, nz = dx/dist, dy/dist, dz/dist
                    self.x -= nx * overlap
                    self.y -= ny * overlap
                    self.z -= nz * overlap
                    other.x += nx * overlap
                    other.y += ny * overlap
                    other.z += nz * overlap
                    # Simple velocity exchange
                    self.vx, other.vx = other.vx, self.vx
                    self.vy, other.vy = other.vy, self.vy
                    self.vz, other.vz = other.vz, self.vz
    
    def draw(self, painter, angle):
        """Draw the ball with 3D perspective and lighting."""
        # Rotate for side view
        rx, ry, rz = self.widget.rotateY(self.x, self.y, self.z, angle)
        scale = self.widget.FOV / (self.widget.FOV + rz + self.widget.BOX_SIZE * 1.5)
        sx = int(self.widget.CENTER_X + rx * scale)
        sy = int(self.widget.CENTER_Y + ry * scale)
        sr = max(2, int(self.radius * scale))
        
        # Create 3D gradient effect
        gradient = QRadialGradient(
            sx - sr * 0.3,  # Light source offset from top-left
            sy - sr * 0.3,
            sr * 1.2         # Gradient radius
        )
        
        # Calculate depth-based color intensity
        depth_factor = max(0.3, min(1.0, (rz + self.widget.BOX_SIZE) / (self.widget.BOX_SIZE * 2)))
        base_intensity = int(150 * depth_factor)
        
        # Gradient colors for 3D sphere effect - orange/red theme
        gradient.setColorAt(0.0, QColor(255, base_intensity + 50, base_intensity + 50))  # Bright highlight
        gradient.setColorAt(0.3, QColor(base_intensity + 30, 30, 30))  # Main color
        gradient.setColorAt(0.7, QColor(base_intensity, 0, 0))         # Mid tone
        gradient.setColorAt(1.0, QColor(max(0, base_intensity - 50), 0, 0))  # Dark edge
        
        # Set up drawing
        brush = QBrush(gradient)
        pen = QPen(QColor(max(0, base_intensity - 30), 0, 0), 1)
        painter.setBrush(brush)
        painter.setPen(pen)
        
        # Draw 3D ball
        painter.drawEllipse(int(sx - sr), int(sy - sr), int(sr * 2), int(sr * 2))
        
        # Add specular highlight for extra 3D effect
        highlight_size = max(2, sr // 4)
        highlight_brush = QBrush(QColor(255, 255, 255, 120))
        painter.setBrush(highlight_brush)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(
            int(sx - sr * 0.4 - highlight_size // 2),
            int(sy - sr * 0.4 - highlight_size // 2),
            int(highlight_size),
            int(highlight_size)
        )


class MqttThread(QThread):
    message_signal = pyqtSignal(str)
    start_signal = pyqtSignal()
    stop_signal = pyqtSignal()
    restart_signal = pyqtSignal()
    activate_signal = pyqtSignal()
    deactivate_signal = pyqtSignal()

    def __init__(self, broker='localhost', port=1883):
        super().__init__()
        mqtt_config = config.settings.mqtt
        self.data_topics = mqtt_config.data_topics
        self.control_topics = mqtt_config.control_topics
        self.broker = mqtt_config.broker
        self.port = mqtt_config.port
        # Fix MQTT deprecation warning by using callback_api_version
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.subscribed = False

    def run(self):
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.broker, self.port)
        self.client.loop_forever()

    def on_connect(self, client, userdata, flags, rc, properties=None):
        for topic in self.control_topics:
            client.subscribe(topic)

    def on_message(self, client, userdata, msg, properties=None):
        print(f"Received message '{msg.payload.decode()}' on topic '{msg.topic}'")

        if msg.topic == "CubeRoomBall/game/start":
            self.handle_start()
        elif msg.topic == "CubeRoomBall/game/Activate":
            self.handle_Activate()
        elif msg.topic == "CubeRoomBall/game/Deactivate":
            self.deactivate_signal.emit()
        elif msg.topic == "CubeRoomBall/game/stop":
            if msg.payload.decode() == "0":
                self.handle_stop()
            elif msg.payload.decode() == "1":
                self.unsubscribe_from_data_topics()
        elif msg.topic == "CubeRoomBall/game/restart":
            print("Game restarted")
            self.handle_restart()
        elif msg.topic == "CubeRoomBall/game/timer":
            global TimerValue
            TimerValue = int(msg.payload.decode())*1000
            print(TimerValue)
            with open("file2.txt", "w") as file:
                file.write(f"{TimerValue}\n")
        elif msg.topic == "CubeRoomBall/game/timerfinal":
            global final_screen_timer_idle
            final_screen_timer_idle = int(msg.payload.decode())*1000
            print(final_screen_timer_idle)
            with open("file.txt", "w") as file:
                file.write(f"{final_screen_timer_idle}\n")
        else:
            if self.subscribed:
                self.handle_data_message(msg)

    def handle_data_message(self, msg):
        data = msg.payload.decode()
        self.message_signal.emit(data)

    def handle_restart(self):
        print("Game restarted")
        self.subscribe_to_data_topics()
        self.restart_signal.emit()     

    def handle_start(self):
        print("Game started")
        self.subscribe_to_data_topics()
        self.start_signal.emit()

    def handle_Activate(self):
        print("Game Activated")
        self.activate_signal.emit()

    def handle_stop(self):
        print("Game stopped")
        self.unsubscribe_from_data_topics()
        self.stop_signal.emit()
   
    def subscribe_to_data_topics(self):
        if not self.subscribed:
            for topic in self.data_topics:
                self.client.subscribe(topic)
            self.subscribed = True

    def unsubscribe_from_data_topics(self):
        if self.subscribed:
            for topic in self.data_topics:
                self.client.unsubscribe(topic)
            self.subscribed = False
    
    def stop(self):
        """Safely stop the MQTT thread and cleanup resources"""
        logger.debug("Stopping MqttThread...")
        
        try:
            # Unsubscribe from all topics first
            if hasattr(self, 'client') and self.client:
                try:
                    # Unsubscribe from data topics
                    if self.subscribed:
                        for topic in self.data_topics:
                            self.client.unsubscribe(topic)
                        self.subscribed = False
                    
                    # Unsubscribe from control topics
                    for topic in self.control_topics:
                        self.client.unsubscribe(topic)
                    
                    logger.debug(" Unsubscribed from all MQTT topics")
                except Exception as e:
                    logger.warning(f"  Error unsubscribing from topics: {e}")
                
                try:
                    # Disconnect the MQTT client gracefully
                    self.client.loop_stop()  # Stop the network loop
                    self.client.disconnect()  # Disconnect from broker
                    logger.debug(" MQTT client disconnected")
                except Exception as e:
                    logger.warning(f"  Error disconnecting MQTT client: {e}")
                
                self.client = None
        
        except Exception as e:
            logger.warning(f"  Error in MQTT cleanup: {e}")
        
        # Wait for thread to finish gracefully
        if self.isRunning():
            if not self.wait(3000):  # Wait 3 seconds
                logger.warning("  MqttThread did not finish gracefully")
                # Only terminate as last resort
                self.terminate()
                self.wait()
        
        logger.debug(" MqttThread stopped successfully")
    
    def run(self):
        """Run MQTT client with proper error handling and cleanup support"""
        try:
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            self.client.connect(self.broker, self.port)
            self.client.loop_forever()  # This will run until loop_stop() is called
        except Exception as e:
            logger.error(f" MQTT thread error: {e}")
        finally:
            logger.debug("MQTT thread run() method exiting")


class GameManager(QThread):
    """
    Updated GameManager that uses the new GameAPI
    Handles the complete game flow:
    1. Authentication with API
    2. Poll for game initialization 
    3. Poll for game start
    4. Submit final scores
    """
    init_signal = pyqtSignal()
    start_signal = pyqtSignal()
    cancel_signal = pyqtSignal()
    submit_signal = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        logger.info("GameManager initializing...")
        
        # Initialize the GameAPI
        try:
            self.api = GameAPI()
            logger.info(" GameAPI initialized successfully")
        except Exception as e:
            logger.error(f" Failed to initialize GameAPI: {e}")
            raise
            
        # Game state
        self.game_result_id = None
        self.submit_score_flag = False
        self.playStatus = True
        self.started_flag = False
        self.cancel_flag = False
        self.game_done = True
        
        logger.info(" GameManager initialized successfully")
        
    def run(self):
        """Main game loop following the proper API flow"""
        logger.info("GameManager starting main loop...")
        
        while self.playStatus:
            try:
                # Step 1: Authenticate
                logger.info("Step 1: Authenticating...")
                if not hasattr(self, 'api') or self.api is None:
                    logger.error(" GameAPI not initialized")
                    time.sleep(5)
                    continue
                    
                if not self.api.authenticate():
                    logger.error(" Authentication failed, retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                
                # Step 2: Poll for game initialization
                logger.info("Step 2: Polling for game initialization...")
                if not self._poll_initialization():
                    continue
                
                # Step 3: Poll for game start
                logger.info("Step 3: Polling for game start...")
                if not self._poll_game_start():
                    continue
                
                # Step 4: Wait for game completion and submit scores
                logger.info("Step 4: Waiting for game completion...")
                if not self._wait_and_submit_scores():
                    continue
                    
            except Exception as e:
                logger.error(f"Error in game loop: {e}")
                time.sleep(5)
                continue
    
    def _poll_initialization(self) -> bool:
        """Poll for game initialization"""
        while self.playStatus:
            try:
                if not hasattr(self, 'api') or self.api is None:
                    logger.error(" GameAPI not available for initialization polling")
                    return False
                    
                game_data = self.api.poll_game_initialization()
                if game_data:
                    self.game_result_id = game_data.get('id')
                    
                    # Extract team and player information
                    global teamName, list_players_name, list_players_id
                    teamName = game_data.get('name', 'Unknown Team')
                    
                    # Extract player info from nodeIDs
                    node_ids = game_data.get('nodeIDs', [])
                    list_players_name = [player.get('name', f'Player {i+1}') for i, player in enumerate(node_ids)]
                    list_players_id = [player.get('userID', f'user_{i+1}') for i, player in enumerate(node_ids)]
                    
                    logger.info(f"Game initialized: {self.game_result_id}")
                    logger.info(f"Team: {teamName}")
                    logger.info(f"Players: {list_players_name}")
                    
                    # Check if home screen is ready
                    global homeOpened
                    if homeOpened:
                        logger.info("Home screen ready, emitting init signal")
                        homeOpened = False
                        self.init_signal.emit()
                        return True
                    else:
                        logger.info("⏳ Waiting for home screen to be ready...")
                
                time.sleep(3)  # Poll every 3 seconds
                
            except Exception as e:
                logger.error(f" Error polling initialization: {e}")
                time.sleep(5)
                
        return False
    
    def _poll_game_start(self) -> bool:
        """Poll for game start and continue monitoring during gameplay - Like CAGE_Game.py"""
        if not self.game_result_id:
            logger.error(" No game result ID available")
            return False
        
        logger.info(f"Starting polling with started_flag={self.started_flag}, cancel_flag={self.cancel_flag}")
        logger.info("Starting continuous polling for game start...")
        
        # Create a simple reference object to avoid lambda timing issues
        class FlagRef:
            def __init__(self, manager):
                self.manager = manager
            def __call__(self, value=None):
                if value is not None:
                    self.manager.started_flag = value
                return self.manager.started_flag
        
        flag_ref = FlagRef(self)
        
        try:
            # Check API availability
            if not hasattr(self, 'api') or self.api is None:
                logger.error(" GameAPI not available for game start polling")
                return False
                
            # Phase 1: Wait for game to start using continuous polling like CAGE
            game_data = self.api.poll_game_start_continuous(
                game_result_id=self.game_result_id,
                submit_score_flag_ref=lambda: self.submit_score_flag,
                started_flag_ref=flag_ref,
                cancel_flag_ref=lambda x: setattr(self, 'cancel_flag', x)
            )
            
            if game_data:
                status = game_data.get('status')
                
                if status == 'playing' and not self.started_flag:
                    logger.info("Game start signal received!")
                    self.start_signal.emit()
                    self.started_flag = True
                    
                    logger.info(" Start signal emitted successfully!")
                    logger.info("Now subsequent 'playing' responses will be ignored")
                    
                    # Phase 2: Continue monitoring during gameplay
                    logger.info("Game started - continuing to monitor for cancellation...")
                    return self._monitor_during_gameplay()
                    
                elif status == 'cancel' or game_data.get('cancelled'):
                    logger.warning("️  Game cancelled before starting")
                    self.cancel_flag = True
                    # CRITICAL: Reset started_flag IMMEDIATELY before emitting cancel
                    self.started_flag = False
                    logger.warning(f"started_flag reset to False before cancel: {self.started_flag}")
                    self.cancel_signal.emit()
                    # Manual reset of essential flags only
                    self.game_result_id = None
                    self.submit_score_flag = False
                    return False
                elif status == 'submit_triggered':
                    logger.info("Score submission triggered before game start")
                    return True
                else:
                    logger.warning(f"️  Unexpected status: {status}")
                    return False
            else:
                logger.warning("️  No game data returned from continuous polling")
                return False
                
        except Exception as e:
            logger.error(f" Error in game start polling: {e}")
            return False
    
    def _monitor_during_gameplay(self) -> bool:
        """Continue monitoring for cancellation during active gameplay (from CAGE)"""
        logger.info("Monitoring for cancellation during gameplay...")
        
        try:
            # Create a callback to check if game has stopped
            def game_stopped_check():
                # Only check if game has stopped AFTER it has actually started
                # This prevents race condition where polling starts before UI sets gameStarted=True
                global gameStarted
                
                # First, give the UI thread time to process the start signal
                # Only check for stop if we're confident the game was actually running
                import time
                current_time = time.time()
                if not hasattr(game_stopped_check, 'start_time'):
                    game_stopped_check.start_time = current_time
                
                # Only start checking for game stop after 2 seconds of polling
                if current_time - game_stopped_check.start_time < 2.0:
                    return False
                
                # Now check if game has actually stopped (timers stopped)
                if not gameStarted:
                    logger.info("Game timers stopped (gameStarted=False) - stopping API polling")
                    return True
                    
                return False
            
            # Check API availability
            if not hasattr(self, 'api') or self.api is None:
                logger.error(" GameAPI not available for gameplay monitoring")
                return False
                
            # Continue continuous polling during gameplay with stop check - Like CAGE
            game_data = self.api.poll_game_start_continuous(
                game_result_id=self.game_result_id,
                submit_score_flag_ref=lambda: self.submit_score_flag,
                started_flag_ref=lambda: self.started_flag,
                cancel_flag_ref=lambda x: setattr(self, 'cancel_flag', x),
                game_stopped_check=game_stopped_check
            )
            
            if game_data:
                status = game_data.get('status')
                logger.info(f"Gameplay monitoring completed with status: {status}")
                
                if status == 'cancel' or game_data.get('cancelled'):
                    logger.warning("️  Game cancelled during gameplay")
                    self.cancel_flag = True
                    # CRITICAL: Reset started_flag IMMEDIATELY before emitting cancel
                    self.started_flag = False
                    logger.warning(f"started_flag reset to False during gameplay cancel: {self.started_flag}")
                    self.cancel_signal.emit()
                    # Manual reset of essential flags only
                    self.game_result_id = None
                    self.submit_score_flag = False
                    return False
                elif status == 'submit_triggered':
                    logger.info("Score submission triggered during gameplay")
                    return True
                else:
                    logger.info(f"Gameplay monitoring completed with status: {status}")
                    return True
            else:
                logger.warning("️  No game data returned during gameplay monitoring")
                return False
                
        except Exception as e:
            logger.error(f" Error monitoring during gameplay: {e}")
            return False
    
    def _wait_and_submit_scores(self) -> bool:
        """Wait for game completion and submit scores"""
        retry_count = 0
        max_retries = 3
        
        while self.playStatus and not self.cancel_flag:
            if self.submit_score_flag:
                logger.info(f"Score submission flag detected, attempt {retry_count + 1}/{max_retries}")
                try:
                    # Prepare individual scores
                    global scored, list_players_id
                    individual_scores = self._prepare_individual_scores(scored, list_players_id)
                    logger.info(f"Prepared individual scores: {individual_scores}")
                    
                    # SAVE PLAYER DATA TO CSV FIRST (before API submission)
                    logger.info("Saving CubeGame player data to CSV before API submission...")
                    self._save_individual_players_csv(self.game_result_id, individual_scores, None)  # None = pre-submission
                    self._save_pre_submission_log(self.game_result_id, individual_scores)
                    logger.info(" CubeGame player data saved locally before submission")
                    
                    # Submit scores with API safety check
                    if not hasattr(self, 'api') or self.api is None:
                        logger.error(" GameAPI not available for score submission")
                        return False
                    
                    # Submit scores using original method (keep as main submitter)
                    logger.info(f"Now submitting CubeGame scores to API with game_result_id: {self.game_result_id}")
                    success = self.api.submit_final_scores(self.game_result_id, individual_scores)
                    
                    # Save player CSV with final submission status (after API submission)
                    self._save_individual_players_csv(self.game_result_id, individual_scores, success)
                    
                    if success:
                        logger.info(" Scores submitted successfully")
                        # Get updated leaderboard
                        self._update_leaderboard()
                        self.submit_signal.emit()
                        self._reset_game_state()
                        return True
                    else:
                        retry_count += 1
                        logger.error(f" Failed to submit scores (attempt {retry_count}/{max_retries})")
                        
                        if retry_count >= max_retries:
                            logger.error(" Max retries reached, giving up on score submission")
                            # Reset flags to prevent infinite loop
                            self.submit_score_flag = False
                            self._reset_game_state()
                            return False
                        
                        time.sleep(2)  # Shorter retry delay
                        
                except Exception as e:
                    retry_count += 1
                    logger.error(f" Error submitting scores (attempt {retry_count}/{max_retries}): {e}")
                    
                    if retry_count >= max_retries:
                        logger.error(" Max retries reached due to exceptions, giving up on score submission")
                        # Reset flags to prevent infinite loop
                        self.submit_score_flag = False
                        self._reset_game_state()
                        return False
                    
                    time.sleep(2)  # Shorter retry delay
            else:
                time.sleep(1)  # Check every second for score submission flag
                
        logger.warning("️  Exiting _wait_and_submit_scores due to playStatus=False or cancel_flag=True")
        return False
    
    def _prepare_individual_scores(self, total_score: int, player_ids: list) -> list:
        """Prepare individual scores in the required format"""
        if not player_ids:
            logger.warning("️  No player IDs available, using default")
            player_ids = ["default_user"]
        
        # Distribute score among players (first player gets any remainder)
        base_score = total_score // len(player_ids)
        remainder = total_score % len(player_ids)
        
        individual_scores = []
        for i, user_id in enumerate(player_ids):
            score = base_score + (remainder if i == 0 else 0)
            individual_scores.append({
                "userID": user_id,
                "nodeID": i + 1,
                "score": score
            })
        
        logger.info(f"Prepared scores for {len(individual_scores)} players")
        return individual_scores
    
    def _save_individual_players_csv(self, game_result_id: str, individual_scores: list, success: bool):
        """Save individual player scores for database revision"""
        try:
            csv_filename = "CubeGame_Individual_Players_Log.csv"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Check if file exists to determine if we need headers
            file_exists = os.path.exists(csv_filename)
            
            with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'timestamp', 'game_result_id', 'user_id', 'node_id', 
                    'individual_score', 'submission_success', 'status'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header if file is new
                if not file_exists:
                    writer.writeheader()
                    logger.info(f"Created new individual players log file: {csv_filename}")
                
                # Determine status based on success parameter
                if success is None:
                    status = "pre_submission"
                elif success:
                    status = "submitted_success"
                else:
                    status = "submitted_failed"
                
                # Write one row per player
                for score_data in individual_scores:
                    writer.writerow({
                        'timestamp': timestamp,
                        'game_result_id': game_result_id,
                        'user_id': score_data.get('userID', 'Unknown'),
                        'node_id': score_data.get('nodeID', 'N/A'),
                        'individual_score': score_data.get('score', 0),
                        'submission_success': success,
                        'status': status
                    })
                
            if success is None:
                logger.info(f"Player data saved to {csv_filename} BEFORE API submission")
            else:
                logger.info(f"Player data status updated in {csv_filename} AFTER API submission")
            
        except Exception as e:
            logger.error(f" Error saving individual players log to CSV: {e}")
            # Don't let CSV errors break the game flow
    
    def _save_pre_submission_log(self, game_result_id: str, individual_scores: list):
        """Save a pre-submission log entry for safety"""
        try:
            csv_filename = "CubeGame_Pre_Submission_Backup.csv"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Check if file exists to determine if we need headers
            file_exists = os.path.exists(csv_filename)
            
            with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'timestamp', 'game_result_id', 'total_players', 'total_score', 
                    'player_ids', 'individual_scores_json', 'status'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header if file is new
                if not file_exists:
                    writer.writeheader()
                    logger.info(f"Created new pre-submission backup file: {csv_filename}")
                
                # Calculate totals
                total_players = len(individual_scores)
                total_score = sum(score_data.get('score', 0) for score_data in individual_scores)
                
                # Create player IDs list
                player_ids = [score_data.get('userID', 'Unknown') for score_data in individual_scores]
                player_ids_str = " | ".join(player_ids)
                
                # Convert individual scores to JSON string for complete backup
                individual_scores_json = json.dumps(individual_scores)
                
                writer.writerow({
                    'timestamp': timestamp,
                    'game_result_id': game_result_id,
                    'total_players': total_players,
                    'total_score': total_score,
                    'player_ids': player_ids_str,
                    'individual_scores_json': individual_scores_json,
                    'status': 'saved_before_submission'
                })
                
            logger.info(f"Pre-submission backup saved to {csv_filename}")
            logger.info(f"   Game ID: {game_result_id}")
            logger.info(f"   Players: {total_players}")
            logger.info(f"   Total Score: {total_score}")
            
        except Exception as e:
            logger.error(f" Error saving pre-submission backup: {e}")
            # Don't let CSV errors break the game flow
    
    def _update_leaderboard(self):
        """Update the leaderboard data"""
        try:
            global list_top5_TheCage
            leaderboard = self.api.get_leaderboard()
            list_top5_TheCage.clear()
            list_top5_TheCage.extend(leaderboard)

            logger.info(f"Leaderboard updated with {len(leaderboard)} entries")
        except Exception as e:
            logger.error(f" Error updating leaderboard: {e}")
    
    def _reset_game_state(self):
        """Reset game state for next round"""
        logger.info("Resetting game state for next round")
        self.game_result_id = None
        self.submit_score_flag = False
        self.started_flag = False
        self.cancel_flag = False
        
        # Reset global game variables
        global scored, serial_scoring_active
        # scored = 0
        serial_scoring_active = False
    
    def trigger_score_submission(self):
        """Trigger score submission (called when game ends)"""
        logger.info("Score submission triggered")
        logger.info(f"Current game state: game_result_id={self.game_result_id}, started_flag={self.started_flag}, cancel_flag={self.cancel_flag}")
        global scored, list_players_id
        logger.info(f"Game data: scored={scored}, list_players_id={list_players_id}")
        self.submit_score_flag = True
        logger.info(f"submit_score_flag set to: {self.submit_score_flag}")
    
    def stop_manager(self):
        """Stop the game manager with comprehensive cleanup"""
        logger.info("Stopping GameManager...")
        
        try:
            # Stop the game loop
            self.playStatus = False
            
            # Disconnect all signals
            try:
                self.init_signal.disconnect()
                self.start_signal.disconnect()
                self.cancel_signal.disconnect()
                self.submit_signal.disconnect()
                logger.debug(" GameManager signals disconnected")
            except Exception as e:
                logger.warning(f"️  Error disconnecting signals: {e}")
            
            # Clean up API object
            if hasattr(self, 'api') and self.api:
                try:
                    # The GameAPI object doesn't have explicit cleanup,
                    # but we can clear the reference
                    self.api = None
                    logger.debug(" GameAPI reference cleared")
                except Exception as e:
                    logger.warning(f"️  Error cleaning API: {e}")
            
            # Reset game state
            try:
                self._reset_game_state()
                logger.debug(" Game state reset")
            except Exception as e:
                logger.warning(f"️  Error resetting game state: {e}")
        
        except Exception as e:
            logger.warning(f"️  Error in GameManager cleanup: {e}")
        
        # Stop the thread gracefully
        try:
            self.quit()
            if not self.wait(5000):  # Wait up to 5 seconds
                logger.warning("️  GameManager thread did not finish gracefully")
                # Don't use terminate() unless absolutely necessary
            logger.debug(" GameManager stopped successfully")
        except Exception as e:
            logger.warning(f"️  Error stopping GameManager thread: {e}")


class Final_Screen(QtWidgets.QMainWindow):
    """Complete Final Screen implementation"""
    
    def load_custom_font(self, font_path):
        font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            print(f"Failed to load font: {font_path}")
            return "Default"
        font_families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
        if font_families:
            return font_families[0]
        return "Default"
    
    def showTable(self):
        if hasattr(self, 'Label'):
            self.Label.hide()
        self.Label2.show()
        self.Label_team_name.show()
        self.LeaderboardTable.show()
        self.UpdateTable()
    
    def TimerWidget(self, centralwidget):
        self.Countdown = QtWidgets.QWidget(centralwidget)
        self.Label = QtWidgets.QLabel(centralwidget)
    
    def hideTable(self):
        if hasattr(self, 'Label2'):
            self.Label2.hide()
        if hasattr(self, 'Label_team_name'):
            self.Label_team_name.hide()
        if hasattr(self, 'LeaderboardTable'):
            self.LeaderboardTable.hide()

    def setupTimer(self):
        # Start the GIF
        self.movie.start()
    
    def setupUi(self, Home):
        Home.setObjectName("Home")
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        Home.setLayoutDirection(QtCore.Qt.LeftToRight)
        Home.setAutoFillBackground(False)
        
        self.centralwidget = QtWidgets.QWidget(Home)
        Home.setGeometry(0, 0, QtWidgets.QDesktopWidget().screenGeometry().width(), QtWidgets.QDesktopWidget().screenGeometry().height())
        print(Home.geometry().width())
        self.font_family = self.load_custom_font("Assets/Fonts/GOTHIC.TTF")
        self.font_family_good = self.load_custom_font("Assets/Fonts/good_times_rg.ttf")

        if Home.geometry().width() > 1920:
            self.movie = QMovie("Assets/1k/CubeRoomBall_final.gif")
            self.movie.setCacheMode(QMovie.CacheAll)
            self.scale = 2
        else:
            self.movie = QMovie("Assets/1k/CubeRoomBall_final.gif")
            self.movie.setCacheMode(QMovie.CacheAll)
            self.scale = 1
        
        self.Background = QtWidgets.QLabel(self.centralwidget)
        self.Background.setScaledContents(True)
        self.Background.setGeometry(0, 0, Home.geometry().width(), Home.geometry().height())
        self.Background.setText("")
        self.Background.setMovie(self.movie)
        self.Background.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
        self.TimerWidget(self.centralwidget)
        
        # Score label
        self.Label2 = QtWidgets.QLabel(self.centralwidget)
        self.Label2.setGeometry(QtCore.QRect(303*self.scale, 609*self.scale, 390*self.scale, 122*self.scale))
        global scored
        self.Label2.setText(str(scored))
        self.Label2.setAlignment(QtCore.Qt.AlignCenter)
        font = QtGui.QFont()
        font.setPointSize(39*self.scale)
        font.setFamily(self.font_family_good)
        self.Label2.setFont(font)
        self.Label2.setStyleSheet("color: rgb(255, 255, 255);")
        self.Label2.hide()
        self.Label2.raise_()
        
        # Team name label
        self.Label_team_name = QtWidgets.QLabel(self.centralwidget)
        self.Label_team_name.setGeometry(QtCore.QRect(108*self.scale, 452*self.scale, 780*self.scale, 122*self.scale))
        global teamName
        self.Label_team_name.setText(teamName)
        self.Label_team_name.setAlignment(QtCore.Qt.AlignCenter)
        font_team = QtGui.QFont()
        font_team.setPointSize(40*self.scale)
        font_team.setFamily(self.font_family_good)
        self.Label_team_name.setFont(font_team)
        self.Label_team_name.setStyleSheet("color: rgb(255, 255, 255);")
        self.Label_team_name.hide()
        self.Label_team_name.raise_()
        
        # Create leaderboard table
        self.frame_2 = QtWidgets.QFrame(self.centralwidget)
        self.frame_2.setGeometry(QtCore.QRect(1009*self.scale, 359*self.scale, 802*self.scale, 595*self.scale))
        self.gridLayout = QtWidgets.QGridLayout(self.frame_2)
        self.LeaderboardTable = QtWidgets.QTableWidget(self.frame_2)
        self.LeaderboardTable.setRowCount(5)
        self.LeaderboardTable.setColumnCount(2)
        
        # Set up table properties
        font = QtGui.QFont()
        font.setFamily(self.font_family_good)
        font.setPointSize(22*self.scale)
        font.setBold(False)
        font.setItalic(False)
        self.LeaderboardTable.setFont(font)
        self.LeaderboardTable.setFocusPolicy(QtCore.Qt.NoFocus)
        self.LeaderboardTable.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.LeaderboardTable.setAutoFillBackground(False)
        self.LeaderboardTable.setLineWidth(0)
        self.LeaderboardTable.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.LeaderboardTable.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.LeaderboardTable.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.LeaderboardTable.setAutoScroll(False)
        self.LeaderboardTable.setAutoScrollMargin(0)
        self.LeaderboardTable.setProperty("showDropIndicator", False)
        self.LeaderboardTable.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.LeaderboardTable.setTextElideMode(QtCore.Qt.ElideLeft)
        self.LeaderboardTable.setShowGrid(False)
        self.LeaderboardTable.setGridStyle(QtCore.Qt.NoPen)
        self.LeaderboardTable.setWordWrap(True)
        self.LeaderboardTable.setCornerButtonEnabled(True)
        self.LeaderboardTable.setObjectName("LeaderboardTable")
        
        # Custom palette configuration for LeaderboardTable - consistent across all states
        palette = QtGui.QPalette()
        
        # Define color scheme once
        white_text = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        white_text.setStyle(QtCore.Qt.SolidPattern)
        transparent_bg = QtGui.QBrush(QtGui.QColor(0, 0, 0, 0))
        transparent_bg.setStyle(QtCore.Qt.SolidPattern)
        light_blue = QtGui.QBrush(QtGui.QColor(102, 171, 255))
        light_blue.setStyle(QtCore.Qt.SolidPattern)
        mid_blue = QtGui.QBrush(QtGui.QColor(65, 142, 235))
        mid_blue.setStyle(QtCore.Qt.SolidPattern)
        dark_blue = QtGui.QBrush(QtGui.QColor(14, 57, 108))
        dark_blue.setStyle(QtCore.Qt.SolidPattern)
        medium_blue = QtGui.QBrush(QtGui.QColor(19, 75, 144))
        medium_blue.setStyle(QtCore.Qt.SolidPattern)
        no_brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        no_brush.setStyle(QtCore.Qt.NoBrush)
        black_shadow = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        black_shadow.setStyle(QtCore.Qt.SolidPattern)
        alt_blue = QtGui.QBrush(QtGui.QColor(141, 184, 235))
        alt_blue.setStyle(QtCore.Qt.SolidPattern)
        tooltip_bg = QtGui.QBrush(QtGui.QColor(255, 255, 220))
        tooltip_bg.setStyle(QtCore.Qt.SolidPattern)
        disabled_alt_blue = QtGui.QBrush(QtGui.QColor(28, 113, 216))
        disabled_alt_blue.setStyle(QtCore.Qt.SolidPattern)
        
        # Apply IDENTICAL styling to ALL states (Active, Inactive, Disabled)
        for state in [QtGui.QPalette.Active, QtGui.QPalette.Inactive, QtGui.QPalette.Disabled]:
            palette.setBrush(state, QtGui.QPalette.WindowText, white_text)
            palette.setBrush(state, QtGui.QPalette.Button, transparent_bg)
            palette.setBrush(state, QtGui.QPalette.Light, light_blue)
            palette.setBrush(state, QtGui.QPalette.Midlight, mid_blue)
            palette.setBrush(state, QtGui.QPalette.Dark, dark_blue)
            palette.setBrush(state, QtGui.QPalette.Mid, medium_blue)
            palette.setBrush(state, QtGui.QPalette.Text, white_text)
            palette.setBrush(state, QtGui.QPalette.BrightText, white_text)
            palette.setBrush(state, QtGui.QPalette.ButtonText, white_text)
            palette.setBrush(state, QtGui.QPalette.Base, no_brush)
            palette.setBrush(state, QtGui.QPalette.Window, transparent_bg)
            palette.setBrush(state, QtGui.QPalette.Shadow, black_shadow)
            palette.setBrush(state, QtGui.QPalette.Highlight, transparent_bg)
            palette.setBrush(state, QtGui.QPalette.HighlightedText, white_text)
            palette.setBrush(state, QtGui.QPalette.ToolTipBase, tooltip_bg)
            palette.setBrush(state, QtGui.QPalette.ToolTipText, black_shadow)
            palette.setBrush(state, QtGui.QPalette.PlaceholderText, white_text)
            
            # Use different AlternateBase for disabled state
            if state == QtGui.QPalette.Disabled:
                palette.setBrush(state, QtGui.QPalette.AlternateBase, disabled_alt_blue)
            else:
                palette.setBrush(state, QtGui.QPalette.AlternateBase, alt_blue)
        
        self.LeaderboardTable.setPalette(palette)
        
        # Gradient palette styling to match the provided image
        self.LeaderboardTable.setStyleSheet("""
            /* QTableWidget Styling - Gradient Blue Palette */
            QTableWidget {
                background: transparent;
                color: #ffffff;  /* White text color */
                gridline-color: rgba(255, 255, 255, 100);  /* Semi-transparent white gridlines */
                selection-background-color: rgba(255, 255, 255, 50);  /* Light selection */
                selection-color: #ffffff;  /* White selection text */
                border: none;  /* No border */
                border-radius: 10px;  /* Rounded corners */
                padding: 8px;
                margin: 4px;
            }

            QHeaderView::section { 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20, 40, 73, 140),      /* #142849 with 55% transparency for headers */
                    stop:0.5 rgba(107, 53, 39, 140),   /* #6b3527 with 55% transparency */
                    stop:1 rgba(181, 102, 59, 140));   /* #b5663b with 55% transparency */
                color: #ffffff;  /* White text color for header sections */
                padding: 12px;  /* Increased padding for header sections */
                border: none;  /* No border */
                border-radius: 5px;  /* Rounded header corners */
                font-weight: bold;  /* Bold font for headers */
                font-family: """ + self.font_family_good + """;  /* Same font as table */
                font-size: """ + str(int(26*self.scale)) + """px;  /* Larger font size */
                margin: 2px;
            }

            QHeaderView {
                background-color: transparent;  /* Transparent background */
                border: none;
            }

            QTableCornerButton::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20, 40, 73, 140),      /* #142849 with 55% transparency */
                    stop:0.5 rgba(107, 53, 39, 140),   /* #6b3527 with 55% transparency */
                    stop:1 rgba(181, 102, 59, 140));   /* #b5663b with 55% transparency */
                border: none;  /* No border */
                border-radius: 5px;
            }

            QTableWidget::item {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20, 40, 73, 102),      /* #142849 with 40% transparency */
                    stop:0.5 rgba(107, 53, 39, 102),   /* #6b3527 with 40% transparency */
                    stop:1 rgba(181, 102, 59, 102));   /* #b5663b with 40% transparency */
                padding: 8px;  /* More padding for items */
                border: none;  /* No border for items */
                color: #ffffff;  /* White text color */
                background: rgba(255, 255, 255, 20);  /* Very subtle background */
                margin: 1px;
                border-radius: 3px;
            }

            QTableWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 100),
                    stop:1 rgba(20, 40, 73, 150));     /* #142849 for selected */
                color: #ffffff;  /* White text for selected items */
                border: none;  /* No border */
            }

            QTableWidget::item:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 80),
                    stop:1 rgba(107, 53, 39, 150));    /* #6b3527 for hover */
                color: #ffffff;  /* White text on hover */
                border: none;  /* No border */
            }

            QTableWidget::item:focus {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 120),
                    stop:1 rgba(181, 102, 59, 180));   /* #b5663b for focus */
                color: #ffffff;  /* White text on focus */
                border: none;  /* No border */
            }
        """)
        
        # Create table items with enhanced properties
        for i in range(5):
            for j in range(2):
                item = QtWidgets.QTableWidgetItem()
                if j == 0:
                    item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                else:
                    item.setTextAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
                self.LeaderboardTable.setItem(i, j, item)
        
        # Set horizontal headers with custom properties
        self.LeaderboardTable.setHorizontalHeaderLabels(["Team", "Score"])
        self.LeaderboardTable.horizontalHeader().setVisible(True)
        self.LeaderboardTable.horizontalHeader().setCascadingSectionResizes(False)
        
        # Calculate column widths for the new table width (802px)
        # Account for table padding (8px), margin (4px), and border (2px) on each side
        # Total padding: (8+4+2) * 2 = 28px, plus some extra buffer for internal spacing
        available_width = int(802 * self.scale - 50)  # More conservative padding calculation
        team_column_width = int(available_width * 0.60)    # 60% for team name
        score_column_width = int(available_width * 0.40)   # 40% for score
        
        # Set the first column to a fixed width, let the second column stretch
        self.LeaderboardTable.horizontalHeader().resizeSection(0, team_column_width)
        self.LeaderboardTable.horizontalHeader().setStretchLastSection(True)
        # Alternative: use section resize mode for better control
        from PyQt5.QtWidgets import QHeaderView
        self.LeaderboardTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.LeaderboardTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.LeaderboardTable.verticalHeader().setVisible(False)
        self.LeaderboardTable.verticalHeader().setCascadingSectionResizes(False)
        
        # Calculate row heights for the new table height (595px)
        # Total available height: 595px minus header and padding
        available_height = int(595 * self.scale - 100)  # Account for header and padding
        row_height = int(available_height / 5)  # Distribute equally among 5 rows
        
        for i in range(5):
            self.LeaderboardTable.verticalHeader().resizeSection(i, row_height)
        self.LeaderboardTable.verticalHeader().setStretchLastSection(True)
        
        self.gridLayout.addWidget(self.LeaderboardTable, 0, 0, 1, 1)
        
        Home.setCentralWidget(self.centralwidget)
        self.timer = QTimer(Home)
        self.timer2 = QTimer(Home)
        self.setupTimer()
        self.UpdateTable()
        self.showTable()
        
        self.retranslateUi(Home)
        QtCore.QMetaObject.connectSlotsByName(Home)
    
    def retranslateUi(self, Home):
        _translate = QtCore.QCoreApplication.translate
        Home.setWindowTitle(_translate("Home", "MainWindow"))
        item = self.LeaderboardTable.horizontalHeaderItem(0)
        item.setText(_translate("Home", "Team"))
        item = self.LeaderboardTable.horizontalHeaderItem(1)
        item.setText(_translate("Home", "Score"))

    def UpdateTable(self):
        global list_top5_TheCage
        sorted_data = sorted(list_top5_TheCage, key=lambda item: item[1], reverse=True)
        
        for i, (team, score) in enumerate(sorted_data):
            if i >= 5:
                break

            team_item = QtWidgets.QTableWidgetItem(team)
            team_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.LeaderboardTable.setItem(i, 0, team_item)

            score_item = QtWidgets.QTableWidgetItem(str(score))
            score_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.LeaderboardTable.setItem(i, 1, score_item)
    
    def closeEvent(self, event):
        logger.info("Final screen closing...")
        
        # Safely stop movie
        if hasattr(self, 'movie') and self.movie:
            try:
                self.movie.stop()
                self.movie.setCacheMode(QMovie.CacheNone)
                self.movie = None
                logger.debug(" Movie cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping movie: {e}")
        
        # Safely stop timers (if they exist)
        if hasattr(self, 'timer') and self.timer:
            try:
                self.timer.stop()
                # Disconnect all signals
                try:
                    self.timer.timeout.disconnect()
                except:
                    pass
                self.timer = None
                logger.debug(" Timer cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping timer: {e}")
        
        if hasattr(self, 'timer2') and self.timer2:
            try:
                self.timer2.stop()
                # Disconnect all signals
                try:
                    self.timer2.timeout.disconnect()
                except:
                    pass
                self.timer2 = None
                logger.debug(" Timer2 cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping timer2: {e}")
        
        # Clean up table widget with safe Qt object handling
        try:
            if hasattr(self, 'LeaderboardTable') and self.LeaderboardTable is not None:
                try:
                    self.LeaderboardTable.hide()
                    self.LeaderboardTable.clear()
                    self.LeaderboardTable.deleteLater()
                    logger.debug(" Table widget cleaned up")
                except (RuntimeError, AttributeError):
                    logger.debug("Table widget already deleted by Qt, skipping cleanup")
                finally:
                    self.LeaderboardTable = None
        except (RuntimeError, SystemError, AttributeError):
            logger.debug("Table widget reference already invalid, skipping cleanup")
            self.LeaderboardTable = None
        
        # Clean up frame with safe Qt object handling
        try:
            if hasattr(self, 'frame_2') and self.frame_2 is not None:
                try:
                    self.frame_2.hide()
                    self.frame_2.deleteLater()
                    logger.debug(" Frame cleaned up")
                except (RuntimeError, AttributeError):
                    logger.debug("Frame already deleted by Qt, skipping cleanup")
                finally:
                    self.frame_2 = None
        except (RuntimeError, SystemError, AttributeError):
            logger.debug("Frame reference already invalid, skipping cleanup")
            self.frame_2 = None
        
        # Clean up labels with safe Qt object handling
        for label_name in ['Label2', 'Label_team_name', 'Label', 'Countdown']:
            try:
                if hasattr(self, label_name):
                    label_obj = getattr(self, label_name)
                    if label_obj is not None:
                        try:
                            label_obj.hide()
                            label_obj.deleteLater()
                            logger.debug(f" {label_name} cleaned up")
                        except (RuntimeError, AttributeError):
                            logger.debug(f"{label_name} already deleted by Qt, skipping cleanup")
                        finally:
                            setattr(self, label_name, None)
            except (RuntimeError, SystemError, AttributeError):
                logger.debug(f"{label_name} reference already invalid, skipping cleanup")
                setattr(self, label_name, None)
        
        # Safely clear background with safe Qt object handling
        try:
            if hasattr(self, 'Background') and self.Background is not None:
                try:
                    self.Background.clear()
                    self.Background.setMovie(None)  # Remove movie reference
                    self.Background.deleteLater()
                    logger.debug(" Background cleared")
                except (RuntimeError, AttributeError):
                    logger.debug("Background already deleted by Qt, skipping cleanup")
                finally:
                    self.Background = None
        except (RuntimeError, SystemError, AttributeError):
            logger.debug("Background reference already invalid, skipping cleanup")
            self.Background = None
        
        # Clean up central widget and all its children with safe Qt object handling
        try:
            if hasattr(self, 'centralwidget') and self.centralwidget is not None:
                try:
                    # Clean up all child widgets
                    for child in self.centralwidget.findChildren(QtCore.QObject):
                        child.deleteLater()
                    self.centralwidget.deleteLater()
                    logger.debug(" Central widget cleaned up")
                except (RuntimeError, AttributeError):
                    logger.debug("Central widget already deleted by Qt, skipping cleanup")
                finally:
                    self.centralwidget = None
        except (RuntimeError, SystemError, AttributeError):
            logger.debug("Central widget reference already invalid, skipping cleanup")
            self.centralwidget = None
        
        event.accept()
        logger.info(" Final screen closed successfully with complete cleanup")
        super().closeEvent(event)


class Active_screen(QWidget):
    """Complete Active Screen implementation"""
    
    def __init__(self, st1_scale_thread=None):
        super().__init__()
        self.st1_scale_thread = st1_scale_thread  # Store reference to ST1 scale thread
        
        # Connect to scale thread signals if available
        if self.st1_scale_thread:
            self.st1_scale_thread.score_updated.connect(self.on_score_updated)
            self.st1_scale_thread.connection_status_changed.connect(self.on_connection_status_changed)
            self.st1_scale_thread.error_occurred.connect(self.on_scale_error)
        
        self.init_mqtt_thread()
        self.player = QMediaPlayer()
    
    def init_mqtt_thread(self):
        """Initialize or reinitialize the MQTT thread"""
        if hasattr(self, 'mqtt_thread') and self.mqtt_thread and hasattr(self.mqtt_thread, 'isRunning') and self.mqtt_thread.isRunning():
            return  # Already running
            
        self.mqtt_thread = MqttThread('localhost')
        self.mqtt_thread.start_signal.connect(self.start_game)
        self.mqtt_thread.stop_signal.connect(self.stop_game)
        self.mqtt_thread.restart_signal.connect(self.restart_game)
        self.mqtt_thread.start()
    
    @pyqtSlot(int)
    def on_score_updated(self, score):
        """Handle score updates from the scale thread"""
        try:
            global scored, serial_scoring_active, gameStarted
            
            if gameStarted:  # Only update score if game is active
                scored = score
                serial_scoring_active = True
                
                # Update the score display
                if hasattr(self, 'label_Score'):
                    self.label_Score.setText(f"Score: {scored}")
                
                # Update cube balls count based on score
                ball_count = min(15, max(0, scored))
                set_cube_balls_count(ball_count)
                
                logger.debug(f"Score updated from scale thread: {scored}")
        except Exception as e:
            logger.error(f" Error handling score update: {e}")
    
    @pyqtSlot(bool)
    def on_connection_status_changed(self, connected):
        """Handle connection status changes from the scale thread"""
        try:
            if connected:
                logger.info(" Scale connected in thread")
            else:
                logger.warning("️ Scale disconnected in thread")
        except Exception as e:
            logger.error(f" Error handling connection status: {e}")
    
    @pyqtSlot(str)
    def on_scale_error(self, error_message):
        """Handle errors from the scale thread"""
        try:
            logger.error(f"Scale thread error: {error_message}")
        except Exception as e:
            logger.error(f" Error handling scale error: {e}")
                
    def play_audio(self):
        """Load and play the audio file with safety checks."""
        try:
            # Ensure player is initialized
            if not hasattr(self, 'player') or self.player is None:
                logger.warning("️  MediaPlayer not initialized, creating new one")
                self.player = QMediaPlayer()
            
            audio_file = "Assets/mp3/2066.wav"
            absolute_path = os.path.abspath(audio_file)
            print("Absolute path:", absolute_path)
            
            # Check if file exists
            if not os.path.exists(absolute_path):
                logger.error(f" Audio file not found: {absolute_path}")
                return
                
            self.player.setMedia(QMediaContent(QtCore.QUrl.fromLocalFile(absolute_path)))
            self.player.setVolume(100)
            self.player.play()
            
            # Safely connect signal (disconnect first to avoid multiple connections)
            try:
                self.player.mediaStatusChanged.disconnect()
            except:
                pass  # No existing connection
            self.player.mediaStatusChanged.connect(self.check_media_status)
            
            logger.debug(" Audio playback started successfully")
            
        except Exception as e:
            logger.error(f" Error playing audio: {e}")
    
    def play_audio_2(self):
        """Load and play the audio file with safety checks."""
        try:
            # Ensure player is initialized
            if not hasattr(self, 'player') or self.player is None:
                logger.warning("️  MediaPlayer not initialized, creating new one")
                self.player = QMediaPlayer()
            
            audio_file = "Assets/mp3/2066.wav"
            absolute_path = os.path.abspath(audio_file)
            print("Absolute path:", absolute_path)
            
            # Check if file exists
            if not os.path.exists(absolute_path):
                logger.error(f" Audio file not found: {absolute_path}")
                return
                
            self.player.setMedia(QMediaContent(QtCore.QUrl.fromLocalFile(absolute_path)))
            self.player.setVolume(100)
            self.player.play()
            
            # Safely connect signal (disconnect first to avoid multiple connections)
            try:
                self.player.mediaStatusChanged.disconnect()
            except:
                pass  # No existing connection
            self.player.mediaStatusChanged.connect(self.check_media_status)
            
            logger.debug(" Audio playback started successfully")
            
        except Exception as e:
            logger.error(f" Error playing audio: {e}")
        
    def check_media_status(self, status):
        """Check media status and stop playback if finished."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.player.stop()
        
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        print(MainWindow.geometry().width())

        if MainWindow.geometry().width() > 1920:
            self.movie = QMovie("Assets/1k/CubeRoomBall_Active.gif")
            self.movie.setCacheMode(QMovie.CacheAll)
            print("1")
            self.scale = 2
        else:
            self.movie = QMovie("Assets/1k/CubeRoomBall_Active.gif")
            self.movie.setCacheMode(QMovie.CacheAll)
            print("2")
            self.scale = 1
        
        global TimerValue
        try:
            with open("file2.txt", "r") as file:
                lines = file.readlines()
                if lines:
                    TimerValue = int(lines[-1].strip())
        except FileNotFoundError:
            print("file2.txt not found. Using default timer value.")
            TimerValue = 30000

        self.centralwidget = QtWidgets.QWidget(MainWindow)
        MainWindow.setCentralWidget(self.centralwidget)
        
        # Load fonts
        self.font_family = self.load_custom_font("Assets/Fonts/GOTHIC.TTF")
        self.font_family_good = self.load_custom_font("Assets/Fonts/good_times_rg.ttf")
        
        # Background
        self.Background = QtWidgets.QLabel(self.centralwidget)
        self.Background.setGeometry(QtCore.QRect(0, 0, 1920*self.scale, 1080*self.scale))
        self.Background.setText("")
        self.Background.setScaledContents(True)

        

        
        # Team name label (original position - right side)
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(187*self.scale, 232*self.scale, 557*self.scale, 122*self.scale))
        self.label.setText(teamName)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        font = QtGui.QFont()
        font.setPointSize(35*self.scale)
        font.setFamily(self.font_family_good)
        self.label.setFont(font)
        self.label.setStyleSheet("color: rgb(255,255,255);")
        
        
        
        # Score label
        self.label_Score = QtWidgets.QLabel(self.centralwidget)
        self.label_Score.setGeometry(QtCore.QRect(1295*self.scale, 232*self.scale, 390*self.scale, 122*self.scale))
        self.label_Score.setAlignment(QtCore.Qt.AlignCenter)
        self.label_Score.setText("Score: "+str(scored))
        font = QtGui.QFont()
        font.setPointSize(39*self.scale)
        font.setFamily(self.font_family_good)
        self.label_Score.setFont(font)
        self.label_Score.setStyleSheet("color: rgb(255,255,255);")
        
        # Timer label (replacing LCD)
        self.label_timer = QtWidgets.QLabel(self.centralwidget)
        self.label_timer.setGeometry(QtCore.QRect(802*self.scale, 232*self.scale, 390*self.scale, 122*self.scale))
        self.label_timer.setAlignment(QtCore.Qt.AlignCenter)
        self.label_timer.setText("00:00")
        font_timer = QtGui.QFont()
        font_timer.setPointSize(45*self.scale)
        font_timer.setFamily(self.font_family_good)
        self.label_timer.setFont(font_timer)
        self.label_timer.setStyleSheet("color: rgb(255,255,255);")
        
        self.set_timer_text(TimerValue//1000)
        
        # Initialize 3D Cube Widget
        self.cube_widget = CubeAndBallWidget(
            width=int(1800 * self.scale), 
            height=int(1000 * self.scale), 
            parent=self.centralwidget
        )
        # Position the cube widget at adjusted coordinates (centered better for larger size)
        self.cube_widget.setGeometry(QtCore.QRect(
            int(60 * self.scale),  # Adjusted X to fit larger widget
            int(140 * self.scale),  # Adjusted Y to fit larger widget  
            int(1800 * self.scale), 
            int(1000 * self.scale)
        ))
        
        # Initialize Matrix Widget with scaled positioning
        # self.setup_matrix_widget()
        
        self.Background.setMovie(self.movie)
        self.movie.start()
        
        # Game timer
        self.TimerGame = QTimer(MainWindow)
        self.TimerGame.setSingleShot(True)
        self.TimerGame.setTimerType(QtCore.Qt.PreciseTimer)
        self.TimerGame.timeout.connect(self.stop_game)
       
        self.timer_one_second = QtCore.QTimer(MainWindow)
        self.timer_one_second.setTimerType(QtCore.Qt.PreciseTimer)
        self.timer_one_second.timeout.connect(self.update_timer)
        self.countdown_time = TimerValue//1000

        # Raise elements to proper layer order
        self.Background.setObjectName("Background")
        self.Background.raise_()
        self.cube_widget.raise_()
        self.label.raise_()
        self.label_Score.raise_()
        self.label_timer.raise_()
        
        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)
    
    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
    
    def set_timer_text(self, value):
        """Set the timer text to the given value in MM:SS format"""
        minutes = value // 60
        seconds = value % 60
        timer_text = f"{minutes:02d}:{seconds:02d}"
        self.label_timer.setText(timer_text)
        
    def update_timer(self):
        global RemainingTime, cube_balls_count
        
        self.countdown_time -= 1
        if gamefinished == True:
            global scored, serial_scoring_active
            
            # No bonuses applied regardless of serial communication status
            if serial_scoring_active:
                print(f"Game finished! Final Score: {scored} (serial score)")
            else:
                print(f"Game finished! Final Score: {scored} (no bonuses applied)")
            
            self.stop_game()
        
        if self.countdown_time == 0:
            self.timer_one_second.stop()
            self.set_timer_text(0)
            # Change timer color to red when time's up
            self.label_timer.setStyleSheet("color: rgb(244,28,23);")
        
        self.label_Score.setText("Score: "+str(scored))
        RemainingTime = self.countdown_time
        self.set_timer_text(self.countdown_time)
        
        cube_balls_count = self.countdown_time
    
    @pyqtSlot()
    def start_game(self):
        global gameStarted, firstDetected, cube_balls_count, serial_scoring_active
        gameStarted = True
        # Reset serial scoring flag at game start
        serial_scoring_active = False
        
        # Connect to ST1 scale thread when game starts
        if self.st1_scale_thread:
            logger.info(" ST1 scale thread connecting...")
            self.st1_scale_thread.connect_for_game()
            self.st1_scale_thread.start_monitoring()
        
        self.timer_one_second.start(1000)
        self.TimerGame.start(TimerValue)
        print("start")
        self.play_audio()
        
        # Start with some balls in the cube
        # cube_balls_count = 3

    @pyqtSlot()
    def stop_game(self):
        global teamName, scored, gameStarted, firstDetected, gamefinished, cube_balls_count
        
        # Cancel any existing deactivate timer first to prevent multiple timers
        if hasattr(self, 'deactivate_timer') and self.deactivate_timer:
            self.deactivate_timer.stop()
            self.deactivate_timer = None
        
        self.label_Score.setText("Score: "+str(scored))
        self.TimerGame.stop()
        self.timer_one_second.stop()
        self.save_final_score_to_csv(teamName, scored)

        self.play_audio_2()
        gameStarted = False
        firstDetected = False
        gamefinished = False
        
        # Stop scale thread monitoring and disconnect when game stops
        if self.st1_scale_thread:
            logger.info(" ST1 scale thread disconnecting...")
            self.st1_scale_thread.stop_monitoring()
            self.st1_scale_thread.disconnect_for_game()
        
        # Clear balls from cube when game stops
        cube_balls_count = 0
        
        
        # Emit deactivate signal directly after 5 seconds to trigger score submission
        def emit_deactivate_signal():
            if self.mqtt_thread and hasattr(self.mqtt_thread, 'deactivate_signal'):
                self.mqtt_thread.deactivate_signal.emit()
                print("deactivate signal emitted")
            else:
                print("mqtt_thread is None, deactivate signal not emitted")
            # Clear the timer reference after execution
            self.deactivate_timer = None
        
        # Store timer reference so it can be cancelled during cleanup
        self.deactivate_timer = QtCore.QTimer()
        self.deactivate_timer.setSingleShot(True)
        self.deactivate_timer.timeout.connect(emit_deactivate_signal)
        self.deactivate_timer.start(5000)
        
        print("stop")
    
    def save_final_score_to_csv(self, team_name, final_score):
        """Save final score to CSV file"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        csv_file_path = "CubeGame.csv"
        
        try:
            with open(csv_file_path, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([team_name, final_score, current_time])
            print("Score saved successfully.")
        except Exception as e:
            print(f"An error occurred while saving the score to CSV: {e}")
    
    @pyqtSlot()
    def restart_game(self):
        self.TimerGame.start(TimerValue)
        print("restart")
        
    def stop_movie(self):
        self.TimerGame.stop()
        
    def load_custom_font(self, font_path):
        font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            print(f"Failed to load font: {font_path}")
            return "Default"
        font_families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
        if font_families:
            return font_families[0]
        return "Default"

    def closeEvent(self, event):
        print("close in active screen")
        logger.info("Active screen closing...")
        
        # Stop and cleanup media player
        if hasattr(self, 'player') and self.player:
            try:
                self.player.stop()
                self.player.setMedia(QMediaContent())  # Clear media
                # Disconnect all signals
                try:
                    self.player.mediaStatusChanged.disconnect()
                except:
                    pass
                self.player = None
                logger.debug(" Media player cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping media player: {e}")
        
        # Safely stop movie
        if hasattr(self, 'movie') and self.movie:
            try:
                self.movie.stop()
                self.movie.setCacheMode(QMovie.CacheNone)
                self.movie = None
                logger.debug(" Movie cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping movie: {e}")
        
        # Cleanup cube widget
        if hasattr(self, 'cube_widget') and self.cube_widget:
            try:
                self.cube_widget.timer.stop()
                self.cube_widget.balls.clear()
                self.cube_widget = None
                logger.debug(" Cube widget cleaned up")
            except Exception as e:
                logger.warning(f"️  Error cleaning up cube widget: {e}")
        
        # Stop and cleanup MQTT thread
        if hasattr(self, 'mqtt_thread') and self.mqtt_thread:
            try:
                # Disconnect all signals first
                try:
                    self.mqtt_thread.start_signal.disconnect()
                    self.mqtt_thread.stop_signal.disconnect()
                    self.mqtt_thread.restart_signal.disconnect()
                    if hasattr(self.mqtt_thread, 'deactivate_signal'):
                        self.mqtt_thread.deactivate_signal.disconnect()
                    if hasattr(self.mqtt_thread, 'activate_signal'):
                        self.mqtt_thread.activate_signal.disconnect()
                    if hasattr(self.mqtt_thread, 'message_signal'):
                        self.mqtt_thread.message_signal.disconnect()
                except:
                    pass
                
                # Stop the thread gracefully using the new stop() method
                self.mqtt_thread.stop()
                self.mqtt_thread = None
                logger.debug(" MQTT thread cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping MQTT thread: {e}")
        
        # Reset global game state
        global gameStarted
        gameStarted = False
        

        
        # Safely stop timers
        if hasattr(self, 'deactivate_timer') and self.deactivate_timer:
            try:
                self.deactivate_timer.stop()
                self.deactivate_timer = None
                logger.debug(" Deactivate timer stopped")
            except Exception as e:
                logger.warning(f"️  Error stopping deactivate timer: {e}")
        
        if hasattr(self, 'timer_one_second') and self.timer_one_second:
            try:
                self.timer_one_second.stop()
                self.timer_one_second = None
                logger.debug(" Timer cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping timer: {e}")
        
        if hasattr(self, 'TimerGame') and self.TimerGame:
            try:
                self.TimerGame.stop()
                self.TimerGame = None
                logger.debug(" Game timer cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping game timer: {e}")
        
        # Safely clear UI widgets
        if hasattr(self, 'Background') and self.Background:
            try:
                self.Background.clear()
                self.Background = None
                logger.debug(" Background cleared")
            except Exception as e:
                logger.warning(f"️  Error clearing background: {e}")
        
        
        
        if hasattr(self, 'label_timer') and self.label_timer:
            try:
                self.label_timer.hide()
                self.label_timer.deleteLater()
                self.label_timer = None
                logger.debug(" Timer label cleaned up")
            except Exception as e:
                logger.warning(f"️  Error cleaning label_timer: {e}")
        
       
        
        # # Clean up matrix widget
        # if hasattr(self, 'matrix_widget') and self.matrix_widget:
        #     try:
        #         self.matrix_widget.hide()
        #         self.matrix_widget.deleteLater()
        #         self.matrix_widget = None
        #         logger.debug(" Matrix widget cleaned up")
        #     except Exception as e:
        #         logger.warning(f"️  Error cleaning matrix widget: {e}")
        
        # Clean up any other widgets
        if hasattr(self, 'centralwidget') and self.centralwidget:
            try:
                # Clean up all child widgets
                for child in self.centralwidget.findChildren(QtCore.QObject):
                    child.deleteLater()
                self.centralwidget = None
            except Exception as e:
                logger.warning(f"️  Error cleaning central widget: {e}")
        
        event.accept()
        logger.info(" Active screen closed successfully with complete cleanup")
        super().closeEvent(event)


class TeamMember_screen(QtWidgets.QMainWindow):
    """Complete TeamMember Screen implementation"""
    
    def load_custom_font(self, font_path):
        font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            print(f"Failed to load font: {font_path}")
            return "Default"
        font_families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
        if font_families:
            return font_families[0]
        return "Default"

    def play_audio(self):
        """Load and play the audio file."""
        audio_file = "Assets/mp3/2066.wav"
        absolute_path = os.path.abspath(audio_file)
        print("Absolute path:", absolute_path)
        self.player.setMedia(QMediaContent(QtCore.QUrl.fromLocalFile(absolute_path)))
        self.player.setVolume(100)
        self.player.play()
        self.player.mediaStatusChanged.connect(self.check_media_status)
    
    def check_media_status(self, status):
        """Check media status and stop playback if finished."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.player.stop()
        
    def setupUi(self, Home):
        Home.setObjectName("Home")
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        Home.setLayoutDirection(QtCore.Qt.LeftToRight)
        Home.setAutoFillBackground(False)
        self.player = QMediaPlayer()

        self.centralwidget = QtWidgets.QWidget(Home)
        self.centralwidget.setFocusPolicy(QtCore.Qt.StrongFocus)
        print(Home.geometry().width())
        self.font_family = self.load_custom_font("Assets/Fonts/GOTHIC.TTF")
        self.font_family_good = self.load_custom_font("Assets/Fonts/good_times_rg.ttf")
        
        if Home.geometry().width() > 1920:
            self.movie = QMovie("Assets/1k/CubeRoomBall_TeamMembers.gif")
            self.movie.setCacheMode(QMovie.CacheAll)
            self.scale = 2
            global scaled
            scaled = 2
        else:
            self.movie = QMovie("Assets/1k/CubeRoomBall_TeamMembers.gif")
            self.movie.setCacheMode(QMovie.CacheAll)
            self.scale = 1  
            scaled = 1
        
        self.Background = QtWidgets.QLabel(self.centralwidget)
        self.Background.setScaledContents(True)
        self.Background.setGeometry(0, 0, Home.geometry().width(), Home.geometry().height())
        self.Background.setText("")
        self.Background.setMovie(self.movie)
        self.Background.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
        #label 
        self.Label_team_name = QtWidgets.QLabel(self.centralwidget)
        self.Label_team_name.setGeometry(QtCore.QRect(558*self.scale, 245*self.scale, 802*self.scale, 62*self.scale))
        global teamName
        self.Label_team_name.setText(teamName)
        self.Label_team_name.setAlignment(QtCore.Qt.AlignCenter)
        font_team = QtGui.QFont()
        font_team.setPointSize(40*self.scale)
        font_team.setFamily(self.font_family_good)
        self.Label_team_name.setFont(font_team)
        self.Label_team_name.setStyleSheet("color: rgb(255, 255, 255);")
        # self.Label_team_name.hide()
        self.Label_team_name.raise_()

        # Create team member display table
        self.frame_2 = QtWidgets.QFrame(self.centralwidget)
        self.frame_2.setGeometry(QtCore.QRect(558*self.scale, 327*self.scale, 802*self.scale, 595*self.scale))
        self.gridLayout = QtWidgets.QGridLayout(self.frame_2)
        self.LeaderboardTable = QtWidgets.QTableWidget(self.frame_2)
        self.LeaderboardTable.setRowCount(5)
        self.LeaderboardTable.setColumnCount(1)
        
        # Set up table properties
        font = QtGui.QFont()
        font.setFamily(self.font_family_good)
        font.setPointSize(22*self.scale)
        font.setBold(False)
        font.setItalic(False)
        self.LeaderboardTable.setFont(font)
        self.LeaderboardTable.setFocusPolicy(QtCore.Qt.NoFocus)
        self.LeaderboardTable.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.LeaderboardTable.setAutoFillBackground(False)
        self.LeaderboardTable.setLineWidth(0)
        self.LeaderboardTable.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.LeaderboardTable.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.LeaderboardTable.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.LeaderboardTable.setAutoScroll(False)
        self.LeaderboardTable.setAutoScrollMargin(0)
        self.LeaderboardTable.setProperty("showDropIndicator", False)
        self.LeaderboardTable.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.LeaderboardTable.setTextElideMode(QtCore.Qt.ElideLeft)
        self.LeaderboardTable.setShowGrid(False)
        self.LeaderboardTable.setGridStyle(QtCore.Qt.NoPen)
        self.LeaderboardTable.setWordWrap(True)
        self.LeaderboardTable.setCornerButtonEnabled(True)
        self.LeaderboardTable.setObjectName("LeaderboardTable")
        
        # Custom palette configuration for LeaderboardTable
        palette = QtGui.QPalette()
        
        # Define color scheme
        white_text = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        white_text.setStyle(QtCore.Qt.SolidPattern)
        transparent_bg = QtGui.QBrush(QtGui.QColor(0, 0, 0, 0))
        transparent_bg.setStyle(QtCore.Qt.SolidPattern)
        light_blue = QtGui.QBrush(QtGui.QColor(102, 171, 255))
        light_blue.setStyle(QtCore.Qt.SolidPattern)
        mid_blue = QtGui.QBrush(QtGui.QColor(65, 142, 235))
        mid_blue.setStyle(QtCore.Qt.SolidPattern)
        dark_blue = QtGui.QBrush(QtGui.QColor(14, 57, 108))
        dark_blue.setStyle(QtCore.Qt.SolidPattern)
        medium_blue = QtGui.QBrush(QtGui.QColor(19, 75, 144))
        medium_blue.setStyle(QtCore.Qt.SolidPattern)
        no_brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        no_brush.setStyle(QtCore.Qt.NoBrush)
        black_shadow = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        black_shadow.setStyle(QtCore.Qt.SolidPattern)
        alt_blue = QtGui.QBrush(QtGui.QColor(141, 184, 235))
        alt_blue.setStyle(QtCore.Qt.SolidPattern)
        tooltip_bg = QtGui.QBrush(QtGui.QColor(255, 255, 220))
        tooltip_bg.setStyle(QtCore.Qt.SolidPattern)
        disabled_alt_blue = QtGui.QBrush(QtGui.QColor(28, 113, 216))
        disabled_alt_blue.setStyle(QtCore.Qt.SolidPattern)
        
        # Apply styling to all states
        for state in [QtGui.QPalette.Active, QtGui.QPalette.Inactive, QtGui.QPalette.Disabled]:
            palette.setBrush(state, QtGui.QPalette.WindowText, white_text)
            palette.setBrush(state, QtGui.QPalette.Button, transparent_bg)
            palette.setBrush(state, QtGui.QPalette.Light, light_blue)
            palette.setBrush(state, QtGui.QPalette.Midlight, mid_blue)
            palette.setBrush(state, QtGui.QPalette.Dark, dark_blue)
            palette.setBrush(state, QtGui.QPalette.Mid, medium_blue)
            palette.setBrush(state, QtGui.QPalette.Text, white_text)
            palette.setBrush(state, QtGui.QPalette.BrightText, white_text)
            palette.setBrush(state, QtGui.QPalette.ButtonText, white_text)
            palette.setBrush(state, QtGui.QPalette.Base, no_brush)
            palette.setBrush(state, QtGui.QPalette.Window, transparent_bg)
            palette.setBrush(state, QtGui.QPalette.Shadow, black_shadow)
            palette.setBrush(state, QtGui.QPalette.Highlight, transparent_bg)
            palette.setBrush(state, QtGui.QPalette.HighlightedText, white_text)
            palette.setBrush(state, QtGui.QPalette.ToolTipBase, tooltip_bg)
            palette.setBrush(state, QtGui.QPalette.ToolTipText, black_shadow)
            palette.setBrush(state, QtGui.QPalette.PlaceholderText, white_text)
            
            if state == QtGui.QPalette.Disabled:
                palette.setBrush(state, QtGui.QPalette.AlternateBase, disabled_alt_blue)
            else:
                palette.setBrush(state, QtGui.QPalette.AlternateBase, alt_blue)
        
        self.LeaderboardTable.setPalette(palette)
        
        # Gradient palette styling to match the provided image (consistent with Final_Screen)
        self.LeaderboardTable.setStyleSheet("""
            /* QTableWidget Styling - Gradient Blue Palette */
            QTableWidget {
                background: transparent;
                color: #ffffff;  /* White text color */
                gridline-color: rgba(255, 255, 255, 100);  /* Semi-transparent white gridlines */
                selection-background-color: rgba(255, 255, 255, 50);  /* Light selection */
                selection-color: #ffffff;  /* White selection text */
                border: none;  /* No border */
                border-radius: 10px;  /* Rounded corners */
                padding: 8px;
                margin: 4px;
            }

            QHeaderView::section { 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20, 40, 73, 140),      /* #142849 with 55% transparency for headers */
                    stop:0.5 rgba(107, 53, 39, 140),   /* #6b3527 with 55% transparency */
                    stop:1 rgba(181, 102, 59, 140));   /* #b5663b with 55% transparency */
                color: #ffffff;  /* White text color for header sections */
                padding: 12px;  /* Increased padding for header sections */
                border: none;  /* No border */
                border-radius: 5px;  /* Rounded header corners */
                font-weight: bold;  /* Bold font for headers */
                font-family: """ + self.font_family_good + """;  /* Same font as table */
                font-size: """ + str(int(26*self.scale)) + """px;  /* Larger font size */
                margin: 2px;
            }

            QHeaderView {
                background-color: transparent;  /* Transparent background */
                border: none;
            }

            QTableCornerButton::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20, 40, 73, 140),      /* #142849 with 55% transparency */
                    stop:0.5 rgba(107, 53, 39, 140),   /* #6b3527 with 55% transparency */
                    stop:1 rgba(181, 102, 59, 140));   /* #b5663b with 55% transparency */
                border: none;  /* No border */
                border-radius: 5px;
            }

            QTableWidget::item {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20, 40, 73, 102),      /* #142849 with 40% transparency */
                    stop:0.5 rgba(107, 53, 39, 102),   /* #6b3527 with 40% transparency */
                    stop:1 rgba(181, 102, 59, 102));   /* #b5663b with 40% transparency */
                padding: 8px;  /* More padding for items */
                border: none;  /* No border for items */
                color: #ffffff;  /* White text color */
                background: rgba(255, 255, 255, 20);  /* Very subtle background */
                margin: 1px;
                border-radius: 3px;
            }

            QTableWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 100),
                    stop:1 rgba(20, 40, 73, 150));     /* #142849 for selected */
                color: #ffffff;  /* White text for selected items */
                border: none;  /* No border */
            }

            QTableWidget::item:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 80),
                    stop:1 rgba(107, 53, 39, 150));    /* #6b3527 for hover */
                color: #ffffff;  /* White text on hover */
                border: none;  /* No border */
            }

            QTableWidget::item:focus {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 120),
                    stop:1 rgba(181, 102, 59, 180));   /* #b5663b for focus */
                color: #ffffff;  /* White text on focus */
                border: none;  /* No border */
            }
        """)
        
        # Create table items
        for i in range(5):
            for j in range(1):
                item = QtWidgets.QTableWidgetItem()
                if j == 0:
                    item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                else:
                    item.setTextAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
                self.LeaderboardTable.setItem(i, j, item)

        # Set horizontal headers (TeamMember screen has 1 column)
        self.LeaderboardTable.setHorizontalHeaderLabels(["Team Member"])
        self.LeaderboardTable.horizontalHeader().setVisible(True)
        self.LeaderboardTable.horizontalHeader().setCascadingSectionResizes(False)
        
        # Calculate column width for the table width (802px) - single column takes full width
        # Account for table padding (8px), margin (4px), and border (2px) on each side
        # Total padding: (8+4+2) * 2 = 28px, plus some extra buffer for internal spacing
        available_width = int(802 * self.scale - 50)  # More conservative padding calculation
        team_member_column_width = available_width  # Full width for single column
        
        # Set the column to use the calculated width with stretch
        from PyQt5.QtWidgets import QHeaderView
        self.LeaderboardTable.horizontalHeader().resizeSection(0, team_member_column_width)
        self.LeaderboardTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.LeaderboardTable.verticalHeader().setVisible(False)
        self.LeaderboardTable.verticalHeader().setCascadingSectionResizes(False)
        
        # Calculate row heights for the table height (595px)
        # Total available height: 595px minus header and padding
        available_height = int(595 * self.scale - 100)  # Account for header and padding
        row_height = int(available_height / 5)  # Distribute equally among 5 rows
        
        for i in range(5):
            self.LeaderboardTable.verticalHeader().resizeSection(i, row_height)
        self.LeaderboardTable.verticalHeader().setStretchLastSection(True)
        
        self.gridLayout.addWidget(self.LeaderboardTable, 0, 0, 1, 1)

        self.LeaderboardTable.update()
        Home.setCentralWidget(self.centralwidget)
        
        self.movie.start()
        
        self.retranslateUi(Home)
        self.play_audio()
        self.UpdateTable()
        
        QtCore.QMetaObject.connectSlotsByName(Home)
    
    def retranslateUi(self, Home):
        _translate = QtCore.QCoreApplication.translate
        Home.setWindowTitle(_translate("Home", "MainWindow"))
        self.LeaderboardTable.setSortingEnabled(True)
        item = self.LeaderboardTable.horizontalHeaderItem(0)
        item.setText(_translate("Home", "Team"))
        
        # Set default data for team members
        __sortingEnabled = self.LeaderboardTable.isSortingEnabled()
        self.LeaderboardTable.setSortingEnabled(False)
        global list_players_name
        for i, player_name in enumerate(list_players_name[:5]):
            if i < 5:
                item = self.LeaderboardTable.item(i, 0)
                item.setText(_translate("Home", player_name))
        self.LeaderboardTable.setSortingEnabled(__sortingEnabled)
    
    def showTable(self):
        try:
            if hasattr(self, 'LeaderboardTable') and self.LeaderboardTable:
                self.LeaderboardTable.show()
                self.UpdateTable()
        except (RuntimeError, AttributeError):
            logger.debug("LeaderboardTable already deleted, skipping show()")
        
    def hideTable(self):
        try:
            if hasattr(self, 'LeaderboardTable') and self.LeaderboardTable:
                self.LeaderboardTable.hide()
        except (RuntimeError, AttributeError):
            logger.debug("LeaderboardTable already deleted, skipping hide()")
    
    def UpdateTable(self):
        """Update table with team member names"""
        global teamName
        self.Label_team_name.setText(teamName)
        self.Label_team_name.show()
        global list_players_name
        for i, player_name in enumerate(list_players_name[:5]):
            if i < 5:
                team_item = QtWidgets.QTableWidgetItem(player_name)
                team_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.LeaderboardTable.setItem(i, 0, team_item)
    
    def closeEvent(self, event):
        logger.info("TeamMember screen closing...")
        
        # Stop and cleanup timers
        if hasattr(self, 'timer') and self.timer:
            try:
                self.timer.stop()
                try:
                    self.timer.timeout.disconnect()
                except:
                    pass
                self.timer = None
                logger.debug(" Timer cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping timer: {e}")
        
        # Stop and cleanup movie
        if hasattr(self, 'movie') and self.movie:
            try:
                self.movie.stop()
                self.movie.setCacheMode(QMovie.CacheNone)
                self.movie = None
                logger.debug(" Movie cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping movie: {e}")
        
        # Stop media player
        if hasattr(self, 'player') and self.player:
            try:
                self.player.stop()
                self.player.setMedia(QMediaContent())
                try:
                    self.player.mediaStatusChanged.disconnect()
                except:
                    pass
                self.player = None
                logger.debug(" Media player cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping media player: {e}")
        
        # Clean up table widget
        if hasattr(self, 'LeaderboardTable') and self.LeaderboardTable:
            try:
                self.LeaderboardTable.hide()
                self.LeaderboardTable.clear()
                self.LeaderboardTable.close()
                self.LeaderboardTable.deleteLater()
                self.LeaderboardTable = None
                logger.debug(" Table widget cleaned up")
            except Exception as e:
                logger.warning(f"️  Error cleaning table widget: {e}")
        
        # Clean up background
        if hasattr(self, 'Background') and self.Background:
            try:
                self.Background.clear()
                self.Background.setMovie(None)
                self.Background.deleteLater()
                self.Background = None
                logger.debug(" Background cleared")
            except Exception as e:
                logger.warning(f"️  Error clearing background: {e}")
        
        # Clean up layout
        if hasattr(self, 'gridLayout') and self.gridLayout:
            try:
                while self.gridLayout.count():
                    child = self.gridLayout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                self.gridLayout = None
                logger.debug(" Grid layout cleaned up")
            except Exception as e:
                logger.warning(f"️  Error cleaning grid layout: {e}")
        
        # Clean up central widget
        if hasattr(self, 'centralwidget') and self.centralwidget:
            try:
                for child in self.centralwidget.findChildren(QtCore.QObject):
                    child.deleteLater()
                self.centralwidget.deleteLater()
                self.centralwidget = None
                logger.debug(" Central widget cleaned up")
            except Exception as e:
                logger.warning(f"️  Error cleaning central widget: {e}")
        
        event.accept()
        logger.info(" TeamMember screen closed successfully with complete cleanup")
        super().closeEvent(event)


class Home_screen(QtWidgets.QMainWindow):
    """Complete Home Screen implementation"""
    
    def load_custom_font(self, font_path):
        font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            print(f"Failed to load font: {font_path}")
            return "Default"
        font_families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
        if font_families:
            return font_families[0]
        return "Default"

    def play_audio(self):
        """Load and play the audio file."""
        audio_file = "Assets/mp3/2066.wav"
        absolute_path = os.path.abspath(audio_file)
        print("Absolute path:", absolute_path)
        self.player.setMedia(QMediaContent(QtCore.QUrl.fromLocalFile(absolute_path)))
        self.player.setVolume(100)
        self.player.play()
        self.player.mediaStatusChanged.connect(self.check_media_status)
    
    def check_media_status(self, status):
        """Check media status and stop playback if finished."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.player.stop()
        
    def setupUi(self, Home):
        Home.setObjectName("Home")
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        Home.setLayoutDirection(QtCore.Qt.LeftToRight)
        Home.setAutoFillBackground(False)
        self.player = QMediaPlayer()

        self.centralwidget = QtWidgets.QWidget(Home)
        self.centralwidget.setFocusPolicy(QtCore.Qt.StrongFocus)
        print(Home.geometry().width())
        self.font_family = self.load_custom_font("Assets/Fonts/GOTHIC.TTF")
        self.font_family_good = self.load_custom_font("Assets/Fonts/good_times_rg.ttf")
        
        if Home.geometry().width() > 1920:
            self.movie = QMovie("Assets/1k/CubeRoomBall_GameName.gif")
            self.movie.setCacheMode(QMovie.CacheAll)
            self.scale = 2
            global scaled
            scaled = 2
        else:
            self.movie = QMovie("Assets/1k/CubeRoomBall_GameName.gif")
            self.movie.setCacheMode(QMovie.CacheAll)
            self.scale = 1  
            scaled = 1
        
        self.Background = QtWidgets.QLabel(self.centralwidget)
        self.Background.setScaledContents(True)
        self.Background.setGeometry(0, 0, Home.geometry().width(), Home.geometry().height())
        self.Background.setText("")
        self.Background.setMovie(self.movie)
        self.Background.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
        # Create leaderboard table
        self.frame_2 = QtWidgets.QFrame(self.centralwidget)
        self.frame_2.setGeometry(QtCore.QRect(560*self.scale, 328*self.scale, 802*self.scale, 595*self.scale))
        self.gridLayout = QtWidgets.QGridLayout(self.frame_2)
        self.LeaderboardTable = QtWidgets.QTableWidget(self.frame_2)
        self.LeaderboardTable.setRowCount(5)
        self.LeaderboardTable.setColumnCount(2)
        

        
        # Set up table properties
        font = QtGui.QFont()
        font.setFamily(self.font_family_good)
        font.setPointSize(22*self.scale)
        font.setBold(False)
        font.setItalic(False)
        self.LeaderboardTable.setFont(font)
        self.LeaderboardTable.setFocusPolicy(QtCore.Qt.NoFocus)
        self.LeaderboardTable.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.LeaderboardTable.setAutoFillBackground(False)
        self.LeaderboardTable.setLineWidth(0)
        self.LeaderboardTable.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.LeaderboardTable.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.LeaderboardTable.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.LeaderboardTable.setAutoScroll(False)
        self.LeaderboardTable.setAutoScrollMargin(0)
        self.LeaderboardTable.setProperty("showDropIndicator", False)
        self.LeaderboardTable.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.LeaderboardTable.setTextElideMode(QtCore.Qt.ElideLeft)
        self.LeaderboardTable.setShowGrid(False)
        self.LeaderboardTable.setGridStyle(QtCore.Qt.NoPen)
        self.LeaderboardTable.setWordWrap(True)
        self.LeaderboardTable.setCornerButtonEnabled(True)
        self.LeaderboardTable.setObjectName("LeaderboardTable")
        
        # Custom palette configuration for LeaderboardTable - consistent across all states
        palette = QtGui.QPalette()
        
        # Define color scheme once
        white_text = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        white_text.setStyle(QtCore.Qt.SolidPattern)
        transparent_bg = QtGui.QBrush(QtGui.QColor(0, 0, 0, 0))
        transparent_bg.setStyle(QtCore.Qt.SolidPattern)
        light_blue = QtGui.QBrush(QtGui.QColor(102, 171, 255))
        light_blue.setStyle(QtCore.Qt.SolidPattern)
        mid_blue = QtGui.QBrush(QtGui.QColor(65, 142, 235))
        mid_blue.setStyle(QtCore.Qt.SolidPattern)
        dark_blue = QtGui.QBrush(QtGui.QColor(14, 57, 108))
        dark_blue.setStyle(QtCore.Qt.SolidPattern)
        medium_blue = QtGui.QBrush(QtGui.QColor(19, 75, 144))
        medium_blue.setStyle(QtCore.Qt.SolidPattern)
        no_brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        no_brush.setStyle(QtCore.Qt.NoBrush)
        black_shadow = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        black_shadow.setStyle(QtCore.Qt.SolidPattern)
        alt_blue = QtGui.QBrush(QtGui.QColor(141, 184, 235))
        alt_blue.setStyle(QtCore.Qt.SolidPattern)
        tooltip_bg = QtGui.QBrush(QtGui.QColor(255, 255, 220))
        tooltip_bg.setStyle(QtCore.Qt.SolidPattern)
        disabled_alt_blue = QtGui.QBrush(QtGui.QColor(28, 113, 216))
        disabled_alt_blue.setStyle(QtCore.Qt.SolidPattern)
        
        # Apply IDENTICAL styling to ALL states (Active, Inactive, Disabled)
        for state in [QtGui.QPalette.Active, QtGui.QPalette.Inactive, QtGui.QPalette.Disabled]:
            palette.setBrush(state, QtGui.QPalette.WindowText, white_text)
            palette.setBrush(state, QtGui.QPalette.Button, transparent_bg)
            palette.setBrush(state, QtGui.QPalette.Light, light_blue)
            palette.setBrush(state, QtGui.QPalette.Midlight, mid_blue)
            palette.setBrush(state, QtGui.QPalette.Dark, dark_blue)
            palette.setBrush(state, QtGui.QPalette.Mid, medium_blue)
            palette.setBrush(state, QtGui.QPalette.Text, white_text)
            palette.setBrush(state, QtGui.QPalette.BrightText, white_text)
            palette.setBrush(state, QtGui.QPalette.ButtonText, white_text)
            palette.setBrush(state, QtGui.QPalette.Base, no_brush)
            palette.setBrush(state, QtGui.QPalette.Window, transparent_bg)
            palette.setBrush(state, QtGui.QPalette.Shadow, black_shadow)
            palette.setBrush(state, QtGui.QPalette.Highlight, transparent_bg)
            palette.setBrush(state, QtGui.QPalette.HighlightedText, white_text)
            palette.setBrush(state, QtGui.QPalette.ToolTipBase, tooltip_bg)
            palette.setBrush(state, QtGui.QPalette.ToolTipText, black_shadow)
            palette.setBrush(state, QtGui.QPalette.PlaceholderText, white_text)
            
            # Use different AlternateBase for disabled state
            if state == QtGui.QPalette.Disabled:
                palette.setBrush(state, QtGui.QPalette.AlternateBase, disabled_alt_blue)
            else:
                palette.setBrush(state, QtGui.QPalette.AlternateBase, alt_blue)
        
        self.LeaderboardTable.setPalette(palette)
        
        # Gradient palette styling to match the provided image (consistent with Final_Screen)
        self.LeaderboardTable.setStyleSheet("""
            /* QTableWidget Styling - Gradient Blue Palette */
            QTableWidget {
                background: transparent;
                color: #ffffff;  /* White text color */
                gridline-color: rgba(255, 255, 255, 100);  /* Semi-transparent white gridlines */
                selection-background-color: rgba(255, 255, 255, 50);  /* Light selection */
                selection-color: #ffffff;  /* White selection text */
                border: none;  /* No border */
                border-radius: 10px;  /* Rounded corners */
                padding: 8px;
                margin: 4px;
            }

            QHeaderView::section { 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20, 40, 73, 140),      /* #142849 with 55% transparency for headers */
                    stop:0.5 rgba(107, 53, 39, 140),   /* #6b3527 with 55% transparency */
                    stop:1 rgba(181, 102, 59, 140));   /* #b5663b with 55% transparency */
                color: #ffffff;  /* White text color for header sections */
                padding: 12px;  /* Increased padding for header sections */
                border: none;  /* No border */
                border-radius: 5px;  /* Rounded header corners */
                font-weight: bold;  /* Bold font for headers */
                font-family: """ + self.font_family_good + """;  /* Same font as table */
                font-size: """ + str(int(26*self.scale)) + """px;  /* Larger font size */
                margin: 2px;
            }

            QHeaderView {
                background-color: transparent;  /* Transparent background */
                border: none;
            }

            QTableCornerButton::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20, 40, 73, 140),      /* #142849 with 55% transparency */
                    stop:0.5 rgba(107, 53, 39, 140),   /* #6b3527 with 55% transparency */
                    stop:1 rgba(181, 102, 59, 140));   /* #b5663b with 55% transparency */
                border: none;  /* No border */
                border-radius: 5px;
            }

            QTableWidget::item {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20, 40, 73, 102),      /* #142849 with 40% transparency */
                    stop:0.5 rgba(107, 53, 39, 102),   /* #6b3527 with 40% transparency */
                    stop:1 rgba(181, 102, 59, 102));   /* #b5663b with 40% transparency */
                padding: 8px;  /* More padding for items */
                border: none;  /* No border for items */
                color: #ffffff;  /* White text color */
                background: rgba(255, 255, 255, 20);  /* Very subtle background */
                margin: 1px;
                border-radius: 3px;
            }

            QTableWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 100),
                    stop:1 rgba(20, 40, 73, 150));     /* #142849 for selected */
                color: #ffffff;  /* White text for selected items */
                border: none;  /* No border */
            }

            QTableWidget::item:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 80),
                    stop:1 rgba(107, 53, 39, 150));    /* #6b3527 for hover */
                color: #ffffff;  /* White text on hover */
                border: none;  /* No border */
            }

            QTableWidget::item:focus {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 120),
                    stop:1 rgba(181, 102, 59, 180));   /* #b5663b for focus */
                color: #ffffff;  /* White text on focus */
                border: none;  /* No border */
            }
        """)
        
        # Create vertical header items
        item = QtWidgets.QTableWidgetItem()
        self.LeaderboardTable.setVerticalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        item.setTextAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignVCenter)
        self.LeaderboardTable.setVerticalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.LeaderboardTable.setVerticalHeaderItem(2, item)
        item = QtWidgets.QTableWidgetItem()
        self.LeaderboardTable.setVerticalHeaderItem(3, item)
        item = QtWidgets.QTableWidgetItem()
        self.LeaderboardTable.setVerticalHeaderItem(4, item)
        
        # Create horizontal header items
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setFamily(self.font_family_good)
        font.setPointSize(20*self.scale)
        item.setFont(font)
        self.LeaderboardTable.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setFamily(self.font_family_good)
        font.setPointSize(20*self.scale)
        item.setFont(font)
        self.LeaderboardTable.setHorizontalHeaderItem(1, item)
        
        # Create table items with enhanced properties
        item = QtWidgets.QTableWidgetItem()
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        item.setFlags(QtCore.Qt.ItemIsSelectable|QtCore.Qt.ItemIsEditable|QtCore.Qt.ItemIsDragEnabled|QtCore.Qt.ItemIsDropEnabled|QtCore.Qt.ItemIsUserCheckable|QtCore.Qt.ItemIsEnabled|QtCore.Qt.ItemIsTristate)
        
        # Create all table items
        for i in range(5):
            for j in range(2):
                item = QtWidgets.QTableWidgetItem()
                if j == 0:
                    item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
                else:
                    item.setTextAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
                self.LeaderboardTable.setItem(i, j, item)

        

        # Set horizontal headers with custom properties (consistent with Final_Screen)
        self.LeaderboardTable.setHorizontalHeaderLabels(["Team", "Score"])
        self.LeaderboardTable.horizontalHeader().setVisible(True)
        self.LeaderboardTable.horizontalHeader().setCascadingSectionResizes(False)
        
        # Calculate column widths for the table width (802px) - consistent with Final_Screen
        # Account for table padding (8px), margin (4px), and border (2px) on each side
        # Total padding: (8+4+2) * 2 = 28px, plus some extra buffer for internal spacing
        available_width = int(802 * self.scale - 50)  # More conservative padding calculation
        team_column_width = int(available_width * 0.60)    # 60% for team name
        score_column_width = int(available_width * 0.40)   # 40% for score
        
        # Set the first column to a fixed width, let the second column stretch
        self.LeaderboardTable.horizontalHeader().resizeSection(0, team_column_width)
        self.LeaderboardTable.horizontalHeader().setStretchLastSection(True)
        # Alternative: use section resize mode for better control
        from PyQt5.QtWidgets import QHeaderView
        self.LeaderboardTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.LeaderboardTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.LeaderboardTable.verticalHeader().setVisible(False)
        self.LeaderboardTable.verticalHeader().setCascadingSectionResizes(False)
        
        # Calculate row heights for the table height (595px) - consistent with Final_Screen
        # Total available height: 595px minus header and padding
        available_height = int(595 * self.scale - 100)  # Account for header and padding
        row_height = int(available_height / 5)  # Distribute equally among 5 rows
        
        for i in range(5):
            self.LeaderboardTable.verticalHeader().resizeSection(i, row_height)
        self.LeaderboardTable.verticalHeader().setStretchLastSection(True)
        
        self.gridLayout.addWidget(self.LeaderboardTable, 0, 0, 1, 1)
        self.LeaderboardTable.hide()

        # self.LeaderboardTable.update()
        Home.setCentralWidget(self.centralwidget)
        
        # Timers for showing table and switching to inactive
        self.timer = QTimer(Home)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.Inactive)
        self.timer.start(11000)
        
        self.movie.start()
        
       
        
        self.timer3 = QTimer(Home)
        self.timer3.setTimerType(Qt.PreciseTimer)
        self.timer3.timeout.connect(self.looping)
        
        self.retranslateUi(Home)
        self.play_audio()
        
        QtCore.QMetaObject.connectSlotsByName(Home)
    
    def retranslateUi(self, Home):
        _translate = QtCore.QCoreApplication.translate
        Home.setWindowTitle(_translate("Home", "MainWindow"))
        self.LeaderboardTable.setSortingEnabled(True)
        item = self.LeaderboardTable.horizontalHeaderItem(0)
        item.setText(_translate("Home", "Team"))
        item = self.LeaderboardTable.horizontalHeaderItem(1)
        item.setText(_translate("Home", "Score"))
        
        # Set default data
        __sortingEnabled = self.LeaderboardTable.isSortingEnabled()
        self.LeaderboardTable.setSortingEnabled(False)
        item = self.LeaderboardTable.item(0, 0)
        item.setText(_translate("Home", "Team 1"))
        item = self.LeaderboardTable.item(0, 1)
        item.setText(_translate("Home", "5"))
        item = self.LeaderboardTable.item(1, 0)
        item.setText(_translate("Home", "Team 2"))
        item = self.LeaderboardTable.item(1, 1)
        item.setText(_translate("Home", "6"))
        item = self.LeaderboardTable.item(2, 0)
        item.setText(_translate("Home", "Team 3"))
        item = self.LeaderboardTable.item(2, 1)
        item.setText(_translate("Home", "548"))
        item = self.LeaderboardTable.item(3, 0)
        item.setText(_translate("Home", "Team 5"))
        item = self.LeaderboardTable.item(3, 1)
        item.setText(_translate("Home", "2"))
        item = self.LeaderboardTable.item(4, 0)
        item.setText(_translate("Home", "Team 55"))
        item = self.LeaderboardTable.item(4, 1)
        item.setText(_translate("Home", "55"))
        self.LeaderboardTable.setSortingEnabled(__sortingEnabled)
    
    def showTable(self):
        self.LeaderboardTable.show()
        self.UpdateTable()
        
    def hideTable(self):
        self.LeaderboardTable.hide()
    
    def UpdateTable(self):
        global list_top5_TheCage
        sorted_data = sorted(list_top5_TheCage, key=lambda item: item[1], reverse=True)

        for i, (team, score) in enumerate(sorted_data):
            if i >= 5:
                break

            team_item = QtWidgets.QTableWidgetItem(team)
            team_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.LeaderboardTable.setItem(i, 0, team_item)

            score_item = QtWidgets.QTableWidgetItem(str(score))
            score_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.LeaderboardTable.setItem(i, 1, score_item)

    def Inactive(self):
        self.timer.stop()
        self.timer3.start(9000)
        if scaled == 1:
            self.movie = QMovie("Assets/1k/CubeRoomBall_inActive.gif")
            self.movie.setCacheMode(QMovie.CacheAll)
        else:
            self.movie = QMovie("Assets/1k/CubeRoomBall_inActive.gif")
            self.movie.setCacheMode(QMovie.CacheAll)
        self.Background.setMovie(self.movie)
        self.movie.start()
        # Safe table show - check if widget still exists
        try:
            if hasattr(self, 'LeaderboardTable') and self.LeaderboardTable:
                self.LeaderboardTable.show()
                self.UpdateTable()
        except (RuntimeError, AttributeError):
            logger.debug("LeaderboardTable already deleted, skipping show()")
        global homeOpened
        homeOpened = True
    
    def looping(self):
        """Enhanced looping function with improved safety (from game2)"""
        logger.debug("Starting looping cycle")
        
        # Safe timer stop
        try:
            if hasattr(self, 'timer3') and self.timer3:
                self.timer3.stop()
        except (RuntimeError, AttributeError):
            pass

        # Safe table hide - check if widget still exists    
        try:
            if hasattr(self, 'LeaderboardTable') and self.LeaderboardTable:
                self.LeaderboardTable.hide()
        except (RuntimeError, AttributeError):
            logger.debug("LeaderboardTable already deleted, skipping hide()")
            
        # Load intro movie with proper scaling
        if scaled == 1:
            self.movie = QMovie("Assets/1k/CubeRoomBall_GameName.gif")
            self.movie.setCacheMode(QMovie.CacheAll)
        else:
            self.movie = QMovie("Assets/1k/CubeRoomBall_GameName.gif")
            self.movie.setCacheMode(QMovie.CacheAll)
            
        # Safe background and movie operations
        try:
            if hasattr(self, 'Background') and self.Background:
                self.Background.setMovie(self.movie)
                self.movie.start()
                logger.debug(" Intro movie started successfully")
        except (RuntimeError, AttributeError):
            logger.debug("Background widget already deleted, skipping movie operations")
            
        # Safe timer restart with proper error handling
        try:
            if hasattr(self, 'timer') and self.timer:
                self.timer.start(11000)
                logger.debug("⏰ Timer restarted for 11 seconds")
        except (RuntimeError, AttributeError):
            logger.debug("Timer already deleted, skipping start()")
            
        # Set homeOpened flag for game manager detection
        global homeOpened
        homeOpened = True
        logger.debug(" Looping cycle completed successfully")
    
    def closeEvent(self, event):
        logger.info("Home screen closing...")
        
        # Stop and cleanup timers
        if hasattr(self, 'timer') and self.timer:
            try:
                self.timer.stop()
                # Disconnect signals
                try:
                    self.timer.timeout.disconnect()
                except:
                    pass
                self.timer = None
                logger.debug(" Timer cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping timer: {e}")
        
        
        
        if hasattr(self, 'timer3') and self.timer3:
            try:
                self.timer3.stop()
                # Disconnect signals
                try:
                    self.timer3.timeout.disconnect()
                except:
                    pass
                self.timer3 = None
                logger.debug(" Timer3 cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping timer3: {e}")
        
        # Stop and cleanup movie
        if hasattr(self, 'movie') and self.movie:
            try:
                self.movie.stop()
                self.movie.setCacheMode(QMovie.CacheNone)
                self.movie = None
                logger.debug(" Movie cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping movie: {e}")
        
        # Stop media player if it exists
        if hasattr(self, 'player') and self.player:
            try:
                self.player.stop()
                self.player.setMedia(QMediaContent())
                try:
                    self.player.mediaStatusChanged.disconnect()
                except:
                    pass
                self.player = None
                logger.debug(" Media player cleaned up")
            except Exception as e:
                logger.warning(f"️  Error stopping media player: {e}")
        
        # Clean up table widget with safe Qt object handling
        try:
            if hasattr(self, 'LeaderboardTable') and self.LeaderboardTable is not None:
                try:
                    self.LeaderboardTable.hide()
                    self.LeaderboardTable.clear()
                    self.LeaderboardTable.close()
                    self.LeaderboardTable.deleteLater()
                    logger.debug(" Table widget cleaned up")
                except (RuntimeError, AttributeError):
                    logger.debug("Table widget already deleted by Qt, skipping cleanup")
                finally:
                    self.LeaderboardTable = None
        except (RuntimeError, SystemError, AttributeError):
            logger.debug("Table widget reference already invalid, skipping cleanup")
            self.LeaderboardTable = None
        
        # Clean up background with safe Qt object handling
        try:
            if hasattr(self, 'Background') and self.Background is not None:
                try:
                    self.Background.clear()
                    self.Background.setMovie(None)  # Remove movie reference
                    self.Background.deleteLater()
                    logger.debug(" Background cleared")
                except (RuntimeError, AttributeError):
                    logger.debug("Background widget already deleted by Qt, skipping cleanup")
                finally:
                    self.Background = None
        except (RuntimeError, SystemError, AttributeError):
            logger.debug("Background widget reference already invalid, skipping cleanup")
            self.Background = None
        
        # Clean up layout with safe Qt object handling
        try:
            if hasattr(self, 'gridLayout') and self.gridLayout is not None:
                try:
                    # Remove all items from layout
                    while self.gridLayout.count():
                        child = self.gridLayout.takeAt(0)
                        if child.widget():
                            child.widget().deleteLater()
                    logger.debug(" Grid layout cleaned up")
                except (RuntimeError, AttributeError):
                    logger.debug("Grid layout already deleted by Qt, skipping cleanup")
                finally:
                    self.gridLayout = None
        except (RuntimeError, SystemError, AttributeError):
            logger.debug("Grid layout reference already invalid, skipping cleanup")
            self.gridLayout = None
        
        # Clean up central widget and all its children with safe Qt object handling
        try:
            if hasattr(self, 'centralwidget') and self.centralwidget is not None:
                try:
                    # Clean up all child widgets
                    for child in self.centralwidget.findChildren(QtCore.QObject):
                        child.deleteLater()
                    self.centralwidget.deleteLater()
                    logger.debug(" Central widget cleaned up")
                except (RuntimeError, AttributeError):
                    logger.debug("Central widget already deleted by Qt, skipping cleanup")
                finally:
                    self.centralwidget = None
        except (RuntimeError, SystemError, AttributeError):
            logger.debug("Central widget reference already invalid, skipping cleanup")
            self.centralwidget = None
        
        event.accept()
        logger.info(" Home screen closed successfully with complete cleanup")
        super().closeEvent(event)


class MainApp(QtWidgets.QMainWindow):
    """Complete Main Application with all screens and new API integration"""
    
    def __init__(self):
        super().__init__()
        logger.info("MainApp initializing with complete UI and new API...")
        
         # Initialize ST1 Scale Thread Communication (but don't connect yet)
        self.st1_scale_thread = None
        self.scale_config = config.settings.serial
        if self.scale_config.enabled:
            try:
                # Create ST1ScaleThread instance (without connecting)
                self.st1_scale_thread = ST1ScaleThread(
                    port=self.scale_config.port,
                    baudrate=self.scale_config.baudrate,
                    timeout=self.scale_config.timeout,
                    data_format=2  # Default to format 2
                )
                logger.info(" ST1 Scale Thread initialized (not connected yet)")
                    
            except Exception as e:
                logger.error(f" Failed to initialize ST1 Scale Thread: {e}")
                self.st1_scale_thread = None
        else:
            logger.info("ℹ️ ST1 Scale communication disabled in configuration")
            
        # Setup mainWindow and screens
        self.sized = QtWidgets.QDesktopWidget().screenGeometry()
        self.ui_final = Final_Screen()
        self.ui_home = Home_screen()
        self.ui_active = Active_screen(st1_scale_thread=self.st1_scale_thread)    
        self.ui_team_member = TeamMember_screen()
        
        self.mainWindow = QtWidgets.QMainWindow()

        self.mainWindow.setObjectName("Home")
        self.mainWindow.setWindowTitle("Cube Room Ball Game - Complete")
        self.mainWindow.setFixedSize(self.sized.width(), self.sized.height())
        self.mainWindow.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        
        # Initialize GameManager with new API
        try:
            self.game_manager = GameManager()
            logger.info(" GameManager initialized with new API")
        except Exception as e:
            logger.error(f" Failed to initialize GameManager: {e}")
            raise
        
       
        # Connection signals for the game manager with safety checks
        if hasattr(self, 'game_manager') and self.game_manager:
            # 1. init_signal: Triggered when the game manager is initialized
            self.game_manager.init_signal.connect(self.start_TeamMember_screen)
            # 2. start_signal: Triggered when the game manager starts
            self.game_manager.start_signal.connect(lambda: (
                self.start_Active_screen(),
                self._safe_mqtt_subscribe(),
                self.ui_active.start_game() if hasattr(self, 'ui_active') and self.ui_active else None
            ))
            # 3. cancel_signal: Triggered when the game manager is cancelled
            self.game_manager.cancel_signal.connect(self._handle_game_cancellation)
            # 4. submit_signal: Triggered when the game manager is submitted
            self.game_manager.submit_signal.connect(self.start_final_screen)
            logger.debug(" GameManager signals connected successfully")
        else:
            logger.error(" GameManager not available for signal connections")
        
        # Connect deactivate signal to trigger score submission (with safety check)
        if (hasattr(self.ui_active, 'mqtt_thread') and hasattr(self.ui_active.mqtt_thread, 'deactivate_signal') and
            hasattr(self, 'game_manager') and self.game_manager):
            self.ui_active.mqtt_thread.deactivate_signal.connect(
                self.game_manager.trigger_score_submission
            )
        else:
            logger.warning("️  MQTT thread or GameManager not properly initialized for deactivate signal")
        # ------------------------------
        self.start_Home_screen()

        """
        @comment: keep this for testing the game manager
        """
        # ------------------------------
        # self.start_Active_screen()
        # self.ui_active.start_game()
        # ------------------------------
        # self.start_final_screen()

        # Start game manager after delay 
        QtCore.QTimer.singleShot(5000, self.game_manager.start)
        
        self.mainWindow.showFullScreen()
        logger.info(" MainApp initialization complete")
    
    # Note: Scale methods moved to ST1ScaleThread for better performance
                
    def start_Home_screen(self):
        logger.info("Starting Home Screen")
        
        # Force stop all timers before transition
        self._force_stop_all_timers()
        
        # Clean up previous screens
        self._cleanup_previous_screens()
        
        # Reset global game state
        global list_players_score, list_players_name, scored, serial_scoring_active
        list_players_score = [0,0,0,0,0]
        list_players_name.clear()
        scored = 0
        serial_scoring_active = False
        
        # Initialize home screen with error handling
        if hasattr(self, 'ui_home') and self.ui_home:
            try:
                self.ui_home.setupUi(self.mainWindow)
                logger.info(" Home screen initialized successfully")
                
                # Set homeOpened flag so game manager can detect home screen is ready
                global homeOpened
                homeOpened = True
                logger.info("Home screen is now ready for game initialization")
                
            except Exception as e:
                logger.error(f" Error setting up home screen: {e}")
                return
        else:
            logger.error(" ui_home not properly initialized")
            return
       
        quit_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence('q'), self.mainWindow)
        quit_shortcut.activated.connect(self.close_application)
        
    def start_TeamMember_screen(self):
        logger.info("Starting TeamMember Screen")
        
        # Clean up previous screens
        self._cleanup_previous_screens()
        
        # Initialize team member screen with error handling
        if hasattr(self, 'ui_team_member') and self.ui_team_member:
            try:
                self.ui_team_member.setupUi(self.mainWindow)
                logger.info(" TeamMember screen initialized successfully")
            except Exception as e:
                logger.error(f" Error setting up team member screen: {e}")
                return
        else:
            logger.error(" ui_team_member not properly initialized")
            return
       
        quit_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence('q'), self.mainWindow)
        quit_shortcut.activated.connect(self.close_application)
    
    def _handle_game_cancellation(self):
        """Robust handler for game cancellation that works regardless of current screen state (improved from CAGE)"""
        logger.warning("" + "=" * 50)
        logger.warning(" GAME CANCELLATION DETECTED")
        logger.warning("" + "=" * 50)
        
        try:
            # Safely cleanup active screen components
            if hasattr(self, 'ui_active') and self.ui_active:
                try:
                    if hasattr(self.ui_active, 'TimerGame') and self.ui_active.TimerGame:
                        self.ui_active.TimerGame.stop()
                        logger.debug("TimerGame stopped")
                except Exception as e:
                    logger.warning(f"️  Error stopping TimerGame: {e}")
                
                try:
                    if hasattr(self.ui_active, 'timer') and self.ui_active.timer:
                        self.ui_active.timer.stop()
                        logger.debug("Timer stopped")
                except Exception as e:
                    logger.warning(f"️  Error stopping timer: {e}")
                
                
                try:
                    if hasattr(self.ui_active, 'mqtt_thread') and self.ui_active.mqtt_thread:
                        self.ui_active.mqtt_thread.unsubscribe_from_data_topics()
                        logger.debug("MQTT unsubscribed")
                except Exception as e:
                    logger.warning(f"️  Error unsubscribing MQTT: {e}")
                
                try:
                    # Check if ui_active is still valid before closing
                    try:
                        self.ui_active.objectName()  # Test if object is still valid
                        self.ui_active.close()
                        logger.debug("Active screen closed")
                    except RuntimeError:
                        logger.debug("Active screen was already deleted by Qt")
                except Exception as e:
                    logger.warning(f"️  Error closing active screen: {e}")
                
                # CRITICAL: Reset the Active_screen state instead of recreating it
                try:
                    logger.info("Resetting Active_screen state after cancellation...")
                    self._reset_active_screen_state()
                    logger.info(" Active_screen state reset successfully")
                    
                except Exception as e:
                    logger.error(f" Error resetting Active_screen state: {e}")
            
            # Force manual reset of essential flags only
            if hasattr(self, 'game_manager') and self.game_manager:
                self.game_manager.game_result_id = None
                self.game_manager.submit_score_flag = False
                self.game_manager.started_flag = False  # CRITICAL: Reset like CAGE_Game.py
                self.game_manager.cancel_flag = False
                logger.debug(f"GameManager flags reset: started_flag={self.game_manager.started_flag}")
            
        except Exception as e:
            logger.error(f" Error during cancellation cleanup: {e}")
        
        # Always try to go to home screen, regardless of cleanup errors
        try:
            logger.info("Moving to home screen after cancellation...")
            self.start_Home_screen()
            logger.info(" Successfully moved to home screen after cancellation")
        except Exception as e:
            logger.error(f" Error moving to home screen after cancellation: {e}")
            # Last resort - try basic home screen setup
            try:
                if hasattr(self, 'ui_home') and self.ui_home:
                    self.ui_home.setupUi(self.mainWindow)
                    self.mainWindow.show()
                    logger.info(" Last resort home screen setup successful")
            except Exception as last_resort_error:
                logger.error(f" Last resort home screen setup failed: {last_resort_error}")
    
    def _reset_active_screen_state(self):
        """Reset Active_screen state without recreating objects to avoid resource conflicts (from CAGE)"""
        try:
            if not hasattr(self, 'ui_active') or not self.ui_active:
                logger.warning("️  ui_active not available for state reset")
                return
            
            logger.info("Resetting Active_screen state without object recreation...")
            
            # Reset game state variables specific to Cube Room Ball
            global gameStarted, firstDetected, scored, serial_scoring_active
            global list_players_score, list_players_name
            
            gameStarted = False
            firstDetected = False
            scored = 0
            serial_scoring_active = False
            
            # Reset score tracking
            list_players_score = [0,0,0,0,0]
            list_players_name.clear()
            
            logger.debug(" Global game state variables reset")
            
            # Reset MediaPlayer state (reuse existing player) - Cube Room Ball doesn't use MediaPlayer
            # Skip MediaPlayer reset for Cube Room Ball
            
            # Reset MQTT thread state (reuse existing connection if available)
            if hasattr(self.ui_active, 'mqtt_thread') and self.ui_active.mqtt_thread:
                try:
                    # Check if MQTT is still connected
                    if (hasattr(self.ui_active.mqtt_thread, 'connected') and 
                        self.ui_active.mqtt_thread.connected and
                        hasattr(self.ui_active.mqtt_thread, 'client') and
                        self.ui_active.mqtt_thread.client):
                        logger.debug(" MQTT thread still connected, reusing existing connection")
                    else:
                        logger.debug("MQTT thread disconnected, will reconnect on next game start")
                except Exception as e:
                    logger.warning(f"️  Error checking MQTT state: {e}")
            
            # Reset UI state if needed
            try:
                # Reset any timers (but don't recreate them)
                if hasattr(self.ui_active, 'timer') and self.ui_active.timer:
                    self.ui_active.timer.stop()
                
                if hasattr(self.ui_active, 'TimerGame') and self.ui_active.TimerGame:
                    self.ui_active.TimerGame.stop()
                
                logger.debug(" UI state reset completed")
                
            except Exception as e:
                logger.warning(f"️  Error resetting UI state: {e}")
                
            logger.info(" Active_screen state reset completed without object recreation")
            
        except Exception as e:
            logger.error(f" Error in _reset_active_screen_state: {e}")

    def _safe_mqtt_subscribe(self):
        """Safely subscribe to MQTT data topics"""
        try:
            if hasattr(self, 'ui_active') and self.ui_active:
                if hasattr(self.ui_active, 'mqtt_thread') and self.ui_active.mqtt_thread:
                    self.ui_active.mqtt_thread.subscribe_to_data_topics()
                    logger.debug(" MQTT subscribed to data topics")
                else:
                    logger.warning("️  MQTT thread not available for subscription")
        except Exception as e:
            logger.warning(f"️  Error subscribing to MQTT: {e}")
    
    def _safe_mqtt_unsubscribe(self):
        """Safely unsubscribe from MQTT data topics"""
        try:
            if hasattr(self, 'ui_active') and self.ui_active:
                if hasattr(self.ui_active, 'mqtt_thread') and self.ui_active.mqtt_thread:
                    self.ui_active.mqtt_thread.unsubscribe_from_data_topics()
                    logger.debug(" MQTT unsubscribed from data topics")
                else:
                    logger.warning("️  MQTT thread not available for unsubscription")
        except Exception as e:
            logger.warning(f"️  Error unsubscribing from MQTT: {e}")
    
    def _cleanup_previous_screens(self):
        """Safely cleanup any previous screen resources"""
        logger.info("Cleaning up previous screens...")
        
        # Clean up active screen
        if hasattr(self, 'ui_active') and self.ui_active:
            try:
                # Stop any running timers
                if hasattr(self.ui_active, 'timer') and self.ui_active.timer:
                    self.ui_active.timer.stop()
                if hasattr(self.ui_active, 'TimerGame') and self.ui_active.TimerGame:
                    self.ui_active.TimerGame.stop()
                # Don't close video here as it might be needed
            except Exception as e:
                logger.warning(f"️  Error cleaning up active screen: {e}")
        
        # Clean up final screen
        if hasattr(self, 'ui_final') and self.ui_final:
            try:
                if hasattr(self.ui_final, 'timer') and self.ui_final.timer:
                    self.ui_final.timer.stop()
                if hasattr(self.ui_final, 'timer2') and self.ui_final.timer2:
                    self.ui_final.timer2.stop()
            except Exception as e:
                logger.warning(f"️  Error cleaning up final screen: {e}")
        
        # Clean up home screen
        if hasattr(self, 'ui_home') and self.ui_home:
            try:
                if hasattr(self.ui_home, 'timer') and self.ui_home.timer:
                    self.ui_home.timer.stop()
                if hasattr(self.ui_home, 'timer2') and self.ui_home.timer2:
                    self.ui_home.timer2.stop()
            except Exception as e:
                logger.warning(f"️  Error cleaning up home screen: {e}")
        
        # Clean up team member screen
        if hasattr(self, 'ui_team_member') and self.ui_team_member:
            try:
                if hasattr(self.ui_team_member, 'timer') and self.ui_team_member.timer:
                    self.ui_team_member.timer.stop()
                if hasattr(self.ui_team_member, 'timer2') and self.ui_team_member.timer2:
                    self.ui_team_member.timer2.stop()
            except Exception as e:
                logger.warning(f"️  Error cleaning up team member screen: {e}")
        
        logger.info(" Previous screens cleaned up")

    def start_Active_screen(self):
        logger.info("Starting Active Screen")
        
        # Safely close home screen
        if hasattr(self, 'ui_home') and self.ui_home:
            try:
                self.ui_home.close()
            except Exception as e:
                logger.warning(f"️  Error closing home screen: {e}")
        
        # Initialize active screen with error handling
        if hasattr(self, 'ui_active') and self.ui_active:
            try:
                # Ensure MQTT thread is initialized (in case it was cleaned up previously)
                self.ui_active.init_mqtt_thread()
                 # Connect deactivate signal to trigger score submission (with safety check)
                if (hasattr(self.ui_active, 'mqtt_thread') and hasattr(self.ui_active.mqtt_thread, 'deactivate_signal') and
                    hasattr(self, 'game_manager') and self.game_manager):
                    self.ui_active.mqtt_thread.deactivate_signal.connect(
                        self.game_manager.trigger_score_submission
                    )
                else:
                    logger.warning("️  MQTT thread or GameManager not properly initialized for deactivate signal")

                self.ui_active.setupUi(self.mainWindow)
            except Exception as e:
                logger.error(f" Error setting up active screen: {e}")
                return
        else:
            logger.error(" ui_active not properly initialized")
            return
        
        quit_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence('q'), self.mainWindow)
        quit_shortcut.activated.connect(self.close_application)

    def start_final_screen(self):
        """Start Final Screen with comprehensive error handling (improved from game2)"""
        logger.info("Starting Final Screen")
        try:
            # Close any current screens safely
            self._close_current_screen()
            
            # Setup and show final screen
            self.ui_final.setupUi(self.mainWindow)
            self.mainWindow.show()
            logger.debug(" Final screen started successfully")
            
            # Read timer value from file with fallback
            try:
                with open("file.txt", "r") as file:
                    lines = file.readlines()
                    if lines:
                        final_screen_timer_idle = int(lines[-1].strip())
                    else:
                        final_screen_timer_idle = game_config.final_screen_timer
            except FileNotFoundError:
                logger.info("file.txt not found. Using default timer value.")
                final_screen_timer_idle = game_config.final_screen_timer
            except (ValueError, IndexError) as e:
                logger.warning(f"️  Error reading timer value: {e}. Using default.")
                final_screen_timer_idle = game_config.final_screen_timer
            
            # Override with default for consistency
            final_screen_timer_idle = 15000
            
            # Set up automatic transition back to home screen after final_screen_timer_idle (improved from game2)
            logger.info(f"⏰ Setting final screen auto-transition timer: {final_screen_timer_idle}ms")
            QtCore.QTimer.singleShot(final_screen_timer_idle, lambda: (
                self.ui_final.close() if hasattr(self, 'ui_final') and self.ui_final is not None and self.ui_final.isVisible() else None,
                self.start_Home_screen() if hasattr(self, 'ui_final') and self.ui_final is not None and not self.ui_final.isVisible() else None
            ))
            
        except Exception as e:
            logger.error(f" Error starting final screen: {e}")

        quit_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence('q'), self.mainWindow)
        quit_shortcut.activated.connect(self.close_application)

    def _close_current_screen(self):
        """Safely close any currently active screen (improved from game2)"""
        try:
            # Clear central widget content
            central_widget = self.mainWindow.centralWidget()
            if central_widget:
                # Get all child widgets
                for child in central_widget.findChildren(QtWidgets.QWidget):
                    try:
                        child.hide()
                        child.deleteLater()
                    except RuntimeError:
                        # Widget already deleted
                        pass
                
                # Clear the central widget
                central_widget.deleteLater()
                self.mainWindow.setCentralWidget(None)
                
            logger.debug(" Current screen closed successfully")
        except Exception as e:
            logger.warning(f"️  Error closing current screen: {e}")

    def close_application(self):
        """Comprehensive application cleanup and shutdown"""
        logger.info("Closing application with comprehensive cleanup...")
        
        try:
            # Stop GameManager thread first
            if hasattr(self, 'game_manager') and self.game_manager:
                try:
                    self.game_manager.stop_manager()
                    logger.debug(" GameManager stopped")
                except Exception as e:
                    logger.warning(f"️  Error stopping GameManager: {e}")
            
            # Clean up all UI screens
            self._cleanup_all_screens()
            
            # Close main window
            if hasattr(self, 'mainWindow') and self.mainWindow:
                try:
                    self.mainWindow.close()
                    logger.debug(" Main window closed")
                except Exception as e:
                    logger.warning(f"️  Error closing main window: {e}")
            
        except Exception as e:
            logger.error(f" Error during application cleanup: {e}")
        
        # Quit the application
        QtWidgets.QApplication.quit()
        logger.info(" Application shutdown complete")
    
    def closeEvent(self, event):
        """Handle application close event with comprehensive cleanup"""
        logger.info("MainApp closeEvent triggered...")
        
        try:
            # Cleanup ST1 scale thread communication
            if hasattr(self, 'st1_scale_thread') and self.st1_scale_thread:
                logger.info("Stopping ST1 scale thread...")
                self.st1_scale_thread.stop_monitoring()
                self.st1_scale_thread.disconnect_for_game()
            
            # Perform the same cleanup as close_application
            if hasattr(self, 'game_manager') and self.game_manager:
                self.game_manager.stop_manager()
            
            self._cleanup_all_screens()
            
        except Exception as e:
            logger.error(f" Error in MainApp closeEvent: {e}")
        
        event.accept()
        logger.info(" MainApp closeEvent completed")
        super().closeEvent(event)
    
    def _cleanup_all_screens(self):
        """Cleanup all screen instances and their resources"""
        logger.info("Cleaning up all screens...")
        
        # Clean up active screen
        if hasattr(self, 'ui_active') and self.ui_active:
            try:
                self.ui_active.close()
                logger.debug(" Active screen closed")
            except Exception as e:
                logger.warning(f"️  Error closing active screen: {e}")
        
        # Clean up final screen  
        if hasattr(self, 'ui_final') and self.ui_final:
            try:
                self.ui_final.close()
                logger.debug(" Final screen closed")
            except Exception as e:
                logger.warning(f"️  Error closing final screen: {e}")
        
        # Clean up home screen
        if hasattr(self, 'ui_home') and self.ui_home:
            try:
                self.ui_home.close()
                logger.debug(" Home screen closed")
            except Exception as e:
                logger.warning(f"️  Error closing home screen: {e}")
        
        # Clean up team member screen
        if hasattr(self, 'ui_team_member') and self.ui_team_member:
            try:
                self.ui_team_member.close()
                logger.debug(" TeamMember screen closed")
            except Exception as e:
                logger.warning(f"️  Error closing team member screen: {e}")
        
        logger.info(" All screens cleaned up")
    
    def _force_stop_all_timers(self):
        """Force stop all timers across all screens for safe shutdown"""
        logger.info("Force stopping all application timers")
        
        # Stop timers in all screen instances
        screen_attrs = ['ui_home', 'ui_active', 'ui_final', 'ui_team_member']
        for screen_attr in screen_attrs:
            if hasattr(self, screen_attr):
                screen = getattr(self, screen_attr)
                if screen:
                    # Check for common timer names and stop them
                    timer_names = ['timer', 'timer2', 'timer3', 'TimerGame', 'traverse_Timer']
                    for timer_name in timer_names:
                        if hasattr(screen, timer_name):
                            timer_obj = getattr(screen, timer_name)
                            if timer_obj:
                                try:
                                    if hasattr(timer_obj, 'stop'):
                                        timer_obj.stop()
                                        logger.debug(f" {screen_attr}.{timer_name} stopped")
                                except (RuntimeError, AttributeError):
                                    logger.debug(f"️  {screen_attr}.{timer_name} already deleted or invalid")
                                except Exception as e:
                                    logger.warning(f"️  Error stopping {screen_attr}.{timer_name}: {e}")
        
        logger.info(" All application timers forcibly stopped")


if __name__ == "__main__":
    # Initialize logging
    from utils.logger import setup_root_logger
    setup_root_logger("INFO")
    
    logger.info("" + "=" * 60)
    logger.info(" STARTING CAGE GAME WITH COMPLETE UI AND NEW API")
    logger.info("" + "=" * 60)
    
    app = QtWidgets.QApplication(sys.argv)
    
    # Initialize leaderboard
    try:
        api = GameAPI()
        if api.authenticate():
            logger.info(" API authentication successful")
            # TODO: Uncomment when leaderboard is needed
            leaderboard = api.get_leaderboard()
            list_top5_TheCage.extend(leaderboard)
            logger.info(f"Initial leaderboard loaded: {len(leaderboard)} entries")
        else:
            logger.warning("️  Failed to authenticate for initial leaderboard")
    except Exception as e:
        logger.error(f" Error loading initial leaderboard: {e}")
    
    # Start main application
    try:
        main_app = MainApp()
        logger.info("Application started successfully!")
        sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
