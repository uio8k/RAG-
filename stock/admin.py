from django.contrib import admin
from .models import (
    User, Financials, DailyPrice, 
    Simulation, Simulation_Transaction, 
    Simulation_NAV_History, Simulation_Holding, TradeOrder,
    Industry, AShareStock, AShareRealtimePrice
)

# --- Industry Administration ---
@admin.register(Industry)
class IndustryAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Industry model.
    Displays industry name and its parent sector.
    """
    list_display = ('name', 'sector')
    search_fields = ('name', 'sector')

# --- Stock Administration (统一股票模型，替代原 Company) ---
@admin.register(AShareStock)
class AShareStockAdmin(admin.ModelAdmin):
    """
    统一股票管理（替代原 Company）
    """
    list_display = ('symbol', 'name', 'industry', 'market', 'market_type', 'current_price', 'total_market_cap', 'updated_at')
    search_fields = ('symbol', 'name')
    list_filter = ('market', 'market_type', 'industry')

# --- Financials Administration ---
@admin.register(Financials)
class FinancialsAdmin(admin.ModelAdmin):
    """
    Admin configuration for Financials.
    Note: Calculated fields (ratios) are defined in models.py as @property.
    """
    list_display = (
        'symbol', 
        'report_date', 
        'current_ratio_display', 
        'quick_ratio_display', 
        'debt_ratio_display'
    )
    list_filter = ('symbol', 'report_date')

    # Helper methods to display @property from models in the admin list
    def current_ratio_display(self, obj):
        return obj.current_ratio
    current_ratio_display.short_description = 'Current Ratio'

    def quick_ratio_display(self, obj):
        return obj.quick_ratio
    quick_ratio_display.short_description = 'Quick Ratio'

    def debt_ratio_display(self, obj):
        return f"{obj.debt_asset_ratio}%"
    debt_ratio_display.short_description = 'Debt-to-Asset %'

# --- Daily Price Administration ---
@admin.register(DailyPrice)
class DailyPriceAdmin(admin.ModelAdmin):
    """
    Admin configuration for historical stock prices.
    """
    list_display = ('symbol', 'trade_date', 'close_price', 'volume')
    list_filter = ('symbol', 'trade_date')
    search_fields = ('symbol__symbol',)

# --- Generic Registration for Simulation & User Models ---
admin.site.register(User)
admin.site.register(Simulation)
admin.site.register(Simulation_Transaction)
admin.site.register(Simulation_NAV_History)
admin.site.register(Simulation_Holding)
admin.site.register(TradeOrder)

# --- A-Share Realtime Price Administration ---
@admin.register(AShareRealtimePrice)
class AShareRealtimePriceAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name', 'price', 'change_pct', 'pe_ratio', 'volume', 'fetched_at')
    search_fields = ('symbol', 'name')
    list_filter = ('fetched_at',)