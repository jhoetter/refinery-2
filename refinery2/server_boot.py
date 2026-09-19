"""Boot: sync store then serve API on port 8000 (frontend is Next.js on :3000)."""
import os

import uvicorn

from scripts.sync_demo import sync

if __name__ == "__main__":
    sync()
    uvicorn.run("refinery2.server:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
