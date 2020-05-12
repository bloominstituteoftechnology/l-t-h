from django.contrib import admin
from .models import Block, Transaction, ChainDifficulty

admin.site.register((Block, Transaction, ChainDifficulty))
