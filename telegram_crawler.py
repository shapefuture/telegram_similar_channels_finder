#!/usr/bin/env python3
"""
Telegram Similar Channels Crawler
A tool to fetch similar Telegram channels.
"""

import os
import sys
import json
import time
import asyncio
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Third-party dependencies
from dotenv import load_dotenv
from telethon import TelegramClient, errors, functions, types
from telethon.tl.types import Channel, Chat, User, InputPeerChannel, InputChannel
from telethon.tl.functions.channels import GetChannelRecommendationsRequest, GetFullChannelRequest

# Configure logging with explicit file mode and permissions
try:
    # Ensure log directory exists
    os.makedirs('logs', exist_ok=True)
    log_file = os.path.join('logs', 'crawler.log')
    
    # Clear previous log file to ensure fresh start
    if os.path.exists(log_file):
        os.remove(log_file)
        
    # Create file handler with explicit flushing
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Create logger and add handlers
    logger = logging.getLogger("TelegramCrawler")
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Explicitly flush after configuration
    for handler in logger.handlers:
        handler.flush()
    
    # Verify logging
    logger.info("Logging system initialized successfully")
    logger.info(f"Logging to: {os.path.abspath(log_file)}")
    
    # Test file writing
    try:
        with open(log_file, 'a') as f:
            f.write("Log file created and writable\n")
        logger.info("Confirmed log file is writable")
    except Exception as e:
        logger.error(f"Failed to write to log file: {str(e)}")

except Exception as e:
    print(f"CRITICAL: Failed to configure logging: {e}")
    raise

# Load environment variables
load_dotenv()

class InputHandler:
    """Handles the loading and validation of input channels."""
    
    @staticmethod
    def load_from_cli(args: List[str]) -> List[str]:
        """Load channel usernames from command line arguments."""
        return args
    
    @staticmethod
    def load_from_file(file_path: str) -> List[str]:
        """Load channel usernames from a JSON or CSV file."""
        if not os.path.exists(file_path):
            logger.error(f"Input file {file_path} not found.")
            return []
        
        try:
            if file_path.endswith('.json'):
                with open(file_path, 'r') as f:
                    channels = json.load(f)
                    if not isinstance(channels, list):
                        logger.error("JSON file must contain a list of channel usernames.")
                        return []
                    return channels
            elif file_path.endswith('.csv'):
                with open(file_path, 'r') as f:
                    return [line.strip() for line in f if line.strip()]
            else:
                logger.error("Unsupported file format. Use .json or .csv")
                return []
        except Exception as e:
            logger.error(f"Error loading input file: {e}")
            return []
    
    @staticmethod
    def validate_channels(channels: List[str]) -> List[str]:
        """Validate and normalize channel usernames."""
        valid_channels = []
        for channel in channels:
            if not channel:
                continue
                
            # Remove @ prefix if present
            if channel.startswith('@'):
                channel = channel[1:]
                
            # Basic validation: no spaces, reasonable length
            if ' ' in channel or len(channel) < 3 or len(channel) > 32:
                logger.warning(f"Invalid channel name: {channel}")
                continue
                
            valid_channels.append(channel)
            
        logger.info(f"Validated {len(valid_channels)} channels out of {len(channels)}")
        return valid_channels

