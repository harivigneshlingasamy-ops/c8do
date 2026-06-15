import os
import json
import hashlib
import threading
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

BLOCKCHAIN_FILE = "blockchain.txt"
MEMPOOL_FILE = "mempool.txt"
PEERS_FILE = "peers.txt"

# -- Validation ---------------------------------------------------------------

def is_valid_hash(h):
    """Must be exactly 64 lowercase hex characters (SHA-256)."""
    if not isinstance(h, str):
        return False
    if len(h) != 64:
        return False
    try:
        int(h, 16)
        return True
    except ValueError:
        return False

# -- Core helpers -------------------------------------------------------------

def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()

def ensure_file(path):
    if not os.path.exists(path):
        open(path, "w", encoding="utf-8").close()

def load_peers():
    ensure_file(PEERS_FILE)
    with open(PEERS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def save_peer(url):
    peers = load_peers()
    if url and url not in peers:
        with open(PEERS_FILE, "a", encoding="utf-8") as f:
            f.write(url + "\n")

def load_chain():
    ensure_file(BLOCKCHAIN_FILE)
    chain = []
    with open(BLOCKCHAIN_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chain.append(json.loads(line))
    return chain

def save_chain(chain):
    with open(BLOCKCHAIN_FILE, "w", encoding="utf-8") as f:
        for block in chain:
            f.write(json.dumps(block) + "\n")

def save_block(block):
    with open(BLOCKCHAIN_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(block) + "\n")

# -- Chain logic ---------------------------------------------------------------

def create_genesis():
    chain = load_chain()
    if len(chain) == 0:
        block = {
            "index": 0,
            "timestamp": str(datetime.utcnow()),
            "document_hash": "GENESIS",
            "previous_hash": "0"
        }
        block["block_hash"] = sha256(json.dumps(block, sort_keys=True))
        save_block(block)
        print("Genesis block created")

def add_hash(doc_hash):
    chain = load_chain()
    # Duplicate check
    for block in chain:
        if block["document_hash"] == doc_hash:
            return None, "duplicate"
    last = chain[-1]
    block = {
        "index": last["index"] + 1,
        "timestamp": str(datetime.utcnow()),
        "document_hash": doc_hash,
        "previous_hash": last["block_hash"]
    }
    block["block_hash"] = sha256(json.dumps(block, sort_keys=True))
    save_block(block)
    return block, None

def is_valid_chain(chain):
    """Verify chain integrity - each block must link to the previous."""
    for i in range(1, len(chain)):
        b = chain[i]
        prev = chain[i - 1]
        if b["previous_hash"] != prev["block_hash"]:
            return False
        check = {k: v for k, v in b.items() if k != "block_hash"}
        if sha256(json.dumps(check, sort_keys=True)) != b["block_hash"]:
            return False
    return True

# -- Peer sync -----------------------------------------------------------------

def sync_from_peers():
    """Longest valid chain wins."""
    peers = load_peers()
    current = load_chain()
    best_chain = current
    best_peer = None

    for peer in peers:
        try:
            print("Trying sync from:", peer)
            with urllib.request.urlopen(peer + "/chain", timeout=10) as r:
                peer_chain = json.loads(r.read().decode())
            if (len(peer_chain) > len(best_chain) and is_valid_chain(peer_chain)):
                best_chain = peer_chain
                best_peer = peer
        except Exception as e:
            print("Sync failed:", peer, e)

    if best_peer:
        save_chain(best_chain)
        print("Adopted longer chain from:", best_peer)

def broadcast_to_peers(doc_hash, origin=None):
    peers = load_peers()
    self_url = os.environ.get("SELF_URL", "").strip()
    for peer in peers:
        if peer == origin:
            continue
        try:
            payload = json.dumps({"hash": doc_hash, "from": self_url}).encode()
            req = urllib.request.Request(
                peer + "/upload",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=10)
            print("Broadcasted to:", peer)
        except Exception as e:
            print("Broadcast failed:", peer, e)

def fetch_from_peers(doc_hash):
    for peer in load_peers():
        try:
            with urllib.request.urlopen(peer + "/verify/" + doc_hash, timeout=10) as r:
                result = json.loads(r.read().decode())
            if result.get("verified"):
                return result
        except Exception:
            pass
    return None

# -- Background sync thread ----------------------------------------------------

def background_sync(interval=300):
    """Re-sync from peers every 5 minutes."""
    while True:
        threading.Event().wait(interval)
        try:
            sync_from_peers()
        except Exception as e:
            print("Background sync error:", e)

# -- HTTP Handler --------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # Suppress noisy request logs

    def send_json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/":
            self.send_json({"name": "C8DOC", "version": "2.0", "status": "running"})

        elif self.path == "/chain":
            self.send_json(load_chain())

        elif self.path == "/peers":
            self.send_json({"peers": load_peers()})

        elif self.path.startswith("/verify/"):
            doc_hash = self.path.split("/")[-1]
            for block in load_chain():
                if block["document_hash"] == doc_hash:
                    self.send_json({
                        "verified": True,
                        "block": block["index"],
                        "timestamp": block["timestamp"],
                        "source": "local"
                    })
                    return
            peer_result = fetch_from_peers(doc_hash)
            if peer_result:
                peer_result["source"] = "peer"
                self.send_json(peer_result)
                return
            self.send_json({"verified": False})

        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))

        if self.path == "/upload":
            doc_hash = body.get("hash", "").strip().lower()

            if not is_valid_hash(doc_hash):
                self.send_json({
                    "error": "invalid hash - must be a 64-character SHA-256 hex string"
                }, 400)
                return

            origin = body.get("from", None)

            with open(MEMPOOL_FILE, "a", encoding="utf-8") as f:
                f.write(doc_hash + "\n")

            block, err = add_hash(doc_hash)

            if err == "duplicate":
                self.send_json({"error": "hash already exists on chain"}, 409)
                return

            broadcast_to_peers(doc_hash, origin=origin)

            self.send_json({
                "success": True,
                "block": block["index"],
                "block_hash": block["block_hash"]
            })

        elif self.path == "/peers/register":
            url = body.get("url", "").strip()

            if not url:
                self.send_json({"error": "url missing"}, 400)
                return

            save_peer(url)

            # SELF_URL env var takes priority (set this in Railway variables)
            # Falls back to Host header so Railway can identify itself automatically
            self_url = os.environ.get("SELF_URL", "").strip()
            if not self_url:
                host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "")
                if host and "localhost" not in host and "127.0.0.1" not in host:
                    self_url = "https://" + host.split(",")[0].strip()

            if self_url and self_url != url:
                try:
                    payload = json.dumps({"url": self_url}).encode()
                    req = urllib.request.Request(
                        url + "/peers/register",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    urllib.request.urlopen(req, timeout=10)
                    print("Mutual register with:", url, "as", self_url)
                except Exception as e:
                    print("Mutual register failed:", url, e)

            self.send_json({"success": True, "peer": url})

        elif self.path == "/sync":
            # Manual trigger for sync
            threading.Thread(target=sync_from_peers, daemon=True).start()
            self.send_json({"success": True, "message": "sync started"})

        else:
            self.send_json({"error": "not found"}, 404)


# -- Main ----------------------------------------------------------------------

if __name__ == "__main__":
    ensure_file(MEMPOOL_FILE)
    ensure_file(PEERS_FILE)
    create_genesis()

    PORT = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", PORT), Handler)

    print("=" * 40)
    print(f"C8DOC Node v2.0 running on {PORT}")
    print("=" * 40)

    # Start server first so Railway marks us healthy immediately,
    # then sync and background tasks run in threads
    threading.Thread(target=sync_from_peers, daemon=True).start()
    threading.Thread(target=background_sync, args=(300,), daemon=True).start()

    server.serve_forever()
