"""
PreInforms API Views
"""

from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from datetime import timedelta

from .models import PreInform
from .serializers import PreInformSerializer, PreInformCreateSerializer
from schedules.models import Schedule


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication that skips CSRF checks.

    This is useful for native/mobile apps that use cookies for auth
    but cannot easily handle CSRF tokens.
    """
    def enforce_csrf(self, request):
        return  # Simply do nothing instead of raising a CSRF error


@method_decorator(csrf_exempt, name='dispatch')
class PreInformCreateView(generics.CreateAPIView):
    """
    API endpoint for users to submit pre-informs
    
    🔥 AUTO-ACCEPTANCE with smart validation for scalability
    
    POST /api/preinforms/
    {
        "route": 1,
        "date_of_travel": "2024-12-25",
        "desired_time": "09:00",
        "boarding_stop": 5,
        "dropoff_stop": 12,
        "passenger_count": 2
    }
    """
    queryset = PreInform.objects.all()
    serializer_class = PreInformCreateSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def perform_create(self, serializer):
        """
        Set the user to currently logged-in user
        Status defaults to 'noted' (auto-accepted) in model
        """
        serializer.save(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """
        Create pre-inform with smart validation
        
        🔥 VALIDATIONS (prevent abuse):
        - Max 10 passengers per pre-inform
        - Future dates only
        - Rate limiting: 10 per hour
        - Valid stop sequence (dropoff after boarding)
        """
        
        # 🔥 VALIDATION 1: Reasonable passenger count
        passenger_count = request.data.get('passenger_count', 1)
        try:
            passenger_count = int(passenger_count)
            if passenger_count > 10:
                return Response(
                    {
                        'success': False,
                        'error': 'Maximum 10 passengers per pre-inform'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            if passenger_count < 1:
                return Response(
                    {
                        'success': False,
                        'error': 'Minimum 1 passenger required'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {
                    'success': False,
                    'error': 'Invalid passenger count'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 🔥 VALIDATION 2: Future date only
        from datetime import date
        date_of_travel = request.data.get('date_of_travel')
        if date_of_travel:
            try:
                travel_date = date.fromisoformat(str(date_of_travel))
                if travel_date < date.today():
                    return Response(
                        {
                            'success': False,
                            'error': 'Cannot pre-inform for past dates'
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except (ValueError, TypeError):
                pass  # Let serializer handle invalid date format
        
        # 🔥 VALIDATION 3: Rate limiting (prevent spam)
        recent_count = PreInform.objects.filter(
            user=request.user,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if recent_count >= 10:
            return Response(
                {
                    'success': False,
                    'error': 'Maximum 10 pre-informs per hour. Please try again later.'
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        # 🔥 VALIDATION 4: Check stop sequence (if both stops provided)
        from routes.models import Stop
        boarding_stop_id = request.data.get('boarding_stop')
        dropoff_stop_id = request.data.get('dropoff_stop')
        
        if boarding_stop_id and dropoff_stop_id:
            try:
                boarding_stop = Stop.objects.get(id=boarding_stop_id)
                dropoff_stop = Stop.objects.get(id=dropoff_stop_id)
                
                if dropoff_stop.sequence <= boarding_stop.sequence:
                    return Response(
                        {
                            'success': False,
                            'error': 'Drop-off stop must be after boarding stop on the route'
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Stop.DoesNotExist:
                pass  # Let serializer handle invalid stop IDs
        
        # All validations passed - create pre-inform
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Return full details with nested objects
        output_serializer = PreInformSerializer(serializer.instance)
        
        return Response(
            {
                'success': True,
                'message': '✅ Pre-inform submitted and accepted automatically!',
                'info': 'Your travel plan has been noted. Buses will be assigned based on demand.',
                'data': output_serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class PreInformListView(generics.ListAPIView):
    """
    API endpoint to list pre-informs
    
    GET /api/preinforms/
    Optional params:
    - user_id: Filter by user
    - route_id: Filter by route
    - date: Filter by travel date
    - status: Filter by status
    """
    serializer_class = PreInformSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = PreInform.objects.all().select_related(
            'user', 'route', 'boarding_stop', 'dropoff_stop'
        )
        
        # Admin can see all, users see only their own
        if self.request.user.role != 'admin':
            queryset = queryset.filter(user=self.request.user)
        
        # Apply filters
        user_id = self.request.query_params.get('user_id')
        route_id = self.request.query_params.get('route_id')
        date = self.request.query_params.get('date')
        status_param = self.request.query_params.get('status')
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if route_id:
            queryset = queryset.filter(route_id=route_id)
        if date:
            queryset = queryset.filter(date_of_travel=date)
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        return queryset.order_by('-created_at')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_preinforms_view(request):
    """
    Get pre-informs for currently logged-in user
    
    GET /api/preinforms/my/
    """
    preinforms = PreInform.objects.filter(
        user=request.user
    ).select_related('route', 'boarding_stop', 'dropoff_stop').order_by('-created_at')
    
    serializer = PreInformSerializer(preinforms, many=True)
    return Response(serializer.data)


@csrf_exempt
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def cancel_preinform_view(request, preinform_id):
    """
    Cancel a pre-inform
    
    DELETE /api/preinforms/<id>/cancel/
    
    🔥 UPDATED: Can cancel 'noted' pre-informs (not just 'pending')
    """
    try:
        preinform = PreInform.objects.get(id=preinform_id, user=request.user)
        
        # Allow cancellation if status is 'noted' (not completed/cancelled)
        if preinform.status in ['completed', 'cancelled']:
            return Response(
                {'error': f'Cannot cancel {preinform.status} pre-informs'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        preinform.status = 'cancelled'
        preinform.save()
        
        return Response({
            'success': True,
            'message': 'Pre-inform cancelled successfully'
        })
        
    except PreInform.DoesNotExist:
        return Response(
            {'error': 'Pre-inform not found'},
            status=status.HTTP_404_NOT_FOUND
        )


def preinform_form_page(request):
    """
    Serve the pre-inform form page
    """
    schedule_id = request.GET.get('schedule_id')
    try:
        schedule = Schedule.objects.get(id=schedule_id)
        context = {'schedule': schedule}
        return render(request, 'preinform_form.html', context)
    except Schedule.DoesNotExist:
        return render(request, 'error.html', {'message': 'Schedule not found'})