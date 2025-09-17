"""
Audio Service for Game Applications
Provides threaded audio playback using QMediaPlayer with multiple sound interfaces
"""

import os
import sys
from typing import Optional, Dict, Any
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtWidgets import QApplication

from .logger import get_logger


class AudioPlayer(QObject):
    """
    Individual audio player that wraps QMediaPlayer with additional functionality
    """
    
    # Signals
    playback_finished = pyqtSignal()
    playback_error = pyqtSignal(str)
    playback_state_changed = pyqtSignal(int)  # QMediaPlayer.State
    
    def __init__(self, audio_file: str, loop: bool = False, volume: int = 100):
        super().__init__()
        self.logger = get_logger(f"{__name__}.AudioPlayer")
        
        self.audio_file = audio_file
        self.loop = loop
        self.volume = volume
        self.should_loop = loop  # Flag to control looping behavior
        
        # Initialize media player
        self.media_player = QMediaPlayer()
        self.media_player.setVolume(volume)
        
        # Connect signals
        self.media_player.stateChanged.connect(self._on_state_changed)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.media_player.error.connect(self._on_error)
        
        # Load audio file
        self._load_audio_file()
        
    def _load_audio_file(self):
        """Load the audio file into the media player"""
        # Convert to absolute path if it's relative
        if not os.path.isabs(self.audio_file):
            # Get the directory of the current script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # Go up one level to the game directory
            game_dir = os.path.dirname(script_dir)
            self.audio_file = os.path.join(game_dir, self.audio_file)
            
        if not os.path.exists(self.audio_file):
            self.logger.error(f"Audio file not found: {self.audio_file}")
            self.playback_error.emit(f"Audio file not found: {self.audio_file}")
            return
            
        media_content = QMediaContent(QUrl.fromLocalFile(self.audio_file))
        self.media_player.setMedia(media_content)
        self.logger.debug(f"Loaded audio file: {self.audio_file}")
        
    def _on_state_changed(self, state):
        """Handle media player state changes"""
        self.playback_state_changed.emit(state)
        
        if state == QMediaPlayer.StoppedState and self.should_loop:
            # Restart playback for loop mode
            self.media_player.play()
            self.logger.debug(f"Restarted looped playback: {self.audio_file}")
        elif state == QMediaPlayer.StoppedState:
            self.playback_finished.emit()
            
    def _on_media_status_changed(self, status):
        """Handle media status changes"""
        if status == QMediaPlayer.EndOfMedia and self.should_loop:
            # Restart for loop mode
            self.media_player.setPosition(0)
            self.media_player.play()
            
    def _on_error(self, error):
        """Handle media player errors"""
        error_msg = f"Media player error: {error}"
        self.logger.error(error_msg)
        self.playback_error.emit(error_msg)
        
    def play(self):
        """Start playback"""
        if self.media_player.state() != QMediaPlayer.PlayingState:
            # Re-enable looping if this player was configured to loop
            self.should_loop = self.loop
            self.media_player.play()
            self.logger.debug(f"Started playback: {self.audio_file}")
            
    def stop(self):
        """Stop playback"""
        if self.media_player.state() != QMediaPlayer.StoppedState:
            # Disable looping temporarily to prevent auto-restart
            self.should_loop = False
            self.media_player.stop()
            self.logger.debug(f"Stopped playback: {self.audio_file}")
            
    def pause(self):
        """Pause playback"""
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.logger.debug(f"Paused playback: {self.audio_file}")
            
    def set_volume(self, volume: int):
        """Set volume (0-100)"""
        self.volume = max(0, min(100, volume))
        self.media_player.setVolume(self.volume)
        self.logger.debug(f"Set volume to {self.volume}% for: {self.audio_file}")
        
    def get_state(self) -> int:
        """Get current playback state"""
        return self.media_player.state()
        
    def is_playing(self) -> bool:
        """Check if currently playing"""
        return self.media_player.state() == QMediaPlayer.PlayingState
        
    def set_loop(self, loop: bool):
        """Enable or disable looping"""
        self.loop = loop
        self.should_loop = loop
        self.logger.debug(f"Set loop to {loop} for: {self.audio_file}")


