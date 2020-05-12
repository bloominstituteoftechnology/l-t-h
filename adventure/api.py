from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
# from pusher import Pusher
from django.http import JsonResponse
from decouple import config
from django.contrib.auth.models import User
from .models import *
from rest_framework.decorators import api_view
import json
from django.utils import timezone
from datetime import datetime, timedelta
from adv_blockchain.blockchain import Blockchain
from util.ls8 import generate_snitch_ls8
import math
import random

# instantiate pusher
# pusher = Pusher(app_id=config('PUSHER_APP_ID'), key=config('PUSHER_KEY'), secret=config('PUSHER_SECRET'), cluster=config('PUSHER_CLUSTER'))

SHOP_ROOM_ID=1
TRANSMOGRIFIER_ROOM_ID=495  # TODO: Create rooms
NAME_CHANGE_ROOM_ID=467
FLIGHT_SHRINE_ROOM_ID=22
DASH_SHRINE_ROOM_ID=461
CARRY_SHRINE_ROOM_ID=499
WARP_SHRINE_ROOM_ID=374
RECALL_SHRINE_ROOM_ID=492
WISHING_WELL_ROOM_ID=55
ATHENAEUM_ROOM_ID=486
SNITCH_LEADERBOARD_ROOM_ID=986
DARK_WELL_ROOM_ID=555
DONUT_ROOM_ID=15
PIZZA_ROOM_ID=314

NAME_CHANGE_PRICE=1000

PENALTY_COOLDOWN_VIOLATION=5
PENALTY_NOT_FOUND=5
PENALTY_CANT_AFFORD=5
PENALTY_CANNOT_MOVE_THAT_WAY=5
PENALTY_TOO_HEAVY=5
PENALTY_UPHILL = 5
PENALTY_TRAP = 30

PENALTY_CAVE_FLY = 10

PENALTY_BAD_DASH = 20

PENALTY_BLASPHEMY = 30

MIN_COOLDOWN = 1.0
MAX_COOLDOWN = 600.0

DONUT_PRICE = 2000
DONUT_BOOST_TIME = 300.0
DONUT_BOOST_SCALE = 0.7

PIZZA_PRICE = 1000
PIZZA_BOOST_TIME = 600.0


# Generates a randomized item from the item passed in.  Returns the new item
# NOTE: This does not delete the old item
def randomize_item(item):
    quality = random.triangular(-1, 1)
    adjective = ""

    item_value = 0

    if quality < 0:
        adjective = "poor"
        item_value = 200
        if quality < -.5:
            adjective = "terrible"
            item_value = 100
            if quality < -.9:
                adjective = "appalling"
                item_value = 10
    else:
        adjective = "nice"
        item_value = 500
        if quality > .5:
            adjective = "well-crafted"
            item_value = 1000
            if quality > .9:
                adjective = "exquisite"
                item_value = 2000

    atts = {}

    if random.random() > 0.5:
        itemtype = "FOOTWEAR"
        name = f"{adjective} boots"
        aliases = f"{name},boots"
        description = "These are transmogrified boots."
        atts['STRENGTH'] = math.floor(1.0 + 2.0 * random.random())
        atts['SPEED'] = math.floor(50 + 50 * quality)
    else:
        itemtype = "BODYWEAR"
        name = f"{adjective} jacket"
        aliases = f"{name},jacket"
        description = "This is a transmogrified jacket."
        atts['STRENGTH'] = math.floor(6.0 + 4.0 * random.random())
        atts['SPEED'] = 0

    i = Item(name=name,
             group=item.group,
             description=description,
             weight=1,
             aliases=aliases,
             value=item_value,
             itemtype=itemtype,
             attributes=json.dumps(atts))
    i.save()

    return i


def check_cooldown_error(player):
    """
    Return cooldown error if cooldown is bad, None if it's valid
    """
    if player.cooldown > timezone.now():
        t_delta = (player.cooldown - timezone.now())
        cooldown_seconds = min(MAX_COOLDOWN, t_delta.seconds + t_delta.microseconds / 1000000 + PENALTY_COOLDOWN_VIOLATION)
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.save()
        return JsonResponse({"cooldown": cooldown_seconds, 'errors':[f"Cooldown Violation: +{PENALTY_COOLDOWN_VIOLATION}s CD"]}, safe=True, status=400)
    return None

def api_response(player, cooldown_seconds, errors=None, messages=None):
    if errors is None:
        errors = []
    if messages is None:
        messages = []
    room = player.room()
    if not player.group.vision_enabled:
        response = JsonResponse({'room_id':room.id,
                                 'title': "A Dark Room",
                                 'description':"You cannot see anything.",
                                 'coordinates':room.coordinates,
                                 'exits':room.exits(),
                                 'cooldown': cooldown_seconds,
                                 'errors': errors,
                                 'messages':messages}, safe=True)
    elif player.currentRoom >= 500:
        response = JsonResponse({'room_id':room.id,
                                 'title': room.title,
                                 'description':room.description,
                                 'coordinates':room.coordinates,
                                 'elevation':room.elevation,
                                 'terrain':room.terrain,
                                 'players':room.playerNamesAll(player.id),
                                 'items':room.itemNamesAll(player.group),
                                 'exits':room.exits(),
                                 'cooldown': cooldown_seconds,
                                 'errors': errors,
                                 'messages':messages}, safe=True)
    else:
        response = JsonResponse({'room_id':room.id,
                                 'title': room.title,
                                 'description':room.description,
                                 'coordinates':room.coordinates,
                                 'elevation':room.elevation,
                                 'terrain':room.terrain,
                                 'players':room.playerNames(player.id, player.group),
                                 'items':room.itemNames(player.group),
                                 'exits':room.exits(),
                                 'cooldown': cooldown_seconds,
                                 'errors': errors,
                                 'messages':messages}, safe=True)
    return response


def player_api_response(player, cooldown_seconds, errors=None, messages=None):
    if errors is None:
        errors = []
    if messages is None:
        messages = []
    status = []

    bodywear = player.getBodywear()
    footwear = player.getFootwear()
    bodywear_name = None
    footwear_name = None
    if bodywear is not None:
        bodywear_name = bodywear.name
    if footwear is not None:
        footwear_name = footwear.name

    abilities = []
    if player.has_rename:
        abilities.append('pray')
        abilities.append('mine')
    if player.can_fly:
        abilities.append('fly')
    if player.can_dash:
        abilities.append('dash')
    if player.can_carry:
        abilities.append('carry')
        carried_item = player.get_carried_item()
        if carried_item is not None:
            status.append(f"Glasowyn is carrying {carried_item.name}")
    if player.can_warp:
        abilities.append('warp')
    if player.can_recall:
        abilities.append('recall')

    response_dictionary = {'name':player.name,
                             'cooldown': cooldown_seconds,
                             'encumbrance': player.encumbrance,
                             'strength': player.strength,
                             'speed': player.speed,
                             'gold': player.gold,
                             'bodywear': bodywear_name,
                             'footwear': footwear_name,
                             'inventory': player.inventory(),
                             'abilities': abilities,
                             'status': status,
                             'has_mined': player.has_mined,
                             'errors': errors,
                             'messages': messages}
    if player.sugar_rush_active():
        t_delta = player.donut_boost - timezone.now()
        response_dictionary["sugar_rush"] = t_delta.seconds + t_delta.microseconds / 1000000
    if player.pizza_power_active():
        t_delta = player.pizza_power - timezone.now()
        response_dictionary["pizza_power"] = t_delta.seconds + t_delta.microseconds / 1000000
    if player.snitches > 0:
        response_dictionary["snitches"] = player.snitches
    response = JsonResponse(response_dictionary, safe=True)
    return response

def item_examine_api_response(item, cooldown_seconds, errors=None, messages=None):
    if errors is None:
        errors = []
    if messages is None:
        messages = []
    response = JsonResponse({'name':item.name,
                             'description':item.description,
                             'weight':item.weight,
                             'itemtype':item.itemtype,
                             'level':item.level,
                             'exp':item.exp,
                             'attributes':item.attributes,
                             'cooldown': cooldown_seconds,
                             'errors': errors,
                             'messages': messages}, safe=True)
    return response

def player_examine_api_response(player, cooldown_seconds, errors=None, messages=None):
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


def well_examine_api_response(player, cooldown_seconds, errors=None, messages=None):
    if errors is None:
        errors = []
    if messages is None:
        messages = []
    if player.has_rename and player.group.has_clear_well:
        description = f"You see a faint pattern in the water...\n\nMine your coin in room {player.mining_room}"
    elif player.has_rename:
        description = "You see a faint pattern in the water...\n\n" + player.mining_puzzle
    else:
        description = "You see a faint message in the water...\n\n"
        description += "'One with no name is unworthy to mine.'"
    response = JsonResponse({'name':"Wishing Well",
                             'description': description,
                             'cooldown': cooldown_seconds,
                             'errors': errors,
                             'messages': messages}, safe=True)
    return response


