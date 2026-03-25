import asyncio
import base64
import json
import websockets
import os
from dotenv import load_dotenv

load_dotenv()

def sts_connect():
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise Exception("DEEP_API_KEY not found ")
    
    sts_ws =websockets.connect(
        "wss://agent.deepgram.com/v1/agent/converse",
        subprotocols=["token" , api_key]

    )
    return sts_ws


'''def load_config():
    with open("config.json" , "r") as f:
        return json.load(f)
    
'''
HEALTH_PROMPT = """
You are an automated health guidance assistant.

You are NOT a doctor.
You do NOT diagnose conditions.
You do NOT prescribe medication or dosage.

You provide general health information, wellness guidance,
and recommend next steps such as contacting a healthcare provider.

Always:
- Ask if the user is comfortable continuing
- Speak calmly and respectfully

If the user reports chest pain, breathing difficulty, fainting,
severe confusion, or heavy bleeding:
Say:
"I can’t help with this situation. Please seek emergency medical care immediately."
Then STOP speaking.
"""

def build_config(country):
    language = "en-IN" if country=="IN" else "en-US"
    greeting = (
        "Hello, this is an automated health assistant calling to check on your wellbeing."
        if country=="IN" else
        "Hello, this is an automated health assistant calling to support your health."
    )
    return {
        "type": "Settings",
        "audio": {
            "input": {"encoding": "mulaw", "sample_rate": 8000},
            "output": {"encoding": "mulaw", "sample_rate": 8000, "container": "none"}
        },
        "agent": {
            "language": language,
            "greeting": greeting,
            "listen": {"provider": {"type": "deepgram", "model": "nova-3"}},
            "think": {"provider": {"type": "open_ai", "model": "gpt-4o-mini", "temperature": 0.4},
                      "prompt": HEALTH_PROMPT},
            "speak": {"provider": {"type": "deepgram", "model": "aura-2-thalia-en"}}
        }
    }


async def handle_barge_in(decoded,twilio_ws,streamsid):
    if decoded["type"] == "UserStartedSpeaking":
        clear_message ={
            "event": "clear",
            "streamSid":streamsid
        }
        await twilio_ws.send(json.dumps(clear_message))


async def handle_text_message(decoded,twilio_ws,sts_ws,streamsid):
    await handle_barge_in(decoded,twilio_ws,streamsid)



async def sts_sender(sts_ws,audio_queue):
    print("sts_sender started")
    while True:
        chunk = await audio_queue.get()
        await sts_ws.send(chunk)



async def sts_receiver(sts_ws,twilio_ws,streamsid_queue):
    print("sts_receiver started")
    streamsid = await streamsid_queue.get()

#loading data from deepgram
    async for message in sts_ws:
        if isinstance(message, str):
            decoded=json.loads(message)
            await handle_text_message(decoded, twilio_ws, sts_ws, streamsid)
        else:
            await twilio_ws.send(json.dumps({
                "event":"media",
                "streamSid":streamsid,
                "media":{"payload":base64.b64encode(message).decode("ascii")}
            }))

async def twilio_receiver(twilio_ws,audio_queue,streamsid_queue):
    BUFFER_SIZE = 20 * 160
    inbuffer = bytearray(b"")     
    async for message in twilio_ws:
        
        data = json.loads(message)
        event = data.get("event")
        
        if event == "start":
            streamsid_queue.put_nowait(data["start"]["streamSid"])
        elif event=="media" and data["media"]["track"]=="inbound":
            inbuffer.extend(base64.b64decode(data["media"]["payload"]))
        elif event=="stop":
            break

        while len(inbuffer)>= BUFFER_SIZE:
            audio_queue.put_nowait(inbuffer[:BUFFER_SIZE])
            inbuffer = inbuffer[BUFFER_SIZE:]

         
async def twilio_handler(twilio_ws):
    print("Twilio WebSocket CONNECTED")
    audio_queue = asyncio.Queue()
    streamsid_queue=asyncio.Queue()
    
    async with sts_connect() as sts_ws:
       # config_message=load_config()
        #await sts_ws.send(json.dumps(config_message))
        # TEMP: hardcode country for now
        country = "IN"   # later derive from phone number
        config_message = build_config(country)
        await sts_ws.send(json.dumps(config_message))

        #await asyncio.wait(
         # [
          #  asyncio.ensure_future(sts_sender(sts_ws,audio_queue)),
           # asyncio.ensure_future(sts_receiver(sts_ws,twilio_ws,streamsid_queue)),
            #asyncio.ensure_future(twilio_receiver(twilio_ws,audio_queue,streamsid_queue)),
          #]

        #)
        tasks = [
            asyncio.create_task(sts_sender(sts_ws, audio_queue)),
            asyncio.create_task(sts_receiver(sts_ws, twilio_ws, streamsid_queue)),
            asyncio.create_task(twilio_receiver(twilio_ws, audio_queue, streamsid_queue)),
        ]
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED
        )

        # Clean shutdown
        for task in pending:
            task.cancel()

    await  twilio_ws.close()

async def main():
   await websockets.serve(twilio_handler,"0.0.0.0", 5000)
   print("Started sever ")
   await asyncio.Future()

if __name__=="__main__":
    asyncio.run(main())
   