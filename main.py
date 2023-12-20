import json
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from collections import defaultdict

app = FastAPI()

app.mount('/static', StaticFiles(directory='static'), name='static')

templates = Jinja2Templates(directory="templates")

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = defaultdict(dict)
        self.generator = self.get_notification_generator()

    async def get_notification_generator(self):
        while True:
            message = yield
            msg = message["message"]
            room_name = message["room_name"]
            await self.send_personal_message(msg, room_name)

    async def connect(self, websocket: WebSocket, room_name: str):
        await websocket.accept()
        if self.active_connections[room_name] == {} or len(self.active_connections[room_name]) == 0:
            self.active_connections[room_name] = []
        self.active_connections[room_name].append(websocket)
        print(f'CONNECTIONS: {self.active_connections[room_name]}')

    async def push(self, msg: str, room_name: str = None):
        message = {'message': msg, 'room_name': room_name}
        await self.generator.asend(message)
    def get_members(self, room_name):
        try:
            return self.active_connections[room_name]
        except Exception:
            return None

    def disconnect(self, websocket: WebSocket, room_name: str):
        self.active_connections[room_name].remove(websocket)
        print(f'CONNECTION REMOVED\nREMAINING CONNECTIONS: {self.active_connections[room_name]}')

    async def send_personal_message(self, message: str, room_name: str):
        ongoing_connections = []
        while len(self.active_connections[room_name]) > 0:
            websocket = self.active_connections[room_name].pop()
            await websocket.send_text(message)
            ongoing_connections.append(websocket)
        self.active_connections[room_name] = ongoing_connections

    # async def broadcast(self, message: str):
    #     for connection in self.active_connections:
    #         await connection.send_text(message)


manager = ConnectionManager()


@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})

@app.get("/{room_name}/{user_name}")
async def get(request: Request, room_name: str, user_name: str):
    return templates.TemplateResponse('chat.html', {'request': request, 'room_name': room_name, 'user_name': user_name})

@app.websocket("/ws/{room_name}")
async def websocket_endpoint(websocket: WebSocket, room_name: str):
    await manager.connect(websocket, room_name)
    try:
        while True:
            data = await websocket.receive_text()
            # print(type(data))
            # print(data)
            # d = json.loads(data)
            # d['room_name'] = room_name
            print(manager.get_members('newroom'))

            room_members = (
                manager.get_members(room_name)
                if manager.get_members(room_name) is not None
                else []
            )

            if websocket not in room_members:
                print("SENDER NOT IN ROOM: RECONNECTING")
                await manager.connect(websocket, room_name)
            await manager.send_personal_message(data, room_name)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_name)