def book_of_knowledge_examine_api_response(player, cooldown_seconds, errors=None, messages=None):
    if errors is None:
        errors = []
    if messages is None:
        messages = []
    grounded_items = len(Item.objects.filter(group=player.group, player=None))
    if not player.has_rename:
        description = f"Greetings. Seek out the services of Pirate Ry and the world will open for you.\n\n"
        description += "He has been spotted on the southeast coast of the island."
        description += f"\n\nThere are {grounded_items} treasures on the ground."
    else:
        ranks = []
        players = Player.objects.filter(group=player.group, has_rename=True).order_by("-gold")
        i = 1
        for p in players:
            ranks.append(f"{i}. {p.gold} - {p.name}")
            i += 1
        description = f"Greetings, {player.name}. {player.group.name} gold rank:\n\n"
        description += "\n".join(ranks)
        description += f"\n\nThere are {grounded_items} treasures on the ground."
    response = JsonResponse({'name':"Book of Knowledge",
                             'description': description,
                             'cooldown': cooldown_seconds,
                             'errors': errors,
                             'messages': messages}, safe=True)
    return response



def snitch_leaderboard_examine_api_response(player, cooldown_seconds, errors=None, messages=None):
    if errors is None:
        errors = []
    if messages is None:
        messages = []
    ranks = []
    players = Player.objects.filter(group=player.group, has_rename=True).order_by("-snitches")
    i = 1
    for p in players:
        if p.snitches > 0:
            ranks.append(f"{i}. {p.snitches} - {p.name}")
            i += 1
    description = f"Greetings, {player.name}. {player.group.name} golden snitch rank:\n\n"
    description += "\n".join(ranks)
    response = JsonResponse({'name':"Golden Snitch Board",
                             'description': description,
                             'cooldown': cooldown_seconds,
                             'errors': errors,
                             'messages': messages}, safe=True)
    return response



def get_snitch_puzzle():
    snitch = Item.objects.get(itemtype="SNITCH")
    return generate_snitch_ls8(snitch.room.id)


def dark_well_examine_api_response(player, cooldown_seconds, errors=None, messages=None):
    if errors is None:
        errors = []
    if messages is None:
        messages = []
    if player.has_rename and player.group.has_clear_well:
        snitch = Item.objects.get(itemtype="SNITCH")
        description = f"You see a faint pattern in the water...\n\nFind the snitch in room {snitch.room.id}"
    elif player.has_rename:
        description = "You see a faint pattern in the water...\n\n" + get_snitch_puzzle()
    else:
        description = "You see a faint message in the water...\n\n"
        description += "'One with no name is unworthy to mine.'"
    response = JsonResponse({'name':"Wishing Well",
                             'description': description,
                             'cooldown': cooldown_seconds,
                             'errors': errors,
                             'messages': messages}, safe=True)
    return response


def get_cooldown(player, cooldown_scale):
    speed_adjustment = (player.speed - 10) // 10

    if player.donut_boost > timezone.now():
        cooldown_scale *= DONUT_BOOST_SCALE

    if player.group is not None:
        time_factor = player.group.cooldown
    else:
        time_factor = 60
    if player.group.catchup_enabled and not player.has_rename:
        time_factor = min(time_factor, 10)
    return max(MIN_COOLDOWN, cooldown_scale * time_factor - speed_adjustment)



@csrf_exempt
@api_view(["GET"])
def initialize(request):
    player = request.user.player

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    cooldown_seconds = get_cooldown(player, 0.0)
    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()

    return api_response(player, cooldown_seconds)


@api_view(["POST"])
def move(request):
    player = request.user.player
    print(f"MOVE: {request.user.username}")
    # import pdb; pdb.set_trace()
    data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    dirs={"n": "north", "s": "south", "e": "east", "w": "west"}
    reverse_dirs = {"n": "south", "s": "north", "e": "west", "w": "east"}
    direction = data['direction']
    room = player.room()
    nextRoomID = None
    cooldown_seconds = get_cooldown(player, 1.0)
    errors = []
    messages = []
    if direction == "n":
        nextRoomID = room.n_to
    elif direction == "s":
        nextRoomID = room.s_to
    elif direction == "e":
        nextRoomID = room.e_to
    elif direction == "w":
        nextRoomID = room.w_to
    if nextRoomID is not None and nextRoomID >= 0:
        nextRoom = Room.objects.get(id=nextRoomID)
        player.currentRoom=nextRoomID
        messages.append(f"You have walked {dirs[direction]}.")
        elevation_change = player.room().elevation - room.elevation
        if elevation_change > 0:
            messages.append(f"Uphill Penalty: {PENALTY_UPHILL}s CD")
            cooldown_seconds += PENALTY_UPHILL
        if player.strength <= player.encumbrance:
            messages.append(f"Heavily Encumbered: +100% CD")
            cooldown_seconds *= 2
        if nextRoom.terrain == "TRAP":
            messages.append(f"It's a trap!: +{PENALTY_TRAP}s CD")
            cooldown_seconds += PENALTY_TRAP
        if 'next_room_id' in data:
            if data['next_room_id'].isdigit() and int(data['next_room_id']) == nextRoomID:
                messages.append(f"Wise Explorer: -50% CD")
                cooldown_seconds /= 2
            else:
                messages.append(f"Foolish Explorer: +50% CD")
                cooldown_seconds *= 1.5
        if nextRoomID == DONUT_ROOM_ID:
            messages.append('Grumpy Tommy welcomes you to the shop and says, "What do you want? I have a raid in 15 minutes."')
        # if nextRoom.terrain == "MOUNTAIN" and len(Player.objects.filter(id=9)) > 0:
        #     pusher.trigger(f'p-channel-{Player.objects.get(id=9).uuid}', u'broadcast', {'message':f'{player.name} has walked {dirs[direction]} to room {nextRoom.id}.'})
        player.move_log = f"{player.move_log};{direction}{nextRoomID}"
        player.num_moves += 1
    else:
        cooldown_seconds += PENALTY_CANNOT_MOVE_THAT_WAY
        errors.append(f"You cannot move that way: +{PENALTY_CANNOT_MOVE_THAT_WAY}s CD")
    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)




@api_view(["POST"])
def take(request):
    player = request.user.player
    data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    alias = data['name']
    room = player.room()
    item = room.findItemByAlias(alias, player.group)
    if player.in_dark():
        item = room.findItemAllByAlias(alias, player.group)
    cooldown_seconds = get_cooldown(player, 0.5)
    errors = []
    messages = []
    if item is None:
        cooldown_seconds += PENALTY_NOT_FOUND
        errors.append(f"Item not found: +{PENALTY_NOT_FOUND}s CD")
    elif player.strength * 2 <= player.encumbrance + item.weight:
        cooldown_seconds += PENALTY_TOO_HEAVY
        errors.append(f"Item too heavy: +{PENALTY_TOO_HEAVY}s CD")
    elif item.itemtype == "SNITCH":
        messages.append(f"A great warmth floods your body as your hand closes around the snitch before it vanishes.")
        player.snitches += 1
        item.resetSnitch()
    else:
        messages.append(f"You have picked up {item.name}")
        player.addItem(item)
    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)

@api_view(["POST"])
def gamble(request):
    player = request.user.player
    data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    alias = data['name']
    item = player.findItemByAlias(alias)
    cooldown_seconds = get_cooldown(player, 1.0)
    errors = []
    messages = []
    if player.currentRoom != TRANSMOGRIFIER_ROOM_ID:
        cooldown_seconds += PENALTY_NOT_FOUND
        errors.append(f"Transmogrifier not found: +{PENALTY_NOT_FOUND}")
    else:
        if item is None:
            cooldown_seconds += PENALTY_NOT_FOUND
            errors.append(f"Item not found: +{PENALTY_NOT_FOUND}s CD")
        else:
            print("player is: ", player.name)
            print("player balance is, ", Blockchain.get_user_balance(request.user.id))
            if Blockchain.get_user_balance(player.id) >= 1:
                # Spend the coin by giving it back to the server
                Blockchain.new_transaction(player.id, 0, 1)

                oldname = item.name
                new_item = randomize_item(item)
                player.addItem(new_item)
                item.levelUpAndRespawn()
                messages.append(f"Your {oldname} transmogrified into {new_item.name}!")
            else:
                cooldown_seconds += PENALTY_CANT_AFFORD
                errors.append(f"You don't have a Lambda Coin: +{PENALTY_CANT_AFFORD}s CD")

    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player,
                        cooldown_seconds,
                        errors=errors,
                        messages=messages)


@api_view(["POST"])
def drop(request):
    player = request.user.player
    data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    alias = data['name']
    room = player.room()
    item = player.findItemByAlias(alias)
    cooldown_seconds = get_cooldown(player, 0.5)
    errors = []
    messages = []
    if item is None:
        cooldown_seconds += PENALTY_NOT_FOUND
        errors.append(f"Item not found: +{PENALTY_NOT_FOUND}s CD")
    else:
        messages.append(f"You have dropped {item.name}")
        room.addItem(item)
    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)


