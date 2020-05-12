from django.http import JsonResponse
from .models import Block, ChainDifficulty, Transaction
from django.core import serializers
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from rest_framework.decorators import api_view
from django.utils import timezone
from datetime import datetime, timedelta

from .blockchain import Blockchain
from adventure.api import check_cooldown_error, get_cooldown, api_response, PENALTY_BLASPHEMY

from adventure.models import Player, Room, Item, Group

import json

REWARD_PER_BLOCK = 1

PENALTY_DUPLICATE_PROOF_VIOLATION = 10
PENALTY_INVALID_PROOF_VIOLATION = 30

PENALTY_WRONG_MINING_ROOM = 100


def blockchain_api_response(player, cooldown_seconds, errors=None, messages=None):
    if errors is None:
        errors = []
    if messages is None:
        messages = []
    response = JsonResponse({'name':player.name,
                             'description':player.name + player.description,
                             'cooldown': cooldown_seconds,
                             'errors': errors,
                             'messages': messages}, safe=True)
    return response


@api_view(["POST"])
def mine(request):
    player = request.user.player

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    cooldown_seconds = get_cooldown(player, 1.0)

    errors = []
    messages = []

    if not player.has_rename:
        cooldown_seconds += PENALTY_BLASPHEMY
        errors.append(f"One with no name is unworthy to mine: +{PENALTY_BLASPHEMY}s")
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.save()
        return blockchain_api_response(player, cooldown_seconds, errors=errors, messages=messages)

    if player.currentRoom != player.mining_room:
        cooldown_seconds += PENALTY_WRONG_MINING_ROOM
        errors.append(f"There is no coin here: +{PENALTY_WRONG_MINING_ROOM}s")
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.save()
        return blockchain_api_response(player, cooldown_seconds, errors=errors, messages=messages)

    # Get the blockchain from the database
    # For now, assume there is only one and get that
    blockchain = Block.objects.all()
    # Determine if proof is valid
    last_block = blockchain.last()
    last_proof = last_block.proof

    body_unicode = request.body.decode('utf-8')
    values = json.loads(body_unicode)

    submitted_proof = values.get('proof')
    player_id = player.id

    if submitted_proof <= -9223372036854775808 or submitted_proof >= 9223372036854775807:
        cooldown_seconds += PENALTY_BLASPHEMY
        errors.append(f"We don't traffic with numbers that big!: +{PENALTY_BLASPHEMY}s")
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.save()
        return blockchain_api_response(player, cooldown_seconds, errors=errors, messages=messages)

    if Blockchain.valid_proof(last_proof, submitted_proof):
        # We must receive a reward for finding the proof.
        # The sender is "0" to signify that this node has mine a new coin
        Blockchain.new_transaction(
            sender="0",
            recipient=player_id,
            amount=REWARD_PER_BLOCK,
        )

        # Forge the new Block by adding it to the chain
        previous_hash = Blockchain.hash(last_block)

        block = Blockchain.new_block(submitted_proof, previous_hash)
        messages.append("New Block Forged")

        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.has_mined = True
        player.generate_mining_puzzle("MEDIUM")  # save()

        response = {
            'index': block.index,
            'transactions': str(block.transactions),
            'proof': block.proof,
            'previous_hash': block.previous_hash,
            'cooldown': cooldown_seconds,
            'messages': messages,
            'errors': errors
        }

        return JsonResponse(response)
    else:
        # Check if solution would have worked on a previous block.
        for block in blockchain[::-1]:
            if Blockchain.valid_proof(block.proof, submitted_proof):
                # Flag successful attempt that was too late
                player.has_mined = True
                cooldown_seconds += PENALTY_DUPLICATE_PROOF_VIOLATION
                player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
                player.save()
                errors.append("Proof already submitted: ")
                return JsonResponse({"cooldown": cooldown_seconds, 'errors':[f"Proof already submitted: +{PENALTY_DUPLICATE_PROOF_VIOLATION}s CD"]}, safe=True, status=400)
        cooldown_seconds += PENALTY_INVALID_PROOF_VIOLATION
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.save()
        return JsonResponse({"cooldown": cooldown_seconds, 'errors':[f"Invalid proof: +{PENALTY_INVALID_PROOF_VIOLATION}s CD"]}, safe=True, status=400)


# def new_transaction(request):
#     player = request.user.player
#     # Get the blockchain from the database
#     # For now, assume there is only one and get that
#     blockchain = Block.objects.all()

#     body_unicode = request.body.decode('utf-8')
#     values = json.loads(body_unicode)

#     # Check that the required fields are in the POST'ed data
#     required = ['sender', 'recipient', 'amount']
#     if not all(k in values for k in required):
#         return 'Missing Values', 400

#     # Create a new Transaction
#     index = Blockchain.new_transaction(values['sender'],
#                                        values['recipient'],
#                                        values['amount'])

#     # -1 means the transaction failed due to insufficient funds
#     if index > 0:
#         response = {'message': f'Transaction will be added to Block {index}'}
#     else:
#         response = {'message': 'ERROR: Sender has insufficient funds'}
#     return JsonResponse(response)

@api_view(["GET"])
def get_balance(request):
    player = request.user.player

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    cooldown_seconds = get_cooldown(player, 0.0)
    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()

    body_unicode = request.body.decode('utf-8')

    # Check that the required fields are in the POST'ed data
    player_id = player.id
    balance = Blockchain.get_user_balance(player_id)

    response = {'cooldown': cooldown_seconds, 'messages': [f'You have a balance of {balance} Lambda Coins'], 'errors': []}
    return JsonResponse(response)


@api_view(["GET"])
def totals(request):
    total_coins = {}
    for transaction in Transaction.objects.all():
        # Should only be one, but just in case
        recipient = transaction.recipient
        playername = ""
        if (len(recipient) > 10):
            continue
        elif recipient == "0":
            playername = "server"
        else:
            player = Player.objects.get(id=int(recipient))
            playername = player.name
        if playername not in total_coins:
            total_coins[playername] = 5
        else:
            total_coins[playername] += 5
    response = {
        'totals': total_coins
    }

    return JsonResponse(response)


# @api_view(["GET"])
# def full_chain(request):
#     player = request.user.player
#     # Get the blockchain from the database
#     # For now, assume there is only one and get that
#     blockchain = Block.objects.all()

#     data = serializers.serialize('json', blockchain)

#     return JsonResponse(data, safe=False)


@api_view(["GET"])
def last_proof(request):
    player = request.user.player

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    cooldown_seconds = get_cooldown(player, 0.0)
    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()

    # Get the blockchain from the database
    # For now, assume there is only one and get that
    blockchain = Block.objects.all()

    last_proof_value = blockchain.last().proof
    response = {
        'proof': last_proof_value,
        'difficulty': ChainDifficulty.objects.all().last().difficulty,
        'cooldown': cooldown_seconds,
        'messages': [],
        'errors': []
    }
    return JsonResponse(response)
