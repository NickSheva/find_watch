from django.urls import path
from .views import HomePageView, ParseView, ProductListView


urlpatterns = [
    path('', HomePageView.as_view(), name='home'),
    path('parse/', ParseView.as_view(), name='parse_view'),
    # path('parse-progress/', sse_progress, name='parse_progress'),
    path('products/', ProductListView.as_view(), name='product_list'),
    # Добавляем этот путь
]