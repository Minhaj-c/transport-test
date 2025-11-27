from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages


def web_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)

            # Redirect based on role
            if user.is_superuser:
                return redirect("/admin/")
            if user.role == "admin":
                return redirect("/admin-dashboard/")
            if user.role == "zonal_admin":
                return redirect("/zonal-admin/")
            if user.role == "driver":
                return redirect("/")  # add driver page later
            if user.role == "passenger":
                return redirect("/")

            return redirect("/")

        else:
            messages.error(request, "Invalid email or password")

    return render(request, "login.html")


def web_logout(request):
    logout(request)
    return redirect("/login/")
