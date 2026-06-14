import os
import json
import hashlib
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

BLOCKCHAIN_FILE = "blockchain.txt"
MEMPOOL_FILE = "mempool.txt"


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def load_chain():
    chain = []

    if not os.path.exists(BLOCKCHAIN_FILE):
        open(BLOCKCHAIN_FILE, "w").close()

    with open(BLOCKCHAIN_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                chain.append(json.loads(line))

    return chain


def save_block(block):
    with open(BLOCKCHAIN_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(block) + "\n")


def create_genesis():
    chain = load_chain()

    if len(chain) == 0:

        block = {
            "index": 0,
            "timestamp": str(datetime.utcnow()),
            "document_hash": "GENESIS",
            "previous_hash": "0"
        }

        block["block_hash"] = sha256(
            json.dumps(block)
        )

        save_block(block)

        print("Genesis block created")


def add_hash(doc_hash):

    chain = load_chain()

    last = chain[-1]

    block = {
        "index": last["index"] + 1,
        "timestamp": str(datetime.utcnow()),
        "document_hash": doc_hash,
        "previous_hash": last["block_hash"]
    }

    block["block_hash"] = sha256(
        json.dumps(block)
    )

    save_block(block)

    return block


class Handler(BaseHTTPRequestHandler):

    def send_json(self, data, code=200):

        self.send_response(code)

        self.send_header(
            "Content-Type",
            "application/json"
        )

        self.end_headers()

        self.wfile.write(
            json.dumps(data).encode()
        )

    def do_GET(self):

        if self.path == "/":

            self.send_json({
                "name": "C8DOC",
                "status": "running"
            })

            return

        if self.path == "/chain":

            chain = load_chain()

            self.send_json(chain)

            return

        if self.path.startswith("/verify/"):

            doc_hash = self.path.split("/")[-1]

            chain = load_chain()

            for block in chain:

                if block["document_hash"] == doc_hash:

                    self.send_json({
                        "verified": True,
                        "block": block["index"],
                        "timestamp": block["timestamp"]
                    })

                    return

            self.send_json({
                "verified": False
            })

            return

        self.send_json({
            "error": "not found"
        }, 404)

    def do_POST(self):

        if self.path == "/upload":

            length = int(
                self.headers["Content-Length"]
            )

            data = self.rfile.read(length)

            body = json.loads(data)

            doc_hash = body.get("hash")

            if not doc_hash:

                self.send_json({
                    "error": "hash missing"
                }, 400)

                return

            with open(
                MEMPOOL_FILE,
                "a",
                encoding="utf-8"
            ) as f:

                f.write(doc_hash + "\n")

            block = add_hash(doc_hash)

            self.send_json({
                "success": True,
                "block": block["index"],
                "block_hash": block["block_hash"]
            })

            return

        self.send_json({
            "error": "not found"
        }, 404)


if __name__ == "__main__":

    if not os.path.exists(MEMPOOL_FILE):

        open(
            MEMPOOL_FILE,
            "w",
            encoding="utf-8"
        ).close()

    create_genesis()

    PORT = int(
        os.environ.get(
            "PORT",
            8080
        )
    )

    server = HTTPServer(
        ("0.0.0.0", PORT),
        Handler
    )

    print("==============================")
    print(f"C8DOC Node running on port {PORT}")
    print("==============================")

    server.serve_forever()
