from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .metrics import snapshot
from .models import Batch
from .permissions import BatchPermissions, visible_batches
from .services import create_batch


class BatchSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source="owner.username", read_only=True)
    count = serializers.IntegerField(min_value=1, max_value=24, write_only=True)
    duration = serializers.IntegerField(min_value=1, max_value=12, write_only=True)
    fail_first = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = Batch
        fields = ("id", "title", "owner", "mode", "count", "duration", "fail_first", "created_at", "published_at")
        read_only_fields = ("created_at", "published_at")

    def create(self, validated_data):
        return create_batch(**validated_data)

    def update(self, instance, validated_data):
        if set(validated_data) != {"title"}:
            raise serializers.ValidationError("Тек title өрісін өзгертуге болады.")
        instance.title = validated_data["title"]
        instance.save(update_fields=["title"])
        return instance


class BatchViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
    mixins.UpdateModelMixin, viewsets.GenericViewSet,
):
    serializer_class = BatchSerializer
    permission_classes = (BatchPermissions,)
    queryset = Batch.objects.select_related("owner")
    http_method_names = ["get", "post", "patch", "head", "options"]

    def list(self, request, *args, **kwargs):
        self.queryset = visible_batches(request.user, self.get_queryset())
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get"], url_path="status")
    def status(self, request, pk=None):
        return Response(snapshot(self.get_object()), headers={"Cache-Control": "no-store"})


@api_view(["GET"])
def me(request):
    return Response({
        "user": request.user.username, "role": request.user.role,
        "auth": type(request.successful_authenticator).__name__,
    })