@api_view(["POST"])
def examine(request):
    player = request.user.player
    data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    alias = data['name']
    room = player.room()
    # import pdb; pdb.set_trace()
    item = room.findItemByAlias(alias, player.group)
    if item is None:
        item = player.findItemByAlias(alias)
    players = room.findPlayerByName(alias, player.group)
    cooldown_seconds = get_cooldown(player, 0.5)
    errors = []
    messages = []
    if player.currentRoom == WISHING_WELL_ROOM_ID and (alias.lower() == "well" or alias.lower() == "wishing well"):
        return well_examine_api_response(player, cooldown_seconds, errors=errors, messages=messages)
    elif player.currentRoom == DARK_WELL_ROOM_ID and (alias.lower() == "well" or alias.lower() == "wishing well"):
        return dark_well_examine_api_response(player, cooldown_seconds, errors=errors, messages=messages)
    elif player.currentRoom == ATHENAEUM_ROOM_ID and (alias.lower() == "book"):
        return book_of_knowledge_examine_api_response(player, cooldown_seconds, errors=errors, messages=messages)
    elif player.currentRoom == SNITCH_LEADERBOARD_ROOM_ID and (alias.lower() == "board"):
        return snitch_leaderboard_examine_api_response(player, cooldown_seconds, errors=errors, messages=messages)
    if item is not None:
        # Examine item
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.save()
        return item_examine_api_response(item, cooldown_seconds, errors=errors, messages=messages)
    if len(players) > 0:
        # Examine player
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.save()
        return player_examine_api_response(players[0], cooldown_seconds, errors=errors, messages=messages)
    cooldown_seconds += PENALTY_NOT_FOUND
    errors.append(f"Item not found: +{PENALTY_NOT_FOUND}s CD")
    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)




@api_view(["POST"])
def status(request):
    player = request.user.player

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    cooldown_seconds = get_cooldown(player, 0)

    return player_api_response(player, cooldown_seconds)


@api_view(["POST"])
def buy(request):
    player = request.user.player
    data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    cooldown_seconds = get_cooldown(player, 0.2)

    errors = []
    messages = []

    if player.currentRoom != PIZZA_ROOM_ID and player.currentRoom != DONUT_ROOM_ID and player.currentRoom != SHOP_ROOM_ID:
        cooldown_seconds += PENALTY_NOT_FOUND
        errors.append(f"Shop not found: +{PENALTY_NOT_FOUND}")
    elif not player.has_rename:
        messages.append("Who are you? We only serve people with names!")
        cooldown_seconds += PENALTY_BLASPHEMY
        errors.append(f"Name Error: +{PENALTY_BLASPHEMY}s CD")
    elif player.currentRoom == SHOP_ROOM_ID:
        messages.append("Sorry, nothing to sell at this time!")
    elif player.currentRoom == DONUT_ROOM_ID:
        if not data["name"] or data["name"].lower() != "donut":
            cooldown_seconds += PENALTY_NOT_FOUND
            messages.append(f"We only sell donuts.")
            errors.append(f"Item not found: +{PENALTY_NOT_FOUND}s CD")
        elif "confirm" not in data or data["confirm"].lower() != "yes":
            messages.append(f"That'll be {DONUT_PRICE} gold.")
            messages.append(f"(include 'confirm':'yes' to complete the purchase)")
        elif player.gold < DONUT_PRICE:
            messages.append(f"You can't afford that. Get out of here!")
            errors.append(f"Cannot Afford: +{PENALTY_NOT_FOUND}s CD")
            cooldown_seconds += PENALTY_NOT_FOUND
        else:
            messages.append(f"As you eat the donut, a rush of sugar courses through your veins. You suddenly feel as if time can't slow you down. Better make the most of it before the sugar crash hits.")
            player.donut_boost = timezone.now() + timedelta(0,DONUT_BOOST_TIME)
            player.gold -= DONUT_PRICE
    elif player.currentRoom == PIZZA_ROOM_ID:
        if not data["name"] or data["name"].lower() != "pizza":
            cooldown_seconds += PENALTY_NOT_FOUND
            messages.append(f"We only sell pizza.")
            errors.append(f"Item not found: +{PENALTY_NOT_FOUND}s CD")
        elif "confirm" not in data or data["confirm"].lower() != "yes":
            messages.append(f"That'll be {PIZZA_PRICE} gold.")
            messages.append(f"(include 'confirm':'yes' to complete the purchase)")
        elif player.gold < PIZZA_PRICE:
            messages.append(f"You can't afford that.")
            errors.append(f"Cannot Afford: +{PENALTY_NOT_FOUND}s CD")
            cooldown_seconds += PENALTY_NOT_FOUND
        else:
            hints = ["Treasures are probably where other people aren't.",
                    f"How long it would take to gather {DONUT_PRICE} gold? What would you do with it?",
                     "Some things might reveal secrets upon further inspection.",
                     "Is a herring a bird? or is it a fish? does it matter if it's red?",
                     "If you moved around and yanked your soul through space and time then back to your original dimension, would you be close to where you started?",
                     "Pouring a cup of coffee on your face helps you to wake up more than by drinking it.",
                     "The birth of Kool-aid man had to be traumatic.",
                     "Some rooms take longer to travel through than others. Could you find a better way?",
                     "0x48! 0xa8! 0x82! 0xab! HLT! WELL that was weird... but why was it so famiLiar? Seems str8nge.",
                     "What happens if you try to fly in a cave? Seems like a bad idea.",
                     "Do snitches really get stitches? Maybe they get rewarded instead."]
            hint = random.choice(hints)
            messages.append(f"As he hands you a pizza, Mr. Red Egg mumbles, '{hint}'")
            messages.append(f"The delicious pizza courses through your veins, giving you a surge of strength!")

            player.pizza_power = timezone.now() + timedelta(0,PIZZA_BOOST_TIME)
            player.gold -= PIZZA_PRICE
    else:
        print(player.currentRoom)
        print(PIZZA_ROOM_ID)
        cooldown_seconds += PENALTY_NOT_FOUND
        errors.append(f"Shop not found: +{PENALTY_NOT_FOUND}")

    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)


@api_view(["POST"])
def sell(request):
    player = request.user.player
    data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    cooldown_seconds = get_cooldown(player, 0.2)

    errors = []
    messages = []

    if player.currentRoom != SHOP_ROOM_ID:
        cooldown_seconds += PENALTY_NOT_FOUND
        errors.append(f"Shop not found: +{PENALTY_NOT_FOUND}")
    else:
        item = player.findItemByAlias(data["name"])
        if item is None:
            cooldown_seconds += PENALTY_NOT_FOUND
            errors.append(f"Item not found: +{PENALTY_NOT_FOUND}s CD")
        elif "confirm" not in data or data["confirm"].lower() != "yes":
            messages.append(f"I'll give you {item.value} gold for that {item.name}.")
            messages.append(f"(include 'confirm':'yes' to sell {item.name})")
        else:
            messages.append(f"Thanks, I'll take that {item.name}.")
            messages.append(f"You have received {item.value} gold.")
            player.gold += item.value
            item.levelUpAndRespawn()

    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)


@api_view(["POST"])
def wear(request):
    player = request.user.player
    data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    alias = data['name']
    item = player.findItemByAlias(alias)
    cooldown_seconds = get_cooldown(player, 0.5)
    errors = []
    messages = []
    if item is None:
        cooldown_seconds += PENALTY_NOT_FOUND
        errors.append(f"Item not found: +{PENALTY_NOT_FOUND}s CD")
    else:
        if player.wearItem(item):
            messages.append(f"You wear {item.name}")
        else:
            messages.append(f"You cannot wear {item.name}")
    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return player_api_response(player, cooldown_seconds, errors=errors, messages=messages)


@api_view(["POST"])
def remove(request):
    player = request.user.player
    data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    alias = data['name']
    print("DO WE GET HERE???")
    item = player.removeItem(alias)
    cooldown_seconds = get_cooldown(player, 0.5)
    errors = []
    messages = []
    if item is None:
        cooldown_seconds += PENALTY_NOT_FOUND
        errors.append(f"Item not found: +{PENALTY_NOT_FOUND}s CD")
    else:
        messages.append(f"You remove {item.name}")
    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return player_api_response(player, cooldown_seconds, errors=errors, messages=messages)



