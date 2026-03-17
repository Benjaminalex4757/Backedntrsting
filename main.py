from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
import json
import os

app = Flask(__name__)
# CORS enabled for all origins
CORS(app, resources={r"/api/*": {"origins": "*"}})

ORBIT_BASE_URL = "https://api.orbit-provider.com/api/provider/agy/v1/messages"

@app.route('/api/proxy', methods=['POST', 'OPTIONS'])
@app.route('/api/proxy/<path:path>', methods=['POST', 'OPTIONS'])
def proxy_request(path=None):
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    try:
        incoming_data = request.json
        
        # API Key handle karna (Bearer Auth aur x-api-key dono ko support karega)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header.split(" ")[1]
        else:
            api_key = request.headers.get("x-api-key", "")
            
        # --- OPENAI SE ANTHROPIC FORMAT CONVERTER ---
        messages = incoming_data.get("messages", [])
        system_prompt = ""
        anthropic_messages = []
        
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt += msg.get("content", "") + "\n"
            else:
                anthropic_messages.append(msg)
        
        payload = {
            "model": incoming_data.get("model", ""),
            "max_tokens": incoming_data.get("max_tokens", 8192),
            "messages": anthropic_messages,
            "stream": True, # STREAMING ON
            "temperature": incoming_data.get("temperature", 0.3)
        }
        
        if system_prompt.strip():
            payload["system"] = system_prompt.strip()

        # Strict Disguise Headers
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/event-stream, */*",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site"
        }

        # Orbit ko Streaming Request bhejna
        req = requests.post(ORBIT_BASE_URL, headers=headers, json=payload, stream=True)

        if req.status_code != 200:
            return jsonify({"error": "Provider Error", "status": req.status_code, "details": req.text}), req.status_code

        # Generator function jo SSE chunks wapis bhejega
        def generate():
            for line in req.iter_lines():
                if line:
                    yield line.decode('utf-8') + '\n\n'

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500

if __name__ == '__main__':
    # Railway environment variable se PORT khud uthayega, warna local par 5000 use karega
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
