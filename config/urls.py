from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from apps.dashboard.views import landing_view

def favicon_view(request):
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<defs>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#4F6BFF"/>
<stop offset="1" stop-color="#17B88A"/>
</linearGradient>
</defs>
<rect width="32" height="32" rx="9" fill="url(#g)"/>
<path d="M10 21 16 9l6 12" stroke="white" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""
    return HttpResponse(svg_content, content_type="image/svg+xml")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('favicon.ico', favicon_view),
    
    # Landing page
    path('', landing_view, name='landing'),
    
    # App modules routing
    path('accounts/', include('apps.accounts.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('projects/', include('apps.projects.urls')),
    path('agents/', include('apps.agents.urls')),
    path('skills/', include('apps.skills.urls')),
    path('memory/', include('apps.memory.urls')),
    path('generator/', include('apps.generator.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
