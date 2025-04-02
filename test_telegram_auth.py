#!/usr/bin/env python3
"""
Simple Telegram API authentication test
"""

import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv
import os

load_dotenv()

async def main():
    client = TelegramClient(
        'test_session',
        os.getenv('TELEGRAM_API_ID'),
        os.getenv('TELEGRAM_API_HASH')
    )
    
    print("Connecting to Telegram...")
    await client.connect()
    
    if not await client.is_user_authorized():
        phone = os.getenv('TELEGRAM_PHONE')
        if not phone:
            phone = input("Enter phone number (with country code): ")
        
        print(f"Sending code to {phone}...")
        await client.send_code_request(phone)
        
        code = input("Enter received code: ")
        try:
            await client.sign_in(phone, code)
            print("Successfully signed in!")
        except Exception as e:
            print(f"Sign in failed: {e}")
            return
    
    me = await client.get_me()
    print(f"Authenticated as: {me.first_name} ({me.phone})")
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
