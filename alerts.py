"""
PROJECT HOPE v3.0 - Text Alerts via Twilio
"""
import config

class Alerts:
    def __init__(self):
        self.enabled = bool(config.TWILIO_SID and config.TWILIO_TOKEN and config.TWILIO_PHONE and config.MY_PHONE)
        self.client = None
        if self.enabled:
            try:
                from twilio.rest import Client
                self.client = Client(config.TWILIO_SID, config.TWILIO_TOKEN)
            except Exception as e:
                print(f"[ALERTS] Twilio init failed: {e}")
                self.enabled = False

    def send(self, message):
        if not self.enabled or not self.client:
            print(f"[ALERT] {message}")
            return False
        try:
            self.client.messages.create(body=f"PROJECT HOPE\n{message}", from_=config.TWILIO_PHONE, to=config.MY_PHONE)
            return True
        except Exception as e:
            print(f"[ALERT ERR] {e}")
            return False
