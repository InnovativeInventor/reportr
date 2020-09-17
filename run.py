import app
import uvicorn
import os


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=os.environ.get("HOST"),
        port=8000,
        log_level="info",
        debug=True,
    )
