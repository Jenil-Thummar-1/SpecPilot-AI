from django.contrib import admin
from apps.memory.models import Conversation, Session, MemoryEntry

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('project', 'session_id', 'created_at')

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'is_active', 'created_at')
    list_filter = ('is_active',)

@admin.register(MemoryEntry)
class MemoryEntryAdmin(admin.ModelAdmin):
    list_display = ('session', 'memory_type', 'role', 'importance_score', 'created_at')
    list_filter = ('memory_type', 'role')
    search_fields = ('content',)
