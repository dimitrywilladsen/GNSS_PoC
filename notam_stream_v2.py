import os
import stomp
import ssl
from dotenv import load_dotenv

load_dotenv()

# --- VERIFICATION STEP ---
USER = os.getenv("SCDS_USER")
PASS = os.getenv("SCDS_PASS")
QUEUE = os.getenv("SCDS_QUEUE")

print(f"DEBUG: Attempting login for: {USER}")
print(f"DEBUG: Password length: {len(PASS) if PASS else 0} chars")

def connect_diagnostic():
    HOST = "scds.swim.faa.gov"
    PORT = 443
    
    conn = stomp.Connection12([(HOST, PORT)])
    
    # Python 3.14 Legacy SSL Context
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.options |= 0x4 

    conn.set_ssl([(HOST, PORT)], context)

    try:
        # Use a generic 'client-id' if your email is being rejected
        # Sometimes SCDS prefers a simple string like 'mysession123'
        conn.connect(
            username=USER, 
            passcode=PASS, 
            wait=True,
            headers={
                'client-id': USER, # Must match your SWIFT username
                'host': HOST,
                'accept-version': '1.2'
            }
        )
        print("✅ SUCCESS! Connected.")
        conn.subscribe(destination=QUEUE, id=1, ack='auto')
        
    except Exception as e:
        print(f"❌ REJECTED: {e}")

if __name__ == "__main__":
    connect_diagnostic()