from fastapi import FastAPI, UploadFile
import shutil
from vision.pipeline import process_video

app = FastAPI()

@app.post("/upload")
async def upload(file: UploadFile):
    path = f"videos/{file.filename}"

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    process_video(path)

    return {"status": "processed"}