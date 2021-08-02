"""
title           : blockchain.py
description     : A blockchain implemenation
author          : Adil Moujahid
date_created    : 20180212
date_modified   : 20180309
version         : 0.5
usage           : python blockchain.py
                  python blockchain.py -p 5000
                  python blockchain.py --port 5000
python_version  : 3.6.1
Comments        : The blockchain implementation is mostly based on [1].
                  I made a few modifications to the original code in order to add RSA encryption to the transactions
                  based on [2], changed the proof of work algorithm, and added some Flask routes to interact with the
                  blockchain from the dashboards
References      : [1] https://github.com/dvf/blockchain/blob/master/blockchain.py
                  [2] https://github.com/julienr/ipynb_playground/blob/master/bitcoin/dumbcoin/dumbcoin.ipynb
"""

from collections import OrderedDict

import binascii
import random
from typing import final, Optional
from typing import List

import Crypto
import Crypto.Random
from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4
from pytreemap import TreeMap
import jsonpickle as jspkl

import requests

import negotiation.negotiation as ng
import node as nd

MINING_SENDER: final = "THE BLOCKCHAIN"
REAL_CANDIDATES_NUMBER: final = 4
MINING_REWARD: final = 1
MINING_DIFFICULTY: final = 2
INITIAL_SEED: final = 2458912
MAX_SEED: final = 2000000
REPUTATION_PENALTY: final = 0.2
INSUFFICIENT_BALANCE_GRAVITY: final = -1
FALSE_SIGNATURE_GRAVITY: final = -3
INVALID_CHAIN_GRAVITY: final = -2
VALIDATION_MERIT: final = 1
MINIMUM_REPUTATION: final = 0.1
DEFAULT_REPUTATION: final = 1
MIN_GAIN: final = 0.5
MAX_GAIN: final = 2
MIN_OPERATOR: final = 0
MAX_OPERATOR: final = 1


