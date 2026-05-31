from django.urls import path
from . import views

# Global error handlers
handler404 = 'stock.views.custom_404'
handler500 = 'stock.views.custom_500'

urlpatterns = [
    # ==========================================
    # 1. Core Pages
    # ==========================================
    path("", views.index, name="index"),
    path("transactions/", views.transactions_view, name="transactions"),

    # ==========================================
    # 2. Authentication
    # ==========================================
    path("login/", views.login_view, name="login"),
    path('accounts/login/', views.login_view),
    path("register/", views.register_view, name="register"),
    path("guest/", views.guest_login_view, name="guest_login"),
    path("logout/", views.logout_view, name="logout"),
    path("api/current_sim/", views.current_sim),

    # ==========================================
    # 3. Market Data
    # ==========================================
    path("stock/<str:symbol>/", views.stock_detail, name="stock_detail"),
    path("stock/<str:symbol>/financials/", views.stock_financials, name="stock_financials"),
    path("stock/<str:symbol>/history/", views.stock_history_full, name="stock_history"), 

    # ==========================================
    # 4. Exchange Core API
    # ==========================================
    path("api/search/", views.api_search, name="api_search"),
    path("api/v1/search/", views.api_search, name="api_search_v1"),
    path("api/v1/trades/", views.process_transaction, name="process_transaction"),
    path("api/v1/order/cancel/<int:order_id>/", views.cancel_order, name="cancel_order"),
    path("api/v1/indicators/calculate/", views.api_calculate_custom_indicator, name="api_custom_indicator"),
    # AI 助手 API
    path("api/v1/ai/chat/", views.ai_chat_api, name="ai_chat_api"),

    # ==========================================
    # 5. Simulation Control
    # ==========================================
    path("simulation/advance/", views.advance_simulation_date, name="advance_date"),

    # 6. Reports & Documents (New Section)

    path("transaction/pdf/<int:transaction_id>/", views.generate_transaction_pdf, name="generate_transaction_pdf"),
]