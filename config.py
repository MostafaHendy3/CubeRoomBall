"""
Configuration Management for Cage Game
Handles all configuration settings for the game application
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class APIConfig:
    """API configuration settings"""
    base_url: str = "https://dev-eaa25-api-hpfyfcbshkabezeh.uaenorth-01.azurewebsites.net/"
    email: str = "eaa25admin@gmail.com"
    password: str = "qhv#1kGI$"
    # game_id: str = "314bc08a-e3b7-4ace-bf83-33141b014a97" 

    game_id: str = "878f6f84-7d65-4ecc-9450-872ca7e1a3f3"
    # game_name: str = "Cube Room Ball Game"
    game_name: str = "Falcon's Grasp"
    # game_status_timeout: int = 30  # Timeout for game status polling in seconds
    # submit_score_timeout: int = 11  # Timeout for submit score in seconds
    
   # Timeout settings (in seconds)
    auth_timeout: int = 30
    game_status_timeout: int = 8
    submit_score_timeout: int = 20
    leaderboard_timeout: int = 12


@dataclass
class GameConfig:
    """Game configuration settings"""
    timer_value: int = 15000  # Default timer value in milliseconds
    final_screen_timer: int = 15000  # Final screen display time
    ball_weight: int = 100

@dataclass
class SerialConfig:
    """Serial communication configuration settings"""
    enabled: bool = True  # Enable/disable serial communication
    port: str = "/dev/pts/9"  # Serial port
    baudrate: int = 9600
    timeout: float = 1.0


@dataclass
class MQTTConfig:
    """MQTT configuration settings"""
    broker: str = "localhost"
    port: int = 1883
    data_topics: list = None
    control_topics: list = None
    
    def __post_init__(self):
        if self.data_topics is None:
            self.data_topics = [
                "CubeRoomBall/score/Pub",
            ]
        
        if self.control_topics is None:
            self.control_topics = [
                "CubeRoomBall/game/start",
                "CubeRoomBall/game/stop", 
                "CubeRoomBall/game/restart",
                "CubeRoomBall/game/timer",
                "CubeRoomBall/game/Activate",
                "CubeRoomBall/game/Deactivate",
                "CubeRoomBall/game/timerfinal"
            ]


@dataclass
class Settings:
    """Main settings container"""
    api: APIConfig
    game: GameConfig
    mqtt: MQTTConfig
    serial: SerialConfig
    
    @classmethod
    def load(cls, config_file: Optional[str] = None) -> 'Settings':
        """Load settings from environment variables or config file"""
        
        # Load API settings from environment or defaults
        api_config = APIConfig(
            base_url=os.getenv('CAGE_API_BASE_URL', APIConfig.base_url),
            email=os.getenv('CAGE_API_EMAIL', APIConfig.email),
            password=os.getenv('CAGE_API_PASSWORD', APIConfig.password),
            game_id=os.getenv('CAGE_GAME_ID', APIConfig.game_id),
            game_name=os.getenv('CAGE_GAME_NAME', APIConfig.game_name),
            game_status_timeout=int(os.getenv('CAGE_GAME_STATUS_TIMEOUT', APIConfig.game_status_timeout)),
        )
        
        # Load game settings
        game_config = GameConfig(
            timer_value=int(os.getenv('CAGE_TIMER_VALUE', GameConfig.timer_value)),
            final_screen_timer=int(os.getenv('CAGE_FINAL_TIMER', GameConfig.final_screen_timer)),
            ball_weight=int(os.getenv('CAGE_BALL_WEIGHT', GameConfig.ball_weight)),
        )
        
        # Load MQTT settings
        mqtt_config = MQTTConfig(
            broker=os.getenv('CAGE_MQTT_BROKER', MQTTConfig.broker),
            port=int(os.getenv('CAGE_MQTT_PORT', MQTTConfig.port)),
        )
        
        # Load Serial settings
        serial_config = SerialConfig(
            enabled=os.getenv('CAGE_SERIAL_ENABLED', 'true').lower() == 'true',
            port=os.getenv('CAGE_SERIAL_PORT', SerialConfig.port),
            baudrate=int(os.getenv('CAGE_SERIAL_BAUDRATE', SerialConfig.baudrate)),
            timeout=float(os.getenv('CAGE_SERIAL_TIMEOUT', SerialConfig.timeout)),
        )
        
        return cls(
            api=api_config,
            game=game_config,
            mqtt=mqtt_config,
            serial=serial_config
        )


# Global settings instance
settings = Settings.load()


# Backwards compatibility
class Config:
    """Legacy config class for backwards compatibility"""
    
    @property
    def settings(self):
        return settings


config = Config()
