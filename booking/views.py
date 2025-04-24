from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from datetime import datetime
from django.db.models import Sum
from .models import Room, Customer, Booking


def home(request):
    rooms = Room.objects.filter(is_available=True)
    return render(request, 'booking/home.html', {'rooms': rooms})


def booking(request):
    return render(request, 'booking/booking_form.html')


def get_available_room(room_type, check_in, check_out):
    rooms = Room.objects.filter(room_type=room_type)
    for room in rooms:
        overlapping = Booking.objects.filter(
            room=room,
            check_in_date__lt=check_out,
            check_out_date__gt=check_in
        )
        if not overlapping.exists():
            return room
    return None


def submit_booking(request):
    if request.method == "POST":
        name = request.POST.get('name')
        email = request.POST.get('email')
        room_type = request.POST.get('room_type')
        check_in = request.POST.get('check_in_date')
        check_out = request.POST.get('check_out_date')

        try:
            guests = int(request.POST.get('guests') or 1)
        except ValueError:
            guests = 1

        # Return with form filled if missing required fields
        if not name or not email or not room_type:
            return render(request, 'booking/booking_form.html', {
                "error": "Namn, e-post och rumstyp krävs.",
                "prefill": request.POST
            })

        # Convert dates safely
        try:
            check_in_date = datetime.strptime(check_in, "%Y-%m-%d").date()
            check_out_date = datetime.strptime(check_out, "%Y-%m-%d").date()
        except ValueError:
            return render(request, 'booking/booking_form.html', {
                "error": "Felaktigt datumformat.",
                "prefill": request.POST
            })

        # Validate date order
        if check_out_date <= check_in_date:
            return render(request, 'booking/booking_form.html', {
                "error": "❌ Utcheckningsdatum måste vara efter incheckningsdatum.",
                "prefill": request.POST
            })

        # Find available room
        room = get_available_room(room_type, check_in_date, check_out_date)
        if not room:
            return render(request, 'booking/booking_form.html', {
                "error": "❌ Alla rum av denna typ är upptagna för valda datum.",
                "prefill": request.POST
            })

        # Create or update customer
        customer, created = Customer.objects.get_or_create(email=email)
        if created or not customer.name:
            customer.name = name
            customer.save()

        # Calculate price and save booking
        nights = (check_out_date - check_in_date).days
        total_price = room.price * nights

        booking = Booking.objects.create(
            customer=customer,
            room=room,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            total_price=total_price,
            guests=guests
        )

        return redirect('booking_confirmation', booking_id=booking.id)

    return redirect('home')


def booking_confirmation(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    return render(request, 'booking/confirmation.html', {'booking': booking})


def gallery(request):
    return render(request, 'booking/gallery.html')


def admin_dashboard(request):
    bookings = Booking.objects.all()
    income = bookings.aggregate(Sum('total_price'))['total_price__sum'] or 0
    return render(request, 'booking/admin_dashboard.html', {
        'bookings': bookings,
        'income': income
    })


def edit_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    if request.method == 'POST':
        booking.check_in_date = request.POST.get('check_in_date')
        booking.check_out_date = request.POST.get('check_out_date')
        booking.total_price = request.POST.get('total_price')
        booking.save()
        return redirect('admin_dashboard')

    return render(request, 'booking/edit_booking.html', {'booking': booking})


def delete_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    room = booking.room
    room.is_available = True
    room.save()
    booking.delete()
    return redirect('admin_dashboard')


def room_search(request):
    rooms = Room.objects.filter(is_available=True)

    check_in = request.GET.get('check_in')
    check_out = request.GET.get('check_out')
    guests = request.GET.get('guests')
    room_type = request.GET.get('room_type')
    capacity = request.GET.get('capacity')
    max_price = request.GET.get('max_price')

    try:
        guests = int(guests) if guests else None
    except ValueError:
        guests = None

    try:
        capacity = int(capacity) if capacity else None
    except ValueError:
        capacity = None

    try:
        max_price = float(max_price) if max_price else None
    except ValueError:
        max_price = None

    if room_type:
        rooms = rooms.filter(room_type__icontains=room_type)
    if capacity:
        rooms = rooms.filter(capacity__gte=capacity)
    if max_price:
        rooms = rooms.filter(price__lte=max_price)

    if check_in and check_out:
        try:
            check_in_date = datetime.strptime(check_in, "%Y-%m-%d").date()
            check_out_date = datetime.strptime(check_out, "%Y-%m-%d").date()
            if check_in_date < check_out_date:
                rooms = rooms.exclude(
                    booking__check_in_date__lt=check_out_date,
                    booking__check_out_date__gt=check_in_date
                )
        except ValueError:
            pass

    if guests:
        rooms = rooms.filter(capacity__gte=guests)

    return render(request, 'booking/room_search.html', {'rooms': rooms})


def get_latest_bookings(request):
    bookings = Booking.objects.all().values(
        'id', 'customer__name', 'room__room_number', 'room__room_type',
        'check_in_date', 'check_out_date', 'total_price'
    )
    return JsonResponse({'bookings': list(bookings)})
