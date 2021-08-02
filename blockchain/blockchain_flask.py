from functools import wraps
from time import time
from typing import Optional

import jsonpickle as jspkl
import json

import requests
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import binascii
import Crypto
import Crypto.Random
from Crypto.PublicKey import RSA
from blockchain import Blockchain, MINING_SENDER, MINING_REWARD, REPUTATION_PENALTY, FALSE_SIGNATURE_GRAVITY, \
    VALIDATION_MERIT, INVALID_CHAIN_GRAVITY

# Instantiate the Node
app = Flask(__name__)
CORS(app)

# Initialize the blockchain variable to None until the user initializes the main wallet.
blockchain: Optional[Blockchain] = None


# JSONP decorator to support JSONP
def support_jsonp(f):
    """Require user authorization"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        callback = request.args.get('callback', False)
        if callback:
            content = str(callback) + '(' + json.dumps(dict(f(*args, **kwargs).json)) + ')'
            return app.response_class(content, mimetype='application/json')
        else:
            return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def index():
    if blockchain is not None:
        return render_template('./index.html')
    else:
        return 'Blockchain not initialized yet.', 400


@app.route('/init_blockchain', methods=['GET'])
@support_jsonp
def init_blockchain():
    global blockchain
    # RSA.importKey(binascii.unhexlify(prks.encode()))
    private_key_string = request.args.get('private_key')
    # Instantiate the Blockchain and the main wallet
    if private_key_string is None:
        random_gen = Crypto.Random.new().read
        private_key = RSA.generate(1024, random_gen)
    else:
        private_key = RSA.importKeybinascii.unhexlify(private_key_string)
    public_key = private_key.publickey()
    response = {
        'private_key': binascii.hexlify(private_key.exportKey(format='DER')).decode('ascii'),
        'public_key': binascii.hexlify(public_key.exportKey(format='DER')).decode('ascii')
    }
    if blockchain is None:
        blockchain = Blockchain(public_key=response['public_key'])
    # Format the JSONP response
    return jsonify(response)


@app.route('/configure')
def configure():
    if blockchain is not None:
        return render_template('./configure.html')
    else:
        return 'Blockchain not initialized yet.', 400


@app.route('/transactions/broadcast', methods=["POST"])
def broadcast_transaction():
    """
    Sends a new transaction in broadcast
    """
    if blockchain is not None:
        values = request.form

        # Check that the required fields are in the POST data
        required = ['sender_address', 'recipient_address', 'amount', 'signature', 'timestamp']
        if not all(k in values for k in required):
            return 'Missing values', 400

        # Create a new Transaction
        transaction_added = blockchain.add_pending_transaction(
            values['sender_address'], values['recipient_address'], values['amount'],
            values['signature'], values['timestamp']
        )

        if transaction_added:
            for node in blockchain.nodes:
                print('http://' + node + '/transactions/new_pending')
                try:
                    response_broadcast = requests.get('http://' + node + '/transactions/new_pending')
                except:
                    print("Node with url '" + node + "' isn't connected or doesn't exist anymore.")
                    continue  # skip the current iteration if we can't connect with the node

                if response_broadcast.status_code == 200:
                    print('http://' + node + '/transactions/new_pending completed successfully')
                else:
                    print('http://' + node + '/transactions/new_pending failed')

        response = {'message': 'Transaction broadcast completed'}
        return jsonify(response), 200
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


@app.route('/transactions/new_pending', methods=['POST'])
def new_pending_transaction():
    if blockchain is not None:
        values = request.form

        # Check that the required fields are in the POST data
        required = ['sender_address', 'recipient_address', 'amount', 'signature', 'timestamp']
        if not all(k in values for k in required):
            return 'Missing values', 400

        # Create a new Transaction
        transaction_added = blockchain.add_pending_transaction(
            values['sender_address'], values['recipient_address'], values['amount'],
            values['signature'], values['timestamp']
        )

        # Send in broadcast to all neighbours
        if transaction_added:
            for node in blockchain.nodes:
                print('http://' + node + '/transactions/new_pending')
                try:
                    response_broadcast = requests.get('http://' + node + '/transactions/new_pending')
                except:
                    print("Node with url '" + node + "' isn't connected or doesn't exist anymore.")
                    continue  # skip the current iteration if we can't connect with the node

                if response_broadcast.status_code == 200:
                    print('http://' + node + '/transactions/new_pending completed successfully')
                else:
                    print('http://' + node + '/transactions/new_pending failed')

        response = {'message': 'Pending transaction added successfully!'}
        return jsonify(response), 200
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    if blockchain is not None:
        values = request.form

        # Check that the required fields are in the POST data
        required = ['sender_address', 'recipient_address', 'amount', 'signature', 'timestamp']
        if not all(k in values for k in required):
            return 'Missing values', 400
        # Create a new Transaction
        transaction_result = blockchain.submit_transaction(
            values['sender_address'], values['recipient_address'], values['amount'],
            values['signature'], values['timestamp']
        )

        if not transaction_result:
            response = {'message': 'Invalid Transaction!'}
            return jsonify(response), 406
        else:
            response = {'message': 'Transaction will be added to Block ' + str(transaction_result)}
            return jsonify(response), 201
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


@app.route('/transactions/get', methods=['GET'])
def get_transactions():
    if blockchain is not None:
        # Get transactions from transactions pool
        transactions = blockchain.transactions

        response = {'transactions': transactions}
        return jsonify(response), 200
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


@app.route('/chain', methods=['GET'])
def full_chain():
    if blockchain is not None:
        response = {
            'chain': blockchain.chain,
            'length': len(blockchain.chain),
        }
        return jsonify(response), 200
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


@app.route('/candidates', methods=['GET'])
def candidates():
    if blockchain is not None:
        response = {
            'candidates': {
                cand_url: jspkl.dumps(blockchain.candidates[cand_url]) for cand_url in blockchain.candidates
            }
        }
        return jsonify(response), 200
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


@app.route('/update_candidates', methods=['GET'])
def update_candidates():
    if blockchain is not None:
        new_candidates = blockchain.get_candidates_from_nodes()
        for candidate_address in new_candidates:
            blockchain.candidates.put(candidate_address, new_candidates[candidate_address])
        response = {
            'message': "Candidates updated successfully!"
        }
        return jsonify(response), 200
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


@app.route('/reputation/neighbourhood_research', methods=['GET'])
def neighbourhood_search_for_reputation():
    """
    This function will return the reputation of the given node, if it is included in the neighbourhood
    """
    if blockchain is not None:
        reputation: float = -1
        node_url = request.args.get('node_url')
        if node_url in blockchain.nodes:
            reputation = blockchain.nodes[node_url].reputation
        response = {
            'reputation': reputation
        }
        return jsonify(response), 200
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


@app.route('/reputation/broadcast_research', methods=['GET'])
def broadcast_search_for_reputation():
    """
    This function will return the reputation of the given node, broadcasting the research to all the neighbours
    """
    if blockchain is not None:
        reputation: float = -1

        # In future, we could save the original sender address, in order to send the response directly to him,
        # making a point to point response (O(n) messages in total) instead of a double broadcast response
        # (O(n^2)? messages in total)
        node_url = request.args.get('node_url')
        request_id = request.args.get('request_id')

        # If we don't have received the request yet,  or send
        # the request in broadcast otherwise
        if request_id not in blockchain.reputation_requests:

            # Return the node reputation if we find it in our neighbourhood
            if node_url in blockchain.nodes:
                reputation = blockchain.nodes[node_url].reputation

            # Or send the request in broadcast otherwise
            if reputation == -1:
                for node_url in blockchain.nodes:
                    try:
                        resp = requests.get(
                            'http://' + node_url + '/reputation/broadcast_research?' + 'node_url=' + node_url
                            + '&request_id=' + request_id)
                    except:
                        print("Node with url '" + node_url + "' isn't connected or doesn't exist anymore.")
                        continue  # skip the current iteration if we can't connect with the node
                    reputation = resp.json()['reputation']

                    # Stop the broadcasting if we find the reputation
                    if reputation != -1:
                        break

        response = {
            'reputation': reputation
        }
        return jsonify(response), 200
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


@app.route('/reputation/change_reputation', methods=['GET'])
def change_reputation():
    """
    Changes the reputation of the given address, if it is our neighbour, and broadcasts a message to all our
    neighbours, to notify them of the wrong or the correct attitude of the address.
    """
    if blockchain is not None:
        request_id = request.args.get('request_id')
        node_address = request.args.get('node_address')
        change_lvl: int = int(request.args.get('change_lvl'))

        if request_id not in blockchain.reputation_requests:

            if not FALSE_SIGNATURE_GRAVITY <= change_lvl <= VALIDATION_MERIT:
                return 'Wrong given change level', 400

            # Diminish the reputation of the address if it is our neighbour
            if node_address in blockchain.addresses:
                node_url = blockchain.addresses[node_address]
                if blockchain.nodes[node_url].reputation + change_lvl * REPUTATION_PENALTY >= 0:
                    blockchain.nodes[node_url].reputation += change_lvl * REPUTATION_PENALTY
                else:
                    blockchain.nodes[node_url].reputation = 0

            # Broadcast the message to all our neighbours
            for node_url in blockchain.nodes:
                print('http://' + node_url + '/reputation/change_reputation')
                try:
                    requests.get(
                        'http://' + node_url + '/reputation/change_reputation?' + 'node_url=' + node_url +
                        '&request_id=' + request_id
                    )
                except:
                    print("Node with url '" + node_url + "' isn't connected or doesn't exist anymore.")
                    continue  # skip the current iteration if we can't connect with the node

                print('http://' + node_url + '/reputation/change_reputation completed successfully')

            success = True
            message = 'Node ' + node_address + ' reputation changed!'

        else:
            success = False
            message = 'Node ' + node_address + ' reputation already changed!'

        response = {
            'success': success,
            'message': message
        }
        return jsonify(response), 200
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


@app.route('/mine', methods=['GET'])
def mine():
    """
    This function will try to mine a new block by joining the negotiation process.
    If we are the winner address, we will check the negotiation winner of the neighbour nodes, to grant that no node
    has a different winner address.
    """
    if blockchain is not None:
        last_block = blockchain.chain[-1]

        # Candidate to the negotiation and execute the negotiation algorithm
        winner = blockchain.proof_of_negotiation()

        # If we won the negotiation, then start validating the block
        if winner.address != blockchain.node_id:
            return

        # We must receive a reward for winning the reputation.
        blockchain.submit_transaction(
            sender_address=MINING_SENDER, recipient_address=blockchain.node_id,
            value=MINING_REWARD, signature="", timestamp=time()
        )

        # Forge the new Block by adding it to the chain
        previous_hash = blockchain.hash(last_block)
        block = blockchain.create_block(previous_hash, blockchain.node_id)

        # Broadcast the new chain
        print("Sending the new chain in broadcast...")
        for node_url in blockchain.nodes:
            print('http://' + node_url + '/nodes/resolve')
            try:
                requests.get('http://' + node_url + '/resolve')
            except:
                print("Node with url '" + node_url + "' isn't connected or doesn't exist anymore.")
        print("New chain broadcast completed successfully!")

        # Check if the validator of the last block is the same as the neighbour nodes
        for node_url in blockchain.nodes:
            print('http://' + node_url + '/nodes/resolve')
            try:
                neighbour_chain = requests.get('http://' + node_url + '/chain').json()["chain"]
            except:
                print("Node with url '" + node_url + "' isn't connected or doesn't exist anymore.")
                continue  # skip the current iteration if we can't connect with the node
            validator_address = neighbour_chain[-1]["validator"]
            # If the address of the validator of the last block is different from the winner address, decrease the
            # reputation of the neighbour, because the node tried to put false negotiation winner in the last block
            if validator_address != winner.address:
                blockchain.change_reputation(
                    node_address=blockchain.nodes[node_url].address,
                    change_lvl=INVALID_CHAIN_GRAVITY
                )

        response = {
            'message': "New Block Forged",
            'block_number': block['block_number'],
            'transactions': block['transactions'],
            'validator': block['validator'],
            'previous_hash': block['previous_hash']
        }
        return jsonify(response), 200
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    if blockchain is not None:
        # Nodes will be passed as a ',' separated list, in which each element will be like '<node_url>-<node_address>'
        values = request.form
        node_strings = values.get('nodes').replace(" ", "").split(',')

        if node_strings is None:
            return "Error: Please supply a valid list of nodes", 400

        for node_string in node_strings:
            node_url, node_address = node_string.split('-')
            blockchain.register_node(node_url, node_address)

        response = {
            'message': 'New nodes have been added',
            'total_nodes': [node for node in blockchain.nodes],
        }
        return jsonify(response), 201
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    if blockchain is not None:
        replaced = blockchain.resolve_conflicts()

        if replaced:
            # Broadcast the new chain
            print("Sending the new chain in broadcast...")
            for node_url in blockchain.nodes:
                print('http://' + node_url + '/nodes/resolve')
                try:
                    requests.get('http://' + node_url + '/resolve')
                except:
                    print("Node with url '" + node_url + "' isn't connected or doesn't exist anymore.")
            print("New chain broadcast completed successfully!")

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
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


@app.route('/nodes/get', methods=['GET'])
def get_nodes():
    if blockchain is not None:
        response = {
            'nodes': [jspkl.dumps(blockchain.nodes[node]) for node in blockchain.nodes]
        }
        return jsonify(response), 200
    else:
        response = {'message': 'Blockchain hasn\'t been initialized yet!'}
        return jsonify(response), 400


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='127.0.0.1', port=port)
