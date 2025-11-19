# main.py - Simple MEZOPOTAMYA.TRAVEL Backend API
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
import sqlite3
import json
import requests
from datetime import datetime
import uvicorn
import os

# Import RAG modules
from document_processor import DocumentProcessor
from vector_store import VectorStore
from rag_service import RAGService

app = FastAPI(
    title="Mezopotamya.Travel API",
    description="""
    ## 🏛️ Mezopotamya.Travel - Tourism AI Assistant Platform
    
    A comprehensive REST API for the Mezopotamya.Travel tourism platform. This API provides:
    
    * **AI Chat Assistant**: Interactive chat with RAG (Retrieval-Augmented Generation) support
    * **Destination Management**: Browse and search tourism destinations in the GAP region
    * **Personalized Recommendations**: Get AI-powered travel recommendations based on interests
    * **Document Management**: Ingest and search tourism documents using vector embeddings
    * **Itinerary Generation**: Create personalized travel itineraries
    * **Route Planning**: Generate optimized routes between destinations
    
    ### Features
    - 🔍 Semantic search powered by Qdrant vector database
    - 🤖 Local LLM integration via Ollama (Llama 2, Mistral)
    - 📊 SQLite database for structured data
    - 🌐 Multi-language support (Turkish, English)
    - 📝 RAG-powered responses with context awareness
    
    ### API Access
    - Swagger UI: `/docs`
    - ReDoc: `/redoc`
    - OpenAPI JSON: `/openapi.json`
    """,
    version="1.0.0",
    contact={
        "name": "AGENTİC DYNAMİC YAZILIM",
        "email": "info@mezopotamya.travel",
        "url": "https://mezopotamya.travel"
    },
    license_info={
        "name": "Proprietary",
        "url": "https://mezopotamya.travel/license"
    },
    tags_metadata=[
        {
            "name": "Health",
            "description": "Health check and API information endpoints"
        },
        {
            "name": "Chat",
            "description": "AI chat assistant endpoints with RAG support"
        },
        {
            "name": "Destinations",
            "description": "Tourism destination management and browsing"
        },
        {
            "name": "Recommendations",
            "description": "Personalized travel recommendations based on user interests"
        },
        {
            "name": "Documents",
            "description": "Document ingestion and semantic search for RAG"
        },
        {
            "name": "Itineraries",
            "description": "Generate and manage travel itineraries"
        },
        {
            "name": "Routes",
            "description": "Route planning and generation between locations"
        },
        {
            "name": "System",
            "description": "System status and configuration endpoints"
        }
    ]
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG components
vector_store = None
document_processor = None
rag_service = None

# Database helper
def get_db_connection():
    """Get database connection using configured path"""
    db_path = os.getenv("DATABASE_PATH", "mezopotamya.db")
    return sqlite3.connect(db_path)

# Database setup
def init_db():
    global vector_store, document_processor, rag_service
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Create existing tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS destinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            location TEXT,
            rating REAL,
            image_url TEXT,
            tags TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            message TEXT,
            response TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT PRIMARY KEY,
            interests TEXT,
            visited_places TEXT,
            language TEXT DEFAULT 'tr'
        )
    ''')
    
    # New tables for RAG functionality
    c.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            type TEXT,
            source TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            chunk_text TEXT,
            chunk_index INTEGER,
            vector_id TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS itineraries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            route_data TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            waypoints TEXT,
            distance REAL,
            duration TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert sample data
    sample_destinations = [
        ("Göbeklitepe", "Dünyanın en eski tapınak kompleksi, 12.000 yıllık tarih", "Tarihi", "Şanlıurfa", 4.8, "gobekli.jpg", "tarih,arkeoloji,unesco"),
        ("Balıklıgöl", "Hz. İbrahim'in ateşe atıldığı yer, kutsal göl", "Dini", "Şanlıurfa", 4.7, "balikligol.jpg", "din,tarih,göl"),
        ("Nemrut Dağı", "Kommagene Krallığı'nın dev heykelleri", "Tarihi", "Adıyaman", 4.9, "nemrut.jpg", "tarih,unesco,dağ"),
        ("Harran", "Koni evleriyle ünlü antik şehir", "Tarihi", "Şanlıurfa", 4.5, "harran.jpg", "tarih,mimari,antik"),
        ("Hasankeyf", "12.000 yıllık tarihi yerleşim", "Tarihi", "Batman", 4.6, "hasankeyf.jpg", "tarih,kale,höyük"),
        ("Mardin Kalesi", "Taş evleriyle ünlü tarihi şehir", "Tarihi", "Mardin", 4.7, "mardin.jpg", "tarih,mimari,kale"),
        ("Diyarbakır Surları", "Çin Seddi'nden sonra en uzun sur", "Tarihi", "Diyarbakır", 4.4, "sur.jpg", "tarih,sur,unesco"),
        ("Zeugma Mozaik Müzesi", "Dünyanın en büyük mozaik müzesi", "Müze", "Gaziantep", 4.8, "zeugma.jpg", "müze,mozaik,sanat")
    ]
    
    c.executemany('INSERT OR IGNORE INTO destinations (name, description, category, location, rating, image_url, tags) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                  sample_destinations)
    
    conn.commit()
    conn.close()
    
    # Initialize Qdrant and RAG services
    try:
        vector_store = VectorStore()
        if vector_store.is_connected():
            vector_store.ensure_collection(vector_size=384)
            print("✅ Qdrant bağlantısı başarılı")
        else:
            print("⚠️ Qdrant bağlantısı başarısız, RAG özellikleri devre dışı")
    except Exception as e:
        print(f"⚠️ Qdrant başlatma hatası: {e}")
        vector_store = None
    
    # Initialize document processor
    try:
        chunk_size = int(os.getenv("CHUNK_SIZE", "512"))
        chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "50"))
        document_processor = DocumentProcessor(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        print("✅ Document processor hazır")
    except Exception as e:
        print(f"⚠️ Document processor başlatma hatası: {e}")
        document_processor = None
    
    # Initialize RAG service
    if vector_store and document_processor:
        try:
            rag_service = RAGService(vector_store=vector_store, document_processor=document_processor)
            print("✅ RAG servisi hazır")
        except Exception as e:
            print(f"⚠️ RAG servisi başlatma hatası: {e}")
            rag_service = None

# Pydantic models
class ChatMessage(BaseModel):
    """Request model for chat endpoint"""
    user_id: str = Field(..., description="Unique identifier for the user", example="user123")
    message: str = Field(..., description="User's message/question", example="Göbeklitepe hakkında bilgi verir misin?")
    language: str = Field(default="tr", description="Response language (tr/en)", example="tr")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "message": "Göbeklitepe hakkında bilgi verir misin?",
                "language": "tr"
            }
        }

class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str = Field(..., description="AI assistant's response", example="Göbeklitepe, dünyanın en eski tapınak kompleksidir...")
    user_id: str = Field(..., description="User identifier", example="user123")
    
    class Config:
        schema_extra = {
            "example": {
                "response": "Göbeklitepe, dünyanın en eski tapınak kompleksidir. M.Ö. 10.000 yıllarına dayanan bu yapı, Şanlıurfa'da bulunur.",
                "user_id": "user123"
            }
        }

class Destination(BaseModel):
    """Destination model"""
    id: Optional[int] = Field(None, description="Unique destination identifier")
    name: str = Field(..., description="Name of the destination", example="Göbeklitepe")
    description: str = Field(..., description="Detailed description", example="Dünyanın en eski tapınak kompleksi")
    category: str = Field(..., description="Destination category", example="Tarihi")
    location: str = Field(..., description="City/region location", example="Şanlıurfa")
    rating: float = Field(..., description="User rating (0-5)", ge=0, le=5, example=4.8)
    image_url: str = Field(..., description="URL to destination image", example="gobekli.jpg")
    tags: List[str] = Field(..., description="Tags for filtering", example=["tarih", "arkeoloji", "unesco"])
    
    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "name": "Göbeklitepe",
                "description": "Dünyanın en eski tapınak kompleksi, 12.000 yıllık tarih",
                "category": "Tarihi",
                "location": "Şanlıurfa",
                "rating": 4.8,
                "image_url": "gobekli.jpg",
                "tags": ["tarih", "arkeoloji", "unesco"]
            }
        }

class RecommendationRequest(BaseModel):
    """Request model for recommendations"""
    user_id: str = Field(..., description="Unique identifier for the user", example="user123")
    interests: List[str] = Field(..., description="List of user interests/tags", example=["tarih", "arkeoloji"])
    max_results: int = Field(default=5, description="Maximum number of recommendations", ge=1, le=20, example=5)
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "interests": ["tarih", "arkeoloji"],
                "max_results": 5
            }
        }

class RecommendationResponse(BaseModel):
    """Response model for recommendations"""
    recommendations: List[Destination] = Field(..., description="List of recommended destinations")
    user_id: str = Field(..., description="User identifier", example="user123")

class DocumentIngestRequest(BaseModel):
    """Request model for document ingestion"""
    title: str = Field(..., description="Document title", example="GAP Bölgesi Turizm Rehberi")
    content: str = Field(..., description="Document content/text", example="GAP bölgesi tarihi ve kültürel zenginlikleriyle...")
    type: str = Field(default="general", description="Document type: itinerary, route, destination_info, general", example="general")
    source: Optional[str] = Field(None, description="Document source URL or reference", example="https://example.com/guide")
    
    class Config:
        schema_extra = {
            "example": {
                "title": "GAP Bölgesi Turizm Rehberi",
                "content": "GAP bölgesi tarihi ve kültürel zenginlikleriyle ünlüdür...",
                "type": "general",
                "source": "https://example.com/guide"
            }
        }

class DocumentIngestResponse(BaseModel):
    """Response model for document ingestion"""
    document_id: int = Field(..., description="Created document ID", example=1)
    title: str = Field(..., description="Document title", example="GAP Bölgesi Turizm Rehberi")
    chunks_created: int = Field(..., description="Number of chunks created", example=15)
    status: str = Field(..., description="Ingestion status", example="success")

class DocumentSearchRequest(BaseModel):
    """Request model for document search"""
    query: str = Field(..., description="Search query", example="Göbeklitepe tarihi")
    top_k: int = Field(default=5, description="Number of results to return", ge=1, le=50, example=5)
    filter_type: Optional[str] = Field(None, description="Filter by document type", example="destination_info")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "Göbeklitepe tarihi",
                "top_k": 5,
                "filter_type": "destination_info"
            }
        }

class DocumentSearchResponse(BaseModel):
    """Response model for document search"""
    query: str = Field(..., description="Search query", example="Göbeklitepe tarihi")
    results: List[dict] = Field(..., description="Search results with scores")
    count: int = Field(..., description="Number of results returned", example=5)

class ChatHistoryItem(BaseModel):
    """Single chat history item"""
    message: str = Field(..., description="User message", example="Göbeklitepe nedir?")
    response: str = Field(..., description="AI response", example="Göbeklitepe dünyanın en eski...")
    timestamp: str = Field(..., description="Timestamp of the conversation", example="2024-01-15 10:30:00")

class ChatHistoryResponse(BaseModel):
    """Response model for chat history"""
    user_id: str = Field(..., description="User identifier", example="user123")
    history: List[ChatHistoryItem] = Field(..., description="List of chat history items")

class ItineraryRequest(BaseModel):
    """Request model for itinerary generation"""
    interests: List[str] = Field(..., description="User interests for itinerary", example=["tarih", "kültür"])
    duration: str = Field(default="3 gün", description="Trip duration", example="3 gün")
    locations: Optional[List[str]] = Field(None, description="Preferred locations/cities", example=["Şanlıurfa", "Mardin"])
    language: str = Field(default="tr", description="Response language", example="tr")
    
    class Config:
        schema_extra = {
            "example": {
                "interests": ["tarih", "kültür"],
                "duration": "3 gün",
                "locations": ["Şanlıurfa", "Mardin"],
                "language": "tr"
            }
        }

class ItineraryResponse(BaseModel):
    """Response model for itinerary generation"""
    itinerary_id: int = Field(..., description="Generated itinerary ID", example=1)
    itinerary: str = Field(..., description="Generated itinerary text", example="1. Gün: Şanlıurfa...")
    preferences: dict = Field(..., description="User preferences used", example={"interests": ["tarih"], "duration": "3 gün"})
    sources: List[str] = Field(default=[], description="Source documents used", example=[])

class RouteRequest(BaseModel):
    """Request model for route generation"""
    start_location: str = Field(..., description="Starting location", example="Şanlıurfa")
    end_location: str = Field(..., description="Ending location", example="Mardin")
    waypoints: Optional[List[str]] = Field(None, description="Optional waypoints", example=["Harran"])
    language: str = Field(default="tr", description="Response language", example="tr")
    
    class Config:
        schema_extra = {
            "example": {
                "start_location": "Şanlıurfa",
                "end_location": "Mardin",
                "waypoints": ["Harran"],
                "language": "tr"
            }
        }

class RouteResponse(BaseModel):
    """Response model for route generation"""
    route_id: int = Field(..., description="Generated route ID", example=1)
    route: str = Field(..., description="Route description", example="Şanlıurfa'dan Mardin'e...")
    start_location: str = Field(..., description="Starting location", example="Şanlıurfa")
    end_location: str = Field(..., description="Ending location", example="Mardin")
    waypoints: List[str] = Field(default=[], description="Waypoints", example=["Harran"])
    sources: List[str] = Field(default=[], description="Source documents used", example=[])

# Ollama LLM integration
def query_llm(prompt: str, model: str = "llama2"):
    """Query local Ollama instance"""
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            }
        )
        if response.status_code == 200:
            return response.json()['response']
        else:
            # Fallback to simple response if Ollama is not running
            return generate_simple_response(prompt)
    except:
        # Fallback response if Ollama is not available
        return generate_simple_response(prompt)

def generate_simple_response(prompt: str) -> str:
    """Simple rule-based fallback responses"""
    prompt_lower = prompt.lower()
    
    if "göbeklitepe" in prompt_lower:
        return "Göbeklitepe, dünyanın en eski tapınak kompleksidir. M.Ö. 10.000 yıllarına dayanan bu yapı, Şanlıurfa'da bulunur. UNESCO Dünya Mirası listesindedir."
    elif "otel" in prompt_lower or "konaklama" in prompt_lower:
        return "Bölgede birçok otel seçeneği bulunmaktadır. Şanlıurfa'da Hilton, Dedeman gibi büyük oteller var. Mardin'de butik taş evler popülerdir."
    elif "yemek" in prompt_lower or "ne yenir" in prompt_lower:
        return "GAP bölgesi zengin mutfağıyla ünlüdür. Urfa kebabı, çiğ köfte, Mardin'in kibe'si, Gaziantep baklavası mutlaka denenmeli lezzetlerdir."
    elif "ulaşım" in prompt_lower:
        return "Bölgeye havayolu ile Şanlıurfa, Gaziantep veya Diyarbakır havalimanlarından ulaşabilirsiniz. Şehirler arası otobüs seferleri de mevcuttur."
    else:
        return "GAP bölgesi, tarihi ve kültürel zenginlikleriyle sizi bekliyor. Size nasıl yardımcı olabilirim?"

# API Endpoints
@app.get(
    "/",
    tags=["Health"],
    summary="API Root",
    description="Get API information and version",
    response_description="API information"
)
def read_root():
    """
    Root endpoint that returns basic API information.
    
    Returns:
        - API name
        - API version
    """
    return {"message": "Mezopotamya.Travel API", "version": "1.0"}

@app.post(
    "/chat",
    tags=["Chat"],
    summary="AI Chat Assistant",
    description="""
    Chat with the AI tourism assistant. This endpoint uses RAG (Retrieval-Augmented Generation) 
    to provide context-aware responses about tourism in the GAP region.
    
    The assistant can:
    - Answer questions about destinations
    - Provide travel recommendations
    - Help with trip planning
    - Share information about local culture and history
    
    Supports Turkish (tr) and English (en) languages.
    """,
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": {
                        "response": "Göbeklitepe, dünyanın en eski tapınak kompleksidir. M.Ö. 10.000 yıllarına dayanan bu yapı, Şanlıurfa'da bulunur.",
                        "user_id": "user123"
                    }
                }
            }
        }
    }
)
def chat_endpoint(chat: ChatMessage):
    """
    AI Chat endpoint with RAG support.
    
    Processes user messages and returns AI-generated responses using:
    - RAG service (if available) for context-aware answers
    - Fallback to basic LLM if RAG is unavailable
    - Conversation history tracking
    
    The conversation is automatically saved to the database.
    """
    # Use RAG service if available, otherwise fallback to basic LLM
    if rag_service:
        try:
            result = rag_service.query(
                user_query=chat.message,
                language=chat.language,
                top_k=5
            )
            response = result['response']
        except Exception as e:
            print(f"RAG query error: {e}")
            # Fallback to basic LLM
            prompt = f"""Sen Mezopotamya bölgesi turizm asistanısın. Kullanıcı sorusu: {chat.message}
    
    Bölgedeki önemli yerler: Göbeklitepe, Balıklıgöl, Nemrut Dağı, Harran, Mardin, Hasankeyf.
    
    Kullanıcıya yardımcı ol, kısa ve öz cevap ver. Dil: {chat.language}"""
            response = query_llm(prompt)
    else:
        # Fallback to basic LLM
        prompt = f"""Sen Mezopotamya bölgesi turizm asistanısın. Kullanıcı sorusu: {chat.message}
    
    Bölgedeki önemli yerler: Göbeklitepe, Balıklıgöl, Nemrut Dağı, Harran, Mardin, Hasankeyf.
    
    Kullanıcıya yardımcı ol, kısa ve öz cevap ver. Dil: {chat.language}"""
        response = query_llm(prompt)
    
    # Save conversation
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO conversations (user_id, message, response) VALUES (?, ?, ?)',
              (chat.user_id, chat.message, response))
    conn.commit()
    conn.close()
    
    return {"response": response, "user_id": chat.user_id}

@app.get(
    "/destinations",
    tags=["Destinations"],
    summary="List Destinations",
    description="""
    Get a list of all tourism destinations in the GAP region.
    
    Can optionally filter by category:
    - Tarihi (Historical)
    - Dini (Religious)
    - Müze (Museum)
    - Doğa (Nature)
    - Kültür (Cultural)
    
    Returns destinations with their details including:
    - Name, description, category
    - Location, rating
    - Tags for filtering
    - Image URL
    """,
    response_model=List[Destination],
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "List of destinations",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 1,
                            "name": "Göbeklitepe",
                            "description": "Dünyanın en eski tapınak kompleksi",
                            "category": "Tarihi",
                            "location": "Şanlıurfa",
                            "rating": 4.8,
                            "image_url": "gobekli.jpg",
                            "tags": ["tarih", "arkeoloji", "unesco"]
                        }
                    ]
                }
            }
        }
    }
)
def get_destinations(
    category: Optional[str] = Field(None, description="Filter by category", example="Tarihi")
):
    """
    Get all destinations or filter by category.
    
    Args:
        category: Optional category filter (e.g., "Tarihi", "Dini", "Müze")
    
    Returns:
        List of destination objects
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    if category:
        c.execute('SELECT * FROM destinations WHERE category = ?', (category,))
    else:
        c.execute('SELECT * FROM destinations')
    
    destinations = []
    for row in c.fetchall():
        destinations.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "category": row[3],
            "location": row[4],
            "rating": row[5],
            "image_url": row[6],
            "tags": row[7].split(',') if row[7] else []
        })
    
    conn.close()
    return destinations

@app.post(
    "/recommendations",
    tags=["Recommendations"],
    summary="Get Personalized Recommendations",
    description="""
    Get AI-powered personalized travel recommendations based on user interests.
    
    Uses content-based filtering to match destinations with user interests.
    Returns destinations sorted by relevance and rating.
    
    Example interests:
    - tarih (history)
    - arkeoloji (archaeology)
    - din (religion)
    - kültür (culture)
    - doğa (nature)
    - mimari (architecture)
    """,
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "List of recommended destinations",
            "content": {
                "application/json": {
                    "example": {
                        "recommendations": [
                            {
                                "id": 1,
                                "name": "Göbeklitepe",
                                "description": "Dünyanın en eski tapınak kompleksi",
                                "category": "Tarihi",
                                "location": "Şanlıurfa",
                                "rating": 4.8,
                                "image_url": "gobekli.jpg",
                                "tags": ["tarih", "arkeoloji", "unesco"],
                                "match_score": 0.85
                            }
                        ],
                        "user_id": "user123"
                    }
                }
            }
        }
    }
)
def get_recommendations(request: RecommendationRequest):
    """
    Get personalized recommendations based on user interests.
    
    Uses content-based filtering to match destinations with user interests.
    Results are sorted by relevance and rating.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    # Simple content-based filtering
    interests_str = ','.join(request.interests)
    query = f"""
        SELECT * FROM destinations 
        WHERE tags LIKE '%{interests_str}%' 
        ORDER BY rating DESC 
        LIMIT {request.max_results}
    """
    
    c.execute(query)
    recommendations = []
    for row in c.fetchall():
        recommendations.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "category": row[3],
            "location": row[4],
            "rating": row[5],
            "image_url": row[6],
            "tags": row[7].split(',') if row[7] else [],
            "match_score": 0.85  # Simple static score for now
        })
    
    conn.close()
    return {"recommendations": recommendations, "user_id": request.user_id}

@app.get(
    "/destination/{destination_id}",
    tags=["Destinations"],
    summary="Get Destination Details",
    description="""
    Get detailed information about a specific destination by ID.
    
    Returns complete destination information including:
    - Full description
    - Category and location
    - User ratings
    - Tags and images
    """,
    response_model=Destination,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Destination details",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "name": "Göbeklitepe",
                        "description": "Dünyanın en eski tapınak kompleksi, 12.000 yıllık tarih",
                        "category": "Tarihi",
                        "location": "Şanlıurfa",
                        "rating": 4.8,
                        "image_url": "gobekli.jpg",
                        "tags": ["tarih", "arkeoloji", "unesco"]
                    }
                }
            }
        },
        404: {
            "description": "Destination not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Destination not found"}
                }
            }
        }
    }
)
def get_destination_detail(
    destination_id: int
):
    """
    Get detailed information about a specific destination.
    
    Args:
        destination_id: Unique destination identifier
    
    Returns:
        Destination object with all details
    
    Raises:
        HTTPException 404: If destination is not found
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM destinations WHERE id = ?', (destination_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Destination not found")
    
    return {
        "id": row[0],
        "name": row[1],
        "description": row[2],
        "category": row[3],
        "location": row[4],
        "rating": row[5],
        "image_url": row[6],
        "tags": row[7].split(',') if row[7] else []
    }

@app.get(
    "/chat/history/{user_id}",
    tags=["Chat"],
    summary="Get Chat History",
    description="""
    Retrieve chat history for a specific user.
    
    Returns recent conversations ordered by timestamp (most recent first).
    Useful for displaying conversation history in the UI or resuming previous sessions.
    """,
    response_model=ChatHistoryResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Chat history for the user",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "user123",
                        "history": [
                            {
                                "message": "Göbeklitepe nedir?",
                                "response": "Göbeklitepe dünyanın en eski tapınak kompleksidir...",
                                "timestamp": "2024-01-15 10:30:00"
                            }
                        ]
                    }
                }
            }
        }
    }
)
def get_chat_history(
    user_id: str = Field(..., description="User identifier", example="user123"),
    limit: int = Field(default=10, description="Maximum number of history items", ge=1, le=100, example=10)
):
    """
    Get chat history for a specific user.
    
    Args:
        user_id: Unique user identifier
        limit: Maximum number of history items to return (default: 10, max: 100)
    
    Returns:
        Chat history with messages, responses, and timestamps
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT message, response, timestamp 
        FROM conversations 
        WHERE user_id = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (user_id, limit))
    
    history = []
    for row in c.fetchall():
        history.append({
            "message": row[0],
            "response": row[1],
            "timestamp": row[2]
        })
    
    conn.close()
    return {"user_id": user_id, "history": history}

# RAG and Document Management Endpoints
@app.post(
    "/documents/ingest",
    tags=["Documents"],
    summary="Ingest Document for RAG",
    description="""
    Ingest and process a document for use with RAG (Retrieval-Augmented Generation).
    
    The document is:
    1. Chunked into smaller pieces for processing
    2. Embedded using sentence transformers
    3. Stored in the vector database (Qdrant)
    4. Saved to the SQLite database
    
    Document types:
    - `itinerary`: Travel itinerary documents
    - `route`: Route planning documents
    - `destination_info`: Destination information
    - `general`: General tourism content
    """,
    response_model=DocumentIngestResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Document successfully ingested",
            "content": {
                "application/json": {
                    "example": {
                        "document_id": 1,
                        "title": "GAP Bölgesi Turizm Rehberi",
                        "chunks_created": 15,
                        "status": "success"
                    }
                }
            }
        },
        503: {
            "description": "Document processing service unavailable",
            "content": {
                "application/json": {
                    "example": {"detail": "Document processing service unavailable"}
                }
            }
        },
        500: {
            "description": "Error ingesting document",
            "content": {
                "application/json": {
                    "example": {"detail": "Error ingesting document: <error message>"}
                }
            }
        }
    }
)
def ingest_document(doc: DocumentIngestRequest):
    """
    Ingest and process a document for RAG.
    
    Processes the document, creates embeddings, and stores in both
    the vector database and SQLite database.
    
    Requires:
    - Document processor service to be available
    - Vector store (Qdrant) to be connected
    """
    if not document_processor or not vector_store:
        raise HTTPException(status_code=503, detail="Document processing service unavailable")
    
    try:
        # Process document
        processed = document_processor.process_document(
            text=doc.content,
            title=doc.title,
            doc_type=doc.type,
            source=doc.source
        )
        
        # Generate embeddings for chunks
        chunks_with_embeddings = document_processor.embed_chunks(processed['chunks'])
        
        # Save document to database
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO documents (title, content, type, source)
            VALUES (?, ?, ?, ?)
        ''', (doc.title, doc.content, doc.type, doc.source))
        document_id = c.lastrowid
        
        # Save chunks to database and Qdrant
        vector_ids = []
        for chunk in chunks_with_embeddings:
            vector_id = f"{document_id}_{chunk['chunk_index']}"
            chunk['vector_id'] = vector_id
            vector_ids.append(vector_id)
            
            c.execute('''
                INSERT INTO document_chunks (document_id, chunk_text, chunk_index, vector_id)
                VALUES (?, ?, ?, ?)
            ''', (document_id, chunk['text'], chunk['chunk_index'], vector_id))
        
        conn.commit()
        conn.close()
        
        # Add to Qdrant
        vector_store.add_documents(chunks_with_embeddings, document_id=document_id)
        
        return {
            "document_id": document_id,
            "title": doc.title,
            "chunks_created": len(chunks_with_embeddings),
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting document: {str(e)}")

@app.post(
    "/documents/search",
    tags=["Documents"],
    summary="Semantic Document Search",
    description="""
    Perform semantic search in the document corpus using vector embeddings.
    
    Uses cosine similarity to find the most relevant documents matching the query.
    Results are ranked by relevance score.
    
    Optional filtering by document type:
    - itinerary
    - route
    - destination_info
    - general
    """,
    response_model=DocumentSearchResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Search results",
            "content": {
                "application/json": {
                    "example": {
                        "query": "Göbeklitepe tarihi",
                        "results": [
                            {
                                "document_id": 1,
                                "chunk_text": "Göbeklitepe tarihi hakkında bilgiler...",
                                "score": 0.95
                            }
                        ],
                        "count": 1
                    }
                }
            }
        },
        503: {
            "description": "Search service unavailable",
            "content": {
                "application/json": {
                    "example": {"detail": "Search service unavailable"}
                }
            }
        }
    }
)
def search_documents(search: DocumentSearchRequest):
    """
    Semantic search in document corpus using vector embeddings.
    
    Converts query to embedding and searches Qdrant vector database
    for similar document chunks.
    """
    if not document_processor or not vector_store:
        raise HTTPException(status_code=503, detail="Search service unavailable")
    
    try:
        # Generate query embedding
        query_embedding = document_processor.embed_text(search.query)
        
        # Build filter
        filter_dict = None
        if search.filter_type:
            filter_dict = {'type': search.filter_type}
        
        # Search Qdrant
        results = vector_store.search(
            query_vector=query_embedding,
            limit=search.top_k,
            filter_dict=filter_dict
        )
        
        return {
            "query": search.query,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching documents: {str(e)}")

@app.get(
    "/documents",
    tags=["Documents"],
    summary="List Ingested Documents",
    description="""
    List all ingested documents with pagination support.
    
    Returns document metadata including:
    - Document ID and title
    - Document type and source
    - Creation timestamp
    
    Supports pagination with limit and offset parameters.
    """,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "List of documents",
            "content": {
                "application/json": {
                    "example": {
                        "documents": [
                            {
                                "id": 1,
                                "title": "GAP Bölgesi Turizm Rehberi",
                                "type": "general",
                                "source": "https://example.com/guide",
                                "created_at": "2024-01-15 10:30:00"
                            }
                        ],
                        "count": 1
                    }
                }
            }
        }
    }
)
def list_documents(
    limit: int = Field(default=20, description="Maximum number of documents to return", ge=1, le=100, example=20),
    offset: int = Field(default=0, description="Number of documents to skip", ge=0, example=0)
):
    """
    List ingested documents with pagination.
    
    Args:
        limit: Maximum number of documents (default: 20, max: 100)
        offset: Number of documents to skip (default: 0)
    
    Returns:
        List of document metadata with pagination info
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT id, title, type, source, created_at
        FROM documents
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    
    documents = []
    for row in c.fetchall():
        documents.append({
            "id": row[0],
            "title": row[1],
            "type": row[2],
            "source": row[3],
            "created_at": row[4]
        })
    
    conn.close()
    return {"documents": documents, "count": len(documents)}

@app.delete(
    "/documents/{doc_id}",
    tags=["Documents"],
    summary="Delete Document",
    description="""
    Delete a document and all its associated data.
    
    This operation:
    1. Removes the document from Qdrant vector database
    2. Deletes document chunks from SQLite
    3. Removes the document record from the database
    
    **Warning**: This action cannot be undone.
    """,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Document deleted successfully",
            "content": {
                "application/json": {
                    "example": {
                        "document_id": 1,
                        "status": "deleted"
                    }
                }
            }
        },
        503: {
            "description": "Vector store unavailable",
            "content": {
                "application/json": {
                    "example": {"detail": "Vector store unavailable"}
                }
            }
        },
        500: {
            "description": "Error deleting document",
            "content": {
                "application/json": {
                    "example": {"detail": "Error deleting document: <error message>"}
                }
            }
        }
    }
)
def delete_document(
    doc_id: int
):
    """
    Delete a document and all its associated vectors.
    
    Removes the document from both vector database and SQLite.
    
    Args:
        doc_id: Document ID to delete
    
    Returns:
        Deletion status
    """
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store unavailable")
    
    try:
        # Delete from Qdrant
        vector_store.delete_document(doc_id)
        
        # Delete from database
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('DELETE FROM document_chunks WHERE document_id = ?', (doc_id,))
        c.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
        conn.commit()
        conn.close()
        
        return {"document_id": doc_id, "status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

@app.post(
    "/itineraries/generate",
    tags=["Itineraries"],
    summary="Generate Travel Itinerary",
    description="""
    Generate a personalized travel itinerary using RAG (Retrieval-Augmented Generation).
    
    Creates a detailed travel plan based on:
    - User interests (e.g., history, culture, nature)
    - Trip duration (e.g., "3 gün", "1 hafta")
    - Preferred locations/cities (optional)
    - Language preference
    
    The itinerary is generated using AI with context from ingested documents
    and saved to the database for future reference.
    """,
    response_model=ItineraryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Itinerary generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "itinerary_id": 1,
                        "itinerary": "1. Gün: Şanlıurfa - Göbeklitepe ziyareti...",
                        "preferences": {
                            "interests": ["tarih", "kültür"],
                            "duration": "3 gün",
                            "locations": ["Şanlıurfa", "Mardin"]
                        },
                        "sources": []
                    }
                }
            }
        },
        503: {
            "description": "RAG service unavailable",
            "content": {
                "application/json": {
                    "example": {"detail": "RAG service unavailable"}
                }
            }
        },
        500: {
            "description": "Error generating itinerary",
            "content": {
                "application/json": {
                    "example": {"detail": "Error generating itinerary: <error message>"}
                }
            }
        }
    }
)
def generate_itinerary(request: ItineraryRequest):
    """
    Generate tourism itinerary using RAG.
    
    Uses RAG service to create a personalized itinerary based on
    user preferences, interests, and duration.
    
    Requires:
    - RAG service to be available
    - Vector store (Qdrant) connection
    """
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG service unavailable")
    
    try:
        preferences = {
            'interests': request.interests,
            'duration': request.duration,
            'locations': request.locations or []
        }
        
        result = rag_service.generate_itinerary(
            preferences=preferences,
            language=request.language
        )
        
        # Save itinerary to database
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO itineraries (name, description, route_data)
            VALUES (?, ?, ?)
        ''', (
            f"Plan - {request.duration}",
            result['itinerary'],
            json.dumps(preferences)
        ))
        itinerary_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "itinerary_id": itinerary_id,
            "itinerary": result['itinerary'],
            "preferences": preferences,
            "sources": result.get('context_sources', [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating itinerary: {str(e)}")

@app.post(
    "/routes/generate",
    tags=["Routes"],
    summary="Generate Route Between Locations",
    description="""
    Generate a route between two locations using RAG.
    
    Creates a detailed route description including:
    - Start and end locations
    - Optional waypoints
    - Route information and recommendations
    - Points of interest along the way
    
    Uses RAG to provide context-aware route information based on
    ingested documents and destination data.
    """,
    response_model=RouteResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Route generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "route_id": 1,
                        "route": "Şanlıurfa'dan Mardin'e...",
                        "start_location": "Şanlıurfa",
                        "end_location": "Mardin",
                        "waypoints": ["Harran"],
                        "sources": []
                    }
                }
            }
        },
        503: {
            "description": "RAG service unavailable",
            "content": {
                "application/json": {
                    "example": {"detail": "RAG service unavailable"}
                }
            }
        },
        500: {
            "description": "Error generating route",
            "content": {
                "application/json": {
                    "example": {"detail": "Error generating route: <error message>"}
                }
            }
        }
    }
)
def generate_route(request: RouteRequest):
    """
    Generate route between locations using RAG.
    
    Creates a detailed route description with recommendations
    using RAG service and saved documents.
    
    Requires:
    - RAG service to be available
    - Vector store (Qdrant) connection
    """
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG service unavailable")
    
    try:
        result = rag_service.generate_route(
            start_location=request.start_location,
            end_location=request.end_location,
            waypoints=request.waypoints,
            language=request.language
        )
        
        # Save route to database
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO routes (name, waypoints, distance, duration)
            VALUES (?, ?, ?, ?)
        ''', (
            f"{request.start_location} - {request.end_location}",
            json.dumps(request.waypoints or []),
            0.0,  # Distance would be calculated separately
            "N/A"  # Duration would be calculated separately
        ))
        route_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "route_id": route_id,
            "route": result['route'],
            "start_location": result['start_location'],
            "end_location": result['end_location'],
            "waypoints": result['waypoints'],
            "sources": result.get('context_sources', [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating route: {str(e)}")

@app.get(
    "/qdrant/status",
    tags=["System"],
    summary="Qdrant Vector Database Status",
    description="""
    Get the connection status and collection information for Qdrant vector database.
    
    Returns:
    - Connection status (connected/disconnected)
    - Collection information (if connected)
    - Error message (if disconnected)
    
    Useful for monitoring and debugging vector database connectivity.
    """,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Qdrant status information",
            "content": {
                "application/json": {
                    "examples": {
                        "connected": {
                            "summary": "Qdrant is connected",
                            "value": {
                                "connected": True,
                                "collection": {
                                    "name": "mezopotamya_documents",
                                    "vectors_count": 150,
                                    "points_count": 150
                                }
                            }
                        },
                        "disconnected": {
                            "summary": "Qdrant is disconnected",
                            "value": {
                                "connected": False,
                                "message": "Vector store not initialized"
                            }
                        }
                    }
                }
            }
        }
    }
)
def get_qdrant_status():
    """
    Get Qdrant connection status and collection info.
    
    Returns:
        Connection status and collection information if connected,
        or error message if disconnected
    """
    if not vector_store:
        return {"connected": False, "message": "Vector store not initialized"}
    
    if not vector_store.is_connected():
        return {"connected": False, "message": "Cannot connect to Qdrant"}
    
    info = vector_store.get_collection_info()
    return {
        "connected": True,
        "collection": info
    }

if __name__ == "__main__":
    init_db()
    # Use PORT environment variable (for Render, Heroku, etc.) or default to 8000
    port = int(os.getenv("PORT", 8000))
    
    print("🚀 Mezopotamya.Travel API başlatılıyor...")
    print("📝 Veritabanı hazırlandı")
    print("🤖 LLM entegrasyonu: Ollama")
    if vector_store and vector_store.is_connected():
        print("🔍 Qdrant vektör veritabanı: Bağlı")
    else:
        print("⚠️ Qdrant vektör veritabanı: Bağlantı yok")
    if rag_service:
        print("🧠 RAG servisi: Aktif")
    else:
        print("⚠️ RAG servisi: Devre dışı")
    print(f"🌐 API: http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
