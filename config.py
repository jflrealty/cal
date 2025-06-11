from dotenv import load_dotenv
import os

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL") 
TWILIO_ACCOUNT_SID = "ACa66cc829fd1046db469f69b03467e358"
TWILIO_AUTH_TOKEN = "bc102b54181a3f9d4a7e018f5096c5d2"
TWILIO_WHATSAPP_NUMBER = "whatsapp:+19378703022"