class TelegramCrawler:
    """Handles the interaction with the Telegram API."""
    
    def __init__(self, api_id: str, api_hash: str, phone: str = None, session_name: str = "crawler"):
        """Initialize the Telegram client."""
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_name = session_name
        self.client = None
    
    async def connect(self) -> bool:
        """Connect to Telegram and handle authentication."""
        try:
            logger.info(f"Attempting to connect with API ID: {self.api_id}")
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                if not self.phone:
                    self.phone = input("Enter your phone number (with country code): ")
                
                logger.info(f"Sending code request to: {self.phone}")
                sent_code = await self.client.send_code_request(self.phone)
                logger.info(f"Code sent via: {sent_code}")
                
                code = input("Enter the code you received: ")
                logger.info(f"Attempting sign in with code: {code}")
                
                try:
                    await self.client.sign_in(self.phone, code)
                    logger.info("Successfully signed in")
                except errors.SessionPasswordNeededError:
                    logger.info("2FA required")
                    password = input("Two-factor authentication is enabled. Enter your password: ")
                    await self.client.sign_in(password=password)
                    logger.info("Successfully signed in with 2FA")
                except Exception as e:
                    logger.error(f"Sign in error: {str(e)}")
                    return False
            
            me = await self.client.get_me()
            logger.info(f"Successfully connected as: {me.username or me.phone}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to Telegram: {e}")
            return False
    
    async def get_similar_channels(self, channel_username: str) -> List[Dict[str, Any]]:
        """Fetch similar channels for a given channel using Telegram's GetChannelRecommendationsRequest API."""
        try:
            # Try to resolve the entity first
            entity = await self.client.get_entity(channel_username)
            
            # Check if it's a channel
            if not isinstance(entity, Channel):
                logger.warning(f"{channel_username} is not a channel. Skipping.")
                return []
            
            # Convert to InputChannel for API calls
            input_channel = InputChannel(entity.id, entity.access_hash)
            
            # Use the GetChannelRecommendationsRequest to get similar channels
            logger.info(f"Fetching recommendations for channel: {channel_username}")
            result = await self.client(GetChannelRecommendationsRequest(
                channel=input_channel
            ))
            
            # Process the results
            similar_channels = []
            seen_usernames = set()
            
            for chat in result.chats:
                if not hasattr(chat, 'username') or not chat.username:
                    logger.debug(f"Skipping channel without username: {getattr(chat, 'title', 'Unknown')}")
                    continue
                
                # Skip the original channel
                if chat.username.lower() == channel_username.lower():
                    continue
                
                # Avoid duplicates
                if chat.username.lower() in seen_usernames:
                    continue
                    
                seen_usernames.add(chat.username.lower())
                
                # Get additional details like member count
                members_count = None
                try:
                    full_chat = await self.client(GetFullChannelRequest(
                        channel=chat
                    ))
                    members_count = full_chat.full_chat.participants_count
                except Exception as e:
                    logger.debug(f"Couldn't fetch member count for {chat.username}: {str(e)}")
                
                channel_info = {
                    "title": chat.title,
                    "username": chat.username,
                    "url": f"https://t.me/{chat.username}",
                    "timestamp": datetime.now().isoformat(),
                    "members": members_count
                }
                
                similar_channels.append(channel_info)
            
            logger.info(f"Found {len(similar_channels)} similar channels for {channel_username}")
            return similar_channels
        except errors.FloodWaitError as e:
            # Handle rate limiting
            wait_time = e.seconds
            logger.warning(f"Rate limited. Waiting for {wait_time} seconds")
            await asyncio.sleep(wait_time)
            return []
        except Exception as e:
            logger.error(f"Error fetching similar channels for {channel_username}: {e}")
            return []
            
    
    async def close(self):
        """Close the Telegram client connection."""
        if self.client:
            await self.client.disconnect()
            logger.info("Disconnected from Telegram")

