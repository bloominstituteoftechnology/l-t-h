from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from django.utils import timezone
from util.ls8 import generate_easy_ls8, generate_medium_ls8
import json
import uuid
import random
import math


class Group(models.Model):
    name = models.CharField(max_length=20, unique=True)
    cooldown = models.IntegerField(default=100)
    vision_enabled = models.BooleanField(default=False)
    can_mine = models.BooleanField(default=False)
    catchup_enabled = models.BooleanField(default=False)
    has_clear_well = models.BooleanField(default=False)

class Team(models.Model):
    name = models.CharField(max_length=20, unique=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True)
    tl = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='+', null=True)

class Room(models.Model):
    title = models.CharField(max_length=50, default="DEFAULT TITLE")
    description = models.CharField(max_length=500, default="DEFAULT DESCRIPTION")
    coordinates = models.CharField(max_length=32, default="()")
    n_to = models.IntegerField(blank=True, null=True)
    s_to = models.IntegerField(blank=True, null=True)
    e_to = models.IntegerField(blank=True, null=True)
    w_to = models.IntegerField(blank=True, null=True)
    elevation = models.IntegerField(default=0)
    terrain = models.CharField(max_length=32, default="NORMAL")
    def connectRooms(self, destinationRoom, direction):
        destinationRoomID = destinationRoom.id
        try:
            destinationRoom = Room.objects.get(id=destinationRoomID)
        except Room.DoesNotExist:
            print("That room does not exist")
        else:
            if direction == "n":
                self.n_to = destinationRoomID
            elif direction == "s":
                self.s_to = destinationRoomID
            elif direction == "e":
                self.e_to = destinationRoomID
            elif direction == "w":
                self.w_to = destinationRoomID
            else:
                print("Invalid direction")
                return
            self.save()
    def playerNames(self, currentPlayerID, group):
        return [p.name for p in Player.objects.filter(currentRoom=self.id, group=group, is_tl=False) if p.id != int(currentPlayerID)]
    def playerNamesAll(self, currentPlayerID):
        return [p.name for p in Player.objects.filter(currentRoom=self.id, is_tl=False) if p.id != int(currentPlayerID)]
    def playerUUIDs(self, currentPlayerID, group):
        return [p.uuid for p in Player.objects.filter(currentRoom=self.id, group=group) if p.id != int(currentPlayerID)]
    def addItem(self, item):
        item.room = self
        if item.player is not None:
            p = item.player
            item.player = None
            p.save()
        item.save()
    def findItemByAlias(self, alias, group):
        lower_alias = alias.lower()
        for i in Item.objects.filter(room=self, group=group):
            if lower_alias in i.aliases.split(","):
                return i
        return None
    def findItemAllByAlias(self, alias, group):
        lower_alias = alias.lower()
        for i in Item.objects.filter(room=self):
            if i.itemtype == "SNITCH" and lower_alias in i.aliases.split(","):
                return i
            elif i.group != group:
                continue
            elif lower_alias in i.aliases.split(","):
                return i
        return None
    def findPlayerByName(self, name, group):
        return [p for p in Player.objects.filter(currentRoom=self.id, group=group) if p.name == name.lower()]
    def itemNames(self, group):
        return [i.name for i in Item.objects.filter(room=self, group=group)]
    def itemNamesAll(self, group):
        return [i.name for i in Item.objects.filter(room=self) if i.group != group or i.itemtype == "SNITCH"]
    def exits(self):
        exits = []
        if self.n_to is not None:
            exits.append("n")
        if self.s_to is not None:
            exits.append("s")
        if self.e_to is not None:
            exits.append("e")
        if self.w_to is not None:
            exits.append("w")
        return exits

