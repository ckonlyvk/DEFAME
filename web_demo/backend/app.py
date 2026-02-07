
import asyncio
import json
import queue
import threading

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# --- Adapt Defame imports ---
# Assuming defame is in the python path (parent directory)
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from defame.fact_checker import FactChecker
from defame.common import logger

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(static_dir, "index.html"))

class CheckRequest(BaseModel):
    claim: str



def run_fact_check(claim_text: str, q: queue.Queue, stop_event: threading.Event = None):
    """Runs the fact check in a separate thread.
    
    Args:
        claim_text: The claim to fact-check
        q: Queue for sending events to the frontend
        stop_event: Threading event to signal early termination (currently not used due to blocking FactChecker)
    """
    
    # Setup StageEmitter to send structured events
    from defame.common import StageEmitter
    StageEmitter.set_queue(q)
    
    try:
        # Initialize experiment dir to avoid accessing None in logger.target_dir
        from config.globals import result_base_dir, working_dir
        
        # Ensure working_dir is absolute
        if not working_dir.is_absolute():
             # Fallback if globals.py wasn't patched correctly or relative
             import pathlib
             working_dir = pathlib.Path(__file__).parent.parent.parent
        
        logger.set_experiment_dir(path=result_base_dir / "web_demo")
        
        # Initialize FactChecker
        fact_checker = FactChecker(llm="ollama_deepseek_cloud", procedure_variant="vifactcheck")
        
        # Run check
        # Note: FactChecker.check_content() is blocking and cannot be easily interrupted
        # The stop_event is accepted but not used - client disconnect only stops event streaming
        # Fix: check_content returns 3 values: (veracity, docs, metas)
        veracity, docs, metas = fact_checker.check_content([claim_text])
        
        if not docs:
             raise ValueError("No report generated.")
             
        report = docs[0]
        
        # Send final result
        result = report.get_result_as_dict()
        
        # Serialize report for evidence display
        evidences = []
        if hasattr(report, 'record'):
             for block in report.record:
                 # Check if this is an EvidenceBlock
                 if hasattr(block, 'evidences'):
                     for ev in block.evidences:
                         if ev.is_useful():
                             # Extract clean text from takeaways
                             ev_text = str(ev.takeaways) if ev.takeaways else str(ev.raw)
                             
                             # Try to extract URL from the evidence
                             url = None
                             # Check if the raw result is SearchResults
                             if hasattr(ev.raw, 'sources') and ev.raw.sources:
                                 # Get URLs from all sources
                                 for source in ev.raw.sources:
                                     if hasattr(source, 'url'):
                                         # Create separate evidence entry for each source
                                         source_text = str(source.takeaways) if hasattr(source, 'takeaways') and source.takeaways else ev_text
                                         evidences.append({
                                             "text": source_text,
                                             "url": source.url,
                                             "title": getattr(source, 'title', None)
                                         })
                             else:
                                 # No URL available, just add the evidence text
                                 evidences.append({"text": ev_text, "url": None})

        final_payload = {
            "verdict": result.get("verdict"),
            "justification": result.get("justification"),
            "evidences": evidences
        }
        
        q.put({"status_message": "DONE", "result": final_payload})

    except Exception as e:
        logger.error(f"Error during fact check: {e}")
        q.put({"status_message": "ERROR", "error": str(e)})
    finally:
        # Cleanup StageEmitter
        StageEmitter.set_queue(None)


@app.post("/api/check")
async def check_claim(request: CheckRequest, req: Request):
    q = queue.Queue()
    stop_event = threading.Event()  # Event to signal thread to stop
    
    # Run in a separate thread to not block the event loop
    # Note: Because FactChecker uses shared global state (logger), proper concurrency 
    # control would be needed for a real multi-user app. 
    # For a local demo, we assume one request at a time.
    t = threading.Thread(target=run_fact_check, args=(request.claim, q, stop_event))
    t.start()

    async def event_generator():
        while True:
            # Check if client disconnected
            if await req.is_disconnected():
                logger.info("Client disconnected, stopping fact check...")
                stop_event.set()  # Signal the thread to stop
                break
                
            try:
                # Non-blocking get from queue
                data = q.get_nowait()
                
                # Check for completion or special messages
                if isinstance(data, dict):
                    event_type = data.get("type", "")
                    
                    # Handle final result
                    if data.get("status_message") == "DONE":
                        yield f"event: result\ndata: {json.dumps(data['result'])}\n\n"
                        break
                    elif data.get("status_message") == "ERROR":
                        yield f"event: error\ndata: {json.dumps(data)}\n\n"
                        break
                    
                    # Handle structured stage events from StageEmitter
                    elif event_type == "stage":  # Changed from "step" to "stage"
                        yield f"event: step\ndata: {json.dumps(data)}\n\n"  # Still send as "step" event to frontend
                    elif event_type == "stage_update":  # Changed from "step_update" to "stage_update"
                        yield f"event: step_update\ndata: {json.dumps(data)}\n\n"
                    elif event_type == "log":
                        # Regular log message
                        yield f"event: log\ndata: {json.dumps(data)}\n\n"
                    else:
                        # Normal log message structure from logger.send() is dict(task_id=..., status_message=...)
                        msg = data.get("status_message", "")
                        # Often the message is just text, we send it as log
                        yield f"event: log\ndata: {json.dumps(dict(message=msg))}\n\n"
            except queue.Empty:
                if not t.is_alive() and q.empty():
                    break
                await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
