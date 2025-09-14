"""
Game API Module for Fast Reaction Game
Handles all API communication with the game server following the proper game flow:
1. Poll for game initialization (status=initiated)
2. Poll for game start (status=playing) 
3. Submit scores at end of game
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import ConnectionError, Timeout, RequestException
from typing import Dict, List, Optional, Tuple
import logging
import time
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from utils.logger import get_logger

logger = get_logger(__name__)


class GameAPI:
    """Game API client for server communication"""
    
    def __init__(self):
        logger.info("" + "=" * 60)
        logger.info(" STARTING Fast Reaction GAME API CLIENT INITIALIZATION")
        logger.info("" + "=" * 60)
        
        try:
            # Step 1: Load configuration
            logger.info(" Step 1: Loading API configuration...")
            self.config = config.settings.api
            logger.info(" Configuration loaded successfully")
            
            # Step 2: Extract configuration values with validation
            logger.info(" Step 2: Extracting configuration values...")
            self._validate_and_set_config()
            
            # Step 3: Initialize authentication state
            logger.info(" Step 3: Initializing authentication state...")
            self.token = None
            self.headers = {}
            logger.info(" Authentication state initialized")
            
            # Step 4: Setup HTTP session
            logger.info(" Step 4: Setting up HTTP session...")
            self.session = self._setup_session()
            logger.info(" HTTP session configured")
            
            # Step 5: Validate initialization
            logger.info(" Step 5: Validating initialization...")
            self._validate_initialization()
            
            # Success logging
            logger.info("" + "=" * 60)
            logger.info(" Fast Reaction GAME API CLIENT INITIALIZED SUCCESSFULLY!")
            logger.info("" + "=" * 60)
            logger.info(f" Base URL: {self.base_url}")
            logger.info(f" Game ID: {self.game_id}")
            logger.info(f"️  Game Name: {self.game_name}")
            logger.info(f" Email: {self.email[:10]}...@{self.email.split('@')[1] if '@' in self.email else 'unknown'}")
            logger.info(f" Session: {type(self.session).__name__} with retry strategy")
            logger.info("" + "=" * 60)
            
        except Exception as e:
            logger.error("" + "=" * 60)
            logger.error(" Fast Reaction GAME API CLIENT INITIALIZATION FAILED!")
            logger.error("" + "=" * 60)
            logger.error(f" Error type: {type(e).__name__}")
            logger.error(f" Error details: {str(e)}")
            logger.error("" + "=" * 60)
            
            # Log the specific initialization step that failed
            self._log_initialization_failure(e)
            
            # Re-raise the exception so the calling code knows initialization failed
            raise RuntimeError(f"GameAPI initialization failed: {str(e)}") from e
    
    def _setup_session(self) -> requests.Session:
        """Setup requests session with retry strategy"""
        logger.debug(" Setting up HTTP session with retry strategy...")
        
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
            backoff_factor=1
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        logger.debug(" HTTP session configured with:")
        logger.debug(f"   • Max retries: {retry_strategy.total}")
        logger.debug(f"   • Status codes for retry: {retry_strategy.status_forcelist}")
        logger.debug(f"   • Allowed methods: {retry_strategy.allowed_methods}")
        logger.debug(f"   • Backoff factor: {retry_strategy.backoff_factor}")
        
        return session
    
    def _validate_and_set_config(self):
        """Validate and set configuration values"""
        try:
            # Validate base_url
            if not hasattr(self.config, 'base_url') or not self.config.base_url:
                raise ValueError("base_url is missing or empty in configuration")
            self.base_url = self.config.base_url.rstrip('/')  # Remove trailing slash
            logger.debug(f" Base URL validated: {self.base_url}")
            
            # Validate email
            if not hasattr(self.config, 'email') or not self.config.email:
                raise ValueError("email is missing or empty in configuration")
            if '@' not in self.config.email:
                raise ValueError("email format appears invalid (no @ symbol)")
            self.email = self.config.email
            logger.debug(f" Email validated: {self.email[:10]}...@{self.email.split('@')[1]}")
            
            # Validate password
            if not hasattr(self.config, 'password') or not self.config.password:
                raise ValueError("password is missing or empty in configuration")
            if len(self.config.password) < 6:
                logger.warning("️  Password appears short (less than 6 characters)")
            self.password = self.config.password
            logger.debug(" Password validated (length: {} chars)".format(len(self.password)))
            
            # Validate game_id
            if not hasattr(self.config, 'game_id') or not self.config.game_id:
                raise ValueError("game_id is missing or empty in configuration")
            self.game_id = self.config.game_id
            logger.debug(f" Game ID validated: {self.game_id}")
            
            # Validate game_name
            if not hasattr(self.config, 'game_name') or not self.config.game_name:
                logger.warning("️  game_name is missing, using default")
                self.game_name = "Fast Reaction"
            else:
                self.game_name = self.config.game_name
            logger.debug(f" Game name validated: {self.game_name}")
            
        except Exception as e:
            logger.error(f" Configuration validation failed: {str(e)}")
            raise
    
    def _validate_initialization(self):
        """Validate that initialization completed successfully"""
        validation_errors = []
        
        # Check required attributes
        required_attrs = ['base_url', 'email', 'password', 'game_id', 'game_name', 'session', 'token', 'headers']
        for attr in required_attrs:
            if not hasattr(self, attr):
                validation_errors.append(f"Missing attribute: {attr}")
        
        # Check base_url format
        if hasattr(self, 'base_url'):
            if not self.base_url.startswith(('http://', 'https://')):
                validation_errors.append(f"Invalid base_url format: {self.base_url}")
        
        # Check session type
        if hasattr(self, 'session'):
            if not isinstance(self.session, requests.Session):
                validation_errors.append(f"Invalid session type: {type(self.session)}")
        
        # Check initial auth state
        if hasattr(self, 'token') and self.token is not None:
            validation_errors.append("Token should be None at initialization")
        
        if hasattr(self, 'headers') and self.headers:
            validation_errors.append("Headers should be empty at initialization")
        
        if validation_errors:
            error_msg = "Initialization validation failed: " + "; ".join(validation_errors)
            logger.error(f" {error_msg}")
            raise RuntimeError(error_msg)
        
        logger.info(" Initialization validation passed")
    
    def _log_initialization_failure(self, error):
        """Log detailed information about initialization failure"""
        logger.error("" + "=" * 50)
        logger.error(" INITIALIZATION FAILURE DIAGNOSIS")
        logger.error("" + "=" * 50)
        
        # Check what we have so far
        logger.error(" Configuration Status:")
        try:
            if hasattr(self, 'config'):
                logger.error("    Config object loaded")
                logger.error(f"    Config type: {type(self.config)}")
            else:
                logger.error("    Config object not loaded")
        except:
            logger.error("    Error checking config object")
        
        logger.error(" Attribute Status:")
        attrs_to_check = ['base_url', 'email', 'password', 'game_id', 'game_name', 'session', 'token', 'headers']
        for attr in attrs_to_check:
            try:
                if hasattr(self, attr):
                    value = getattr(self, attr)
                    if attr == 'password':
                        logger.error(f"    {attr}: [REDACTED] (length: {len(value) if value else 0})")
                    elif attr == 'email':
                        logger.error(f"    {attr}: {value[:10] if value else 'None'}...")
                    elif attr == 'session':
                        logger.error(f"    {attr}: {type(value).__name__ if value else 'None'}")
                    else:
                        logger.error(f"    {attr}: {str(value)[:50] if value else 'None'}...")
                else:
                    logger.error(f"    {attr}: NOT SET")
            except Exception as e:
                logger.error(f"    {attr}: Error checking - {str(e)}")
        
        logger.error("" + "=" * 50)
        
        # Import traceback for detailed error info
        import traceback
        logger.error(" Full Stack Trace:")
        logger.error(traceback.format_exc())
    
    def authenticate(self) -> bool:
        """Authenticate with the API and get token - waits until server responds"""
        url = f"{self.base_url}/login2"
        data = {
            "email": self.email,
            "password": self.password
        }
        
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                logger.info("" + "=" * 50)
                logger.info(f" AUTHENTICATION ATTEMPT {attempt + 1}/{max_retries}")
                logger.info("" + "=" * 50)
                logger.info(f" POST {url}")
                logger.debug(f" Request data: {{'email': '{self.email[:10]}...', 'password': '***'}}")
                
                start_time = time.time()
                
                # Increase timeout to wait for server response
                response = self.session.post(
                    url, 
                    json=data, 
                    timeout=30  # Wait up to 30 seconds for authentication
                )
                
                elapsed_time = time.time() - start_time
                logger.info(f"️  Response received in {elapsed_time:.2f} seconds")
                logger.info(f" Status Code: {response.status_code}")
                
                response.raise_for_status()
                
                token_data = response.json()
                logger.debug(f" Authentication response structure: {list(token_data.keys())}")
                
                # Extract token from response
                if 'data' in token_data and 'token' in token_data['data']:
                    self.token = token_data['data']['token']
                    logger.debug(" Token found in response.data.token")
                elif 'token' in token_data:
                    self.token = token_data['token']
                    logger.debug(" Token found in response.token")
                else:
                    logger.error(f" No token found in response structure: {list(token_data.keys())}")
                    logger.debug(f"Full response: {token_data}")
                    self.token = None
                
                if self.token:
                    self.headers = {"Authorization": f"Bearer {self.token}"}
                    logger.info("" + "=" * 50)
                    logger.info(" AUTHENTICATION SUCCESSFUL!")
                    logger.info("" + "=" * 50)
                    logger.info(f" Token length: {len(self.token)} characters")
                    logger.info(f" Token preview: {self.token[:20]}...")
                    logger.info(f" Headers configured with Bearer token")
                    logger.info("" + "=" * 50)
                    return True
                else:
                    logger.error(" Authentication failed - no token in response")
                    if attempt < max_retries - 1:
                        logger.warning(f" Retrying authentication in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        continue
                    return False
                    
            except Timeout as e:
                elapsed_time = time.time() - start_time
                logger.error("" + "=" * 50)
                logger.error(f" AUTHENTICATION TIMEOUT (attempt {attempt + 1})")
                logger.error("" + "=" * 50)
                logger.error(f"️  Elapsed time: {elapsed_time:.2f} seconds")
                logger.error(f" Error details: {str(e)}")
                if attempt < max_retries - 1:
                    logger.warning(f" Retrying authentication in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                logger.error(" All timeout retries exhausted")
                return False
            except (ConnectionError, RequestException) as e:
                elapsed_time = time.time() - start_time
                logger.error("" + "=" * 50)
                logger.error(f" AUTHENTICATION CONNECTION ERROR (attempt {attempt + 1})")
                logger.error("" + "=" * 50)
                logger.error(f"️  Elapsed time: {elapsed_time:.2f} seconds")
                logger.error(f" Error type: {type(e).__name__}")
                logger.error(f" Error details: {str(e)}")
                if attempt < max_retries - 1:
                    logger.warning(f" Retrying authentication in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                logger.error(" All connection retries exhausted")
                return False
            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error("" + "=" * 50)
                logger.error(f" UNEXPECTED AUTHENTICATION ERROR (attempt {attempt + 1})")
                logger.error("" + "=" * 50)
                logger.error(f"️  Elapsed time: {elapsed_time:.2f} seconds")
                logger.error(f" Error type: {type(e).__name__}")
                logger.error(f" Error details: {str(e)}")
                logger.error("" + "=" * 50)
                import traceback
                logger.debug(f" Stack trace: {traceback.format_exc()}")
                return False
        
        logger.error("" + "=" * 50)
        logger.error(" AUTHENTICATION COMPLETELY FAILED")
        logger.error("" + "=" * 50)
        logger.error(f" Attempted {max_retries} times with {retry_delay}s delays")
        logger.error("" + "=" * 50)
        return False
    
    def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid authentication token and proper headers"""
        if not self.token:
            logger.warning("" + "=" * 30)
            logger.warning("️  NO AUTHENTICATION TOKEN FOUND")
            logger.warning("" + "=" * 30)
            logger.info(" Attempting automatic authentication...")
            return self.authenticate()
        else:
            logger.debug(f" Authentication token available (length: {len(self.token)})")
            
            # Verify authorization header is properly configured
            if not self.verify_authorization_header():
                logger.warning("️  Authorization header verification failed")
                # Try to recreate headers
                self.headers = {"Authorization": f"Bearer {self.token}"}
                logger.info(" Recreated Authorization header")
                
            return True
    
    def get_game_status(self, game_result_id: str) -> Optional[Dict]:
        """Get current game status"""
        if not self._ensure_authenticated():
            return None
        
        url = f"{self.base_url}/game-result/{game_result_id}"
        
        try:
            response = self.session.get(
                url, 
                headers=self.headers,
                timeout=self.config.game_status_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Game status retrieved: {data.get('data', {}).get('status', 'unknown')}")
                return data.get('data')
            else:
                logger.error(f"Failed to get game status: {response.status_code}")
                return None
                
        except (ConnectionError, Timeout, RequestException) as e:
            logger.error(f"Game status error: {e}")
            return None
    
    def poll_game_initialization(self) -> Optional[Dict]:
        """
        Step 1: Poll for game initialization
        Endpoint: GET /game-result?status=initiated&load_participant=true&gameID={GAMEID}&limit=1
        Returns game data when status is 'initialized'
        """
        logger.info("" + "=" * 40)
        logger.info(" STEP 1: POLLING GAME INITIALIZATION")
        logger.info("" + "=" * 40)
        
        if not self._ensure_authenticated():
            logger.error(" Authentication required for game initialization polling")
            return None
        
        url = f"{self.base_url}/game-result"
        params = {
            "status": "initiated",
            "load_participant": "true", 
            "gameID": self.game_id,
            "limit": "1"
        }
        
        logger.debug(f" GET {url}")
        logger.debug(f" Parameters: {params}")
        logger.debug(f" Timeout: {self.config.game_status_timeout}s")
        logger.debug(f" Authorization: Bearer {self.token[:20] if self.token else 'None'}...")
        logger.debug(f" Headers: {dict(self.headers)}")
        
        start_time = time.time()
        
        try:
            # Using GET as per API specification
            response = self.session.get(
                url,
                params=params,
                headers=self.headers,
                timeout=self.config.game_status_timeout
            )
            
            elapsed_time = time.time() - start_time
            logger.info(f"️  Response received in {elapsed_time:.2f} seconds")
            logger.info(f" Status Code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f" Response data: {data}")
                    games = data.get('data', [])
                    
                    logger.info(f" Response contains {len(games)} games")
                    logger.info(f" Response structure: {list(data.keys())}")
                    
                    if games:
                        game = games[0]
                        logger.info("" + "=" * 40)
                        logger.info(" GAME INITIALIZATION FOUND!")
                        logger.info("" + "=" * 40)
                        logger.info(f" Game ID: {game.get('id')}")
                        logger.info(f" Team: {game.get('name', 'Unknown')}")
                        logger.info(f" Players: {len(game.get('nodeIDs', []))}")
                        logger.info(f" Status: {game.get('status', 'Unknown')}")
                        logger.debug(f" Full game data keys: {list(game.keys())}")
                        logger.info("" + "=" * 40)
                        return game
                    else:
                        logger.info(" No initiated games found - waiting for game admin")
                        return None
                        
                except ValueError as e:
                    logger.error(f" Failed to parse JSON response: {e}")
                    logger.debug(f" Raw response content: {response.text[:200]}...")
                    return None
                except Exception as e:
                    logger.error(f" Unexpected error processing response: {e}")
                    return None
            else:
                # Handle non-200 responses
                response_text = response.text if response.text else "No response text"
                logger.error(f" Failed to poll game initialization: HTTP {response.status_code}")
                logger.error(f" Response text: {response_text[:500]}...")  # Limit to 500 chars
                
                # Log additional response details for debugging
                logger.debug(f" Response headers: {dict(response.headers)}")
                logger.debug(f" Response encoding: {response.encoding}")
                
                return None
                
        except (ConnectionError, Timeout, RequestException) as e:
            elapsed_time = time.time() - start_time
            logger.error("" + "=" * 40)
            logger.error(" GAME INITIALIZATION POLLING ERROR")
            logger.error("" + "=" * 40)
            logger.error(f"️  Elapsed time: {elapsed_time:.2f} seconds")
            logger.error(f" Error type: {type(e).__name__}")
            logger.error(f" Error details: {str(e)}")
            logger.error("" + "=" * 40)
            return None
    
    def poll_game_start(self, game_result_id: str) -> Optional[Dict]:
        """
        Step 2: Poll for game start signal - Single request version
        Endpoint: GET /game-result/{game_result_id}
        Returns game data when status changes to 'playing'
        """
        logger.info("" + "=" * 40)
        logger.info(" STEP 2: POLLING GAME START")
        logger.info("" + "=" * 40)
        
        if not self._ensure_authenticated():
            logger.error(" Authentication required for game start polling")
            return None
        
        url = f"{self.base_url}/game-result/{game_result_id}"
        
        logger.debug(f" GET {url}")
        logger.debug(f" Timeout: {self.config.game_status_timeout}s")
        logger.debug(f" Authorization: Bearer {self.token[:20] if self.token else 'None'}...")
        logger.debug(f" Headers: {dict(self.headers)}")
        
        start_time = time.time()
        
        try:
            # Using GET as per API specification
            response = self.session.get(
                url,
                headers=self.headers,
                timeout=self.config.game_status_timeout
            )
            
            elapsed_time = time.time() - start_time
            logger.info(f"️  Response received in {elapsed_time:.2f} seconds")
            logger.info(f" Status Code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    game_data = data.get('data')
                    
                    if game_data:
                        status = game_data.get('status', 'unknown')
                        logger.info(f" Game status: {status}")
                        
                        if status == "playing":
                            logger.info("" + "=" * 40)
                            logger.info(" GAME START SIGNAL RECEIVED!")
                            logger.info("" + "=" * 40)
                            logger.info(f" Game ID: {game_data.get('id')}")
                            logger.info(f" Status: {status}")
                            logger.debug(f" Full game data keys: {list(game_data.keys())}")
                            logger.info(" READY TO START GAMEPLAY! ")
                            logger.info("" + "=" * 40)
                            return game_data
                        elif status == "cancel":
                            logger.warning("️  Game cancelled by admin")
                            return {"status": "cancel", "cancelled": True}
                        else:
                            logger.info(f" Game not yet started - current status: {status}")
                            return None
                    else:
                        logger.warning("️  No game data in response")
                        return None
                        
                except ValueError as e:
                    logger.error(f" Failed to parse JSON response: {e}")
                    logger.debug(f" Raw response content: {response.text[:200]}...")
                    return None
                except Exception as e:
                    logger.error(f" Unexpected error processing response: {e}")
                    return None
            else:
                # Handle non-200 responses
                response_text = response.text if response.text else "No response text"
                logger.error(f" Failed to poll game start: HTTP {response.status_code}")
                logger.error(f" Response text: {response_text[:500]}...")  # Limit to 500 chars
                
                # Log additional response details for debugging
                logger.debug(f" Response headers: {dict(response.headers)}")
                logger.debug(f" Response encoding: {response.encoding}")
                
                return None
                
        except (ConnectionError, Timeout, RequestException) as e:
            elapsed_time = time.time() - start_time
            logger.error("" + "=" * 40)
            logger.error(" GAME START POLLING ERROR")
            logger.error("" + "=" * 40)
            logger.error(f"️  Elapsed time: {elapsed_time:.2f} seconds")
            logger.error(f" Error type: {type(e).__name__}")
            logger.error(f" Error details: {str(e)}")
            logger.error("" + "=" * 40)
            return None

    def poll_game_start_continuous(self, game_result_id: str, submit_score_flag_ref=None, started_flag_ref=None, cancel_flag_ref=None, max_polls=None, game_stopped_check=None) -> Optional[Dict]:
        """
        Step 2: Continuously poll for game start signal like
        This method polls continuously until game starts, gets cancelled, or score submission is triggered
        
        Args:
            game_result_id: The game result ID to poll
            submit_score_flag_ref: Reference to submit_score_flag for external control
            started_flag_ref: Reference to started_flag for tracking game state  
            cancel_flag_ref: Reference to cancel_flag for tracking cancellation
            max_polls: Maximum number of polls before giving up (None for infinite)
            game_stopped_check: Optional callback to check if game has stopped (returns True to stop polling)
        
        Returns:
            Dict with game data when status changes to 'playing', or cancellation info
        """
        logger.info("" + "=" * 50)
        logger.info(" STEP 2: CONTINUOUS POLLING FOR GAME START")
        logger.info("" + "=" * 50)
        
        if not self._ensure_authenticated():
            logger.error(" Authentication required for game start polling")
            return None
        
        url = f"{self.base_url}/game-result/{game_result_id}"
        logger.info(f" Polling URL: {url}")
        logger.info(f" Using Bearer token: {self.token[:20] if self.token else 'None'}...")
        
        poll_count = 0
        while True:
            if max_polls and poll_count >= max_polls:
                logger.warning(f" Maximum polls ({max_polls}) reached, stopping...")
                return None
            
            # Check if game has stopped (e.g., timers stopped)
            if game_stopped_check and callable(game_stopped_check) and game_stopped_check():
                logger.info(" Game stopped check triggered - exiting polling loop")
                return {'status': 'game_stopped', 'message': 'Game timers stopped'}
            
            poll_count += 1
            try:
                response = None
                start_time = time.time()
                
                response = self.session.get(
                    url, 
                    headers=self.headers,
                    timeout=8
                )
                
                elapsed_time = time.time() - start_time
                logger.debug(f"️  Response received in {elapsed_time:.2f} seconds")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f" Response data: {data}")
                    
                    if data.get('data') and len(data.get('data')) > 0:
                        status = data.get('data').get('status')
                        logger.info(f" Status Received: {status}")
                        
                        # Check if score submission was triggered externally
                        if submit_score_flag_ref and hasattr(submit_score_flag_ref, '__call__') and submit_score_flag_ref():
                            logger.info(" Score submission flag detected - exiting polling")
                            return {"status": "submit_triggered"}
                        elif hasattr(submit_score_flag_ref, 'value') and submit_score_flag_ref.value:
                            logger.info(" Score submission flag detected - exiting polling")
                            return {"status": "submit_triggered"}
                        
                        if status == "playing":
                            # Get current started_flag value 
                            started_flag_value = False
                            if started_flag_ref and hasattr(started_flag_ref, '__call__'):
                                started_flag_value = started_flag_ref()
                            elif hasattr(started_flag_ref, 'value'):
                                started_flag_value = started_flag_ref.value
                            
                            logger.info(f" Status 'playing' received, started_flag: {started_flag_value}")
                            
                            if not started_flag_value:
                                # First time receiving playing status - emit start signal
                                logger.info("" + "=" * 50)
                                logger.info(" FIRST PLAYING SIGNAL - EMITTING START!")
                                logger.info("" + "=" * 50)
                                logger.info(f" Game ID: {game_result_id}")
                                logger.info(f" Status: {status}")
                                logger.info(" RETURNING DATA TO EMIT START SIGNAL! ")
                                logger.info("" + "=" * 50)
                                return data.get('data')
                            else:
                                # Game already started - continue monitoring without emitting
                                logger.info(" Game already started, continuing to monitor for cancel/submit...")
                                continue
                                
                        elif status == "cancel":
                            logger.warning("️" + "=" * 50)
                            logger.warning("️  GAME CANCELLED BY ADMIN")
                            logger.warning("️" + "=" * 50)
                            
                            # Update cancel flag
                            if cancel_flag_ref and hasattr(cancel_flag_ref, '__call__'):
                                cancel_flag_ref(True)
                            elif hasattr(cancel_flag_ref, 'value'):
                                cancel_flag_ref.value = True
                            
                            return {"status": "cancel", "cancelled": True}
                        else:
                            logger.debug(f" Current status: {status} - continuing to poll...")
                    else:
                        logger.debug(" No game data in response")
                else:
                    logger.warning(f"️  HTTP {response.status_code}: {response.text[:200] if response.text else 'No response text'}")
                    
            except (ConnectionError, Timeout, RequestException) as e:
                logger.error(f" Network error during polling: {type(e).__name__}: {str(e)}")
                if response is not None:
                    try:
                        logger.debug(f" Response content: {response.text[:200]}")
                    except:
                        pass
                time.sleep(3)  # Wait before retry on network error
                continue
            except Exception as e:
                logger.error(f" Unexpected error during polling: {type(e).__name__}: {str(e)}")
                if response is not None:
                    try:
                        logger.debug(f" Response content: {response.text[:200]}")
                    except:
                        pass
                time.sleep(2)  # Wait before retry on unexpected error
                continue
            
            # Small delay between polls
            time.sleep(0.5)
        
        return None
    
    def start_game_like_cage(self, game_result_id: str, submit_score_flag_ref, started_flag_ref, cancel_flag_ref) -> bool:
        """
        Simplified interface that matches CAGE_Game.py start_game() method pattern
        Returns True when game starts or gets cancelled, False on error
        """
        logger.info("" + "=" * 50)
        logger.info(" STARTING GAME POLLING (CAGE_Game.py style)")
        logger.info("" + "=" * 50)
        
        game_data = self.poll_game_start_continuous(
            game_result_id=game_result_id,
            submit_score_flag_ref=submit_score_flag_ref,
            started_flag_ref=started_flag_ref,
            cancel_flag_ref=cancel_flag_ref
        )
        
        if game_data:
            status = game_data.get('status')
            if status in ['playing', 'cancel', 'submit_triggered']:
                return True
        
        return False
    
    def submit_final_scores(self, game_result_id: str, individual_scores: List[Dict]) -> bool:
        """
        Step 3: Submit final game scores
        Endpoint: POST /game-result/scoring
        
        Expected format for individual_scores:
        [
            { "userID": "6kKS8O07T9ePXhxW18LC", "nodeID": 1, "score": 1 },
            { "userID": "9Fs9uAUzeZyIF8vcFnIu", "nodeID": 2, "score": 2 },
            ...
        ]
        """
        logger.info("" + "=" * 50)
        logger.info(" STEP 3: SUBMITTING FINAL SCORES")
        logger.info("" + "=" * 50)
        
        if not self._ensure_authenticated():
            logger.error(" Authentication required for score submission")
            return False
        # url endpoint for submit final scores
        #  "https://dev-eaa25-api-hpfyfcbshkabezeh.uaenorth-01.azurewebsites.net/game-result/scoring"
        url = f"{self.base_url}/game-result/scoring"
        data = {
            "gameResultID": game_result_id,
            "individualScore": individual_scores
        }
        
        logger.info(f" Game Result ID: {game_result_id}")
        logger.info(f" Submitting scores for {len(individual_scores)} players")
        logger.debug(f" POST {url}")
        logger.debug(f" Timeout: {self.config.submit_score_timeout}s")
        logger.debug(f" Authorization: Bearer {self.token[:20] if self.token else 'None'}...")
        logger.debug(f" Headers: {dict(self.headers)}")
        
        # Log score summary
        for i, score_data in enumerate(individual_scores):
            logger.info(f"   {i+1}. UserID: {score_data.get('userID', 'Unknown')[:15]}... | "
                       f"NodeID: {score_data.get('nodeID', 'N/A')} | "
                       f"Score: {score_data.get('score', 0)}")
        
        logger.debug(f" Full request data: {data}")
        
        start_time = time.time()
        
        try:
            response = self.session.post(
                url,
                json=data,
                headers=self.headers,
                timeout=self.config.submit_score_timeout
            )
            
            elapsed_time = time.time() - start_time
            logger.info(f"️  Response received in {elapsed_time:.2f} seconds")
            logger.info(f" Status Code: {response.status_code}")
            
            if response.status_code == 200:
                
                logger.info("" + "=" * 50)
                logger.info(" FINAL SCORES SUBMITTED SUCCESSFULLY!")
                logger.info("" + "=" * 50)
                logger.info(f" Game {game_result_id} completed")
                logger.info(f" {len(individual_scores)} player scores recorded")
                logger.info(" Ready for next game cycle")
                logger.info("" + "=" * 50)
                return True
            else:
                logger.error("" + "=" * 50)
                logger.error(" FINAL SCORE SUBMISSION FAILED")
                logger.error("" + "=" * 50)
                logger.error(f" HTTP Status: {response.status_code}")
                logger.error(f" Response: {response.text[:300]}...")
                logger.error("" + "=" * 50)
                return False
                
        except (ConnectionError, Timeout, RequestException) as e:
            elapsed_time = time.time() - start_time
            logger.error("" + "=" * 50)
            logger.error(" SCORE SUBMISSION ERROR")
            logger.error("" + "=" * 50)
            logger.error(f"️  Elapsed time: {elapsed_time:.2f} seconds")
            logger.error(f" Error type: {type(e).__name__}")
            logger.error(f" Error details: {str(e)}")
            logger.error("" + "=" * 50)
            return False
    
    def get_leaderboard(self, game_name: str = None) -> List[Tuple[str, int]]:
        """
        Get current leaderboard from API
        
        Args:
            game_name: Optional game name override. If not provided, uses "Rising Together"
        
        Returns:
            List of tuples (team_name, score) for top teams
        """
        logger.info("" + "=" * 40)
        logger.info(" FETCHING LEADERBOARD")
        logger.info("" + "=" * 40)
        
        if not self._ensure_authenticated():
            logger.error(" Authentication required for leaderboard")
            return []
        
        # Use "Rising Together" as default game name, or provided override
        target_game_name = game_name or self.config.game_name
        
        base_url = f"{self.base_url}/leaderboard/dashboard/based"
        params = {
            "source": "game",
            "nameGame": target_game_name
        }
        
        logger.info(f" GET {base_url}")
        logger.info(f" Parameters: {params}")
        logger.info(f" Target Game: {target_game_name}")
        logger.debug(f" Authorization: Bearer {self.token[:20] if self.token else 'None'}...")
        
        start_time = time.time()
        
        try:
            response = self.session.get(
                base_url,
                params=params,
                headers=self.headers,
                timeout=self.config.leaderboard_timeout
            )
            
            elapsed_time = time.time() - start_time
            logger.info(f"️  Response received in {elapsed_time:.2f} seconds")
            logger.info(f" Status Code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f" Response structure: {list(data.keys())}")
                    logger.debug(f" Full response: {data}")
                    
                    # Extract team names and scores into a list of tuples
                    if 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
                        game_data = data['data'][0]
                        logger.info(f" Game found: {game_data.get('name', 'Unknown')}")
                        logger.info(f" Game ID: {game_data.get('id', 'Unknown')}")
                        
                        teams = game_data.get('list', [])
                        logger.info(f" Teams found: {len(teams)}")
                        
                        if teams:
                            team_scores = []
                            for i, team in enumerate(teams, 1):
                                team_name = team.get('name', f'Team {i}')
                                total_score = team.get('total_score', 0)
                                team_scores.append((team_name[:20], total_score))  # Increased name length
                                logger.info(f"   {i:2d}. {team_name:<20} | Score: {total_score:,}")
                            
                            logger.info("" + "=" * 40)
                            logger.info(f" LEADERBOARD FETCHED: {len(team_scores)} teams")
                            logger.info("" + "=" * 40)
                            return team_scores[:10]  # Return top 10
                        else:
                            logger.info("️" + "=" * 40)
                            logger.info("️  NO TEAMS FOUND IN LEADERBOARD")
                            logger.info("️" + "=" * 40)
                            logger.info(" This could mean:")
                            logger.info("   • No games have been played yet")
                            logger.info("   • Game name doesn't match exactly")
                            logger.info("   • Scores haven't been submitted")
                            return []
                    else:
                        logger.warning("️" + "=" * 40)
                        logger.warning("️  UNEXPECTED RESPONSE STRUCTURE")
                        logger.warning("️" + "=" * 40)
                        logger.warning(f" Data type: {type(data.get('data'))}")
                        logger.warning(f" Data length: {len(data.get('data', [])) if isinstance(data.get('data'), list) else 'N/A'}")
                        return []
                        
                except ValueError as e:
                    logger.error("" + "=" * 40)
                    logger.error(" JSON PARSING ERROR")
                    logger.error("" + "=" * 40)
                    logger.error(f" Error: {e}")
                    logger.error(f" Raw response: {response.text[:300]}...")
                    return []
            else:
                logger.error("" + "=" * 40)
                logger.error(" LEADERBOARD REQUEST FAILED")
                logger.error("" + "=" * 40)
                logger.error(f" HTTP Status: {response.status_code}")
                logger.error(f" Response: {response.text[:300]}...")
                logger.error(f" Headers: {dict(response.headers)}")
                return []
                
        except (ConnectionError, Timeout, RequestException) as e:
            elapsed_time = time.time() - start_time
            logger.error("" + "=" * 40)
            logger.error(" LEADERBOARD REQUEST ERROR")
            logger.error("" + "=" * 40)
            logger.error(f"️  Elapsed time: {elapsed_time:.2f} seconds")
            logger.error(f" Error type: {type(e).__name__}")
            logger.error(f" Error details: {str(e)}")
            return []
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error("" + "=" * 40)
            logger.error(" UNEXPECTED LEADERBOARD ERROR")
            logger.error("" + "=" * 40)
            logger.error(f"️  Elapsed time: {elapsed_time:.2f} seconds")
            logger.error(f" Error type: {type(e).__name__}")
            logger.error(f" Error details: {str(e)}")
            return []
    
    def submit_team_score(self, game_result_id: str, team_name: str, score: int, user_id: str = None, node_id: int = 1) -> bool:
        """
        Simplified method to submit a single team score
        Converts team score to the required individual score format
        """
        logger.info("" + "=" * 30)
        logger.info(" SIMPLIFIED TEAM SCORE SUBMISSION")
        logger.info("" + "=" * 30)
        
        if not user_id:
            # Generate a default user ID if not provided
            user_id = f"team_{team_name.replace(' ', '_').lower()}"
            logger.debug(f" Generated userID: {user_id}")
        
        individual_scores = [{
            "userID": user_id,
            "nodeID": node_id,
            "score": score
        }]
        
        logger.info(f" Team: {team_name}")
        logger.info(f" Score: {score}")
        logger.info(f" UserID: {user_id}")
        logger.info(f" NodeID: {node_id}")
        logger.info("" + "=" * 30)
        
        return self.submit_final_scores(game_result_id, individual_scores)
    
    # Legacy compatibility methods
    def get_initiated_games(self) -> List[Dict]:
        """Legacy method - use poll_game_initialization() instead"""
        logger.warning("️  get_initiated_games() is deprecated - use poll_game_initialization()")
        game = self.poll_game_initialization()
        return [game] if game else []
    
    def submit_scores(self, game_result_id: str, player_scores: List[Dict]) -> bool:
        """Legacy method - use submit_final_scores() instead"""
        logger.warning("️  submit_scores() is deprecated - use submit_final_scores()")
        return self.submit_final_scores(game_result_id, player_scores)
    
    def submit_score(self, team_name: str, score: int) -> bool:
        """Legacy method - requires game_result_id, use submit_team_score() instead"""
        logger.warning("️" + "=" * 40)
        logger.warning("️  DEPRECATED METHOD CALLED")
        logger.warning("️" + "=" * 40)
        logger.warning(" submit_score() is deprecated")
        logger.warning(" Use submit_team_score() with game_result_id instead")
        logger.warning("️" + "=" * 40)
        
        # Try to find a playing game
        logger.info(" Attempting to find active game...")
        game = self.poll_game_initialization()
        if game:
            game_result_id = game.get('id')
            if game_result_id:
                logger.info(f" Found active game: {game_result_id}")
                return self.submit_team_score(game_result_id, team_name, score)
        
        logger.warning(" No active game found - score will be logged locally")
        logger.warning(f" Local score log: {team_name} = {score}")
        return True
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated"""
        return self.token is not None
    
    def clear_authentication(self):
        """Clear authentication state"""
        logger.warning("" + "=" * 30)
        logger.warning(" CLEARING AUTHENTICATION")
        logger.warning("" + "=" * 30)
        logger.info(f" Clearing token (length: {len(self.token) if self.token else 0})")
        self.token = None
        self.headers = {}
        logger.info(" Authentication state cleared")
        logger.warning("" + "=" * 30)
    
    def get_connection_info(self) -> Dict:
        """Get connection information for debugging"""
        return {
            "base_url": self.base_url,
            "game_id": self.game_id,
            "game_name": self.game_name,
            "authenticated": self.is_authenticated(),
            "token_length": len(self.token) if self.token else 0
        }
    
    def get_game_flow_status(self) -> Dict:
        """
        Get comprehensive game flow status for debugging
        Returns current state of the game cycle
        """
        logger.info("" + "=" * 40)
        logger.info(" CHECKING GAME FLOW STATUS")
        logger.info("" + "=" * 40)
        
        status = {
            "authenticated": self.is_authenticated(),
            "game_id": self.game_id,
            "initialization_status": None,
            "playing_status": None,
            "flow_step": "unknown"
        }
        
        logger.debug(f" Authentication status: {status['authenticated']}")
        logger.debug(f" Game ID: {status['game_id']}")
        
        if not self.is_authenticated():
            status["flow_step"] = "authentication_required"
            logger.info(" Authentication required")
            return status
        
        # Check initialization
        logger.debug(" Checking game initialization...")
        init_game = self.poll_game_initialization()
        if init_game:
            status["initialization_status"] = "found"
            status["initialized_game_id"] = init_game.get('id')
            status["team_name"] = init_game.get('name')
            status["flow_step"] = "initialized_waiting_for_start"
            logger.info(f" Game initialized: {status['initialized_game_id']}")
        else:
            status["initialization_status"] = "waiting"
            status["flow_step"] = "waiting_for_initialization"
            logger.info(" Waiting for game initialization")
        
        logger.info("" + "=" * 40)
        logger.info(f" Current flow step: {status['flow_step']}")
        logger.info("" + "=" * 40)
        
        return status
    
    def is_initialized(self) -> bool:
        """
        Check if the GameAPI is properly initialized
        Returns True if all required components are set up
        """
        try:
            required_attrs = ['base_url', 'email', 'password', 'game_id', 'game_name', 'session']
            
            for attr in required_attrs:
                if not hasattr(self, attr):
                    logger.error(f" GameAPI not initialized: missing {attr}")
                    return False
                
                value = getattr(self, attr)
                if value is None or (isinstance(value, str) and not value.strip()):
                    logger.error(f" GameAPI not initialized: {attr} is None or empty")
                    return False
            
            # Check session type
            if not isinstance(self.session, requests.Session):
                logger.error(f" GameAPI not initialized: invalid session type {type(self.session)}")
                return False
            
            logger.debug(" GameAPI is properly initialized")
            return True
            
        except Exception as e:
            logger.error(f" Error checking GameAPI initialization: {str(e)}")
            return False
    
    def verify_authorization_header(self) -> bool:
        """
        Verify that the Authorization header is properly set with Bearer token
        Returns True if header is correctly configured
        """
        try:
            if not self.headers:
                logger.error(" No headers configured")
                return False
            
            if 'Authorization' not in self.headers:
                logger.error(" Authorization header missing")
                return False
            
            auth_header = self.headers['Authorization']
            if not auth_header.startswith('Bearer '):
                logger.error(f" Invalid Authorization header format: {auth_header}")
                return False
            
            if not self.token:
                logger.error(" No authentication token available")
                return False
            
            # Verify token length (should be substantial)
            if len(self.token) < 10:
                logger.warning(f"️  Token seems short: {len(self.token)} characters")
            
            logger.debug(" Authorization header properly configured")
            logger.debug(f" Bearer token length: {len(self.token)} characters")
            logger.debug(f" Token preview: {self.token[:20]}...")
            return True
            
        except Exception as e:
            logger.error(f" Error verifying authorization header: {str(e)}")
            return False