@api_view(["POST"])
def change_name(request):
    player = request.user.player
    data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    cooldown_seconds = get_cooldown(player, 2.0)
    errors = []
    messages = []
    if player.currentRoom != NAME_CHANGE_ROOM_ID:
        cooldown_seconds += 5 * PENALTY_NOT_FOUND
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.save()
        errors.append(f"Name changer not found: +{5 * PENALTY_NOT_FOUND}")
    elif "name" not in data:
        messages.append(f"Arrr, ye' be wantin' to change yer name? I can take care of ye' fer... {NAME_CHANGE_PRICE} gold.")
        messages.append(f"(include 'name':'<NEW_NAME>' in the request)")
    elif "confirm" not in data or data["confirm"].lower() != "aye":
        messages.append(f"Arrr, ye' be wantin' to change yer name? I can take care of ye' fer... {NAME_CHANGE_PRICE} gold.")
        messages.append(f"(include 'confirm':'aye' to change yer name)")
    elif player.gold < NAME_CHANGE_PRICE:
        cooldown_seconds += PENALTY_CANT_AFFORD
        messages.append(f"Ye' don't have enough gold.")
        errors.append(f"Cannot afford: +{PENALTY_CANT_AFFORD}")
    else:
        new_name = data['name']
        oldname = player.name
        player.name = new_name
        player.has_rename = True
        player.gold -= NAME_CHANGE_PRICE
        try:
            player.save()
        except:
            player.name = oldname
            player.gold += NAME_CHANGE_PRICE
            errors.append(f"ERROR: That name is taken.")
        else:
            messages.append(f"You have changed your name to {new_name}.")
            messages.append(f"'Ere's a tip from Pirate Ry: If you find a shrine, try prayin'. Ye' never know who may be listenin'.")
    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)




@api_view(["POST"])
def pray(request):
    player = request.user.player

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    cooldown_seconds = get_cooldown(player, 5.0)
    errors = []
    messages = []
    currentRoom = player.currentRoom
    shrine_rooms = [FLIGHT_SHRINE_ROOM_ID, DASH_SHRINE_ROOM_ID, CARRY_SHRINE_ROOM_ID, WARP_SHRINE_ROOM_ID, RECALL_SHRINE_ROOM_ID]
    if (currentRoom in shrine_rooms) and not player.has_rename:
        cooldown_seconds += PENALTY_BLASPHEMY
        errors.append(f"One with no name is unworthy to pray here: +{PENALTY_BLASPHEMY}s")
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.save()
    elif player.currentRoom == WARP_SHRINE_ROOM_ID:
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.can_warp = True
        player.save()
        messages.append(f"Your feel your body flicker between realities.")
    elif player.currentRoom == FLIGHT_SHRINE_ROOM_ID:
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.can_fly = True
        player.save()
        messages.append(f"You notice your body starts to hover above the ground.")
    elif currentRoom == DASH_SHRINE_ROOM_ID:
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.can_dash = True
        player.save()
        messages.append(f"You feel a mysterious power and speed coiling in your legs.")
    elif currentRoom == CARRY_SHRINE_ROOM_ID:
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.can_carry = True
        player.save()
        messages.append(f"You sense a ghostly presence beside you, eager to ease your burden.")
    elif currentRoom == RECALL_SHRINE_ROOM_ID:
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.can_recall = True
        player.save()
        messages.append(f"You recall your place of origin so vividly that you're almost there.")
    else:
        cooldown_seconds += PENALTY_BLASPHEMY
        player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
        player.save()
        errors.append(f"You cannot pray here: +{PENALTY_BLASPHEMY}s")
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)





@api_view(["POST"])
def fly(request):
    player = request.user.player
    data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    dirs={"n": "north", "s": "south", "e": "east", "w": "west"}
    reverse_dirs = {"n": "south", "s": "north", "e": "west", "w": "east"}
    direction = data['direction']
    room = player.room()
    nextRoomID = None
    cooldown_seconds = get_cooldown(player, 1.0)
    errors = []
    messages = []
    if direction == "n":
        nextRoomID = room.n_to
    elif direction == "s":
        nextRoomID = room.s_to
    elif direction == "e":
        nextRoomID = room.e_to
    elif direction == "w":
        nextRoomID = room.w_to
    if not player.can_fly:
        cooldown_seconds += PENALTY_BLASPHEMY
        errors.append(f"You cannot fly: +{PENALTY_BLASPHEMY}s CD")
    elif nextRoomID is not None and nextRoomID >= 0:
        nextRoom = Room.objects.get(id=nextRoomID)
        player.currentRoom=nextRoomID
        messages.append(f"You have flown {dirs[direction]}.")
        elevation_change = player.room().elevation - room.elevation
        if player.strength <= player.encumbrance:
            messages.append(f"Flying while Heavily Encumbered: +200% CD")
            cooldown_seconds *= 3
        elif elevation_change < 0:
            messages.append(f"Downhill Flight Bonus: Instant CD")
            cooldown_seconds = 1.0
        elif nextRoom.terrain == "CAVE":
            messages.append(f"You bump your head on the cave ceiling: +{PENALTY_CAVE_FLY}s CD")
            cooldown_seconds += PENALTY_CAVE_FLY
        else:
            messages.append(f"Flight Bonus: -10% CD")
            cooldown_seconds *= 0.9
        if nextRoom.terrain == "TRAP":
            messages.append(f"It's a trap!: +{PENALTY_TRAP}s CD")
            cooldown_seconds += PENALTY_TRAP
        if 'next_room_id' in data:
            if data['next_room_id'].isdigit() and int(data['next_room_id']) == nextRoomID:
                messages.append(f"Wise Explorer: -50% CD")
                cooldown_seconds /= 2
            else:
                messages.append(f"Foolish Explorer: +50% CD")
                cooldown_seconds *= 1.5
        if nextRoomID == DONUT_ROOM_ID:
            messages.append('Grumpy Tommy welcomes you to the shop and says, "What do you want? I have a raid in 15 minutes."')
        # if nextRoom.terrain == "MOUNTAIN" and len(Player.objects.filter(id=1)) > 0:
        #     pusher.trigger(f'p-channel-{Player.objects.get(id=1).uuid}', u'broadcast', {'message':f'{player.name} has flown {dirs[direction]} to room {nextRoom.id}.'})
        player.move_log = f"{player.move_log};f{direction}{nextRoomID}"
        player.num_moves += 1
    else:
        cooldown_seconds += PENALTY_CANNOT_MOVE_THAT_WAY
        errors.append(f"You cannot move that way: +{PENALTY_CANNOT_MOVE_THAT_WAY}s CD")
    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)



@api_view(["POST"])
def dash(request):
    player = request.user.player
    data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    dirs={"n": "north", "s": "south", "e": "east", "w": "west"}
    reverse_dirs = {"n": "south", "s": "north", "e": "west", "w": "east"}
    direction = data['direction']
    room_ids = data['next_room_ids'].split(",")
    room_int_ids = [r for r in room_ids if r.isdigit()]
    num_rooms = data['num_rooms']
    cooldown_seconds = get_cooldown(player, 1.0)
    errors = []
    messages = []
    if not player.can_dash:
        cooldown_seconds += PENALTY_BLASPHEMY
        errors.append(f"You cannot dash: +{PENALTY_BLASPHEMY}s CD")
    elif not (num_rooms.isdigit() and int(num_rooms) == len(room_ids) and len(room_int_ids) == int(num_rooms)):
        cooldown_seconds += PENALTY_BAD_DASH
        errors.append(f"Malformed Dash: +{PENALTY_BAD_DASH}s CD")
    else:
        for room_id in room_int_ids:
            room = player.room()
            if direction == "n":
                nextRoomID = room.n_to
            elif direction == "s":
                nextRoomID = room.s_to
            elif direction == "e":
                nextRoomID = room.e_to
            elif direction == "w":
                nextRoomID = room.w_to
            else:
                cooldown_seconds += PENALTY_BAD_DASH
                errors.append(f"Bad Dash: +{PENALTY_BAD_DASH}s CD")
            if int(nextRoomID) == int(room_id):
                player.currentRoom = nextRoomID
                cooldown_seconds += 0.5
                messages.append(f"You have dashed to room {nextRoomID}.")

                elevation_change = player.room().elevation - room.elevation
                if player.strength <= player.encumbrance:
                    messages.append(f"Dashing while Heavily Encumbered: +1s CD")
                    cooldown_seconds += 1
                if elevation_change < 0:
                    messages.append(f"Downhill Dash Bonus: Instant CD")
                    cooldown_seconds -= 0.5
                elif elevation_change > 0:
                    messages.append(f"Uphill Dash Penalty: +0.5s")
                    cooldown_seconds += 0.5
            else:
                cooldown_seconds += PENALTY_BAD_DASH
                errors.append(f"Bad Dash: +{PENALTY_BAD_DASH}s CD")
                break
        if player.room().terrain == "TRAP":
            messages.append(f"It's a trap!: +{PENALTY_TRAP}s CD")
            cooldown_seconds += PENALTY_TRAP

    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)




@api_view(["POST"])
def carry(request):
    player = request.user.player
    data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    alias = data['name']
    room = player.room()
    item = player.findItemByAlias(alias)
    cooldown_seconds = get_cooldown(player, 0.1)
    errors = []
    messages = []
    if not player.can_carry:
        cooldown_seconds += PENALTY_BLASPHEMY
        errors.append(f"There's no one around to carry that: +{PENALTY_BLASPHEMY}s CD")

    elif item is None:
        cooldown_seconds += PENALTY_NOT_FOUND
        errors.append(f"Item not found: +{PENALTY_NOT_FOUND}s CD")
    else:
        messages.append(f"You hand {item.name} to Glasowyn's Ghost")
        player.carried_item = item.id

    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)




