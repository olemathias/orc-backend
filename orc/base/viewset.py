from rest_framework import viewsets, permissions
from django.db.models import Q


class OrcViewSet(viewsets.ModelViewSet):
    """
    Extends ModelViewSet
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filter the queryset
        """
        queryset = super().get_queryset()
        query = None

        if not hasattr(self, 'allow_filters'):
            return queryset

        for key in self.allow_filters:
            val = self.request.query_params.get(key)
            if val is None:
                continue
            if query is None:
                query = Q(**{key: val})
            else:
                query = query | Q(**{key: val})
        if query:
            queryset = queryset.filter(query)

        return queryset