import os
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

# Allow your frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The Disguise Headers to bypass blocks
DISGUISE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site"
}

@app.post("/proxy")
async def proxy_request(request: Request):
    """
    Receives { target_url, method, headers, payload } from the frontend,
    adds the disguise, and forwards the stream back.
    """
    data = await request.json()
    target_url = data.get("target_url")
    method = data.get("method", "POST").upper()
    headers = data.get("headers", {})
    payload = data.get("payload", None)

    # Merge your custom headers with the disguise headers
    final_headers = {**headers, **DISGUISE_HEADERS}
    
    # Remove 'host' so HTTPX automatically calculates it for OpenAI/Gemini
    final_headers.pop("host", None)
    final_headers.pop("Host", None)

    # Handle Standard GET Requests (e.g., checking API Key status & fetching models)
    if method == "GET":
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.get(target_url, headers=final_headers)
            
            # Remove proxy-breaking headers
            resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in ["content-encoding", "content-length", "transfer-encoding", "connection"]}
            return Response(content=resp.content, status_code=resp.status_code, headers=resp_headers)

    # Handle Streaming POST Requests (e.g., AI Translation/Analysis generation)
    if method == "POST":
        client = httpx.AsyncClient(timeout=120.0)
        req = client.build_request("POST", target_url, headers=final_headers, json=payload)
        response = await client.send(req, stream=True)

        async def stream_generator():
            async for chunk in response.aiter_bytes():
                yield chunk
            await response.aclose()
            await client.aclose()

        resp_headers = {k: v for k, v in response.headers.items() if k.lower() not in ["content-encoding", "content-length", "transfer-encoding", "connection"]}
        return StreamingResponse(stream_generator(), status_code=response.status_code, headers=resp_headers)

# Railway automatically passes the PORT environment variable
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)