@api_view(["POST"])
def warp(request):
    player = request.user.player

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    room = player.room()

    cooldown_seconds = get_cooldown(player, 1.0)
    errors = []
    messages = []

    if player.currentRoom >= 500:
        nextRoomID = player.currentRoom - 500
    else:
        nextRoomID = player.currentRoom + 500

    if not player.can_warp:
        cooldown_seconds += PENALTY_BLASPHEMY
        errors.append(f"You cannot warp: +{PENALTY_BLASPHEMY}s CD")
    elif player.bodywear == 0 or player.footwear == 0:
        cooldown_seconds += PENALTY_BLASPHEMY
        errors.append(f"No shirt, no shoes, no warp: +{PENALTY_BLASPHEMY}s CD")
    elif nextRoomID is not None and nextRoomID >= 0:
        player.currentRoom=nextRoomID
        messages.append(f"You have warped to an alternate dimension.")
    else:
        cooldown_seconds += PENALTY_CANNOT_MOVE_THAT_WAY
        errors.append(f"You cannot warp that way: +{PENALTY_CANNOT_MOVE_THAT_WAY}s CD")
    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)



@api_view(["POST"])
def recall(request):
    player = request.user.player

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    cooldown_seconds = get_cooldown(player, 1.0)
    errors = []
    messages = []

    if not player.can_recall:
        cooldown_seconds += PENALTY_BLASPHEMY
        errors.append(f"You cannot recall: +{PENALTY_BLASPHEMY}s CD")
    else:
        player.currentRoom=0
        messages.append(f"You have been recalled to your point of origin.")
    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)


@api_view(["POST"])
def receive(request):
    player = request.user.player
    # data = json.loads(request.body)

    cooldown_error = check_cooldown_error(player)
    if cooldown_error is not None:
        return cooldown_error

    cooldown_seconds = get_cooldown(player, 0.1)
    errors = []
    messages = []

    if not player.can_carry:
        cooldown_seconds += PENALTY_BLASPHEMY
        errors.append(f"There's no one around to receive from: +{PENALTY_BLASPHEMY}s CD")
    else:

        try:
            item = Item.objects.get(id=player.carried_item)
        except Item.DoesNotExist:
            errors.append(f"Glasowyn is not carrying anything: +{PENALTY_BLASPHEMY}s CD")
            cooldown_seconds += PENALTY_BLASPHEMY
        else:
            if item.player != player:
                errors.append(f"Glasowyn is not carrying that: +{PENALTY_BLASPHEMY}s CD")
                cooldown_seconds += PENALTY_BLASPHEMY
            else:
                player.carried_item = 0
                messages.append(f"You receive {item.name} from Glasowyn's Ghost")

    player.cooldown = timezone.now() + timedelta(0,cooldown_seconds)
    player.save()
    return api_response(player, cooldown_seconds, errors=errors, messages=messages)



# @api_view(["POST"])
# def create_world(request):
#     if request.user.id != 1:
#             return JsonResponse({'message':"ERROR"}, safe=True)

