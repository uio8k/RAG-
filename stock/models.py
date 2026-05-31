from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import Sum, F, Q
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.utils import timezone
import uuid
# ==========================================
# 0. Global Constants
# ==========================================
ZERO = Decimal('0.0000')

# ==========================================
# 1. User Model
# ==========================================
class User(AbstractUser):
    gender = models.CharField(max_length=20, blank=True, null=True)
    account_balance = models.DecimalField(
        max_digits=20, 
        decimal_places=4, 
        default=Decimal('100000.0000')
    )

# ==========================================
# 2. Market Reference Data
# ==========================================
class Industry(models.Model):
    """
    Industry Model
    """
    name = models.CharField(max_length=100, unique=True)
    sector = models.CharField(max_length=100, blank=True, null=True) 
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name
    
# ==========================================
# [DEPRECATED] Company Model - 已替换为 AShareStock
# 保留此模型以兼容旧迁移，不再使用。
# ==========================================
class Company(models.Model):
    symbol = models.CharField(max_length=10, primary_key=True)
    full_name = models.CharField(max_length=255)
    industry = models.ForeignKey(
        Industry, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='companies'
    )
    market_cap = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    trailing_pe = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_sales = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    current_price = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    def __str__(self):
        return self.symbol

class Financials(models.Model):
    symbol = models.ForeignKey('AShareStock', on_delete=models.CASCADE, related_name='financials')
    report_date = models.DateField()
    total_revenue = models.BigIntegerField(null=True, blank=True)
    gross_profit = models.BigIntegerField(null=True, blank=True)
    operating_income = models.BigIntegerField(null=True, blank=True)
    net_income = models.BigIntegerField(null=True, blank=True)
    basic_eps = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    total_assets = models.BigIntegerField(null=True, blank=True)           
    total_liabilities = models.BigIntegerField(null=True, blank=True)      
    current_assets = models.BigIntegerField(null=True, blank=True)         
    current_liabilities = models.BigIntegerField(null=True, blank=True)  
    inventory = models.BigIntegerField(null=True, blank=True, default=0)
    

    @property
    def current_ratio(self):
        """Liquidity: Current Assets / Current Liabilities"""
        if self.current_liabilities and self.current_liabilities != 0:
            return round(self.current_assets / self.current_liabilities, 2)
        return 0

    @property
    def quick_ratio(self):
        """Liquidity: (Current Assets - Inventory) / Current Liabilities"""
        if self.current_liabilities and self.current_liabilities != 0:
            inv = self.inventory if self.inventory else 0
            return round((self.current_assets - inv) / self.current_liabilities, 2)
        return 0

    @property
    def debt_asset_ratio(self):
        """Leverage: (Total Liabilities / Total Assets) * 100"""
        if self.total_assets and self.total_assets != 0:
            return round((self.total_liabilities / self.total_assets) * 100, 2)
        return 0

    @property
    def net_margin(self):
        """Profitability: (Net Income / Total Revenue) * 100"""
        if self.total_revenue and self.total_revenue != 0:
            return round((self.net_income / self.total_revenue) * 100, 2)
        return 0

class DailyPrice(models.Model):
    symbol = models.ForeignKey('AShareStock', on_delete=models.CASCADE, related_name='daily_prices')
    financial_id = models.ForeignKey(Financials, on_delete=models.SET_NULL, null=True, blank=True)
    trade_date = models.DateField()
    open_price = models.DecimalField(max_digits=12, decimal_places=4)
    high_price = models.DecimalField(max_digits=12, decimal_places=4)
    low_price = models.DecimalField(max_digits=12, decimal_places=4)
    close_price = models.DecimalField(max_digits=12, decimal_places=4)
    volume = models.BigIntegerField()

    class Meta:
        indexes = [
            models.Index(fields=['symbol', '-trade_date']),
            models.Index(fields=['trade_date']),
        ]


class GlobalSimulationState(models.Model):
    """
    Global control table to synchronize all users to the same virtual timeline.
    """
    current_global_date = models.DateField(default=timezone.now)
    is_market_open = models.BooleanField(default=True)
    last_step_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Global Simulation State"
        verbose_name_plural = "Global Simulation State"

    def __str__(self):
        return f"Global Virtual Date: {self.current_global_date}"
    