class AudioService(QObject):
    """
    Threaded Audio Service that manages multiple audio players
    Provides interfaces for continuous sound, inactive game sound, and active game sound
    """
    
    # Signals
    service_ready = pyqtSignal()
    service_error = pyqtSignal(str)
    player_state_changed = pyqtSignal(str, int)  # player_name, state
    
    def __init__(self, audio_files: Optional[Dict[str, str]] = None):
        super().__init__()
        self.logger = get_logger(f"{__name__}.AudioService")
        
        # Default audio files (can be overridden)
        self.audio_files = audio_files or {
            'continuous': 'Assets/mp3/2066.wav',
            'inactive_game': 'Assets/mp3/2066.wav',
            'active_game': 'Assets/mp3/2066.wav'
        }
        
        # Convert relative paths to absolute paths
        self.audio_files = self._resolve_audio_paths(self.audio_files)
        
        # Audio players
        self.players: Dict[str, AudioPlayer] = {}
        
        # Service state
        self.is_initialized = False
        self.is_running = False
        
        # Initialize players
        self._initialize_players()
        
    def _resolve_audio_paths(self, audio_files: Dict[str, str]) -> Dict[str, str]:
        """Convert relative paths to absolute paths"""
        resolved_files = {}
        for name, file_path in audio_files.items():
            if not os.path.isabs(file_path):
                # Get the directory of the current script
                script_dir = os.path.dirname(os.path.abspath(__file__))
                # Go up one level to the game directory
                game_dir = os.path.dirname(script_dir)
                resolved_files[name] = os.path.join(game_dir, file_path)
            else:
                resolved_files[name] = file_path
        return resolved_files
        
    def _initialize_players(self):
        """Initialize all audio players"""
        try:
            # Continuous sound player (looped)
            if 'continuous' in self.audio_files:
                self.players['continuous'] = AudioPlayer(
                    self.audio_files['continuous'],
                    loop=True,
                    volume=50  # Lower volume for continuous background
                )
                
            # Inactive game sound player
            if 'inactive_game' in self.audio_files:
                self.players['inactive_game'] = AudioPlayer(
                    self.audio_files['inactive_game'],
                    loop=True,
                    volume=70
                )
                
            # Active game sound player
            if 'active_game' in self.audio_files:
                self.players['active_game'] = AudioPlayer(
                    self.audio_files['active_game'],
                    loop=True,
                    volume=80
                )
                
            # Connect player signals
            for name, player in self.players.items():
                player.playback_finished.connect(lambda n=name: self._on_player_finished(n))
                player.playback_error.connect(lambda error, n=name: self._on_player_error(n, error))
                player.playback_state_changed.connect(lambda state, n=name: self._on_player_state_changed(n, state))
                
            self.is_initialized = True
            self.logger.info("Audio service initialized successfully")
            self.service_ready.emit()
            
        except Exception as e:
            error_msg = f"Failed to initialize audio service: {e}"
            self.logger.error(error_msg)
            self.service_error.emit(error_msg)
            
    def _on_player_finished(self, player_name: str):
        """Handle player finished signal"""
        self.logger.debug(f"Player finished: {player_name}")
        
    def _on_player_error(self, player_name: str, error: str):
        """Handle player error signal"""
        self.logger.error(f"Player error in {player_name}: {error}")
        self.service_error.emit(f"Player {player_name}: {error}")
        
    def _on_player_state_changed(self, player_name: str, state: int):
        """Handle player state change signal"""
        self.logger.debug(f"Player {player_name} state changed to: {state}")
        self.player_state_changed.emit(player_name, state)
        
    # Public API Methods
    
    def start_service(self):
        """Start the audio service"""
        if not self.is_initialized:
            self.logger.error("Cannot start service: not initialized")
            return False
            
        self.is_running = True
        self.logger.info("Audio service started")
        return True
        
    def stop_service(self):
        """Stop the audio service and all players"""
        self.is_running = False
        
        # Stop all players
        for name, player in self.players.items():
            player.stop()
            
        self.logger.info("Audio service stopped")
        
    # Continuous Sound Interface
    
    def play_continuous_sound(self):
        """Start playing continuous background sound"""
        if 'continuous' in self.players:
            self.players['continuous'].play()
            self.logger.info("Started continuous sound")
        else:
            self.logger.warning("Continuous sound player not available")
            
    def stop_continuous_sound(self):
        """Stop continuous background sound"""
        if 'continuous' in self.players:
            self.players['continuous'].stop()
            self.logger.info("Stopped continuous sound")
            
    def set_continuous_volume(self, volume: int):
        """Set volume for continuous sound (0-100)"""
        if 'continuous' in self.players:
            self.players['continuous'].set_volume(volume)
            
    # Inactive Game Sound Interface
    
    def play_inactive_game_sound(self):
        """Play sound for inactive game state"""
        if 'inactive_game' in self.players:
            self.players['inactive_game'].play()
            self.logger.info("Started inactive game sound")
        else:
            self.logger.warning("Inactive game sound player not available")
            
    def stop_inactive_game_sound(self):
        """Stop inactive game sound"""
        if 'inactive_game' in self.players:
            self.players['inactive_game'].stop()
            self.logger.info("Stopped inactive game sound")
            
    def set_inactive_game_volume(self, volume: int):
        """Set volume for inactive game sound (0-100)"""
        if 'inactive_game' in self.players:
            self.players['inactive_game'].set_volume(volume)
            
    # Active Game Sound Interface
    
    def play_active_game_sound(self):
        """Play sound for active game state"""
        if 'active_game' in self.players:
            self.players['active_game'].play()
            self.logger.info("Started active game sound")
        else:
            self.logger.warning("Active game sound player not available")
            
    def stop_active_game_sound(self):
        """Stop active game sound"""
        if 'active_game' in self.players:
            self.players['active_game'].stop()
            self.logger.info("Stopped active game sound")
            
    def set_active_game_volume(self, volume: int):
        """Set volume for active game sound (0-100)"""
        if 'active_game' in self.players:
            self.players['active_game'].set_volume(volume)
            
    # General Control Methods
    
    def stop_all_sounds(self):
        """Stop all currently playing sounds"""
        for name, player in self.players.items():
            player.stop()
        self.logger.info("Stopped all sounds")
        
    def pause_all_sounds(self):
        """Pause all currently playing sounds"""
        for name, player in self.players.items():
            player.pause()
        self.logger.info("Paused all sounds")
        
    def get_player_state(self, player_name: str) -> Optional[int]:
        """Get the state of a specific player"""
        if player_name in self.players:
            return self.players[player_name].get_state()
        return None
        
    def is_player_playing(self, player_name: str) -> bool:
        """Check if a specific player is currently playing"""
        if player_name in self.players:
            return self.players[player_name].is_playing()
        return False
        
    def get_available_players(self) -> list:
        """Get list of available player names"""
        return list(self.players.keys())
        
    def update_audio_file(self, player_name: str, audio_file: str):
        """Update the audio file for a specific player"""
        # Resolve the audio file path
        resolved_audio_file = self._resolve_audio_paths({player_name: audio_file})[player_name]
        
        if player_name in self.players and os.path.exists(resolved_audio_file):
            # Stop current player
            self.players[player_name].stop()
            
            # Create new player with new file
            self.players[player_name] = AudioPlayer(
                resolved_audio_file,
                loop=(player_name == 'continuous'),
                volume=self.players[player_name].volume
            )
            
            # Reconnect signals
            self.players[player_name].playback_finished.connect(
                lambda n=player_name: self._on_player_finished(n)
            )
            self.players[player_name].playback_error.connect(
                lambda error, n=player_name: self._on_player_error(n, error)
            )
            self.players[player_name].playback_state_changed.connect(
                lambda state, n=player_name: self._on_player_state_changed(n, state)
            )
            
            self.logger.info(f"Updated audio file for {player_name}: {resolved_audio_file}")
        else:
            self.logger.warning(f"Cannot update audio file for {player_name}: file not found or player not available")
            
    def set_player_loop(self, player_name: str, loop: bool):
        """Enable or disable looping for a specific player"""
        if player_name in self.players:
            self.players[player_name].set_loop(loop)
            self.logger.info(f"Set loop to {loop} for player: {player_name}")
        else:
            self.logger.warning(f"Player not found: {player_name}")
            
    def get_player_loop(self, player_name: str) -> bool:
        """Get the loop setting for a specific player"""
        if player_name in self.players:
            return self.players[player_name].loop
        return False