#     roomGraph = {869: [(46, 62), {'e': 807}], 944: [(46, 64), {'e': 893}], 952: [(47, 59), {'e': 943}], 927: [(47, 60), {'n': 864}], 864: [(47, 61), {'n': 807, 's': 927}], 807: [(47, 62), {'n': 856, 's': 864, 'e': 797, 'w': 869}], 856: [(47, 63), {'s': 807}], 893: [(47, 64), {'e': 819, 'w': 944}], 973: [(47, 65), {'n': 981, 'e': 850}], 981: [(47, 66), {'s': 973}], 943: [(48, 59), {'n': 892, 'w': 952}], 892: [(48, 60), {'n': 812, 's': 943}], 812: [(48, 61), {'n': 797, 's': 892}], 797: [(48, 62), {'s': 812, 'e': 744, 'w': 807}], 725: [(48, 63), {'e': 685}], 819: [(48, 64), {'e': 767, 'w': 893}], 850: [(48, 65), {'n': 954, 'e': 796, 'w': 973}], 954: [(48, 66), {'s': 850}], 994: [(49, 57), {'e': 918}], 942: [(49, 59), {'n': 871}], 871: [(49, 60), {'s': 942, 'e': 783}], 843: [(49, 61), {'e': 742}], 744: [(49, 62), {'n': 685, 'w': 797}], 685: [(49, 63), {'n': 767, 's': 744, 'e': 681, 'w': 725}], 767: [(49, 64), {'n': 796, 's': 685, 'w': 819}], 796: [(49, 65), {'s': 767, 'w': 850}], 862: [(49, 66), {'n': 878, 'e': 861}], 878: [(49, 67), {'s': 862}], 918: [(50, 57), {'n': 933, 'e': 857, 'w': 994}], 933: [(50, 58), {'s': 918}], 846: [(50, 59), {'e': 763}], 783: [(50, 60), {'e': 714, 'w': 871}], 742: [(50, 61), {'e': 698, 'w': 843}], 710: [(50, 62), {'e': 692}], 681: [(50, 63), {'e': 628, 'w': 685}], 781: [(50, 64), {'n': 787, 'e': 671}], 787: [(50, 65), {'n': 861, 's': 781}], 861: [(50, 66), {'n': 930, 's': 787, 'w': 862}], 930: [(50, 67), {'s': 861}], 951: [(51, 53), {'e': 903}], 978: [(51, 54), {'e': 852}], 989: [(51, 55), {'n': 875}], 875: [(51, 56), {'n': 857, 's': 989}], 857: [(51, 57), {'s': 875, 'e': 766, 'w': 918}], 826: [(51, 58), {'n': 763}], 763: [(51, 59), {'s': 826, 'e': 722, 'w': 846}], 714: [(51, 60), {'n': 698, 'w': 783}], 698: [(51, 61), {'n': 692, 's': 714, 'w': 742}], 692: [(51, 62), {'s': 698, 'e': 620, 'w': 710}], 628: [(51, 63), {'n': 671, 'e': 616, 'w': 681}], 671: [(51, 64), {'s': 628, 'w': 781}], 701: [(51, 65), {'e': 647}], 803: [(51, 66), {'n': 834, 'e': 666}], 834: [(51, 67), {'n': 905, 's': 803}], 905: [(51, 68), {'n': 977, 's': 834}], 977: [(51, 69), {'s': 905}], 991: [(51, 70), {'e': 990}], 884: [(52, 52), {'e': 881}], 903: [(52, 53), {'n': 852, 'w': 951}], 852: [(52, 54), {'s': 903, 'e': 791, 'w': 978}], 882: [(52, 55), {'e': 870}], 931: [(52, 56), {'n': 766}], 766: [(52, 57), {'s': 931, 'e': 755, 'w': 857}], 752: [(52, 58), {'e': 608}], 722: [(52, 59), {'e': 606, 'w': 763}], 708: [(52, 60), {'e': 705}], 660: [(52, 61), {'n': 620}], 620: [(52, 62), {'n': 616, 's': 660, 'w': 692}], 616: [(52, 63), {'n': 638, 's': 620, 'e': 613, 'w': 628}], 638: [(52, 64), {'n': 647, 's': 616}], 647: [(52, 65), {'n': 666, 's': 638, 'w': 701}], 666: [(52, 66), {'n': 833, 's': 647, 'e': 729, 'w': 803}], 833: [(52, 67), {'n': 900, 's': 666}], 900: [(52, 68), {'n': 928, 's': 833}], 928: [(52, 69), {'s': 900}], 990: [(52, 70), {'e': 921, 'w': 991}], 987: [(52, 73), {'e': 916}], 998: [(53, 50), {'e': 948}], 898: [(53, 51), {'n': 881}], 881: [(53, 52), {'s': 898, 'e': 867, 'w': 884}], 855: [(53, 53), {'n': 791}], 791: [(53, 54), {'s': 855, 'e': 715, 'w': 852}], 870: [(53, 55), {'n': 765, 'w': 882}], 765: [(53, 56), {'s': 870, 'e': 693}], 755: [(53, 57), {'e': 630, 'w': 766}], 608: [(53, 58), {'n': 606, 'w': 752}], 606: [(53, 59), {'s': 608, 'e': 580, 'w': 722}], 705: [(53, 60), {'n': 657, 'w': 708}], 657: [(53, 61), {'s': 705, 'e': 597}], 614: [(53, 62), {'e': 581}], 613: [(53, 63), {'e': 575, 'w': 616}], 624: [(53, 64), {'n': 689, 'e': 611}], 689: [(53, 65), {'s': 624}], 729: [(53, 66), {'n': 731, 'w': 666}], 731: [(53, 67), {'s': 729}], 886: [(53, 68), {'e': 880}], 921: [(53, 70), {'e': 911, 'w': 990}], 993: [(53, 72), {'n': 916}], 916: [(53, 73), {'s': 993, 'e': 895, 'w': 987}], 899: [(54, 49), {'e': 873}], 948: [(54, 50), {'e': 837, 'w': 998}], 842: [(54, 51), {'e': 774}], 867: [(54, 52), {'e': 788, 'w': 881}], 817: [(54, 53), {'e': 690}], 715: [(54, 54), {'e': 702, 'w': 791}], 694: [(54, 55), {'n': 693}], 693: [(54, 56), {'s': 694, 'e': 640, 'w': 765}], 630: [(54, 57), {'e': 607, 'w': 755}], 615: [(54, 58), {'e': 569}], 580: [(54, 59), {'e': 568, 'w': 606}], 626: [(54, 60), {'n': 597}], 597: [(54, 61), {'s': 626, 'e': 596, 'w': 657}], 581: [(54, 62), {'e': 566, 'w': 614}], 575: [(54, 63), {'e': 547, 'w': 613}], 611: [(54, 64), {'n': 656, 'e': 605, 'w': 624}], 656: [(54, 65), {'n': 727, 's': 611}], 727: [(54, 66), {'n': 759, 's': 656}], 759: [(54, 67), {'n': 880, 's': 727}], 880: [(54, 68), {'s': 759, 'w': 886}], 828: [(54, 69), {'e': 747}], 911: [(54, 70), {'e': 839, 'w': 921}], 949: [(54, 71), {'e': 887}], 845: [(54, 72), {'n': 895, 'e': 838}], 895: [(54, 73), {'s': 845, 'w': 916}], 959: [(55, 47), {'e': 922}], 914: [(55, 48), {'n': 873}], 873: [(55, 49), {'s': 914, 'e': 863, 'w': 899}], 837: [(55, 50), {'e': 761, 'w': 948}], 774: [(55, 51), {'e': 704, 'w': 842}], 788: [(55, 52), {'e': 661, 'w': 867}], 690: [(55, 53), {'e': 653, 'w': 817}], 702: [(55, 54), {'e': 639, 'w': 715}], 636: [(55, 55), {'e': 634}], 640: [(55, 56), {'n': 607, 'w': 693}], 607: [(55, 57), {'s': 640, 'e': 572, 'w': 630}], 569: [(55, 58), {'e': 559, 'w': 615}], 568: [(55, 59), {'n': 573, 'e': 532, 'w': 580}], 573: [(55, 60), {'s': 568}], 596: [(55, 61), {'n': 566, 'w': 597}], 566: [(55, 62), {'s': 596, 'e': 562, 'w': 581}], 547: [(55, 63), {'e': 537, 'w': 575}], 605: [(55, 64), {'n': 679, 'e': 548, 'w': 611}], 679: [(55, 65), {'s': 605}], 697: [(55, 66), {'e': 592}], 683: [(55, 67), {'n': 713, 'e': 641}], 713: [(55, 68), {'n': 747, 's': 683}], 747: [(55, 69), {'n': 839, 's': 713, 'w': 828}], 839: [(55, 70), {'s': 747, 'w': 911}], 887: [(55, 71), {'e': 840, 'w': 949}], 838: [(55, 72), {'n': 851, 'e': 805, 'w': 845}], 851: [(55, 73), {'n': 940, 's': 838}], 940: [(55, 74), {'s': 851}], 964: [(56, 46), {'n': 922}], 922: [(56, 47), {'n': 913, 's': 964, 'w': 959}], 913: [(56, 48), {'n': 863, 's': 922}], 863: [(56, 49), {'n': 761, 's': 913, 'w': 873}], 761: [(56, 50), {'s': 863, 'e': 716, 'w': 837}], 704: [(56, 51), {'e': 691, 'w': 774}], 661: [(56, 52), {'n': 653, 'w': 788}], 653: [(56, 53), {'n': 639, 's': 661, 'w': 690}], 639: [(56, 54), {'n': 634, 's': 653, 'w': 702}], 634: [(56, 55), {'n': 621, 's': 639, 'w': 636}], 621: [(56, 56), {'n': 572, 's': 634}], 572: [(56, 57), {'n': 559, 's': 621, 'w': 607}], 559: [(56, 58), {'s': 572, 'e': 530, 'w': 569}], 532: [(56, 59), {'n': 553, 'e': 513, 'w': 568}], 553: [(56, 60), {'n': 593, 's': 532}], 593: [(56, 61), {'s': 553}], 562: [(56, 62), {'e': 535, 'w': 566}], 537: [(56, 63), {'e': 527, 'w': 547}], 548: [(56, 64), {'n': 655, 'e': 546, 'w': 605}], 655: [(56, 65), {'s': 548}], 592: [(56, 66), {'e': 587, 'w': 697}], 641: [(56, 67), {'n': 663, 'e': 594, 'w': 683}], 663: [(56, 68), {'s': 641}], 730: [(56, 69), {'e': 688}], 792: [(56, 70), {'e': 745}], 840: [(56, 71), {'e': 750, 'w': 887}], 805: [(56, 72), {'e': 776, 'w': 838}], 894: [(56, 73), {'n': 935, 'e': 777}], 935: [(56, 74), {'n': 957, 's': 894}], 957: [(56, 75), {'s': 935}], 947: [(57, 46), {'n': 941}], 941: [(57, 47), {'n': 860, 's': 947}], 860: [(57, 48), {'n': 836, 's': 941}], 836: [(57, 49), {'n': 716, 's': 860}], 716: [(57, 50), {'n': 691, 's': 836, 'w': 761}], 691: [(57, 51), {'n': 677, 's': 716, 'w': 704}], 677: [(57, 52), {'n': 654, 's': 691}], 654: [(57, 53), {'n': 632, 's': 677}], 632: [(57, 54), {'n': 599, 's': 654}], 599: [(57, 55), {'s': 632, 'e': 586}], 589: [(57, 56), {'n': 577}], 577: [(57, 57), {'n': 530, 's': 589}], 530: [(57, 58), {'s': 577, 'e': 526, 'w': 559}], 513: [(57, 59), {'n': 550, 'e': 510, 'w': 532}], 550: [(57, 60), {'n': 570, 's': 513}], 570: [(57, 61), {'s': 550}], 535: [(57, 62), {'e': 528, 'w': 562}], 527: [(57, 63), {'e': 516, 'w': 537}], 546: [(57, 64), {'n': 557, 'e': 541, 'w': 548}], 557: [(57, 65), {'s': 546}], 587: [(57, 66), {'n': 594, 'e': 558, 'w': 592}], 594: [(57, 67), {'n': 649, 's': 587, 'e': 622, 'w': 641}], 649: [(57, 68), {'s': 594}], 688: [(57, 69), {'n': 745, 'e': 668, 'w': 730}], 745: [(57, 70), {'s': 688, 'w': 792}], 750: [(57, 71), {'n': 776, 'e': 743, 'w': 840}], 776: [(57, 72), {'n': 777, 's': 750, 'w': 805}], 777: [(57, 73), {'s': 776, 'e': 785, 'w': 894}], 983: [(58, 46), {'n': 975}], 975: [(58, 47), {'n': 938, 's': 983}], 938: [(58, 48), {'n': 859, 's': 975}], 859: [(58, 49), {'n': 749, 's': 938}], 749: [(58, 50), {'n': 719, 's': 859, 'e': 822}], 719: [(58, 51), {'n': 707, 's': 749, 'e': 800}], 707: [(58, 52), {'n': 670, 's': 719}], 670: [(58, 53), {'n': 619, 's': 707}], 619: [(58, 54), {'n': 586, 's': 670}], 586: [(58, 55), {'n': 564, 's': 619, 'w': 599}], 564: [(58, 56), {'n': 538, 's': 586}], 538: [(58, 57), {'n': 526, 's': 564}], 526: [(58, 58), {'s': 538, 'e': 524, 'w': 530}], 510: [(58, 59), {'n': 517, 'e': 509, 'w': 513}], 517: [(58, 60), {'s': 510}], 555: [(58, 61), {'n': 528}], 528: [(58, 62), {'n': 516, 's': 555, 'w': 535}], 516: [(58, 63), {'s': 528, 'e': 511, 'w': 527}], 541: [(58, 64), {'n': 543, 'e': 512, 'w': 546}], 543: [(58, 65), {'s': 541}], 558: [(58, 66), {'e': 551, 'w': 587}], 622: [(58, 67), {'w': 594}], 738: [(58, 68), {'n': 668}], 668: [(58, 69), {'n': 706, 's': 738, 'e': 643, 'w': 688}], 706: [(58, 70), {'n': 743, 's': 668}], 743: [(58, 71), {'n': 760, 's': 706, 'w': 750}], 760: [(58, 72), {'s': 743}], 785: [(58, 73), {'w': 777}], 934: [(58, 74), {'n': 945, 'e': 811}], 945: [(58, 75), {'n': 967, 's': 934}], 967: [(58, 76), {'s': 945}], 906: [(59, 48), {'n': 872}], 872: [(59, 49), {'n': 822, 's': 906, 'e': 968}], 822: [(59, 50), {'s': 872, 'w': 749}], 800: [(59, 51), {'w': 719}], 809: [(59, 52), {'n': 699}], 699: [(59, 53), {'n': 625, 's': 809}], 625: [(59, 54), {'n': 590, 's': 699}], 590: [(59, 55), {'n': 565, 's': 625}], 565: [(59, 56), {'n': 545, 's': 590}], 545: [(59, 57), {'n': 524, 's': 565}], 524: [(59, 58), {'n': 509, 's': 545, 'w': 526}], 509: [(59, 59), {'s': 524, 'e': 502, 'w': 510}], 501: [(59, 60), {'e': 500}], 523: [(59, 61), {'e': 504}], 529: [(59, 62), {'e': 506}], 511: [(59, 63), {'n': 512, 'e': 507, 'w': 516}], 512: [(59, 64), {'n': 534, 's': 511, 'w': 541}], 534: [(59, 65), {'n': 551, 's': 512}], 551: [(59, 66), {'n': 591, 's': 534, 'w': 558}], 591: [(59, 67), {'n': 627, 's': 551}], 627: [(59, 68), {'n': 643, 's': 591}], 643: [(59, 69), {'n': 676, 's': 627, 'w': 668}], 676: [(59, 70), {'n': 726, 's': 643, 'e': 686}], 726: [(59, 71), {'n': 773, 's': 676, 'e': 746}], 773: [(59, 72), {'n': 789, 's': 726}], 789: [(59, 73), {'s': 773, 'e': 795}], 811: [(59, 74), {'e': 804, 'w': 934}], 968: [(60, 49), {'w': 872}], 849: [(60, 50), {'n': 814, 'e': 955}], 814: [(60, 51), {'n': 757, 's': 849}], 757: [(60, 52), {'n': 695, 's': 814}], 695: [(60, 53), {'n': 669, 's': 757, 'e': 696}], 669: [(60, 54), {'n': 584, 's': 695}], 584: [(60, 55), {'n': 571, 's': 669}], 571: [(60, 56), {'n': 561, 's': 584}], 561: [(60, 57), {'n': 508, 's': 571}], 508: [(60, 58), {'n': 502, 's': 561}], 502: [(60, 59), {'n': 500, 's': 508, 'e': 505, 'w': 509}], 500: [(60, 60), {'n': 504, 's': 502, 'e': 503, 'w': 501}], 504: [(60, 61), {'n': 506, 's': 500, 'e': 544, 'w': 523}], 506: [(60, 62), {'n': 507, 's': 504, 'e': 531, 'w': 529}], 507: [(60, 63), {'n': 514, 's': 506, 'e': 518, 'w': 511}], 514: [(60, 64), {'n': 521, 's': 507, 'e': 515}], 521: [(60, 65), {'n': 522, 's': 514}], 522: [(60, 66), {'n': 536, 's': 521}], 536: [(60, 67), {'n': 658, 's': 522}], 658: [(60, 68), {'n': 678, 's': 536, 'e': 672}], 678: [(60, 69), {'s': 658, 'e': 703}], 686: [(60, 70), {'w': 676}], 746: [(60, 71), {'n': 771, 'w': 726}], 771: [(60, 72), {'s': 746, 'e': 801}], 795: [(60, 73), {'n': 804, 'w': 789}], 804: [(60, 74), {'n': 971, 's': 795, 'e': 970, 'w': 811}], 971: [(60, 75), {'s': 804}], 988: [(61, 48), {'n': 936}], 936: [(61, 49), {'s': 988, 'e': 888}], 955: [(61, 50), {'w': 849}], 784: [(61, 51), {'n': 753}], 753: [(61, 52), {'n': 696, 's': 784, 'e': 775}], 696: [(61, 53), {'s': 753, 'w': 695}], 673: [(61, 54), {'e': 648}], 588: [(61, 55), {'n': 574}], 574: [(61, 56), {'n': 567, 's': 588}], 567: [(61, 57), {'n': 554, 's': 574}], 554: [(61, 58), {'s': 567, 'e': 542}], 505: [(61, 59), {'e': 525, 'w': 502}], 503: [(61, 60), {'w': 500}], 544: [(61, 61), {'e': 552, 'w': 504}], 531: [(61, 62), {'w': 506}], 518: [(61, 63), {'e': 519, 'w': 507}], 515: [(61, 64), {'n': 576, 'w': 514}], 576: [(61, 65), {'n': 582, 's': 515, 'e': 578}], 582: [(61, 66), {'n': 642, 's': 576, 'e': 644}], 642: [(61, 67), {'s': 582}], 672: [(61, 68), {'w': 658}], 703: [(61, 69), {'n': 709, 'e': 733, 'w': 678}], 709: [(61, 70), {'n': 736, 's': 703, 'e': 712}], 736: [(61, 71), {'s': 709, 'e': 786}], 801: [(61, 72), {'w': 771}], 915: [(61, 73), {'e': 889}], 970: [(61, 74), {'w': 804}], 888: [(62, 49), {'e': 832, 'w': 936}], 985: [(62, 50), {'e': 827}], 823: [(62, 51), {'n': 775, 'e': 824}], 775: [(62, 52), {'s': 823, 'e': 790, 'w': 753}], 735: [(62, 53), {'n': 648}], 648: [(62, 54), {'n': 600, 's': 735, 'w': 673}], 600: [(62, 55), {'n': 556, 's': 648, 'e': 610}], 556: [(62, 56), {'n': 549, 's': 600, 'e': 598}], 549: [(62, 57), {'n': 542, 's': 556}], 542: [(62, 58), {'n': 525, 's': 549, 'w': 554}], 525: [(62, 59), {'n': 560, 's': 542, 'e': 533, 'w': 505}], 560: [(62, 60), {'s': 525, 'e': 602}], 552: [(62, 61), {'e': 604, 'w': 544}], 583: [(62, 62), {'n': 519, 'e': 595}], 519: [(62, 63), {'n': 563, 's': 583, 'e': 520, 'w': 518}], 563: [(62, 64), {'s': 519}], 578: [(62, 65), {'w': 576}], 644: [(62, 66), {'n': 664, 'w': 582}], 664: [(62, 67), {'n': 680, 's': 644}], 680: [(62, 68), {'s': 664}], 733: [(62, 69), {'e': 740, 'w': 703}], 712: [(62, 70), {'e': 739, 'w': 709}], 786: [(62, 71), {'n': 798, 'e': 961, 'w': 736}], 798: [(62, 72), {'n': 889, 's': 786}], 889: [(62, 73), {'n': 919, 's': 798, 'e': 923, 'w': 915}], 919: [(62, 74), {'s': 889}], 932: [(63, 48), {'n': 832, 'e': 950}], 832: [(63, 49), {'n': 827, 's': 932, 'e': 844, 'w': 888}], 827: [(63, 50), {'n': 824, 's': 832, 'e': 904, 'w': 985}], 824: [(63, 51), {'s': 827, 'w': 823}], 790: [(63, 52), {'e': 835, 'w': 775}], 779: [(63, 53), {'n': 732}], 732: [(63, 54), {'n': 610, 's': 779}], 610: [(63, 55), {'s': 732, 'w': 600}], 598: [(63, 56), {'e': 659, 'w': 556}], 540: [(63, 57), {'n': 539, 'e': 585}], 539: [(63, 58), {'n': 533, 's': 540}], 533: [(63, 59), {'s': 539, 'w': 525}], 602: [(63, 60), {'e': 612, 'w': 560}], 604: [(63, 61), {'w': 552}], 595: [(63, 62), {'w': 583}], 520: [(63, 63), {'n': 579, 'e': 603, 'w': 519}], 579: [(63, 64), {'n': 601, 's': 520}], 601: [(63, 65), {'n': 617, 's': 579, 'e': 629}], 617: [(63, 66), {'n': 645, 's': 601}], 645: [(63, 67), {'s': 617}], 770: [(63, 68), {'n': 740}], 740: [(63, 69), {'s': 770, 'e': 751, 'w': 733}], 739: [(63, 70), {'w': 712}], 961: [(63, 71), {'w': 786}], 923: [(63, 73), {'w': 889}], 950: [(64, 48), {'w': 932}], 844: [(64, 49), {'w': 832}], 904: [(64, 50), {'e': 976, 'w': 827}], 926: [(64, 51), {'e': 890}], 835: [(64, 52), {'e': 883, 'w': 790}], 816: [(64, 53), {'n': 723}], 723: [(64, 54), {'n': 665, 's': 816}], 665: [(64, 55), {'n': 659, 's': 723, 'e': 700}], 659: [(64, 56), {'s': 665, 'e': 754, 'w': 598}], 585: [(64, 57), {'e': 682, 'w': 540}], 651: [(64, 58), {'n': 637, 'e': 674}], 637: [(64, 59), {'n': 612, 's': 651, 'e': 650}], 612: [(64, 60), {'s': 637, 'e': 635, 'w': 602}], 623: [(64, 61), {'n': 609, 'e': 633}], 609: [(64, 62), {'n': 603, 's': 623, 'e': 652}], 603: [(64, 63), {'n': 618, 's': 609, 'w': 520}], 618: [(64, 64), {'s': 603, 'e': 631}], 629: [(64, 65), {'n': 684, 'e': 667, 'w': 601}], 684: [(64, 66), {'n': 718, 's': 629, 'e': 687}], 718: [(64, 67), {'n': 734, 's': 684, 'e': 782}], 734: [(64, 68), {'s': 718}], 751: [(64, 69), {'n': 810, 'e': 794, 'w': 740}], 810: [(64, 70), {'s': 751}], 976: [(65, 50), {'w': 904}], 890: [(65, 51), {'n': 883, 'w': 926}], 883: [(65, 52), {'s': 890, 'e': 891, 'w': 835}], 831: [(65, 53), {'n': 813}], 813: [(65, 54), {'n': 700, 's': 831, 'e': 858}], 700: [(65, 55), {'s': 813, 'w': 665}], 754: [(65, 56), {'w': 659}], 682: [(65, 57), {'w': 585}], 674: [(65, 58), {'e': 778, 'w': 651}], 650: [(65, 59), {'e': 758, 'w': 637}], 635: [(65, 60), {'e': 720, 'w': 612}], 633: [(65, 61), {'e': 711, 'w': 623}], 652: [(65, 62), {'w': 609}], 646: [(65, 63), {'n': 631, 'e': 662}], 631: [(65, 64), {'s': 646, 'w': 618}], 667: [(65, 65), {'e': 717, 'w': 629}], 687: [(65, 66), {'e': 806, 'w': 684}], 782: [(65, 67), {'w': 718}], 896: [(65, 68), {'n': 794}], 794: [(65, 69), {'n': 802, 's': 896, 'e': 841, 'w': 751}], 802: [(65, 70), {'n': 830, 's': 794, 'e': 865}], 830: [(65, 71), {'s': 802}], 969: [(66, 51), {'n': 891, 'e': 984}], 891: [(66, 52), {'s': 969, 'w': 883}], 907: [(66, 53), {'n': 858, 'e': 925}], 858: [(66, 54), {'s': 907, 'e': 879, 'w': 813}], 854: [(66, 55), {'n': 825}], 825: [(66, 56), {'n': 815, 's': 854}], 815: [(66, 57), {'n': 778, 's': 825}], 778: [(66, 58), {'s': 815, 'w': 674}], 758: [(66, 59), {'w': 650}], 720: [(66, 60), {'w': 635}], 711: [(66, 61), {'n': 721, 'e': 724, 'w': 633}], 721: [(66, 62), {'s': 711}], 662: [(66, 63), {'n': 675, 'w': 646}], 675: [(66, 64), {'s': 662, 'e': 768}], 717: [(66, 65), {'e': 820, 'w': 667}], 806: [(66, 66), {'n': 909, 'w': 687}], 909: [(66, 67), {'n': 910, 's': 806, 'e': 917}], 910: [(66, 68), {'s': 909}], 841: [(66, 69), {'e': 962, 'w': 794}], 865: [(66, 70), {'n': 924, 'e': 897, 'w': 802}], 924: [(66, 71), {'s': 865, 'e': 979}], 984: [(67, 51), {'w': 969}], 965: [(67, 52), {'n': 925, 'e': 980}], 925: [(67, 53), {'s': 965, 'w': 907}], 879: [(67, 54), {'w': 858}], 997: [(67, 55), {'n': 877}], 877: [(67, 56), {'n': 818, 's': 997, 'e': 937}], 818: [(67, 57), {'n': 780, 's': 877, 'e': 829}], 780: [(67, 58), {'n': 772, 's': 818}], 772: [(67, 59), {'n': 748, 's': 780}], 748: [(67, 60), {'n': 724, 's': 772, 'e': 764}], 724: [(67, 61), {'n': 737, 's': 748, 'e': 728, 'w': 711}], 737: [(67, 62), {'n': 756, 's': 724}], 756: [(67, 63), {'s': 737, 'e': 868}], 768: [(67, 64), {'w': 675}], 820: [(67, 65), {'n': 866, 'e': 876, 'w': 717}], 866: [(67, 66), {'s': 820}], 917: [(67, 67), {'e': 929, 'w': 909}], 963: [(67, 68), {'n': 962, 'e': 982}], 962: [(67, 69), {'s': 963, 'w': 841}], 897: [(67, 70), {'e': 986, 'w': 865}], 979: [(67, 71), {'w': 924}], 999: [(68, 51), {'n': 980}], 980: [(68, 52), {'s': 999, 'w': 965}], 937: [(68, 56), {'w': 877}], 829: [(68, 57), {'e': 912, 'w': 818}], 799: [(68, 58), {'n': 769, 'e': 908}], 769: [(68, 59), {'n': 764, 's': 799, 'e': 847}], 764: [(68, 60), {'s': 769, 'e': 848, 'w': 748}], 728: [(68, 61), {'n': 741, 'e': 762, 'w': 724}], 741: [(68, 62), {'s': 728, 'e': 793}], 868: [(68, 63), {'n': 885, 'w': 756}], 885: [(68, 64), {'s': 868}], 876: [(68, 65), {'w': 820}], 929: [(68, 67), {'w': 917}], 982: [(68, 68), {'n': 995, 'w': 963}], 995: [(68, 69), {'s': 982, 'e': 996}], 986: [(68, 70), {'w': 897}], 912: [(69, 57), {'w': 829}], 908: [(69, 58), {'w': 799}], 847: [(69, 59), {'w': 769}], 848: [(69, 60), {'e': 853, 'w': 764}], 762: [(69, 61), {'e': 874, 'w': 728}], 793: [(69, 62), {'n': 808, 'e': 901, 'w': 741}], 808: [(69, 63), {'n': 821, 's': 793, 'e': 920}], 821: [(69, 64), {'n': 974, 's': 808, 'e': 953}], 974: [(69, 65), {'s': 821}], 996: [(69, 69), {'w': 995}], 972: [(70, 58), {'n': 958}], 958: [(70, 59), {'n': 853, 's': 972}], 853: [(70, 60), {'s': 958, 'e': 939, 'w': 848}], 874: [(70, 61), {'e': 902, 'w': 762}], 901: [(70, 62), {'w': 793}], 920: [(70, 63), {'e': 946, 'w': 808}], 953: [(70, 64), {'w': 821}], 939: [(71, 60), {'w': 853}], 902: [(71, 61), {'e': 956, 'w': 874}], 946: [(71, 63), {'w': 920}], 956: [(72, 61), {'e': 960, 'w': 902}], 960: [(73, 61), {'e': 966, 'w': 956}], 966: [(74, 61), {'e': 992, 'w': 960}], 992: [(75, 61), {'w': 966}]}

