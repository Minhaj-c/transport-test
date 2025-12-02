from rest_framework import serializers
from .models import PreInform
from routes.serializers import RouteSerializer, StopSerializer  # adjust if names differ


class PreInformCreateSerializer(serializers.ModelSerializer):
  class Meta:
      model = PreInform
      fields = [
          'route',
          'date_of_travel',
          'desired_time',
          'boarding_stop',
          'dropoff_stop',       # 👈 NEW
          'passenger_count',
      ]

  def validate(self, attrs):
      route = attrs['route']
      boarding = attrs['boarding_stop']
      dropoff = attrs.get('dropoff_stop')

      # boarding must be on this route
      if boarding.route_id != route.id:
          raise serializers.ValidationError({
              'boarding_stop': 'Boarding stop does not belong to the selected route.'
          })

      if dropoff is None:
          raise serializers.ValidationError({
              'dropoff_stop': 'Exit stop is required.'
          })

      if dropoff.route_id != route.id:
          raise serializers.ValidationError({
              'dropoff_stop': 'Exit stop does not belong to the selected route.'
          })

      if dropoff.sequence <= boarding.sequence:
          raise serializers.ValidationError({
              'dropoff_stop': 'Exit stop must come AFTER boarding stop on this route.'
          })

      return attrs


class PreInformSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    route_details = RouteSerializer(source='route', read_only=True)
    stop_details = StopSerializer(source='boarding_stop', read_only=True)
    dropoff_stop_details = StopSerializer(source='dropoff_stop', read_only=True)

    class Meta:
        model = PreInform
        fields = [
            'id',
            'user',
            'user_name',
            'route',
            'route_details',
            'date_of_travel',
            'desired_time',
            'boarding_stop',
            'dropoff_stop',           
            'stop_details',
            'dropoff_stop_details',   
            'passenger_count',
            'status',
            'created_at',
        ]
