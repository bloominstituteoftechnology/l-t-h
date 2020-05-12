# Adventure Blockchain

This app is a Django compatible, partially implemented, block-chain for the Lambda Treasure Hunt.  Players may mine "Lambda Coins" which may then be spent in other parts of the game.

Note that this is not a fully secure blockchain implementation.  As such, students are not permitted to exploit or hack the system to gain an advantage, or harm other players.  The vulnerabilities will not prevent this from happening, but the perpetrator will be logged and dealt with.

# Endpoints

## /api/bc/full_chain/
The `full_chain` endpoint is not available in this implementation

## /api/bc/mine/
Submit a proposed proof and your game token to this endpoint to attempt to mine a block.  If successful, you will receive a Lambda Coin.  Note that if you submit the wrong token as your ID, you will not receive your coin and it will be lost.

JSON POST request:
{
    "proof": new_proof
}

### Proof of Work
The proof of work algorithm for this blockchain is similar to the first one we first used in class, with one exception - *the difficulty level is variable!*

To keep the time between blocks mined at a consistent rate of about one block every 10 minutes, the server will dynamically adjust the number of zeroes required.  

Does hash(last_proof, proof) contain N leading zeroes, where N is the current difficulty level?

## /api/bc/last_proof/
Get the last valid proof to use to mine a new block.  Also returns the current difficulty level, which is the number of `0`'s required at the beginning of the hash for a new proof to be valid.  

JSON Response:
{
    'proof': last_proof_value
    'difficulty': current_difficulty_level
}

## /api/bc/get_balance/
Get the current coin balance of the requested `user_id`.

JSON GET request:
{
    "user_id": requested_id
}


