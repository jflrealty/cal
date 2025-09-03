import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")

# Fallback seguro para não quebrar o main
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "victor.adas@jflrealty.com.br")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
TWILIO_MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

PLOOMES_API_KEY = os.getenv("PLOOMES_API_KEY")

# Kill switch para WhatsApp
SEND_WHATSAPP = os.getenv("SEND_WHATSAPP", "false").lower() in ("1", "true", "yes", "on")
