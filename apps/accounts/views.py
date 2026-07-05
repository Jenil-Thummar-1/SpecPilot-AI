import logging
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.accounts.models import User, Profile

logger = logging.getLogger('specpilot.ai')

def login_view(request):
    """
    Renders login portal and processes authentication.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            logger.info(f"User '{username}' logged in successfully.")
            messages.success(request, f"Welcome back, {username}!")
            return redirect('dashboard')
        else:
            logger.warning(f"Failed login attempt for user '{username}'")
            messages.error(request, "Invalid username or password.")
            
    return render(request, 'accounts/login.html')

def register_view(request):
    """
    Handles registration creation for new users.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        
        # Simple validations
        if not username or not email or not password:
            messages.error(request, "All fields are required.")
            return render(request, 'accounts/register.html')
            
        if password != password_confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, 'accounts/register.html')
            
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return render(request, 'accounts/register.html')
            
        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user)
            logger.info(f"New user '{username}' registered and logged in.")
            messages.success(request, f"Account created! Welcome, {username}!")
            return redirect('dashboard')
        except Exception as e:
            logger.error(f"Error during registration: {str(e)}")
            messages.error(request, "Registration failed. Please check inputs.")
            
    return render(request, 'accounts/register.html')

def logout_view(request):
    """
    Terminates the user's active session.
    """
    username = request.user.username if request.user.is_authenticated else "Anonymous"
    logout(request)
    logger.info(f"User '{username}' logged out.")
    messages.info(request, "You have been logged out.")
    return redirect('landing')

@login_required
def settings_view(request):
    """
    Handles user preferences settings: custom API key, light/dark themes, and bio profiles.
    """
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        api_key = request.POST.get('api_key_override', '').strip()
        theme = request.POST.get('theme_preference', 'dark')
        bio = request.POST.get('bio', '').strip()
        
        email = request.POST.get('email', '').strip()
        
        # Save standard email
        if email:
            request.user.email = email
            request.user.save()

        profile.api_key_override = api_key if api_key else None
        profile.theme_preference = theme
        profile.bio = bio
        profile.save()

        messages.success(request, "System preferences saved successfully!")
        return redirect('settings')

    return render(request, 'accounts/settings.html', {'profile': profile})
