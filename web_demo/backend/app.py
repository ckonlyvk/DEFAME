
import asyncio
import json
import logging
import queue
import threading
from typing import Any, Dict

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

class QueueHandler(logging.Handler):
    """Logging handler that sends logs to a queue."""
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def emit(self, record):
        try:
            msg = self.format(record)
            # Send as a log event
            self.q.put({"status_message": msg})
        except Exception:
            self.handleError(record)

def run_fact_check(claim_text: str, q: queue.Queue):
    """Runs the fact check in a separate thread."""
    
    # Setup custom handler to intercept ALL mafc logs
    # We use 'mafc' logger as defined in defame/common/logger.py
    mafc_logger = logging.getLogger('mafc')
    # Remove existing handlers to avoid double printing if needed, or just add ours
    # For this demo, adding ours is fine.
    
    # We need a formatter
    formatter = logging.Formatter('%(message)s')
    
    q_handler = QueueHandler(q)
    q_handler.setFormatter(formatter)
    q_handler.setLevel(logging.INFO) # Capture INFO and above (including our thinking steps)
    
    mafc_logger.addHandler(q_handler)
    
    try:
        # Initialize experiment dir to avoid accessing None in logger.target_dir
        from config.globals import result_base_dir, working_dir
        
        # Ensure working_dir is absolute
        if not working_dir.is_absolute():
             # Fallback if globals.py wasn't patched correctly or relative
             import pathlib
             working_dir = pathlib.Path(__file__).parent.parent.parent
        
        logger.set_experiment_dir(path=result_base_dir / "web_demo")
        # We don't need set_connection anymore since we hook into logging directly
        
        # Initialize FactChecker
        fact_checker = FactChecker(llm="gpt_4o", procedure_variant="infact")
        
        # Run check
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
        # The logger.error above will be caught by our handler and sent as log
        # But we also want to send an explicit error event to stop frontend
        q.put({"status_message": "ERROR", "error": str(e)})
    finally:
        # Cleanup handler
        mafc_logger.removeHandler(q_handler)


@app.post("/api/check")
async def check_claim(request: CheckRequest):
    q = queue.Queue()
    
    # Run in a separate thread to not block the event loop
    # Note: Because FactChecker uses shared global state (logger), proper concurrency 
    # control would be needed for a real multi-user app. 
    # For a local demo, we assume one request at a time.
    t = threading.Thread(target=run_fact_check, args=(request.claim, q))
    t.start()

    async def event_generator():
        while True:
            try:
                # Non-blocking get from queue
                data = q.get_nowait()
                
                # Check for completion or special messages
                if isinstance(data, dict):
                    if data.get("status_message") == "DONE":
                        yield f"event: result\ndata: {json.dumps(data['result'])}\n\n"
                        break
                    elif data.get("status_message") == "ERROR":
                        yield f"event: error\ndata: {json.dumps(data)}\n\n"
                        break
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
