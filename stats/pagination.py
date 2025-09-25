"""
Advanced pagination classes for Story 18 API Performance Optimization.

Provides cursor-based pagination for high-performance API endpoints
with large datasets and consistent ordering.
"""
from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.response import Response
from django.db.models import F


class OptimizedCursorPagination(CursorPagination):
    """
    High-performance cursor pagination for time-ordered data.
    Ideal for scrobbles and other timestamp-based endpoints.
    """
    page_size = 50
    page_size_query_param = 'limit'
    max_page_size = 200
    ordering = '-timestamp'  # Default ordering by timestamp descending
    cursor_query_param = 'cursor'
    template = 'rest_framework/pagination/numbers.html'

    def get_page_size(self, request):
        """Get page size with validation."""
        if self.page_size_query_param:
            try:
                page_size = int(request.query_params[self.page_size_query_param])
                if page_size < 1:
                    return 1
                elif page_size > self.max_page_size:
                    return self.max_page_size
                return page_size
            except (KeyError, ValueError):
                pass
        return self.page_size

    def get_paginated_response(self, data):
        """Return cursor pagination response with metadata."""
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
            'count': len(data),
        })


class RecentTracksCursorPagination(OptimizedCursorPagination):
    """Optimized cursor pagination for recent tracks endpoint."""
    page_size = 20
    max_page_size = 100
    ordering = '-timestamp'


class ChartDataCursorPagination(OptimizedCursorPagination):
    """Cursor pagination for chart data with date-based ordering."""
    page_size = 100
    max_page_size = 366  # Max days in a year
    ordering = 'period'  # Custom ordering field for chart data


class OptimizedPageNumberPagination(PageNumberPagination):
    """
    Enhanced page number pagination with performance optimizations.
    """
    page_size = 50
    page_size_query_param = 'limit'
    max_page_size = 200
    page_query_param = 'page'

    def get_page_size(self, request):
        """Get page size with validation."""
        if self.page_size_query_param:
            try:
                page_size = int(request.query_params[self.page_size_query_param])
                if page_size < 1:
                    return 1
                elif page_size > self.max_page_size:
                    return self.max_page_size
                return page_size
            except (KeyError, ValueError):
                pass
        return self.page_size

    def get_paginated_response(self, data):
        """Return enhanced pagination response with performance metadata."""
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
            'page_info': {
                'current_page': self.page.number,
                'total_pages': self.page.paginator.num_pages,
                'page_size': len(data),
                'has_next': self.page.has_next(),
                'has_previous': self.page.has_previous(),
            }
        })


class TopItemsPagination(OptimizedPageNumberPagination):
    """Optimized pagination for top artists/albums/tracks with aggregated data."""
    page_size = 25
    max_page_size = 100

    def get_paginated_response(self, data):
        """Return response with period and total scrobbles information."""
        # Access period and total_scrobbles from paginator attributes if available
        period = getattr(self, '_period', 'all')
        total_scrobbles = getattr(self, '_total_scrobbles', 0)

        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
            'period': period,
            'total_scrobbles': total_scrobbles,
            'page_info': {
                'current_page': self.page.number,
                'total_pages': self.page.paginator.num_pages,
                'page_size': len(data),
            }
        })


class HighVolumePagination(OptimizedCursorPagination):
    """
    Specialized pagination for very high volume data.
    Uses cursor pagination with smaller page sizes for consistent performance.
    """
    page_size = 25
    max_page_size = 100
    ordering = '-id'  # Use primary key for consistent ordering

    def get_paginated_response(self, data):
        """Return minimal response for high-volume scenarios."""
        return Response({
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
            'count': len(data),
        })


class DetailViewPagination(OptimizedPageNumberPagination):
    """Pagination for detail views with related data (e.g., track scrobbles)."""
    page_size = 100
    max_page_size = 500

    def get_paginated_response(self, data):
        """Return detailed pagination info for related data."""
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
            'pagination': {
                'current_page': self.page.number,
                'total_pages': self.page.paginator.num_pages,
                'page_size': len(data),
                'has_more': self.page.has_next(),
                'start_index': self.page.start_index(),
                'end_index': self.page.end_index(),
            }
        })


# Pagination class mappings for different endpoint types
PAGINATION_CLASSES = {
    'recent_tracks': RecentTracksCursorPagination,
    'top_items': TopItemsPagination,
    'chart_data': ChartDataCursorPagination,
    'high_volume': HighVolumePagination,
    'detail_view': DetailViewPagination,
    'default': OptimizedPageNumberPagination,
}


def get_pagination_class(endpoint_type='default'):
    """Get appropriate pagination class for endpoint type."""
    return PAGINATION_CLASSES.get(endpoint_type, OptimizedPageNumberPagination)