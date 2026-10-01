from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(required=True)
    finish = serializers.CharField(required=True)
    range_miles = serializers.FloatField(required=False, min_value=50, max_value=1500)
    mpg = serializers.FloatField(required=False, min_value=1, max_value=50)
    starting_fuel_gallons = serializers.FloatField(required=False, min_value=0)
    corridor_miles = serializers.FloatField(required=False, min_value=1, max_value=15)
    geometry = serializers.ChoiceField(required=False, choices=["simplified", "full", "none"])