class AudioServiceThread(QThread):
    """
    Thread wrapper for AudioService to run in background
    """
    
    # Signals
    service_ready = pyqtSignal()
    service_error = pyqtSignal(str)
    player_state_changed = pyqtSignal(str, int)
    
    def __init__(self, audio_files: Optional[Dict[str, str]] = None):
        super().__init__()
        self.audio_service = AudioService(audio_files)
        
        # Connect service signals to thread signals
        self.audio_service.service_ready.connect(self.service_ready.emit)
        self.audio_service.service_error.connect(self.service_error.emit)
        self.audio_service.player_state_changed.connect(self.player_state_changed.emit)
        
    def run(self):
        """Thread entry point"""
        # Start the audio service
        self.audio_service.start_service()
        
        # Keep thread alive
        self.exec_()
        
    def stop(self):
        """Stop the audio service and thread"""
        self.audio_service.stop_service()
        self.quit()
        self.wait()
        
    # Delegate methods to audio service
    def play_continuous_sound(self):
        self.audio_service.play_continuous_sound()
        
    def stop_continuous_sound(self):
        self.audio_service.stop_continuous_sound()
        
    def set_continuous_volume(self, volume: int):
        self.audio_service.set_continuous_volume(volume)
        
    def play_inactive_game_sound(self):
        self.audio_service.play_inactive_game_sound()
        
    def stop_inactive_game_sound(self):
        self.audio_service.stop_inactive_game_sound()
        
    def set_inactive_game_volume(self, volume: int):
        self.audio_service.set_inactive_game_volume(volume)
        
    def play_active_game_sound(self):
        self.audio_service.play_active_game_sound()
        
    def stop_active_game_sound(self):
        self.audio_service.stop_active_game_sound()
        
    def set_active_game_volume(self, volume: int):
        self.audio_service.set_active_game_volume(volume)
        
    def stop_all_sounds(self):
        self.audio_service.stop_all_sounds()
        
    def pause_all_sounds(self):
        self.audio_service.pause_all_sounds()
        
    def get_player_state(self, player_name: str):
        return self.audio_service.get_player_state(player_name)
        
    def is_player_playing(self, player_name: str):
        return self.audio_service.is_player_playing(player_name)
        
    def get_available_players(self):
        return self.audio_service.get_available_players()
        
    def update_audio_file(self, player_name: str, audio_file: str):
        self.audio_service.update_audio_file(player_name, audio_file)
        
    def set_player_loop(self, player_name: str, loop: bool):
        self.audio_service.set_player_loop(player_name, loop)
        
    def get_player_loop(self, player_name: str):
        return self.audio_service.get_player_loop(player_name)


# Example usage and testing
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Create audio service thread
    audio_files = {
        'continuous': 'Assets/mp3/2066.wav',
        'inactive_game': 'Assets/mp3/2066.wav',
        'active_game': 'Assets/mp3/2066.wav'
    }
    
    audio_thread = AudioServiceThread(audio_files)
    
    # Connect signals
    audio_thread.service_ready.connect(lambda: print("Audio service ready!"))
    audio_thread.service_error.connect(lambda error: print(f"Audio service error: {error}"))
    audio_thread.player_state_changed.connect(
        lambda name, state: print(f"Player {name} state: {state}")
    )
    
    # Start the thread
    audio_thread.start()
    
    # Wait for service to be ready
    audio_thread.service_ready.wait()
    
    # Test the service
    print("Testing audio service...")
    
    # Test continuous sound
    audio_thread.play_continuous_sound()
    
    # Test other sounds after a delay
    import time
    time.sleep(2)
    audio_thread.play_inactive_game_sound()
    
    time.sleep(2)
    audio_thread.play_active_game_sound()
    
    time.sleep(5)
    audio_thread.stop_all_sounds()
    
    # Clean up
    audio_thread.stop()
    app.quit()
