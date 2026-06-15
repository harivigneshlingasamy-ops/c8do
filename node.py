import os
import json
import hashlib
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

BLOCKCHAIN_FILE = "blockchain.txt"
MEMPOOL_FILE = "mempool.txt"
PEERS_FILE = "peers.txt"


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def ensure_file(path):
    if not os.path.exists(path):
        open(path, "w", encoding="utf-8").close()


def load_peers():

    ensure_file(PEERS_FILE)

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

    ensure_file(BLOCKCHAIN_FILE)

    chain = []

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


def save_chain(chain):

    with open(

        BLOCKCHAIN_FILE,

        "w",

        encoding="utf-8"

    ) as f:

        for block in chain:

            f.write(

                json.dumps(block)

                + "\n"

            )


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

            json.dumps(

                block,

                sort_keys=True

            )

        )

        save_block(block)

        print(

            "Genesis block created"

        )


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

        json.dumps(

            block,

            sort_keys=True

        )

    )

    save_block(block)

    return block


def sync_from_peers():

    peers = load_peers()

    print("Peers:", peers)

    for peer in peers:

        try:

            print("Trying:", peer)

            with urllib.request.urlopen(
                peer + "/chain",
                timeout=10
            ) as response:

                text = response.read().decode()

                print("RAW RESPONSE:")

                print(text)

                peer_chain = json.loads(text)

            print(
                "Peer blocks:",
                len(peer_chain)
            )

            local_chain = load_chain()

            print(
                "Local blocks:",
                len(local_chain)
            )

            if len(peer_chain) > len(local_chain):

                save_chain(peer_chain)

                print(
                    "Synced from",
                    peer
                )

                return

            else:

                print(
                    "Local chain already up to date"
                )

        except Exception:

            import traceback

            print("====================")

            print("SYNC FAILED")

            print("Peer:", peer)

            traceback.print_exc()

            print("====================")


class Handler(

    BaseHTTPRequestHandler

):

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

            json.dumps(data)

            .encode()

        )


    def do_GET(self):

        if self.path == "/":

            self.send_json({

                "name":

                "C8DOC",

                "status":

                "running"

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


        if self.path.startswith(

            "/verify/"

        ):

            doc_hash = (

                self.path

                .split("/")[-1]

            )

            for block in load_chain():

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

            body = json.loads(

                self.rfile.read(

                    length

                )

            )

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

    ensure_file(

        MEMPOOL_FILE

    )

    ensure_file(

        PEERS_FILE

    )

    create_genesis()

    sync_from_peers()

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

    print("=" * 30)

    print(

        f"C8DOC Node running on {PORT}"

    )

    print("=" * 30)

    server.serve_forever()
