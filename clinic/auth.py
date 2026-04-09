"""Custom JWT login logic for the backend.

The mobile app sends `{ email, password }` when logging in.
However, Django/JWT often expects `{ username, password }`.

This serializer/view pair supports BOTH:
- email + password
- username + password

Implementation idea:
If an email is provided, we look up the associated user and populate the
configured `USERNAME_FIELD` before delegating to SimpleJWT's validation.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Allow logging in with either `email`+`password` or `username`+`password`."""

    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TokenObtainPairSerializer normally requires USERNAME_FIELD; relax it.
        if self.username_field in self.fields:
            self.fields[self.username_field].required = False
            self.fields[self.username_field].allow_blank = True

    def validate(self, attrs):
        # Accept either email or username.
        email = (attrs.get("email") or "").strip()
        username = (attrs.get(self.username_field) or "").strip()

        if not email and not username:
            raise serializers.ValidationError(
                {"detail": "Email or username is required."}
            )

        # If email is provided, translate it into the configured username field.
        if email and not attrs.get(self.username_field):
            User = get_user_model()
            # Use a case-insensitive search so EMAIL@EXAMPLE.COM works.
            user = User.objects.filter(email__iexact=email).only(self.username_field).first()
            if user is not None:
                attrs[self.username_field] = getattr(user, self.username_field)
            else:
                # Fallback: some installations use email as username.
                attrs[self.username_field] = email

        return super().validate(attrs)


class EmailOrUsernameTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailOrUsernameTokenObtainPairSerializer
