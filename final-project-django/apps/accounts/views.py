from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import LoginSerializer, LogoutSerializer, RegisterSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


@extend_schema_view(
    post=extend_schema(
        request=LoginSerializer,
        responses={
            200: inline_serializer(
                name="LoginTokenPair",
                fields={
                    "access": serializers.CharField(),
                    "refresh": serializers.CharField(),
                },
            )
        },
    )
)
class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            if str(token.get(api_settings.USER_ID_CLAIM)) != str(request.user.pk):
                raise serializers.ValidationError(
                    {"refresh": "Not your refresh token."}
                )
            token.blacklist()
        except TokenError as exc:
            raise serializers.ValidationError(
                {"refresh": "Invalid or revoked token."}
            ) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses=inline_serializer(
            name="CurrentUser",
            fields={
                "id": serializers.IntegerField(),
                "email": serializers.EmailField(),
                "display_name": serializers.CharField(),
            },
        )
    )
    def get(self, request):
        return Response(
            {
                "id": request.user.pk,
                "email": request.user.email,
                "display_name": request.user.display_name,
            }
        )