class Blockchain:

    def __init__(self, public_key: str):
        random.seed(INITIAL_SEED)  # Set the random number generator initial seed, for the random selection of nodes
        self.pending_transactions: dict = {}  # Pending transactions, to be verified
        self.transactions: list = []  # Transactions to be added to the next block, already verified
        self.candidates: TreeMap = TreeMap()  # Validator candidates for the negotiation
        self.chain: list = []  # The chain of validated blocks
        self.nodes = {}  # url->Node mapping neighbours of our node in the blockchain network
        self.addresses = {}  # blockchainAddress->url mapping of our node's neighbours in the blockchain network
        self.reputation_requests = OrderedDict()  # Reputation-related requests, to avoid infinite broadcast loops-


        # TODO: replace with the node blockchain address
        self.node_id = public_key  # Main blockchain address of the node

        # Create genesis block
        self.create_block(previous_hash='00', validator_address=None, negotiation_price=None)

    def register_node(self, node_url, node_address):
        """blockchain.py
            Add a new node to the list of nodes, calculating his reputation too.

            :param node_url: the url of the node to register
            :param node_address: the address of the node to register
        """
        # Checking node_url has valid format
        parsed_url = urlparse(node_url)

        if parsed_url.netloc or parsed_url.path:
            # Accepts an URL with or without scheme like '192.168.0.5:5000'.

            # If the node is already our neighbour but has changed url, update it, otherwise calculate his reputation.
            if node_address not in self.addresses:
                node_reputation: float = self.__search_node_reputation(node_url)
            else:
                node_reputation: float = self.nodes[self.addresses[node_address]].reputation
                del self.nodes[self.addresses[node_address]]

            new_node: nd.Node = nd.Node(node_url, node_reputation, node_address)
            self.nodes[new_node.url] = new_node
            self.addresses[node_address] = node_url
        else:
            raise ValueError('Invalid URL')

    def __search_node_reputation(self, node_url) -> float:
        """
        Returns the reputation of the node with the given url, asking it to our neighbours, and broadcasting the request
        if they don't know it.
        The request id generated will be in the format: <node_address><timestamp>RS.

        :param node_url: the url of the node which we want to get the reputation
        :return: the reputation of the node with the given url, if it exists, 1 otherwise.
        """
        reputation: float = -1
        request_id: str = str(self.node_id) + str(time()) + "RS"

        for neighbour_url in self.nodes:
            try:
                resp = requests.get('http://' + neighbour_url + '/reputation/neighbourhood_research?' + 'node_url='
                                    + node_url)
                reputation = resp.json()['reputation']
            except:
                print("Node with url '" + neighbour_url + "' isn't connected or doesn't exist anymore.")

            # Stop the broadcasting if we find the reputation
            if reputation != -1:
                break

        for neighbour_url in self.nodes:
            try:
                resp = requests.get('http://' + neighbour_url + '/reputation/broadcast_research?' + 'node_url=' + node_url
                                    + '&request_id=' + request_id)
                reputation = resp.json()['reputation']
            except:
                print("Node with url '" + neighbour_url + "' isn't connected or doesn't exist anymore.")

            # Stop the broadcasting if we find the reputation
            if reputation != -1:
                break

        # If the node is not found (reputation is -1), then it either doesn't exist, or it's a node new to the network,
        # so we set his reputation to 1, the default value
        if reputation == -1:
            reputation = 1
        return reputation

    def change_reputation(self, node_address, change_lvl: int, no_broadcast_flag: bool = False):
        """
        Updates the reputation of the given address, if it is our neighbour, and sends a broadcast request to notify
        them of the wrong or correct behaviour of the address, if no_broadcast_flag is false.
        The new reputation r', given the old reputation r, is calculated by the following formula:
        r' = r + change_lvl.
        The request id generated will be in the format: <node_address><timestamp>RD.

        :param node_address: the address of the node to change the reputation
        :param change_lvl: the level of the reputation change (may be positive or negative depending on the behaviour)
        :param no_broadcast_flag: false by default, if
                                  true, the message of the reputation change wont be sent in broadcast
                                  (intended to be used in when
        """
        request_id = str(self.node_id) + str(time()) + "RC"
        node_address = node_address
        change_lvl: int = change_lvl

        if request_id not in self.reputation_requests:

            if change_lvl <= 0:
                return 'Wrong given gravity level', 400

            # Diminish the reputation of the address if it is our neighbour
            if node_address in self.addresses:
                node_url = self.addresses[node_address]

                if self.nodes[node_url].reputation - change_lvl*REPUTATION_PENALTY >= 0:
                    self.nodes[node_url].reputation -= change_lvl * REPUTATION_PENALTY
                else:
                    self.nodes[node_url].reputation = 0

            # Broadcast the message to all our neighbours
            for node_url in self.nodes:
                print('http://' + node_url + '/reputation/change_reputation')
                try:
                    requests.get(
                        'http://' + node_url + '/reputation/change_reputation?' + 'node_url=' + node_url + '&request_id='
                        + request_id
                    )

                    print('http://' + node_url + '/reputation/change_reputation completed successfully')
                except:
                    print("Node with url '" + node_url + "' isn't connected or doesn't exist anymore.")

    def get_node_balance(self, node_address) -> float:
        """
        Returns the balance of the node with the given url.

        :param node_address: the blockchain address of the node to calculate the balance
        :return: the balance of the node
        """
        # This will be implemented with Merkel Trees in the future
        balance = 0
        for block in self.chain:
            transactions = block["transactions"]
            for transaction in transactions:
                if transaction['recipient_address'] == node_address:
                    balance += transaction["value"]
                elif transaction['sender_address'] == node_address:
                    balance -= transaction['value']
        return balance

    def verify_transaction_signature(self, sender_address, signature, transaction):
        """
        Check that the provided signature corresponds to transaction
        signed by the public key (sender_address)
        """
        public_key = RSA.importKey(binascii.unhexlify(sender_address))
        verifier = PKCS1_v1_5.new(public_key)
        h = SHA.new(str(transaction).encode('utf8'))
        return verifier.verify(h, binascii.unhexlify(signature))

    def add_pending_transaction(self, sender_address, recipient_address, value, signature, timestamp) -> bool:
        """
        Adds a transaction to the pending transaction dictionary.

        :param sender_address: the address of the sender
        :param recipient_address: the address of the recipient
        :param value: the value of the transaction
        :param signature: the signature of the transaction, to be verified
        :param timestamp: the time in which the transaction was created
        :return: True if the transaction is added transaction dictionary, False if it was already added previously.
        """
        transaction = OrderedDict({
            'sender_address': sender_address,
            'recipient_address': recipient_address,
            'value': value,
            'timestamp': timestamp,
            'signature': signature
        })
        if Blockchain.transaction_key(transaction) in self.pending_transactions:
            return False
        else:
            self.pending_transactions.update({Blockchain.transaction_key(transaction): transaction})
            return True

    def submit_transaction(self, sender_address, recipient_address, value, signature, timestamp):
        """
        Add a transaction to transactions array if the signature verified and the balance of the sender is enough.
        """
        transaction = OrderedDict({
            'sender_address': sender_address,
            'recipient_address': recipient_address,
            'timestamp': timestamp,
            'value': value
        })

        # Reward for mining a block
        if sender_address == MINING_SENDER:
            self.transactions.append(transaction)
            return len(self.chain) + 1
        # Manages transactions from wallet to another wallet
        else:
            # If the balance is not sufficient to do the transaction, we diminish the reputation of the sender address,
            # if the signature is verified
            transaction_verification = self.verify_transaction_signature(sender_address, signature, transaction)
            if self.get_node_balance(sender_address) < value and transaction_verification:
                self.change_reputation(sender_address, INSUFFICIENT_BALANCE_GRAVITY)

            elif transaction_verification:
                self.transactions.append(transaction)
                return len(self.chain) + 1
            else:
                # TOCHECK: if the transaction is invalid, we diminish the reputation of the recipient address, who sent
                # the false transaction (we need to do further research to verify the "fairness" of this aspect)
                self.change_reputation(recipient_address, FALSE_SIGNATURE_GRAVITY)
            return False

    def create_block(self, previous_hash, validator_address=None, negotiation_price=None):
        """
        Add a block of pending transactions to the blockchain, if they are valid
        """

        # Add all the valid transactions to the valid transaction array
        for pending_transaction in self.pending_transactions.values():
            self.submit_transaction(
                pending_transaction["sender_address"],
                pending_transaction["recipient_address"],
                pending_transaction["value"],
                pending_transaction["signature"],
                pending_transaction["timestamp"]
            )

        # Forge the new block with the valid transactions
        block = {'block_number': len(self.chain) + 1,
                 'timestamp': time(),
                 'transactions': self.transactions,
                 'random_factor': random.randint(0, MAX_SEED),  # store the rand factor in the block to improve decentr.
                 'validator': validator_address,  # address of the validator
                 'negotiation_price': negotiation_price,  # the selling price of the validation right
                 'previous_hash': previous_hash
                 }

        # Reset the current list of transactions
        self.transactions = []

        self.chain.append(block)
        return block

    def hash(self, block):
        """
        Create a SHA-256 hash of a block
        """
        # We must make sure that the Dictionary is Ordered, or we'll have inconsistent hashes
        block_string = json.dumps(block, sort_keys=True).encode()

        return hashlib.sha256(block_string).hexdigest()

    @staticmethod
    def transaction_key(transaction) -> str:
        """
        Computes the key of a transaction, composed by the sender, receiver and timestamp, separated by ','
        """
        k = transaction['sender_address'] + ',' + transaction['recipient_address'] + ',' + str(transaction['timestamp'])
        return k

    def valid_chain(self, chain):
        """
        check if a blockchain is valid
        """
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            # print(last_block)
            # print(block)
            # print("\n-----------\n")
            # Check that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # TODO: add control on block validator (maybe with beacon nodes)
            #  request to verify the validator existence and reputation

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        Resolve conflicts between blockchain's nodes
        by replacing our chain with the longest one in the network.
        """
        neighbours = self.nodes
        new_chain = None

        # We're only looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in our network
        for node_url in neighbours:
            print('http://' + node_url + '/chain')
            try:
                response = requests.get('http://' + node_url + '/chain')
            except:
                print("Node with url '" + node_url + "' isn't connected or doesn't exist anymore.")
                continue  # Skip the current iteration if we can't connect with the node

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                valid_chain_flag = self.valid_chain(chain)

                # If the received chain is not valid, we diminish the reputation of the sender node
                if not valid_chain_flag:
                    self.change_reputation(self.nodes[node_url].address, INVALID_CHAIN_GRAVITY)

                if length > max_length and valid_chain_flag:
                    max_length = length
                    new_chain = chain

        # Replace our chain if we discovered a new, valid chain longer than ours,
        # and increase the reputation of the validator (the no_broadcast_flag is true be because the validator already
        # notifies his neighbours of the validation)
        if new_chain:
            self.chain = new_chain
            validator_address = self.chain[-1]["validator"]
            self.change_reputation(
                node_address=validator_address,
                change_lvl=VALIDATION_MERIT,
                no_broadcast_flag=True
            )
            return True

        return False

    def get_candidates_from_nodes(self) -> dict:
        # Dictionary to contain all the new candidates to the negotiation
        new_candidates = {}
        neighbours = self.nodes

        # For each node, send request to get the candidate list from the node and add it to the dictionary,
        # if their reputation is higher than the minimum, and if their balance is higher than the minimum,
        # in other words, if their balance + the base reward from COINBASE is higher than the previous block cost
        for node in neighbours:
            if neighbours[node].reputation >= MINIMUM_REPUTATION:
                print('Requesting http://' + node + '/candidates')
                try:
                    response = requests.get('http://' + node + '/candidates')
                except:
                    print("Node with url '" + node + "' isn't connected or doesn't exist anymore.")
                    continue  # skip the current iteration if we can't connect with the node

                # Pick the candidates from the response
                resp_candidates: dict = response.json()["candidates"]

                # Check if the candidate map contains MYSELF_STRING, and replace it with the ip of the sender
                try:
                    sender_account = resp_candidates["myself"]
                    new_candidates[node] = sender_account
                    # Overwrite their reputation/address to prevent false addresses/reputations (trolling/scam)
                    resp_candidates[node].reputation = self.nodes[node].reputation
                    resp_candidates[node].address = self.nodes[node].address
                    del resp_candidates["myself"]
                except KeyError:
                    pass

                # For all the candidates received from the neighbour
                for candidate_url in resp_candidates:
                    # De-jsonify the candidate to get the Node instance associated with the candidate
                    candidate: nd.Node = jspkl.loads(resp_candidates[candidate_url])

                    # Select the candidate only if their balance is enough (last block cost + MINING_REWARD)
                    if self.get_node_balance(candidate.address) + MINING_REWARD > self.chain[-1]["negotiation_price"]:
                        new_candidates.update({candidate_url: candidate})

        return new_candidates

    def proof_of_negotiation(self) -> nd.Node:
        print("Getting valid chain...")
        if self.resolve_conflicts():
            print('Our chain was replaced.')
        else:
            print('Our chain is authoritative.')

        # Set the RNG seed to according to the last block,
        # to make sure that the numbers generated by the nodes are the same
        random.seed(self.chain[-1]['random_factor'])

        # Get the candidates from the other nodes and add ourself to them (our ip), represented by the MYSELF_STRING
        # As for our reputation, we can easily put a default value here, since the neighbour nodes will replace it with
        # our real reputation
        self.candidates[nd.MYSELF_STRING] = nd.Node(
            url=nd.MYSELF_STRING,
            reputation=DEFAULT_REPUTATION,
            address=self.node_id
        )

        # Insert the new candidates obtained from neighbours into our candidates
        new_candidates = self.get_candidates_from_nodes()
        for candidate_url in new_candidates:
            self.candidates.put(candidate_url, new_candidates[candidate_url])

        # TOCHECK: force the neighbours to update their candidates
        for node in self.nodes:
            print('Requesting http://' + node + '/update_candidates')
            try:
                requests.get('http://' + node + '/update_candidates')
            except:
                print("Node with url '" + node + "' isn't connected or doesn't exist anymore.")

        # If present, remove the validator of the last block from the candidates
        for candidate_url in self.candidates:
            if self.candidates[candidate_url].address == self.chain[-1]["validator"]:
                del self.candidates[candidate_url]

        # Choose the effective candidates
        chosen_candidates = self.__choose_candidates()
        # Choose an Asker candidate between them and remove it from the operator list
        asker_candidate = self.__choose_asker(chosen_candidates)

        # Create the Asker (the 'formulating' or not the offer attribute is a random boolean, as described in the paper)
        asker: ng.Asker = ng.Asker(
            identifier=asker_candidate.address,
            balance=self.get_node_balance(asker_candidate.url),
            formulating=bool(random.randint(0, 1))
        )
        asker.offer = asker.generate_offer(minimum=abs(self.chain[-1]['negotiation_price'] - MINING_REWARD))

        # Create the Bidder (the 'acceptance' attribute is True regardless of all, as described in the paper)
        # The proposed price from the bidder will be, as for now, the base plus a random float value between some bounds
        bidder: ng.Bidder = ng.Bidder(
            identifier=self.chain[-1]["validator"],
            offer=random.uniform(MIN_GAIN, MAX_GAIN),
            balance=self.get_node_balance(self.chain[-1]["validator"]),
            acceptance=True
        )

        # Create the operators
        operators = List[ng.NegotiationActor]
        # As for now, the operator offer will be minimum plus a small random float
        for candidate_url in self.candidates:
            operator = ng.NegotiationActor(
                identifier=self.candidates[candidate_url].address,
                offer=random.uniform(MIN_OPERATOR, MAX_OPERATOR),
                balance=self.get_node_balance(self.candidates[candidate_url].url)
            )
            operators.append(operator)

        # Get a winner using the negotiation algorithm, and the corresponding Node object
        success, winner_actor = ng.negotiation(asker, bidder, *operators)
        winner: Optional[nd.Node] = None
        for candidate_url in self.candidates:
            if self.candidates[candidate_url].address == winner_actor.identifier:
                winner = self.candidates[candidate_url]

        # Empty the candidate dictionary
        self.candidates = TreeMap()
        # Return the validator
        return winner

    def __choose_candidates(self) -> dict:
        # Select the effective candidates, by a reputation-weighted roulette wheel algorithm
        # In the future, the candidates will be chosen from different coin age groups, to grant democracy

        candidate_keys = list(self.candidates.key_set())  # Candidate keys
        candidate_weights = [self.candidates[candidate]["reputation"] for candidate in candidate_keys]  # Reputations
        candidates_num = [i for i in range(0, len(candidate_keys))]  # Indexes of the candidates
        chosen_candidates = OrderedDict()  # Chosen candidates dictionary

        for i in range(0, REAL_CANDIDATES_NUMBER + 1):
            # Pick the candidate index
            selected_index = random.choices(population=candidates_num, weights=candidate_weights, k=1)[0]
            # To prevent selection of the same candidate twice, set his weight to 0
            candidate_weights[selected_index] = 0
            # Put the corresponding candidate into the Chosen candidates dictionary
            selected_key = candidate_keys[selected_index]
            chosen_candidates[selected_key] = self.candidates[selected_key]

        return chosen_candidates

    def __choose_asker(self, chosen_candidates):
        # TODO: develop more complex algorithm for choosing the asker
        return chosen_candidates[0]

