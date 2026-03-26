from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from db.database import engine, Base
import json
from pydantic import BaseModel

# Create database tables (in prod use Alembic)
import db.models  # Required to register tables with Base before create_all()
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------
# WebSocket Manager for Progress Tracking
# -----------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)

    def disconnect(self, websocket: WebSocket, project_id: str):
        if project_id in self.active_connections:
            self.active_connections[project_id].remove(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]

    async def broadcast_to_project(self, project_id: str, message: dict):
        if project_id in self.active_connections:
            for connection in self.active_connections[project_id]:
                await connection.send_text(json.dumps(message))

manager = ConnectionManager()

@app.websocket("/ws/project/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await manager.connect(websocket, project_id)
    try:
        while True:
            data = await websocket.receive_text() # keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)

@app.get("/")
def read_root():
    return {"message": "AdClip AI API Tracker"}

class WsBroadcast(BaseModel):
    project_id: str
    status: str
    message: str

@app.post("/api/internal/ws_broadcast")
async def internal_ws_broadcast(data: WsBroadcast):
    await manager.broadcast_to_project(data.project_id, {"status": data.status, "message": data.message})
    return {"success": True}

from api.routes import router as api_router
app.include_router(api_router, prefix="/api")

# Later we will include routers from api/routes.py
