import hashlib
import json
from time import time
from uuid import uuid4
from ecdsa import SigningKey, VerifyingKey
import requests

class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.load_chain()  # Load the chain from file on startup

        if not self.chain:  # If the chain is empty, create the genesis block
            self.new_block(previous_hash='1', proof=100)

    def register_node(self, address):
        """Add a new node to the network."""
        self.nodes.add(address)

    def valid_chain(self, chain):
        """Check if a blockchain is valid."""
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            # Check if hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False
            # Check if Proof of Work is correct
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False
            last_block = block
            current_index += 1
        return True

    def resolve_conflicts(self):
        """Consensus Algorithm: longest valid chain replaces our chain."""
        neighbors = self.nodes
        new_chain = None

        max_length = len(self.chain)

        for node in neighbors:
            # Replace this with actual network requests to get other nodes' chains
            length = len(node.chain)
            chain = node.chain

            if length > max_length and self.valid_chain(chain):
                max_length = length
                new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

        return False

    def new_block(self, proof, previous_hash=None):
        """Create a new Block in the Blockchain."""
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        self.current_transactions = []
        self.chain.append(block)
        self.save_chain()  # Save the chain after adding a new block
        return block

    def new_transaction(self, sender, recipient, amount, signature=None):
        """Add a new transaction with digital signature validation."""

        # Skip validation if this is a mining reward or signature is empty
        if sender == "0" or not signature:
            self.current_transactions.append({
                'sender': sender,
                'recipient': recipient,
                'amount': amount,
            })
            return self.last_block['index'] + 1

        # Validate signature for normal transactions
        sender_public_key = VerifyingKey.from_string(bytes.fromhex(sender))
        message = f'{sender}{recipient}{amount}'.encode()
        if not sender_public_key.verify(bytes.fromhex(signature), message):
            raise ValueError("Invalid transaction signature")

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        """Create a SHA-256 hash of a block."""
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        """Proof of Work Algorithm."""
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """Validate the proof: hash(last_proof, proof) must have 4 leading zeroes."""
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def save_chain(self):
        with open('blockchain\\templates\\blockchain.json', 'w') as f:
            json.dump(self.chain, f, indent=4)

    def load_chain(self):
        try:
            with open('blockchain\\templates\\blockchain.json', 'r') as f:
                self.chain = json.load(f)
        except FileNotFoundError:
            self.chain = []

    def broadcast_block(self, block):
        """Send the block to all registered nodes in the network."""
        for node in self.nodes:
            url = f"http://{node}/block/new"
            try:
                response = requests.post(url, json=block)
                if response.status_code != 200:
                    print(f"Failed to send block to {node}")
            except requests.exceptions.RequestException:
                print(f"Error sending block to {node}")


from flask import Flask, jsonify, request, render_template
from uuid import uuid4

app = Flask(__name__)

# Instantiate the blockchain
blockchain = Blockchain()

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

@app.route('/mine', methods=['GET'])
def mine():
    # Your mining logic here
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # Reward for finding the proof
    blockchain.new_transaction(
        sender="0",  # indicates this node has mined a new block
        recipient=node_identifier,  # your node address
        amount=1,  # reward amount
        signature=""  # no signature needed for mining rewards
    )

    # Forge the new Block by adding it to the chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)
    blockchain.broadcast_block(block)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response)


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    print("Received method:", request.method)  # This should print "POST"
    values = request.get_json()

    # Check that the required fields are in the POST'ed data
    required = ['sender_id', 'recipient_id', 'amount', 'signature']
    if not all(k in values for k in required):
        return jsonify({'message': 'Missing values'}), 400

    sender_public_key = get_user_public_key(values['sender_id']) # type: ignore
    recipient_public_key = get_user_public_key(values['recipient_id']) # type: ignore

    if not sender_public_key or not recipient_public_key:
        return jsonify({'message': 'Invalid user ID'}), 404

    # Process the transaction
    try:
        index = blockchain.new_transaction(sender_public_key, recipient_public_key, values['amount'], values['signature'])
        response = {'message': f'Transaction will be added to Block {index}'}
        return jsonify(response), 201
    except ValueError as e:
        return jsonify({'message': str(e)}), 400


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200

@app.route('/')
def home():
    return render_template('mine.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


from ecdsa import SigningKey

# Generate keys for a user
sk = SigningKey.generate()  # Private key
vk = sk.get_verifying_key()  # Public key

# Sign a message
message = b"Send 10 tokens to Bob"
signature = sk.sign(message)

# Verify the signature
assert vk.verify(signature, message)

# Send the public key and signature to the blockchain as part of the transaction
sender_public_key = vk.to_string().hex()
transaction_signature = signature.hex()


def resolve_conflicts(self):
    """Consensus Algorithm: longest valid chain replaces our chain."""
    neighbors = self.nodes
    new_chain = None
    max_length = len(self.chain)

    for node in neighbors:
        # Replace with network code to fetch other nodes' chains
        length = len(node.chain)
        chain = node.chain

        if length > max_length and self.valid_chain(chain):
            max_length = length
            new_chain = chain

    if new_chain:
        self.chain = new_chain
        return True

    return False
