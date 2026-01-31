
import uvicorn
import os
import sys

if __name__ == "__main__":
    # Ensure src is in path
    sys.path.append(os.path.join(os.getcwd(), "src"))
    
    print("🚀 Starting FTMO Pro Trader...")
    print("👉 Open http://127.0.0.1:8000 in your browser")
    
    try:
        uvicorn.run("src.api.server:app", host="127.0.0.1", port=8000, reload=True)
    except KeyboardInterrupt:
        print("Shutting down...")