# ==========================================
# 3. Simulation & Portfolio
# ==========================================
class Simulation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        CLOSED = 'CLOSED', 'Closed'

    class Mode(models.TextChoices):
        LIVE = 'LIVE', 'Live Multiplayer'  # Now implies the shared exchange mode
        BACKTEST = 'BACKTEST', 'Private Backtest'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='simulations')
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    
    # This now syncs with GlobalSimulationState.current_global_date for LIVE mode
    current_virtual_date = models.DateField(default=timezone.now)

    initial_cash = models.DecimalField(max_digits=20, decimal_places=4)
    available_cash = models.DecimalField(max_digits=20, decimal_places=4, default=ZERO)

    
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.LIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """
        Overrides the save method to automate ledger initialization.
        When a new simulation is created, we set available_cash = initial_cash
        and create an initial cash flow record for audit purposes.
        """
        # 1. Check if this is a new instance creation
        is_new = self._state.adding 

        if is_new:
            # 2. Sync financial fields with initial_cash on creation
            self.available_cash = self.initial_cash
            

        # 3. Save the Simulation instance first to get an ID
        super().save(*args, **kwargs)

        # 4. Automatically record the initial deposit in the Cash Flow ledger
        if is_new:
            # Local import to prevent circular dependency
            from .models import Simulation_Cash_Flow
            
            Simulation_Cash_Flow.objects.create(
                sim=self,
                change_type=Simulation_Cash_Flow.FlowType.INIT,
                before_balance=Decimal('0.0000'),
                amount=self.initial_cash,
                after_balance=self.initial_cash,
                # Unique request_id for auditing purposes
                request_id=f"AUTO_INIT_{self.id}_{int(timezone.now().timestamp())}"
            )

    @property
    def total_fees(self):
        """
        Aggregates all recorded transaction fees from the cash flow ledger.
        This helps reconcile the gap between Floating PnL and NAV.
        """
        from .models import Simulation_Cash_Flow
        # Summing all negative amounts marked as 'FEE'
        result = self.cash_flows.filter(change_type=Simulation_Cash_Flow.FlowType.FEE).aggregate(models.Sum('amount'))['amount__sum']
        return abs(result) if result else Decimal('0.0000')
    @property
    def total_realized_pnl(self):
        result = self.transactions.aggregate(models.Sum('realized_pnl'))['realized_pnl__sum']
        return result if result else Decimal('0.0000')
    @property
    def market_value(self):

        from .models import Simulation_Holding, DailyPrice
        total = ZERO
        holdings = self.holdings.all()
        for h in holdings:
            price_rec = DailyPrice.objects.filter(
                symbol=h.symbol, 
            trade_date__lte=self.current_virtual_date
            ).order_by('-trade_date').first()
            if price_rec:
                total += h.quantity * price_rec.close_price
        return total

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(available_cash__gte=0),
                name='simulation_cash_non_negative_v2'
            )
        ]


class TradeOrder(models.Model):
    """
    Order Book for peer-to-peer trading.
    """
    class OrderSide(models.TextChoices):
        BUY = 'BUY', 'Buy'
        SELL = 'SELL', 'Sell'

    class OrderStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PARTIAL = 'PARTIAL', 'Partially Filled'
        FILLED = 'FILLED', 'Filled'
        CANCELLED = 'CANCELLED', 'Cancelled'
        EXPIRED = 'EXPIRED', 'Expired'

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sim = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name='orders')
    symbol = models.ForeignKey('AShareStock', on_delete=models.CASCADE)
    
    side = models.CharField(max_length=10, choices=OrderSide.choices)
    price = models.DecimalField(max_digits=12, decimal_places=4)
    quantity = models.IntegerField()
    filled_quantity = models.IntegerField(default=0)
    
    status = models.CharField(max_length=10, choices=OrderStatus.choices, default=OrderStatus.FILLED)
    order_date = models.DateField() # The virtual date when the order was placed
    created_at = models.DateTimeField(auto_now_add=True)
   
    avg_cost_snapshot = models.DecimalField(
        max_digits=18, 
        decimal_places=4, 
        null=True, 
        blank=True,
        default=0
    )

    class Meta:
        indexes = [
            models.Index(fields=['symbol', 'status', 'side', 'price']),
        ]
