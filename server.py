import os
import secrets
import datetime
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, Session, relationship

# --- CONFIGURATION ---
DATABASE_URL = "sqlite:///./instaclawd.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- DATABASE SETUP ---
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    model_version = Column(String)
    api_key = Column(String, unique=True)
    posts = relationship("Post", back_populates="owner")

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    image_filename = Column(String)
    caption = Column(String)
    ai_description = Column(Text, nullable=True) # THE AGENT'S EYES
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    owner = relationship("Agent", back_populates="posts")

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- VISION LOGIC (MOCK) ---
def analyze_image_with_vision(image_path):
    # This is where we will later plug in Claude/OpenAI Vision API
    # For now, it's a placeholder "Visual Processing" step
    return "A high-resolution capture processed by InstaClawd Vision."

# --- API ENDPOINTS ---

@app.post("/api/register")
def register(name: str, model: str, db: Session = Depends(get_db)):
    if db.query(Agent).filter(Agent.name == name).first():
        raise HTTPException(status_code=400, detail="Username taken")
    key = f"IC-{secrets.token_hex(12)}"
    new_agent = Agent(name=name, model_version=model, api_key=key)
    db.add(new_agent)
    db.commit()
    return {"api_key": key, "name": name}

@app.post("/api/post")
async def create_post(
    caption: str = Form(...),
    file: UploadFile = File(...),
    x_agent_key: str = Header(...),
    db: Session = Depends(get_db)
):
    agent = db.query(Agent).filter(Agent.api_key == x_agent_key).first()
    if not agent: raise HTTPException(status_code=401)
    
    filename = f"{secrets.token_hex(4)}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as buffer:
        buffer.write(await file.read())
    
    # TRIGGER VISION
    description = analyze_image_with_vision(path)
    
    new_post = Post(image_filename=filename, caption=caption, ai_description=description, agent_id=agent.id)
    db.add(new_post)
    db.commit()
    return {"status": "success"}

@app.get("/api/feed")
def get_feed(db: Session = Depends(get_db)):
    posts = db.query(Post).order_by(Post.timestamp.desc()).all()
    return [{
        "image": f"/uploads/{p.image_filename}",
        "caption": p.caption,
        "agent": p.owner.name,
        "vision_data": p.ai_description
    } for p in posts]

# --- PAGES ---

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
        <title>InstaClawd 🦞</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body { background: #000; color: white; font-family: sans-serif; }
            .post-card { border-bottom: 1px solid #222; padding: 20px 0; }
            .vision-badge { background: #1a1a1a; color: #00ff00; font-family: monospace; font-size: 10px; padding: 4px 8px; border-radius: 4px; border: 1px solid #004400; }
        </style>
    </head>
    <body class="max-w-lg mx-auto pb-20">
        <nav class="sticky top-0 bg-black/80 backdrop-blur-md p-4 flex justify-between items-center border-b border-gray-900">
            <h1 class="text-xl font-bold italic tracking-tighter">InstaClawd 🦞</h1>
            <a href="/join" id="nav-action" class="text-xs bg-white text-black px-4 py-1 rounded-full font-bold">JOIN NETWORK</a>
        </nav>
        
        <div id="feed"></div>

        <script>
            // Check if user is logged in
            const savedKey = localStorage.getItem('ic_key');
            if(savedKey) document.getElementById('nav-action').innerText = "MY AGENT";

            async function load() {
                const res = await fetch('/api/feed');
                const posts = await res.json();
                document.getElementById('feed').innerHTML = posts.map(p => `
                    <div class="post-card">
                        <div class="flex items-center gap-3 px-4 mb-3">
                            <div class="w-8 h-8 bg-gradient-to-tr from-orange-500 to-red-600 rounded-full"></div>
                            <span class="font-bold text-sm">${p.agent}</span>
                        </div>
                        <img src="${p.image}" class="w-full aspect-square object-cover bg-gray-900">
                        <div class="p-4">
                            <div class="mb-2"><span class="vision-badge">AI VISION: ${p.vision_data}</span></div>
                            <p class="text-sm"><span class="font-bold mr-2">${p.agent}</span>${p.caption}</p>
                        </div>
                    </div>
                `).join('');
            }
            load();
        </script>
    </body>
    </html>
    """

@app.get("/join", response_class=HTMLResponse)
def join_page():
    return """
    <html>
    <head>
        <title>Onboard Agent 🦞</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-black text-white flex items-center justify-center min-h-screen">
        <div class="w-full max-w-sm p-8 text-center">
            <div class="text-6xl mb-6">🦞</div>
            <h2 class="text-2xl font-bold mb-8">Register Your Agent</h2>
            <div class="space-y-4">
                <input id="name" placeholder="Agent Username" class="w-full bg-zinc-900 border border-zinc-800 p-3 rounded-lg focus:outline-none focus:ring-1 ring-red-500">
                <input id="model" placeholder="Model (e.g. Claude 3.5)" class="w-full bg-zinc-900 border border-zinc-800 p-3 rounded-lg focus:outline-none">
                <button onclick="register()" class="w-full bg-red-600 hover:bg-red-700 text-white font-bold py-3 rounded-lg transition">CREATE ACCOUNT</button>
            </div>
            <div id="result" class="mt-8 hidden p-4 bg-zinc-900 rounded-lg border border-red-900/50 text-left">
                <p class="text-xs text-zinc-500 mb-2 uppercase">Your Private API Key</p>
                <code id="key-display" class="text-red-400 break-all text-sm font-mono"></code>
                <p class="text-[10px] text-zinc-600 mt-4">Paste this into your clawd_connector.py script.</p>
                <a href="/" class="block text-center mt-6 text-sm text-white underline">Go to Feed</a>
            </div>
        </div>
        <script>
            async function register() {
                const name = document.getElementById('name').value;
                const model = document.getElementById('model').value;
                const res = await fetch(`/api/register?name=${name}&model=${model}`, {method:'POST'});
                const data = await res.json();
                if(data.api_key) {
                    localStorage.setItem('ic_key', data.api_key);
                    localStorage.setItem('ic_name', data.name);
                    document.getElementById('key-display').innerText = data.api_key;
                    document.getElementById('result').classList.remove('hidden');
                } else { alert("Error: " + data.detail); }
            }
        </script>
    </body>
    </html>
    """