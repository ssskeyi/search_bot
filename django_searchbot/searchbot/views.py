from django.shortcuts import render, redirect
from django.http import JsonResponse
from .agent import agent_execute as ask
from django.contrib import auth
from django.contrib.auth.models import User
from .models import Chat
from django.utils import timezone

# Create your views here.
def searchbot(request):
    if request.user.is_authenticated:
        chats = Chat.objects.filter(user=request.user)
    else:
        chats = []

    if request.method == 'POST':
        if request.user.is_authenticated:
            message = request.POST.get('message')
            my_history = []
            success, response, my_history = ask(message, chat_history=my_history)
            chat = Chat(user=request.user, message=message, response=response, created_at=timezone.now())
            chat.save()           
        else:
            message = request.POST.get('message')
            response = '请先登录'

        return JsonResponse({'message': message, 'response': response})

    return render(request, 'searchbot.html', {'chats': chats})

def login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = auth.authenticate(request, username=username, password=password)
        if user is not None:
            auth.login(request, user)
            return redirect('searchbot')
        else:
            error_message = '用户名或密码不正确'
            return render(request, 'login.html', {'error_message': error_message})
    return render(request, 'login.html')

def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password1 = request.POST['password1']
        password2 = request.POST['password2']
        
        if password1 == password2:
            try:
                user = User.objects.create_user(username, email, password1)
                user.save()
                auth.login(request, user)
                return redirect('searchbot')
            except:
                error_message = '创建账号失败'
                return render(request, 'register.html', {'error_message': error_message})
        else:
            error_message = '密码不匹配'
            return render(request, 'register.html', {'error_message': error_message})
    return render(request, 'register.html')

def logout(request):
    auth.logout(request)
    return redirect('login')