# ==========================================
# 4. Trading & Auditing
# ==========================================
class Simulation_Transaction(models.Model):
    voucher_no = models.CharField(
        max_length=64, 
       
        db_index=True, 
        null=True, 
        blank=True,
        verbose_name="凭证编号"
    )
    

    digital_signature = models.CharField(
        max_length=100, 
        null=True, 
        blank=True
    )
    class TransType(models.TextChoices):
        BUY = 'BUY', 'Buy'
        SELL = 'SELL', 'Sell'

    sim = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name='transactions')
    symbol = models.ForeignKey('AShareStock', on_delete=models.CASCADE)
    daily_price = models.ForeignKey(DailyPrice, on_delete=models.SET_NULL, null=True)
    trade_date = models.DateField()
    type = models.CharField(max_length=4, choices=TransType.choices)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=4)
    total_amount = models.DecimalField(max_digits=20, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)
    matched_order = models.ForeignKey(TradeOrder, on_delete=models.SET_NULL, null=True, blank=True)
    opponent_order = models.ForeignKey(TradeOrder, on_delete=models.SET_NULL, null=True, blank=True,related_name='counterpart_transactions')
    realized_pnl = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    fees = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0.0000'))

    def save(self, *args, **kwargs):
        
        if not self.voucher_no:
            
            count = Simulation_Transaction.objects.filter(sim=self.sim).count()
            order_number = count + 1
            
            
            self.voucher_no = f"TX-{self.sim.id}-{order_number:04d}"
            
        
        if not self.digital_signature:
            self.digital_signature = uuid.uuid4().hex
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.voucher_no} - {self.symbol_id} ({self.type})"

    
class Simulation_Cash_Flow(models.Model):
    class FlowType(models.TextChoices):
        BUY = 'BUY', 'Purchase'
        SELL = 'SELL', 'Liquidation'
        FEE = 'FEE', 'Commission'
        INIT = 'INIT', 'Initial Deposit'

    sim = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name='cash_flows')
    change_type = models.CharField(max_length=10, choices=FlowType.choices)
    before_balance = models.DecimalField(max_digits=20, decimal_places=4)
    amount = models.DecimalField(max_digits=20, decimal_places=4) # Negative for Buy/Fee
    after_balance = models.DecimalField(max_digits=20, decimal_places=4)
    transaction = models.ForeignKey(Simulation_Transaction, on_delete=models.SET_NULL, null=True, blank=True)
    request_id = models.CharField(max_length=64, unique=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if abs((self.before_balance + self.amount) - self.after_balance) > Decimal('0.0001'):
            raise ValidationError("Cash flow audit failed: balance mismatch.")

# ==========================================
# 5. Inventory & Snapshots
# ==========================================
class Simulation_Holding(models.Model):
    sim = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name='holdings')
    symbol = models.ForeignKey('AShareStock', on_delete=models.CASCADE)
    quantity = models.IntegerField()
    avg_cost = models.DecimalField(max_digits=20, decimal_places=4)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['sim', 'symbol'], name='unique_holding_per_sim')
        ]
        indexes = [
            models.Index(fields=['sim', 'symbol']),
        ]

class Simulation_NAV_History(models.Model):
    sim = models.ForeignKey(Simulation, on_delete=models.CASCADE, related_name='nav_history')
    record_date = models.DateField()
    nav = models.DecimalField(max_digits=20, decimal_places=4)
    cash = models.DecimalField(max_digits=20, decimal_places=4)
    market_value = models.DecimalField(max_digits=20, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        
        return f"{self.sim.name} - {self.record_date}"


# ==========================================
# 6. A-Share Stock Model (统一股票模型，替代 Company)
# ==========================================
class AShareStock(models.Model):
    """
    统一股票基本信息表（替代原 Company 模型）
    存储 A 股全量列表，同时兼容原 Company 的所有字段。
    """
    symbol = models.CharField(max_length=10, primary_key=True, verbose_name="股票代码")
    name = models.CharField(max_length=100, verbose_name="股票名称")
    # === 原 Company 兼容字段 ===
    industry = models.ForeignKey(
        'Industry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='a_stocks',
        verbose_name="所属行业"
    )
    market = models.CharField(max_length=4, verbose_name="市场(SH/SZ/BJ)")
    market_type = models.CharField(max_length=20, blank=True, null=True, verbose_name="板块类型")
    total_market_cap = models.BigIntegerField(null=True, blank=True, verbose_name="总市值(元)")
    trailing_pe = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="市盈率")
    price_sales = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="市销率")
    current_price = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, verbose_name="最新价")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "股票"
        verbose_name_plural = "股票"
        ordering = ['symbol']

    @property
    def full_name(self):
        """兼容原 Company.full_name，返回 name"""
        return self.name

    def __str__(self):
        return f"{self.symbol} {self.name}"


class AShareRealtimePrice(models.Model):
    """
    A 股实时行情缓存表（来源：东方财富）
    每次 fetch 更新，保留最新快照。
    """
    symbol = models.CharField(max_length=10, db_index=True, verbose_name="股票代码")
    name = models.CharField(max_length=100, verbose_name="股票名称")
    price = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="最新价")
    open_price = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="开盘价")
    high_price = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="最高价")
    low_price = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="最低价")
    pre_close = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="昨收价")
    volume = models.BigIntegerField(default=0, verbose_name="成交量(手)")
    amount = models.DecimalField(max_digits=20, decimal_places=2, default=0, verbose_name="成交额")
    change_pct = models.DecimalField(max_digits=8, decimal_places=4, default=0, verbose_name="涨跌幅(%)")
    pe_ratio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="市盈率")
    fetched_at = models.DateTimeField(auto_now=True, verbose_name="抓取时间")

    class Meta:
        verbose_name = "A股实时行情"
        verbose_name_plural = "A股实时行情"
        indexes = [
            models.Index(fields=['symbol']),
            models.Index(fields=['-change_pct']),  # 按涨跌幅排序
        ]

    def __str__(self):
        return f"{self.symbol} {self.name} ¥{self.price}"