class Player(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    tl = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='+', null=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=64, unique=True, null=True)
    active = models.BooleanField(default=True)
    has_rename = models.BooleanField(default=False)
    has_mined = models.BooleanField(default=False)
    is_tl = models.BooleanField(default=False)
    description = models.CharField(max_length=140, default=" looks like an ordinary person.")
    currentRoom = models.IntegerField(default=0)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    cooldown = models.DateTimeField(blank=True, auto_now_add=True)
    gold = models.IntegerField(default=0)
    strength = models.IntegerField(default=10)
    speed = models.IntegerField(default=10)
    bodywear = models.IntegerField(default=0)
    footwear = models.IntegerField(default=0)
    encumbrance = models.IntegerField(default=0)
    can_fly = models.BooleanField(default=False)
    can_dash = models.BooleanField(default=False)
    can_carry = models.BooleanField(default=False)
    can_warp = models.BooleanField(default=False)
    can_recall = models.BooleanField(default=False)
    carried_item = models.IntegerField(default=0)
    snitches = models.IntegerField(default=0)
    mining_room = models.IntegerField(default=0)
    mining_puzzle = models.TextField(default="")
    donut_boost = models.DateTimeField(blank=True, auto_now_add=True)
    pizza_power = models.DateTimeField(blank=True, auto_now_add=True)
    num_moves = models.IntegerField(default=0)
    move_log = models.TextField(default="")
    def initialize(self):
        if self.currentRoom == 0:
            self.currentRoom = Room.objects.first().id
            self.save()
    def room(self):
        try:
            return Room.objects.get(id=self.currentRoom)
        except Room.DoesNotExist:
            self.initialize()
            return self.room()
    def in_dark(self):
        return self.currentRoom >= 500
    def addItem(self, item):
        if self.group == item.group:
            item.player = self
            item.room = None
            item.save()
        else:
            return False
    def inventory(self):
        return [i.name for i in Item.objects.filter(player=self) if i.id != self.bodywear and i.id != self.footwear]
    def findItemByAlias(self, alias):
        lower_alias = alias.lower()
        for i in Item.objects.filter(player=self):
            if lower_alias in i.aliases.split(",") and i.id != self.bodywear and i.id != self.footwear:
                return i
        return None
    def wearItem(self, item):
        if item.player is None or item.player.id != self.id or item.group != item.player.group:
            return False
        if item.itemtype == "BODYWEAR":
            self.bodywear = item.id
        elif item.itemtype == "FOOTWEAR":
            self.footwear = item.id
        else:
            return False
        return True
    def getFootwear(self):
        if self.footwear == 0:
            return None
        # Do these need nullchecks?
        return Item.objects.get(id=self.footwear)
    def getBodywear(self):
        if self.bodywear == 0:
            return None
        # Do these need nullchecks?
        return Item.objects.get(id=self.bodywear)
    def removeItem(self, item_alias):
        bodywear = self.getBodywear()
        footwear = self.getFootwear()
        print("HERE!!!!!")
        print(bodywear)
        print(footwear)
        if bodywear is not None:
            if item_alias.lower() in bodywear.aliases.split(","):
                self.bodywear = 0
                return bodywear
        if footwear is not None:
            if item_alias.lower() in footwear.aliases.split(","):
                self.footwear = 0
                return footwear
        return None
    def save(self, *args, **kwargs):
        items = Item.objects.filter(player=self)
        weight = 0
        base_speed = 10
        base_strength = 10
        if self.pizza_power_active():
            base_strength *= 2
        for item in items:
            if item.id != self.carried_item:
                weight += item.weight
            if item.id == self.footwear or item.id == self.bodywear:
                print(item.attributes)
                attr = json.loads(item.attributes)
                if 'SPEED' in attr:
                    base_speed += attr['SPEED']
                if 'STRENGTH' in attr:
                    base_strength += attr['STRENGTH']
        self.encumbrance = weight
        self.speed = base_speed
        self.strength = base_strength
        super(Player, self).save(*args, **kwargs)
    def get_carried_item(self):
        if self.can_carry:
            items = Item.objects.filter(player=self)
            for item in items:
                if item.id == self.carried_item:
                    return item
        return None
    def generate_mining_puzzle(self, difficulty):
        mining_room_id = random.randrange(100, 499)
        ls8_puzzle = "ERROR"
        if difficulty == "MEDIUM":
            ls8_puzzle = generate_medium_ls8(mining_room_id)
        else:
            ls8_puzzle = generate_easy_ls8(mining_room_id)
        self.mining_room = mining_room_id
        self.mining_puzzle = ls8_puzzle
        self.save()
    def sugar_rush_active(self):
        return True
    def pizza_power_active(self):
        return True



@receiver(post_save, sender=User)
def create_user_player(sender, instance, created, **kwargs):
    if created:
        Player.objects.create(user=instance, name=instance.username.lower())
        Token.objects.create(user=instance)
        instance.player.generate_mining_puzzle("EASY")

@receiver(post_save, sender=User)
def save_user_player(sender, instance, **kwargs):
    instance.player.save()



class Item(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, blank=True, null=True)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=20, default="DEFAULT_ITEM")
    description = models.CharField(max_length=200, default="DEFAULT DESCRIPTION")
    weight = models.IntegerField(default=1)
    aliases = models.CharField(max_length=200, default="")
    value = models.IntegerField(default=1)
    itemtype = models.CharField(max_length=20, default="DEFAULT")
    attributes = models.CharField(max_length=1000, default="{}")
    level = models.IntegerField(default=1)
    exp = models.IntegerField(default=0)
    def __str__(self):
        return self.name
    def unsetItem(self):
        self.player = None
        self.room = None
        self.save()
    def resetSnitch(self):
        if self.itemtype != "SNITCH":
            return
        randomDarkID = random.randint(500, 1000)  # Cannot be in 499, Glasowyn's Grave, although that will change with more rooms
        self.player = None
        self.room = Room.objects.get(id=randomDarkID)
        self.save()
    def levelUpAndRespawn(self):
        self.unsetItem()
        randomID = random.randint(2, 498)  # Cannot be in 499, Glasowyn's Grave, although that will change with more rooms
        self.room = Room.objects.get(id=randomID)
        self.exp += 1
        self.level = math.floor(math.log2(self.exp)) + 1
        self.value = self.level * 100
        self.weight = self.level // 2 + 1
        treasure_names = [
            ("tiny treasure", "This is a tiny piece of treasure"),
            ("small treasure", "This is a small piece of treasure"),
            ("shiny treasure", "This is a shiny piece of treasure"),
            ("great treasure", "This is a great pile of treasure"),
            ("amazing treasure", "This is an amazing pile of treasure"),
            ("spectacular treasure", "This is a spectacular pile of treasure"),
            ("dazzling treasure", "This is a dazzling pile of treasure"),
            ("brilliant treasure", "This is a brilliant pile of treasure"),
            ("sparkling treasure" "This is a sparkling bounty of treasure")
        ]
        self.name = treasure_names[min(self.level - 1, len(treasure_names) - 1)][0]
        self.description = treasure_names[min(self.level - 1, len(treasure_names) - 1)][1]
        self.aliases = f"treasure,{self.name}"
        self.itemtype = "TREASURE"
        self.save()






