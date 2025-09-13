#!/usr/bin/env python3
"""
External CSV Submitter Script for CubeGame

This script reads data from the CSV log files and submits scores to the API.
Useful for:
- Backup submissions
- Re-processing failed submissions  
- Data verification
- Manual score corrections
"""

import csv
import sys
import os
import argparse
from datetime import datetime
from typing import List, Dict, Optional

# Add the current directory to Python path to import the API
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from api.game_api import GameAPI
    from config import config
    from utils.logger import get_logger
except ImportError as e:
    print(f"❌ Error importing required modules: {e}")
    print("Make sure you're running this script from the game4 directory")
    sys.exit(1)

# Setup logging
logger = get_logger(__name__)

class CubeGameCSVSubmitter:
    """External script to submit CubeGame scores from CSV files"""
    
    def __init__(self):
        """Initialize the CSV submitter"""
        try:
            self.api = GameAPI()
            logger.info("✅ GameAPI initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize GameAPI: {e}")
            raise
    
    def read_submissions_csv(self, filename: str = "CubeGame_Pre_Submission_Backup.csv") -> List[Dict]:
        """Read the submissions log CSV file"""
        submissions = []
        
        if not os.path.exists(filename):
            logger.error(f"❌ CSV file not found: {filename}")
            return submissions
        
        try:
            with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
                # Try to detect if there's a header
                first_line = csvfile.readline().strip()
                csvfile.seek(0)
                
                # Check if first line looks like a header
                has_header = 'timestamp' in first_line.lower()
                
                if has_header:
                    reader = csv.DictReader(csvfile)
                else:
                    # Define headers manually if CSV doesn't have them
                    fieldnames = ['timestamp', 'game_result_id', 'total_players', 'total_score', 
                                'player_ids', 'individual_scores_json', 'status']
                    reader = csv.DictReader(csvfile, fieldnames=fieldnames)
                
                for row in reader:
                    if row['game_result_id']:  # Skip empty rows
                        submissions.append(row)
                        
            logger.info(f"📊 Read {len(submissions)} submissions from {filename}")
            return submissions
            
        except Exception as e:
            logger.error(f"❌ Error reading CSV file {filename}: {e}")
            return []
    
    def read_individual_players_csv(self, filename: str = "CubeGame_Individual_Players_Log.csv") -> Dict[str, List[Dict]]:
        """Read player data from backup CSV with JSON field or individual players CSV"""
        players_by_game = {}
        
        # First try to read from pre-submission backup (which has JSON data)
        backup_filename = "CubeGame_Pre_Submission_Backup.csv"
        if os.path.exists(backup_filename):
            logger.info(f"📊 Reading player data from {backup_filename} (JSON format)")
            players_by_game = self._read_players_from_backup(backup_filename)
            if players_by_game:
                return players_by_game
        
        # Fallback to individual players CSV
        if not os.path.exists(filename):
            logger.error(f"❌ CSV file not found: {filename}")
            return players_by_game
        
        try:
            with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
                # Try to detect if there's a header
                first_line = csvfile.readline().strip()
                csvfile.seek(0)
                
                # Check if first line looks like a header
                has_header = 'timestamp' in first_line.lower()
                
                if has_header:
                    reader = csv.DictReader(csvfile)
                else:
                    # Define headers manually if CSV doesn't have them
                    fieldnames = ['timestamp', 'game_result_id', 'user_id', 'node_id', 
                                'individual_score', 'submission_success', 'status']
                    reader = csv.DictReader(csvfile, fieldnames=fieldnames)
                
                for row in reader:
                    if row['game_result_id']:  # Skip empty rows
                        game_id = row['game_result_id']
                        if game_id not in players_by_game:
                            players_by_game[game_id] = []
                        
                        players_by_game[game_id].append({
                            'userID': row['user_id'],
                            'nodeID': int(row['node_id']) if row['node_id'].isdigit() else 1,
                            'score': int(row['individual_score']) if row['individual_score'].isdigit() else 0
                        })
            
            total_games = len(players_by_game)
            total_players = sum(len(players) for players in players_by_game.values())
            logger.info(f"👥 Read {total_players} player records from {total_games} games")
            return players_by_game
            
        except Exception as e:
            logger.error(f"❌ Error reading CSV file {filename}: {e}")
            return {}
    
    def _read_players_from_backup(self, filename: str) -> Dict[str, List[Dict]]:
        """Extract player data from the JSON field in backup CSV"""
        players_by_game = {}
        
        try:
            import json
            with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
                # Try to detect if there's a header
                first_line = csvfile.readline().strip()
                csvfile.seek(0)
                
                # Check if first line looks like a header
                has_header = 'timestamp' in first_line.lower()
                
                if has_header:
                    reader = csv.DictReader(csvfile)
                else:
                    # Define headers manually if CSV doesn't have them
                    fieldnames = ['timestamp', 'game_result_id', 'total_players', 'total_score', 
                                'player_ids', 'individual_scores_json', 'status']
                    reader = csv.DictReader(csvfile, fieldnames=fieldnames)
                
                for row in reader:
                    if row['game_result_id'] and row.get('individual_scores_json'):
                        # Only process pre_submission entries
                        status = row.get('status', '').lower().strip()
                        if status != 'saved_before_submission':
                            logger.debug(f"⏭️  Skipping row with status: {status}")
                            continue
                            
                        game_id = row['game_result_id']
                        
                        # Skip if we already processed this game (avoid duplicates)
                        if game_id in players_by_game:
                            logger.debug(f"⏭️  Game {game_id} already processed, skipping duplicate")
                            continue
                            
                        try:
                            # Parse the JSON data
                            json_data = row['individual_scores_json']
                            # Handle double quotes in CSV
                            json_data = json_data.replace('""', '"')
                            individual_scores = json.loads(json_data)
                            
                            players_by_game[game_id] = individual_scores
                            logger.debug(f"📊 Extracted {len(individual_scores)} players for game {game_id} (pre_submission)")
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"⚠️  Error parsing JSON for game {game_id}: {e}")
                            continue
            
            total_games = len(players_by_game)
            total_players = sum(len(players) for players in players_by_game.values())
            logger.info(f"👥 Extracted {total_players} player records from {total_games} games (from JSON)")
            return players_by_game
            
        except Exception as e:
            logger.error(f"❌ Error reading backup CSV file {filename}: {e}")
            return {}
    
    def submit_from_csv(self, game_result_id: str = None, dry_run: bool = False, 
                       force_resubmit: bool = False) -> bool:
        """Submit CubeGame scores from CSV files"""
        
        logger.info("🧊" + "=" * 60)
        logger.info("🧊 EXTERNAL CUBEGAME CSV SUBMITTER STARTED")
        logger.info("🧊" + "=" * 60)
        
        # Read CSV files
        submissions = self.read_submissions_csv()
        players_by_game = self.read_individual_players_csv()
        
        if not submissions:
            logger.error("❌ No submissions found in CSV")
            return False
        
        if not players_by_game:
            logger.error("❌ No player data found in CSV")
            return False
        
        success_count = 0
        total_count = 0
        
        for submission in submissions:
            total_count += 1
            current_game_id = submission['game_result_id']
            
            # Filter by specific game_result_id if provided
            if game_result_id and current_game_id != game_result_id:
                continue
            
            # Check if this is a pre-submission entry that needs to be submitted
            status = submission.get('status', '').lower().strip()
            if status != 'saved_before_submission':
                logger.debug(f"⏭️  Skipping {current_game_id} - status: {status} (not pre_submission)")
                continue
            
            # Get player data for this game
            if current_game_id not in players_by_game:
                logger.warning(f"⚠️  No player data found for game {current_game_id}")
                continue
            
            individual_scores = players_by_game[current_game_id]
            
            logger.info("🧊" + "=" * 50)
            logger.info(f"🎯 Processing CubeGame Team: {current_game_id}")
            logger.info(f"👥 Players: {len(individual_scores)}")
            logger.info(f"🏆 Total Score: {sum(score['score'] for score in individual_scores)}")
            logger.info(f"📅 Original Timestamp: {submission.get('timestamp', 'Unknown')}")
            logger.info(f"📊 Status: {submission.get('status', 'Unknown')}")
            
            # Log player details for verification
            for i, score_data in enumerate(individual_scores):
                logger.debug(f"   Player {i+1}: UserID={score_data.get('userID', 'Unknown')[:15]}... | "
                           f"NodeID={score_data.get('nodeID', 'N/A')} | Score={score_data.get('score', 0)}")
            
            if dry_run:
                logger.info("🔍 DRY RUN - Would submit:")
                for i, score_data in enumerate(individual_scores):
                    logger.info(f"   {i+1}. UserID: {score_data['userID'][:15]}... | "
                               f"NodeID: {score_data['nodeID']} | "
                               f"Score: {score_data['score']}")
                logger.info("✅ DRY RUN - Submission would be attempted")
                success_count += 1
                continue
            
            # Actual submission
            try:
                logger.info("🚀 Submitting CubeGame scores to API...")
                success = self.api.submit_final_scores(current_game_id, individual_scores)
                
                if success:
                    logger.info("✅ External CubeGame submission successful!")
                    success_count += 1
                    
                    # Update CSV to mark as successfully submitted externally
                    self._update_csv_status(current_game_id, True, "external_resubmission")
                else:
                    logger.error("❌ External CubeGame submission failed")
                    self._update_csv_status(current_game_id, False, "external_failed")
                    
            except Exception as e:
                logger.error(f"💥 Exception during CubeGame submission: {e}")
                self._update_csv_status(current_game_id, False, f"external_error: {str(e)}")
        
        # Summary
        logger.info("🧊" + "=" * 60)
        logger.info("🧊 EXTERNAL CUBEGAME SUBMISSION SUMMARY")
        logger.info("🧊" + "=" * 60)
        logger.info(f"✅ Successful: {success_count}")
        logger.info(f"❌ Failed: {total_count - success_count}")
        logger.info(f"📊 Total Processed: {total_count}")
        logger.info("🧊" + "=" * 60)
        
        return success_count > 0
    
    def _update_csv_status(self, game_result_id: str, success: bool, method: str):
        """Update CSV file with external submission status"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_filename = "CubeGame_External_Submissions_Status.csv"
            
            # Check if file exists
            file_exists = os.path.exists(status_filename)
            
            with open(status_filename, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['timestamp', 'game_result_id', 'external_submission_success', 'method', 'notes']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow({
                    'timestamp': timestamp,
                    'game_result_id': game_result_id,
                    'external_submission_success': success,
                    'method': method,
                    'notes': f"External CubeGame resubmission via CSV script"
                })
                
            logger.debug(f"📝 Updated external status for {game_result_id}")
            
        except Exception as e:
            logger.warning(f"⚠️  Error updating external status CSV: {e}")
    
    def list_available_games(self):
        """List all CubeGame games available in CSV for submission"""
        submissions = self.read_submissions_csv()
        players_by_game = self.read_individual_players_csv()
        
        if not submissions:
            logger.info("❌ No CubeGame games found in CSV files")
            return
        
        logger.info("🧊" + "=" * 60)
        logger.info("🧊 AVAILABLE CUBEGAME TEAMS/GAMES IN CSV")
        logger.info("🧊" + "=" * 60)
        
        for submission in submissions:
            game_id = submission['game_result_id']
            timestamp = submission.get('timestamp', 'Unknown')
            status = submission.get('status', 'Unknown')
            total_score = submission.get('total_score', '0')
            
            player_count = len(players_by_game.get(game_id, []))
            
            # Only show pre_submission entries
            if status.lower().strip() == 'saved_before_submission':
                logger.info(f"🧊 CubeGame Team/Game ID: {game_id}")
                logger.info(f"   📅 Timestamp: {timestamp}")
                logger.info(f"   📊 Status: {status} ✅")
                logger.info(f"   👥 Players: {player_count}")
                logger.info(f"   🏆 Total Score: {total_score}")
                logger.info("   " + "-" * 40)
            else:
                logger.debug(f"🔍 Skipping {game_id} - Status: {status} (not pre_submission)")

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description='Submit CubeGame scores from CSV files')
    parser.add_argument('--game-id', type=str, help='Specific game result ID to submit')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be submitted without actually submitting')
    parser.add_argument('--force', action='store_true', help='Force resubmit even if already successful')
    parser.add_argument('--list', action='store_true', help='List all available games in CSV')
    
    args = parser.parse_args()
    
    try:
        submitter = CubeGameCSVSubmitter()
        
        if args.list:
            submitter.list_available_games()
            return
        
        # Submit from CSV
        success = submitter.submit_from_csv(
            game_result_id=args.game_id,
            dry_run=args.dry_run,
            force_resubmit=args.force
        )
        
        if success:
            logger.info("🎉 External CubeGame CSV submission completed successfully!")
        else:
            logger.error("❌ External CubeGame CSV submission failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("⚠️  Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
