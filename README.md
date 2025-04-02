# Telegram Similar Channels Crawler

A Python-based tool that fetches similar channel recommendations from Telegram and exports them to Google Sheets.

## Features

- Fetch similar Telegram channels via Telegram's official API
- Process and organize channel data with proper metadata
- Export results to Google Sheets
- Support multiple input methods (CLI, file, Google Sheets)
- Proper error handling and logging
- Rate limiting protection to avoid Telegram API limits

## Requirements

- Python 3.7+
- Telegram API credentials (API ID and API Hash)
- Google Sheets API credentials (service account JSON file)

## Installation

1. Clone this repository
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your credentials
4. Prepare your Google Sheets service account JSON file

## Getting API Credentials

### Telegram API Credentials

1. Visit [my.telegram.org/apps](https://my.telegram.org/apps)
2. Log in with your Telegram account
3. Fill in the form with any name and description
4. Get your API ID and API Hash
5. Add these values to your `.env` file

### Google Sheets API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Sheets API and Google Drive API
4. Create a service account
5. Download the service account JSON key file
6. Place this file in your project directory and update the path in your `.env` file

## Usage

The script supports three methods of inputting channel usernames:

### From Command Line

```bash
python telegram_crawler.py --channels channelname1 channelname2 channelname3