async def process_channels(input_channels: List[str], config: Dict[str, Any]) -> Dict[str, Any]:
    """Main process to fetch similar channels with CSV export capability."""
    logger.info("PROCESS_CHANNELS STARTED")
    # Initialize handlers
    telegram_crawler = TelegramCrawler(
        api_id=config['telegram_api_id'],
        api_hash=config['telegram_api_hash'],
        phone=config.get('telegram_phone'),
        session_name=config.get('telegram_session', 'crawler')
    )
    
    # Connect to Telegram
    if not await telegram_crawler.connect():
        logger.error("Failed to connect to Telegram. Exiting.")
        return {
            "total_channels": len(input_channels),
            "successful_channels": 0,
            "failed_channels": len(input_channels),
            "total_similar_channels": 0,
            "export_status": "Failed to connect to Telegram API",
            "similar_channels": {}
        }
    
    # Process channels
    total_channels = len(input_channels)
    successful_channels = 0
    failed_channels = 0
    all_similar_channels = []
    channel_similar_channels = {}  # Dictionary to track similar channels by input channel
    
    # Define headers for the CSV export
    headers = ["Source Channel", "Title", "Username", "URL", "Members", "Category"]
    all_rows = []  # Collect all rows for export
    
    # Process each channel with rate limiting
    for idx, channel in enumerate(input_channels, 1):
        logger.info(f"Processing channel {idx}/{total_channels}: {channel}")
        
        try:
            similar_channels = await telegram_crawler.get_similar_channels(channel)
            
            if similar_channels:
                # Store the similar channels for this input channel
                channel_similar_channels[channel] = similar_channels
                
                # Prepare rows for export
                for channel_info in similar_channels:
                    row = [
                        channel,  # Source channel
                        channel_info["title"],
                        channel_info["username"],
                        channel_info["url"],
                        str(channel_info["members"]) if channel_info["members"] else "Unknown",
                        channel_info.get("category", "Unknown")
                    ]
                    all_rows.append(row)
                
                all_similar_channels.extend(similar_channels)
                successful_channels += 1
            else:
                logger.warning(f"No similar channels found for {channel}")
                failed_channels += 1
        except Exception as e:
            logger.error(f"Error processing channel {channel}: {e}")
            failed_channels += 1
        
        # Apply rate limiting
        if idx < total_channels:
            delay = config.get('delay_between_channels', 8)
            logger.info(f"Waiting {delay} seconds before processing next channel")
            await asyncio.sleep(delay)
    
    # Close Telegram connection
    await telegram_crawler.close()
    
    # Log summary
    logger.info(f"Completed processing {total_channels} channels")
    logger.info(f"Successful: {successful_channels}, Failed: {failed_channels}")
    logger.info(f"Total similar channels found: {len(all_similar_channels)}")
    
    # Organize similar channels by input channel
    similar_channels_by_input = {}
    for input_channel, similar_list in channel_similar_channels.items():
        similar_channels_by_input[input_channel] = similar_list
    
    # Prepare export data
    export_data = {
        "headers": headers,
        "rows": all_rows
    }
    
    # Save results in simplified format
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"results_{timestamp}.json"
    
    # Extract usernames and format as strings with quotes
    usernames = [f"'{channel['username']}'"
                for channels in similar_channels_by_input.values()
                for channel in channels]
    
    result_data = {
        'similar_channels': usernames,
        'timestamp': datetime.now().isoformat()
    }
    
    with open(output_file, 'w') as f:
        json.dump(result_data, f, indent=2)
        logger.info(f"Results saved to {output_file}")
        
    return result_data

def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    config = {
        'telegram_api_id': os.getenv('TELEGRAM_API_ID'),
        'telegram_api_hash': os.getenv('TELEGRAM_API_HASH'),
        'telegram_phone': os.getenv('TELEGRAM_PHONE'),
        'telegram_session': os.getenv('TELEGRAM_SESSION', 'crawler'),
        'delay_between_channels': int(os.getenv('DELAY_BETWEEN_CHANNELS', '3')),
        'batch_size': int(os.getenv('BATCH_SIZE', '50'))
    }
    
    # Validate required configs
    
    # Validate required configs
    missing_configs = []
    if not config['telegram_api_id']:
        missing_configs.append('TELEGRAM_API_ID')
    if not config['telegram_api_hash']:
        missing_configs.append('TELEGRAM_API_HASH')
    
    if missing_configs:
        logger.error(f"Missing required configuration: {', '.join(missing_configs)}")
        logger.error("Please check your .env file or environment variables")
        sys.exit(1)
    
    return config

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Telegram Similar Channels Crawler')
    
    # Input methods (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--channels', nargs='+', help='List of Telegram channel usernames')
    input_group.add_argument('--file', help='Path to a JSON or CSV file containing channel usernames')
    
    # Optional arguments
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='INFO',
                       help='Set logging level (default: INFO)')
    parser.add_argument('--delay', type=int, help='Delay between processing channels (seconds)')
    parser.add_argument('--session', help='Custom session name for Telegram client')
    
    return parser.parse_args()

async def main():
    """Main entry point of the application."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Load configuration
    config = load_config()
    
    # Override config with command line arguments if provided
    if args.delay:
        config['delay_between_channels'] = args.delay
    
    # Load input channels
    input_channels = []
    if args.channels:
        input_channels = args.channels
        logger.info(f"Loaded {len(input_channels)} channels from command line")
    elif args.file:
        input_channels = InputHandler.load_from_file(args.file)
        logger.info(f"Loaded {len(input_channels)} channels from file: {args.file}")
    
    
    # Validate channels
    valid_channels = InputHandler.validate_channels(input_channels)
    if not valid_channels:
        logger.error("No valid channels to process. Exiting.")
        return
    
    logger.info(f"Starting processing of {len(valid_channels)} channels")
    result = await process_channels(valid_channels, config)
    logger.info("Processing completed")
    return result

if __name__ == "__main__":
    asyncio.run(main())
