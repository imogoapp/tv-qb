import os

import uvicorn


if __name__ == "__main__":
    # TVQB_RELOAD=1 reinicia o servidor sozinho quando um arquivo .py de app/ muda (util ao desenvolver).
    reload = os.environ.get("TVQB_RELOAD") == "1"
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=reload, reload_dirs=["app"] if reload else None)