#     rooms = {}
#     for i in range(500, 1000):
#         rooms[i] = Room(title=f"Darkness", description=f"You are standing on grass and surrounded by darkness.", coordinates=f"({roomGraph[i][0][0]},{roomGraph[i][0][1]})",id=i)
#         rooms[i].save()

#     for roomID in roomGraph:
#         room = rooms[roomID]
#         if 'n' in roomGraph[roomID][1]:
#             rooms[roomID].connectRooms(rooms[roomGraph[roomID][1]['n']], 'n')
#         if 's' in roomGraph[roomID][1]:
#             rooms[roomID].connectRooms(rooms[roomGraph[roomID][1]['s']], 's')
#         if 'e' in roomGraph[roomID][1]:
#             rooms[roomID].connectRooms(rooms[roomGraph[roomID][1]['e']], 'e')
#         if 'w' in roomGraph[roomID][1]:
#             rooms[roomID].connectRooms(rooms[roomGraph[roomID][1]['w']], 'w')

#     return JsonResponse({'message':"SUCCESS"}, safe=True)





@api_view(["GET"])
def player_state(request):
    player = request.user.player
    if not player.is_tl:
        response = JsonResponse({'ERROR':'BAD_REQUEST'}, safe=True)
    else:
        # TODO: Make Dynamic
        g = Group.objects.last()
        all_players = Player.objects.filter(group=g)
        players = {}
        for player in all_players:
            player_data = {}
            player_data["real_name"] = player.user.username
            player_data["name"] = player.name
            player_data["has_rename"] = player.has_rename
            player_data["has_mined"] = player.has_mined
            player_data["gold"] = player.gold
            player_data["snitches"] = player.snitches
            player_data["lambda_coins"] = Blockchain.get_user_balance(player.id)
            player_data["room_id"] = player.currentRoom
            player_data["can_fly"] = player.can_fly
            player_data["can_dash"] = player.can_dash
            player_data["can_carry"] = player.can_carry
            players[player.id] = player_data
        response = JsonResponse({'players':players}, safe=True)
    return response










