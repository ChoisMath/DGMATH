import os
from solapi import SolapiMessageService
from solapi.messages import Message
from app.config import Config
from app.utils import send_sms_notification

# Load environment variables (for local testing)
# In a deployed environment, these would be automatically loaded.
Config.load_env_variables()

# Initialize Solapi service (similar to app.db.py)
# For testing, we'll directly initialize it here.
SOLAPI_API_KEY = os.environ.get('SOLAPI_API_KEY')
SOLAPI_API_SECRET = os.environ.get('SOLAPI_API_SECRET')
SOLAPI_SENDER_PHONE = os.environ.get('SOLAPI_SENDER_PHONE')

solapi_service = None
if SOLAPI_API_KEY and SOLAPI_API_SECRET:
    try:
        solapi_service = SolapiMessageService(SOLAPI_API_KEY, SOLAPI_API_SECRET)
        print("SolapiMessageService initialized successfully.")
    except Exception as e:
        print(f"Error initializing SolapiMessageService: {e}")
else:
    print("SOLAPI_API_KEY or SOLAPI_API_SECRET not set. Cannot initialize Solapi service.")

# Set the initialized solapi_service to app.db.py's global variable for send_sms_notification to use
# This is a workaround for testing outside Flask app context.
from app.db import solapi_service as db_solapi_service
db_solapi_service = solapi_service

# Test SMS sending
if solapi_service and SOLAPI_SENDER_PHONE:
    test_phone_number = "01012345678"  # Replace with a real phone number for testing
    test_message = "안녕하세요! 테스트 메시지입니다. Solapi 연동 확인."
    
    print(f"Attempting to send SMS to {test_phone_number} with message: {test_message}")
    success = send_sms_notification(test_phone_number, test_message)
    
    if success:
        print("SMS test message sent successfully!")
    else:
        print("Failed to send SMS test message.")
else:
    print("Skipping SMS test: Solapi service not initialized or sender phone not set.")
