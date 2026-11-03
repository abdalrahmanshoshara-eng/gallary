"""Response serializers for core endpoints (used for the OpenAPI schema and output)."""

from rest_framework import serializers


class HealthCheckSerializer(serializers.Serializer):
    name = serializers.CharField()
    status = serializers.ChoiceField(choices=["ok", "degraded", "error"])
    latency_ms = serializers.FloatField()
    detail = serializers.CharField(allow_blank=True)


class LivenessSerializer(serializers.Serializer):
    status = serializers.CharField()
    server_time = serializers.DateTimeField()


class ReadinessSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ready", "not_ready"])
    server_time = serializers.DateTimeField()
    checks = HealthCheckSerializer(many=True)
