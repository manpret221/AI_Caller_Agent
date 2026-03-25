from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()
WS_URL = os.getenv("WS_URL")
if not WS_URL:
    raise RuntimeError(" WS_URL is NOT set")

print("🔥 USING WS_URL:", WS_URL)
client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

def call_user(phone_number):
    try:
        call = client.calls.create(
            to=str(phone_number),  # ✅ ensure string
            from_=os.getenv("TWILIO_FROM_NUMBER"),
            twiml=f"""
            <Response>
                <Say voice="alice">Connecting you now.</Say>
                <Connect>
                    <Stream url="{os.getenv('WS_URL')}" />
                </Connect>
            </Response>
            """
        )
        print("Calling:", phone_number, "Call SID:", call.sid)
        return call.sid
    except Exception as e:
        print("Failed to call:", phone_number, "Error:", e)
        return None


if __name__=="__main__":
    numbers = ["+919882397989","+917018487497"]
    for num in numbers:
        call_user(num)