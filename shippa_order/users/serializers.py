from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from users.models import User, PointsLog


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'points'
        ]
        read_only_fields = [
            'points'
        ]


class PointSerializer(serializers.ModelSerializer):
    points_spent = serializers.IntegerField(default=0)
    points_added = serializers.IntegerField(default=0)

    class Meta:
        model = User
        fields = [
            'points_spent', 'points_added'
        ]

    def to_representation(self, instance):
        return {
            "points": instance.points
        }

    def validate_points_spent(self, value):
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValidationError({
                "points_spent": "points_spent should be a positive integer."
            })

        if value and value < 0:
            raise ValidationError("points_spent should be a positive integer.")

        return value

    def validate_points_added(self, value):
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValidationError({
                "points_added": "points_added should be a positive integer."
            })

        if value and int(value) < 0:
            raise ValidationError("points_added should be a positive integer.")

        return value

    def to_internal_value(self, data):
        data = super().to_internal_value(data)

        points_spent = data.get('points_spent', 0)
        points_added = data.get('points_added', 0)

        if not points_spent and not points_added:
            raise ValidationError(
                {"error": "Either One of 'points_spent' or 'points_added' is required."}
            )

        if points_spent and points_added:
            raise ValidationError(
                {"error": "It is not allowed to add and spend points at the same time."}
            )

        return {
            "points_spent": points_spent,
            "points_added": points_added
        }

    def update(self, instance, validated_data):
        points = instance.points
        points_spent = validated_data.get('points_spent', 0)
        points_added = validated_data.get('points_added', 0)
        if points_spent:
            calculated_points = points - points_spent
        else:
            calculated_points = points + points_added

        if calculated_points < 0:
            raise ValidationError({
                "points": "Not enough points."
            })

        instance.points = calculated_points

        with transaction.atomic():
            instance.save()
            PointsLog(
                user=instance,
                points_spent=points_spent,
                points_added=points_added
            ).save()

        return instance


class PointsLogSerializers(serializers.ModelSerializer):

    class Meta:
        model = PointsLog
        fields = [
            "points_spent", "points_added", "created_at"
        ]


# noinspection PyAbstractClass
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        permission_list = ('superuser', 'staff', 'active')

        user_permission = None
        for permission in permission_list:
            if getattr(user, f"is_{permission}"):
                user_permission = permission
                break

        token['user_level'] = user_permission
        return token
