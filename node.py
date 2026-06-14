import os
import json
import hashlib
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

BLOCKCHAIN_FILE = "blockchain.txt"
MEMPOOL_FILE = "mempool.txt"
PEERS_FILE = "peers.txt"


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def load_peers():

    if not os.path.exists(PEERS_FILE):

        open(
            PEERS_FILE,
            "w",
            encoding="utf-8"
        ).close()

    with open(
        PEERS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return [

            line.strip()

            for line in f

            if line.strip()

        ]


def save_peer(url):

    peers = load_peers()

    if url not in peers:

        with open(
            PEERS_FILE,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(url + "\n")


def load_chain():

    chain = []

    if not os.path.exists(BLOCKCHAIN_FILE):

        open(
            BLOCKCHAIN_FILE,
            "w"
        ).close()

    with open(
        BLOCKCHAIN_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:

            line = line.strip()

            if line:

                chain.append(
                    json.loads(line)
                )

    return chain


def save_block(block):

    with open(
        BLOCKCHAIN_FILE,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            json.dumps(block)
            + "\n"
        )


def create_genesis():

    chain = load_chain()

    if len(chain) == 0:

        block = {

            "index": 0,

            "timestamp":
            str(datetime.utcnow()),

            "document_hash":
            "GENESIS",

            "previous_hash":
            "0"

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

        "index":
        last["index"] + 1,

        "timestamp":
        str(datetime.utcnow()),

        "document_hash":
        doc_hash,

        "previous_hash":
        last["block_hash"]

    }

    block["block_hash"] = sha256(

        json.dumps(block)

    )

    save_block(block)

    return block


class Handler(BaseHTTPRequestHandler):

    def send_json(
        self,
        data,
        code=200
    ):

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

            self.send_json(

                load_chain()

            )

            return


        if self.path == "/peers":

            self.send_json({

                "peers":

                load_peers()

            })

            return


        if self.path.startswith("/verify/"):

            doc_hash = (

                self.path

                .split("/")[-1]

            )

            chain = load_chain()

            for block in chain:

                if (

                    block

                    ["document_hash"]

                    ==

                    doc_hash

                ):

                    self.send_json({

                        "verified":

                        True,

                        "block":

                        block["index"],

                        "timestamp":

                        block["timestamp"]

                    })

                    return

            self.send_json({

                "verified":

                False

            })

            return


        self.send_json({

            "error":

            "not found"

        },404)


    def do_POST(self):

        if self.path == "/upload":

            length = int(

                self.headers

                ["Content-Length"]

            )

            data = self.rfile.read(

                length

            )

            body = json.loads(data)

            doc_hash = body.get(

                "hash"

            )

            if not doc_hash:

                self.send_json({

                    "error":

                    "hash missing"

                },400)

                return

            with open(

                MEMPOOL_FILE,

                "a",

                encoding="utf-8"

            ) as f:

                f.write(

                    doc_hash

                    + "\n"

                )

            block = add_hash(

                doc_hash

            )

            self.send_json({

                "success":

                True,

                "block":

                block["index"],

                "block_hash":

                block["block_hash"]

            })

            return


        if self.path == "/peers/register":

            length = int(

                self.headers

                ["Content-Length"]

            )

            body = json.loads(

                self.rfile.read(

                    length

                )

            )

            url = body.get(

                "url"

            )

            if not url:

                self.send_json({

                    "error":

                    "url missing"

                },400)

                return

            save_peer(url)

            self.send_json({

                "success":

                True,

                "peer":

                url

            })

            return


        self.send_json({

            "error":

            "not found"

        },404)


if __name__ == "__main__":

    for f in [

        MEMPOOL_FILE,

        PEERS_FILE

    ]:

        if not os.path.exists(f):

            open(

                f,

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

        (

            "0.0.0.0",

            PORT

        ),

        Handler

    )

    print("="*30)

    print(

        f"C8DOC Node running on {PORT}"

    )

    print("="*30)

    server.serve_forever()
