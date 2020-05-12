import hashlib
import requests

import sys

from uuid import uuid4
import time

def proof_of_work(last_proof, difficulty):
    """
    Simple Proof of Work Algorithm
    - Find a number p' such that hash(pp') contains `difficulty` leading
    zeroes, where p is the previous p'
    - p is the previous proof, and p' is the new proof
    """

    print("Searching for next proof")
    proof = 0
    while valid_proof(last_proof, proof, difficulty) is False:
        proof += 1

    print("Proof found: " + str(proof))
    return proof


def valid_proof(last_proof, proof, difficulty):
    """
    Validates the Proof:  Does hash(last_proof, proof) contain `difficulty`
    leading zeroes?
    """
    guess = f'{last_proof}{proof}'.encode()
    guess_hash = hashlib.sha256(guess).hexdigest()
    return guess_hash[:difficulty] == "0" * difficulty


if __name__ == '__main__':
    # What node are we interacting with?
    if len(sys.argv) > 1:
        node = sys.argv[1]
    else:
        node = "http://localhost:5000"

    coins_mined = 0

    # Load or create ID
    # f = open("my_id.txt", "r")
    # id = f.read()
    # print("ID is", id)
    # f.close()
    # if len(id) == 0:
    #     f = open("my_id.txt", "w")
    #     # Generate a globally unique ID
    #     id = str(uuid4()).replace('-', '')
    #     print("Created new ID: " + id)
    #     f.write(id)
    #     f.close()
    auth_key = "01e6368ccdd81059ba8672ded4647847bda843a1"
    # Run forever until interrupted
    while True:
        # Get the last proof from the server
        headers = {}
        headers['Authorization'] = f"Token {auth_key}"
        headers["Content-Type"] = "application/json"
        r = requests.get(url=node + "/last_proof/", headers=headers)
        r.headers['Authorization'] = f"Token {auth_key}"
        r.headers["Content-Type"] = "application/json"
        data = r.json()
        print("data: ", data)
        print("Last Proof: ", data.get('proof'))
        print("Difficulty: ", data.get('difficulty'))
        print(data.get('cooldown'))
        print("Cooldown: ", data.get("cooldown"))
        time.sleep(data.get("cooldown"))
        new_proof = proof_of_work(data.get('proof'), data.get('difficulty'))

        post_data = {"proof": new_proof}

        r = requests.post(url=node + "/mine", json=post_data, headers=headers)
        data = r.json()
        if data.get('messages') == 'New Block Forged':
            coins_mined += 1
            print("Total coins mined: " + str(coins_mined))
        else:
            print(data.get('errors'))
        time.sleep(data.get("cooldown"))

