"""
Flask Backend for Medical AI Chatbot - Production Ready
Optimized for Render deployment
"""
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os
import sys
import queue
import threading
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import your graph
from src.langgraph.graph import build_graph

# Initialize Flask app with static files
app = Flask(__name__, static_folder='static', static_url_path='')

# CORS Configuration
CORS(app, resources={
    r"/*": {
        "origins": "*",  # Change to specific domain in production
        "methods": ["GET", "POST", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Get port from environment (Render provides this)
PORT = int(os.environ.get('PORT', 8000))

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'chat_history.db')

def init_db():
    """Initialize SQLite database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                message TEXT NOT NULL,
                is_user BOOLEAN NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_chat_id 
            ON messages(chat_id)
        ''')

        # Add image_data column if it doesn't exist
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN image_data TEXT')
            print("⚙️ Migrated database: added image_data column")
        except sqlite3.OperationalError:
            # Column already exists
            pass

        conn.commit()
        conn.close()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database init error: {e}")

# Initialize on startup
print("🔄 Initializing...")
init_db()

print("🔄 Building LangGraph...")
try:
    graph = build_graph()
    print("✅ Graph ready")
except Exception as e:
    print(f"❌ Graph error: {e}")
    graph = None

# Serve frontend
@app.route('/')
def index():
    """Serve frontend index.html"""
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve static files (CSS, JS, etc)"""
    try:
        return send_from_directory('static', path)
    except:
        return send_from_directory('static', 'index.html')

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "message": "Medical AI API is running",
        "graph_loaded": graph is not None,
        "port": PORT
    })

@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint with SSE token and progress streaming"""
    try:
        data = request.json
        query = data.get('query', '').strip()
        chat_id = data.get('chat_id')
        image = data.get('image')  # Optional Base64 image data string

        if not query and not image:
            return jsonify({"error": "Query or image is required"}), 400

        if not graph:
            return jsonify({"error": "AI model not initialized"}), 500

        print(f"📨 Query: {query[:50]}...")

        # Fetch chat history for memory (last 5 messages)
        history = []
        if chat_id:
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT message, is_user 
                    FROM messages 
                    WHERE chat_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT 5
                ''', (chat_id,))
                rows = cursor.fetchall()
                conn.close()
                # Reverse to make it chronological (oldest to newest)
                history = [{"message": row["message"], "is_user": bool(row["is_user"])} for row in reversed(rows)]
                print(f"🧠 Loaded {len(history)} messages from history")
            except Exception as db_err:
                print(f"⚠️ Error loading chat history for memory: {db_err}")

        # Extract patient intake form data
        intake_data = data.get('intake_data')
        if intake_data:
            print(f"🩺 Patient Profile Context: {intake_data}")

        # Create thread-safe queue for events
        event_queue = queue.Queue()

        # Run through graph in a background thread
        initial_state = {
            "query": query,
            "tool": "",
            "results": [],
            "metadata": {
                "event_queue": event_queue,
                "intake_data": intake_data
            },
            "final_answer": "",
            "history": history,
            "image": image
        }

        def run_graph():
            try:
                result_state = graph.invoke(initial_state)
                event_queue.put({"type": "complete", "result": result_state})
            except Exception as ex:
                print(f"❌ Error in graph background thread: {ex}")
                event_queue.put({"type": "error", "message": str(ex)})

        thread = threading.Thread(target=run_graph)
        thread.start()

        def event_generator():
            while True:
                try:
                    # Wait up to 30s for the next token or status event
                    evt = event_queue.get(timeout=30.0)
                except queue.Empty:
                    # Keep-alive event to prevent browser/proxy timeouts
                    yield f"data: {json.dumps({'type': 'keep-alive'})}\n\n"
                    continue

                if evt["type"] == "complete":
                    res = evt["result"]
                    answer = res.get("final_answer", "Sorry, I couldn't generate a response.")
                    tool_used = res.get("tool", "unknown")
                    raw_results = res.get("results", [])

                    # Extract structured sources/citations from raw results
                    sources = []
                    seen_urls = set()
                    for r in raw_results:
                        if not isinstance(r, str):
                            continue
                        
                        # If PubMed paper
                        if "Source: PubMed" in r:
                            lines = r.split("\n")
                            title = lines[0].replace("**", "").strip()
                            link = ""
                            for line in lines:
                                if line.strip().startswith("Link:"):
                                    link = line.replace("Link:", "").strip()
                            if title and link and link not in seen_urls:
                                sources.append({"title": title, "url": link, "type": "pubmed"})
                                seen_urls.add(link)
                                
                        # If Europe PMC paper
                        elif "Authors:" in r and "Journal:" in r:
                            lines = r.split("\n")
                            title = lines[0].replace("**", "").strip()
                            link = ""
                            for line in lines:
                                if line.strip().startswith("PMID:"):
                                    pmid = line.replace("PMID:", "").strip()
                                    if pmid:
                                        link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                                elif line.strip().startswith("DOI:") and not link:
                                    doi = line.replace("DOI:", "").strip()
                                    if doi:
                                        link = f"https://doi.org/{doi}"
                            if title and link not in seen_urls:
                                sources.append({"title": title, "url": link or "#", "type": "research"})
                                seen_urls.add(link)
                                
                        # If WebSearch
                        elif "Source: http" in r or "Source:  http" in r:
                            lines = r.split("\n")
                            title = lines[0].replace("**", "").strip()
                            link = ""
                            for line in lines:
                                if line.strip().startswith("Source:"):
                                    link = line.replace("Source:", "").strip()
                            if title and link and link not in seen_urls:
                                sources.append({"title": title, "url": link, "type": "web"})
                                seen_urls.add(link)

                    # Save complete exchange to database
                    if chat_id:
                        save_message(chat_id, query, True, image)
                        save_message(chat_id, answer, False)
                        update_chat_title(chat_id, query)

                    # Yield final complete packet with structured sources
                    yield f"data: {json.dumps({'type': 'complete', 'answer': answer, 'tool_used': tool_used, 'sources': sources})}\n\n"
                    break

                elif evt["type"] == "error":
                    yield f"data: {json.dumps({'type': 'error', 'message': evt['message']})}\n\n"
                    break

                else:
                    # Forward progress status and tokens to the client
                    yield f"data: {json.dumps(evt)}\n\n"

        return Response(event_generator(), mimetype='text/event-stream')

    except Exception as e:
        print(f"❌ Chat error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/chats', methods=['GET'])
def get_chats():
    """Get all chat sessions"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, title, created_at, updated_at 
            FROM chats 
            ORDER BY updated_at DESC
            LIMIT 100
        ''')

        chats = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({"chats": chats})

    except Exception as e:
        print(f"❌ Get chats error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/chats/<chat_id>', methods=['GET'])
def get_chat(chat_id):
    """Get specific chat with messages"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM chats WHERE id = ?', (chat_id,))
        chat = cursor.fetchone()

        if not chat:
            conn.close()
            return jsonify({"error": "Chat not found"}), 404

        cursor.execute('''
            SELECT message, is_user, image_data, created_at 
            FROM messages 
            WHERE chat_id = ? 
            ORDER BY created_at ASC
        ''', (chat_id,))

        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({
            "chat": dict(chat),
            "messages": messages
        })

    except Exception as e:
        print(f"❌ Get chat error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/chats', methods=['POST'])
def create_chat():
    """Create new chat session"""
    try:
        data = request.json
        chat_id = data.get('chat_id')
        title = data.get('title', 'New Chat')

        if not chat_id:
            return jsonify({"error": "chat_id required"}), 400

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM chats WHERE id = ?', (chat_id,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"message": "Chat exists", "chat_id": chat_id})

        cursor.execute('INSERT INTO chats (id, title) VALUES (?, ?)', (chat_id, title))
        conn.commit()
        conn.close()

        return jsonify({"message": "Chat created", "chat_id": chat_id})

    except Exception as e:
        print(f"❌ Create chat error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/chats/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """Delete chat session"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM messages WHERE chat_id = ?', (chat_id,))
        cursor.execute('DELETE FROM chats WHERE id = ?', (chat_id,))

        conn.commit()
        conn.close()

        return jsonify({"message": "Chat deleted"})

    except Exception as e:
        print(f"❌ Delete chat error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/chats/clear', methods=['DELETE'])
def clear_all_chats():
    """Clear all chat history"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM messages')
        cursor.execute('DELETE FROM chats')

        conn.commit()
        conn.close()

        return jsonify({"message": "All chats cleared"})

    except Exception as e:
        print(f"❌ Clear chats error: {e}")
        return jsonify({"error": str(e)}), 500

def save_message(chat_id, message, is_user, image_data=None):
    """Save message to database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM chats WHERE id = ?', (chat_id,))
        if not cursor.fetchone():
            title = message[:50] + ('...' if len(message) > 50 else '')
            cursor.execute('INSERT INTO chats (id, title) VALUES (?, ?)', (chat_id, title))

        cursor.execute('UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE id = ?', (chat_id,))
        cursor.execute('INSERT INTO messages (chat_id, message, is_user, image_data) VALUES (?, ?, ?, ?)',
                      (chat_id, message, is_user, image_data))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Save message error: {e}")

def update_chat_title(chat_id, first_message):
    """Update chat title from first message"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ? AND is_user = 1', (chat_id,))
        count = cursor.fetchone()[0]

        if count == 1:
            title = first_message[:50] + ('...' if len(first_message) > 50 else '')
            cursor.execute('UPDATE chats SET title = ? WHERE id = ?', (title, chat_id))
            conn.commit()

        conn.close()
    except Exception as e:
        print(f"❌ Update title error: {e}")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🏥 Medical AI Chatbot")
    print("="*60)
    print(f"🌐 Server: http://0.0.0.0:{PORT}")
    print("="*60 + "\n")

    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=False,  # Set False for production
        threaded=True
    )