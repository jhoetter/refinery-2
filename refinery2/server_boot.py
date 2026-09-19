"""Boot: sync store then serve UI+API on port 3000."""
import uvicorn

from scripts.sync_demo import sync

if __name__ == "__main__":
    sync()
    uvicorn.run("refinery2.server:app", host="0.0.0.0", port=3000)
