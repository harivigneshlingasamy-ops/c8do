import os
import json
import hashlib
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

BLOCKCHAIN_FILE = "blockchain.txt"
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


def load_chain():

    chain = []

    if not os.path.exists(BLOCKCHAIN_FILE):

        open(
            BLOCKCHAIN_FILE,
            "w",
            encoding="utf-8"
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

        save_chain([block])

        print(
            "Genesis created"
        )


def sync_from_peers():

    peers = load_peers()

    print("Peers:", peers)

    local_chain = load_chain()

    for peer in peers:

        try:

            print(
                "Trying:",
                peer
            )

            with urllib.request.urlopen(

                peer + "/chain",

                timeout=10

            ) as response:

                peer_chain = json.loads(

                    response.read()

                    .decode()

                )

            print(

                "Peer blocks:",

                len(peer_chain)

            )

            if len(peer_chain) > len(local_chain):

                save_chain(

                    peer_chain

                )

                print(

                    "Synced from",

                    peer

                )

                return

            else:

                print(

                    "Already latest"

                )

        except Exception as e:

            print(

                "Sync failed"

            )

            print(e)


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


        self.send_json({

            "error":

            "not found"

        },404)


if __name__ == "__main__":

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
