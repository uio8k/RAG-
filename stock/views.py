from django.shortcuts import render, HttpResponseRedirect
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, F, Sum
from django.utils import timezone
import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from .models import *
from django.db.models import  OuterRef, Subquery, DecimalField
from django.db import transaction
from django.db.models import DecimalField, FloatField, IntegerField
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, HttpResponseRedirect, get_object_or_404  
from .models import Simulation_Cash_Flow
import ast
import operator
import matplotlib.pyplot as plt
from matplotlib import font_manager
import os
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from django.http import HttpResponse
import io
import uuid
from agents.brain import FinancialBrain
from memory.manager import MemoryManager


# === AI 引擎懒加载（避免所有 Django 命令都加载模型） ===
_ada_brain = None
_ada_init_failed = False


def get_ada_brain():
    """懒加载获取 AI 引擎单例，仅在首次 AI 对话请求时初始化"""
    global _ada_brain, _ada_init_failed
    if _ada_brain is None and not _ada_init_failed:
        try:
            print("--- [System] 正在初始化 Ada-Finance AI 引擎... ---")
            _ada_brain = FinancialBrain()
        except Exception as e:
            print(f"--- [Warning] AI 引擎初始化失败: {e} ---")
            _ada_init_failed = True
    return _ada_brain


# === Agent Memory Hub 懒加载 ===
_memory_manager = None


def get_memory_manager():
    """懒加载获取 MemoryManager 单例，仅在首次 AI 对话时初始化
    
    如果 LongTermMemory 无法加载嵌入模型（无网络），自动降级为纯短期记忆模式。
    """
    global _memory_manager
    if _memory_manager is None:
        print("--- [MemoryHub] 正在初始化 Agent Memory Hub... ---")
        try:
            _memory_manager = MemoryManager()
            # 触发长期记忆初始化（检测嵌入模型是否可用）
            if _memory_manager.long_term:
                _memory_manager.long_term._get_embedder()
            print("--- [MemoryHub] 完整模式初始化完成 (短期 + 长期 + 工作 + 情景) ---")
        except Exception as e:
            print(f"--- [MemoryHub] 长期记忆不可用 ({e})，降级为纯短期记忆模式 ---")
            _memory_manager = MemoryManager(long_term=None)
        print("--- [MemoryHub] 初始化完成 ---")
    return _memory_manager


FONT_PATH = r"C:\Users\24300\Desktop\Stock\fonts\msyh.ttc"
if os.path.exists(FONT_PATH):
    font_prop = font_manager.FontProperties(fname=FONT_PATH)
    plt.rcParams['font.sans-serif'] = [font_prop.get_name()]
    plt.rcParams['axes.unicode_minus'] = False
# ==========================================
# GLOBAL SETTINGS & PRECISION CONSTANTS
# ==========================================
ZERO = Decimal('0.0000')
SEARCH_LIMIT = 20
INITIAL_BALANCE = Decimal('100000.00')
PRECISION_4 = Decimal('0.0001')
PRECISION_2 = Decimal('0.01')
COMMISSION_RATE = Decimal('0.0003') # 0.03% Transaction Fee

def safe_eval_formula(formula_str, context):
    """
    Safely evaluates a mathematical formula string using Abstract Syntax Trees (AST).
    
    Args:
        formula_str (str): The raw string from the user (e.g., "net_income / total_revenue").
        context (dict): A dictionary mapping variable names to their numeric values 
                       (e.g., {'net_income': 100, 'total_revenue': 500}).
    
    Returns:
        Decimal: The result of the calculation.
    
    Raises:
        Exception: If the formula contains illegal operations or undefined variables.
    """
    # Define allowed operators for calculation
    # This acts as a whitelist to prevent execution of malicious code
    allowed_operators = {
        ast.Add: operator.add, 
        ast.Sub: operator.sub, 
        ast.Mult: operator.mul, 
        ast.Div: operator.truediv,
        ast.USub: operator.neg  # Supports negative numbers like -5
    }

    def eval_node(node):
        # Case 1: The node is a literal number (e.g., 100 or 0.05)
        if isinstance(node, ast.Num):
            return Decimal(str(node.n))
        
        # Case 2: The node is a binary operation (e.g., a + b, a / b)
        elif isinstance(node, ast.BinOp):
            left_val = eval_node(node.left)
            right_val = eval_node(node.right)
            op_type = type(node.op)
            
            if op_type in allowed_operators:
                # Case 2.1: Robust Division handling
                if op_type == ast.Div:
                    # Use a small epsilon to prevent division by zero or near-zero values
                    # This avoids extreme spikes in the chart caused by tiny denominators
                    if abs(right_val) < Decimal('0.000001'):
                        return Decimal('0')
                    return left_val / right_val
                return allowed_operators[op_type](left_val, right_val)
            raise ValueError(f"Operator {op_type.__name__} is not allowed.")
            
        # Case 3: The node is a unary operation (e.g., -income)
        elif isinstance(node, ast.UnaryOp):
            operand_val = eval_node(node.operand)
            op_type = type(node.op)
            if op_type in allowed_operators:
                return allowed_operators[op_type](operand_val)
            raise ValueError(f"Unary operator {op_type.__name__} is not allowed.")

        # Case 4: The node is a variable name (e.g., total_revenue)
        elif isinstance(node, ast.Name):
            # Fetch the value from the provided financial context
            val = context.get(node.id)
            if val is None:
                raise NameError(f"Variable '{node.id}' is not found in financial data.")
            return Decimal(str(val))
        
        else:
            raise TypeError(f"Unsupported syntax: {type(node).__name__}")

    try:
        # Clean the string and parse it into an expression tree
        # mode='eval' ensures we only process a single expression, not a script
        cleaned_formula = formula_str.replace(" ", "")
        tree = ast.parse(cleaned_formula, mode='eval')
        return eval_node(tree.body)
    except Exception as e:
        # Catch and re-raise with a clear message for the frontend
        raise Exception(f"Formula Error: {str(e)}")
    

def quantize_4(value):
    return Decimal(value).quantize(PRECISION_4, rounding=ROUND_HALF_UP)

# ==========================================
# 1. ROBUST MARKET DATA ENGINE
# ==========================================

def get_market_price(symbol_obj, target_date):
    """
    Finds the most recent closing price on or before target_date.
    Handles weekends, holidays, and market suspensions.
    """
    try:
        price_record = DailyPrice.objects.filter(
            symbol=symbol_obj,
            trade_date__lt=target_date
        ).latest('trade_date')
        return price_record
    except DailyPrice.DoesNotExist:
        return None


def calculate_nav_optimized(sim, target_date):
    """
    Production-grade NAV calculation optimized for RDBMS.
    Formula: Available Cash + Frozen Buying Cash + Current Market Value
    
    This implementation replaces Python loops with Database Aggregations.
    """
    
    # --- 1. Subquery: Get the latest close price for each symbol before target_date ---
    # This prevents loading thousands of historical price rows into memory.
    latest_price_subquery = DailyPrice.objects.filter(
        symbol=OuterRef('symbol'),
        trade_date__lt=target_date
    ).order_by('-trade_date').values('close_price')[:1]

    # --- 2. Calculate Frozen Cash (Unfilled Buy Orders) ---
    # Summing (price * remaining_qty) directly in the database.
    # We ignore COMMISSION_RATE here for simplicity, or add it if strictly required.
    frozen_data = TradeOrder.objects.filter(
        sim=sim,
        side='BUY',
        status__in=['PENDING', 'PARTIAL']
    ).aggregate(
        total_frozen=Sum(
            F('price') * (F('quantity') - F('filled_quantity')),
            output_field=DecimalField()
        )
    )
    frozen_cash = frozen_data['total_frozen'] or Decimal('0.0000')

    # --- 3. Calculate Market Value (Existing Holdings) ---
    # Annotate each holding with the latest price from subquery, then aggregate.
    holding_data = sim.holdings.exclude(quantity=0).annotate(
        latest_price=Subquery(latest_price_subquery, output_field=DecimalField())
    ).aggregate(
        total_mkt_val=Sum(
            F('quantity') * F('latest_price'),
            output_field=DecimalField()
        )
    )
    holdings_market_value = holding_data['total_mkt_val'] or Decimal('0.0000')

    # --- 4. Calculate Market Value (Locked in Sell Orders) ---
    # Shares locked in sell orders are still assets owned by the user.
    sell_order_data = TradeOrder.objects.filter(
        sim=sim,
        side='SELL',
        status__in=['PENDING', 'PARTIAL']
    ).annotate(
        latest_price=Subquery(latest_price_subquery, output_field=DecimalField())
    ).aggregate(
        frozen_mkt_val=Sum(
            (F('quantity') - F('filled_quantity')) * F('latest_price'),
            output_field=DecimalField()
        )
    )
    frozen_shares_market_value = sell_order_data['frozen_mkt_val'] or Decimal('0.0000')

    # --- 5. Final Aggregation ---
    total_market_value = holdings_market_value + frozen_shares_market_value
    total_nav = sim.available_cash + frozen_cash + total_market_value

    # Returns exactly what the frontend needs
    return total_nav, total_market_value

# Helper to ensure 4 decimal places for financial calculations
def quantize_4(val):
    return val.quantize(Decimal('0.0001'))

# ==========================================
# 2. AUTHENTICATION & IDENTITY (ER: Stock_User)
# ==========================================

def register_view(request):
    """
    Handles user registration and initializes a default trading simulation.
    Synchronizes the new user's virtual clock with the Global Master Clock.
    """
    if request.method == "POST":
        d = request.POST
        if d['password'] != d['confirmation']:
            return render(request, "stock/register.html", {"message": "Passwords mismatch."})
        
        try:
            with transaction.atomic():
                # 1. Fetch Global Simulation State to sync the start date
                global_state = GlobalSimulationState.objects.select_for_update().first()
                if not global_state:
                    # Emergency initialization if global state is missing
                    initial_date = datetime.strptime("2026-03-02", "%Y-%m-%d").date()
                    global_state = GlobalSimulationState.objects.create(
                        current_global_date=initial_date,
                        is_market_open=True
                    )
                
                # The "Time Machine" entry point for this user
                shared_virtual_date = global_state.current_global_date

                # 2. Create the User profile
                user = User.objects.create_user(d['username'], d['email'], d['password'])
                user.first_name = d.get('firstname', '')
                user.last_name = d.get('lastname', '')
                user.gender = d.get('gender', 'Other')
                user.account_balance = INITIAL_BALANCE
                user.save()
                
                # 3. Create the Simulation instance synced to Global Clock
                new_sim = Simulation.objects.create(
                    user=user,
                    name=f"Standard Alpha Strategy - {user.username}",
                    start_date=shared_virtual_date,
                    current_virtual_date=shared_virtual_date,
                    initial_cash=INITIAL_BALANCE,
                    available_cash=INITIAL_BALANCE,
                )

                # 4. Create the initial NAV history entry for the shared start date
                Simulation_NAV_History.objects.create(
                    sim=new_sim,
                    record_date=shared_virtual_date,
                    nav=INITIAL_BALANCE,
                    cash=INITIAL_BALANCE,
                    market_value=Decimal('0.00')
                )

            login(request, user)
            return HttpResponseRedirect(reverse("index"))
            
        except Exception as e:
            # It's better to log the exception here for debugging
            return render(request, "stock/register.html", {"message": str(e)})
            
    return render(request, "stock/register.html")

def guest_login_view(request):
    """
    Guest mode: creates a temporary anonymous user account with a default
    simulation, then logs them in automatically. No username/password required.
    Each guest gets a unique UUID-based identity.
    """
    import uuid as uuid_lib
    from datetime import date

    guest_id = uuid_lib.uuid4().hex[:8]
    guest_username = f"guest_{guest_id}"
    guest_email = f"{guest_username}@guest.stockx.local"
    guest_password = uuid_lib.uuid4().hex

    try:
        with transaction.atomic():
            # 1. Sync with Global Simulation State
            global_state = GlobalSimulationState.objects.select_for_update().first()
            if not global_state:
                initial_date = datetime.strptime("2026-03-02", "%Y-%m-%d").date()
                global_state = GlobalSimulationState.objects.create(
                    current_global_date=initial_date,
                    is_market_open=True
                )
            shared_virtual_date = global_state.current_global_date

            # 2. Create guest user
            user = User.objects.create_user(guest_username, guest_email, guest_password)
            user.first_name = 'Guest'
            user.last_name = guest_id
            user.gender = 'Other'
            user.account_balance = INITIAL_BALANCE
            user.save()

            # 3. Create default simulation
            new_sim = Simulation.objects.create(
                user=user,
                name=f"Guest Explorer - {guest_username}",
                start_date=shared_virtual_date,
                current_virtual_date=shared_virtual_date,
                initial_cash=INITIAL_BALANCE,
                available_cash=INITIAL_BALANCE,
            )

            # 4. Initial NAV record
            Simulation_NAV_History.objects.create(
                sim=new_sim,
                record_date=shared_virtual_date,
                nav=INITIAL_BALANCE,
                cash=INITIAL_BALANCE,
                market_value=Decimal('0.00')
            )

        # 5. Log in the guest automatically
        login(request, user)
        return HttpResponseRedirect(reverse("index"))

    except Exception as e:
        print(f"[GUEST LOGIN ERROR] {e}")
        return render(request, "stock/login.html", {
            "message": f"游客模式暂时不可用，请稍后再试。错误: {e}"
        })

import traceback
from django.http import HttpResponse

@csrf_exempt
def login_view(request):
    print("\n====== LOGIN DEBUG START ======")

    try:
        print("Method:", request.method)
        print("POST:", dict(request.POST))
        print("COOKIES:", request.COOKIES)

        if request.method == "POST":
            u = request.POST.get("username")
            p = request.POST.get("password")

            print("username:", u)
            print("password:", p)

            if not u or not p:
                return HttpResponse("❌ username or password is None")

            user = authenticate(request, username=u, password=p)

            print("authenticate result:", user)

            if user is not None:
                login(request, user)
                print("login success")
                return HttpResponseRedirect(reverse("index"))
            else:
                print("authenticate failed")
                return HttpResponse("AUTH FAILED")

        return render(request, "stock/login.html")

    except Exception as e:
        print("EXCEPTION:")
        traceback.print_exc()
        return HttpResponse(f"SERVER ERROR:\n{str(e)}")

@login_required
def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("login"))

# ==========================================
# 3. MARKET EXPLORER (ER: Company, Financials)
# ==========================================

@login_required
def index(request):
    """
    Dashboard view for the multiplayer trading simulation.
    Synchronizes all users to a shared virtual timeline via GlobalSimulationState.
    """
    # 1. Fetch or Initialize Global Simulation State (The Master Clock)
    from datetime import date
    today = date.today()
    global_state = GlobalSimulationState.objects.first()
    
    if not global_state:
        # Emergency fallback if no state exists in DB
        global_state = GlobalSimulationState.objects.create(
            current_global_date=today,
            is_market_open=True
        )
    elif global_state.current_global_date != today:
        # 同步到本地计算机时间
        global_state.current_global_date = today
        global_state.save(update_fields=['current_global_date'])
    
    virtual_today = global_state.current_global_date

    # 2. Fetch the primary simulation account for the current user
    user_sims = Simulation.objects.filter(user=request.user).order_by('-created_at')
    active_sim = user_sims.first()
    
    # 3. Sync user's simulation date to local time
    if active_sim and active_sim.current_virtual_date != today:
        active_sim.current_virtual_date = today
        active_sim.save(update_fields=['current_virtual_date'])
    
    # 3. Lazy Initialization: Create a simulation if none exists
    if not active_sim:
        active_sim = Simulation.objects.create(
            user=request.user,
            name=f"Alpha Strategy - {request.user.username}",
            start_date=virtual_today,
            current_virtual_date=virtual_today, # Sync with global clock
            initial_cash=INITIAL_BALANCE,
            available_cash=INITIAL_BALANCE,
        )
        # Create the initial record for the performance chart
        Simulation_NAV_History.objects.create(
            sim=active_sim, 
            record_date=virtual_today,
            nav=INITIAL_BALANCE, 
            cash=INITIAL_BALANCE, 
            market_value=Decimal('0.00')
        )

    # 4. Market Explorer Logic: Fetch industries and filter companies
    all_industries = Industry.objects.all()
    selected_industry_id = request.GET.get('industry')
    query = request.GET.get('q', '').strip()

    # Start with all stocks
    companies_qs = AShareStock.objects.all()

    # Apply Industry filter if selected
    if selected_industry_id:
        companies_qs = companies_qs.filter(industry_id=selected_industry_id)

    # Apply Search query if exists
    if query:
        companies_qs = companies_qs.filter(
            Q(symbol__icontains=query) | Q(name__icontains=query)
        )

    # Slice to top 20 and process prices based on virtual timeline
    popular_companies = companies_qs[:20]
    processed_stocks = []
    
    for comp in popular_companies:
        price_rec = DailyPrice.objects.filter(
            symbol=comp,
            trade_date__lt=virtual_today
        ).order_by('-trade_date').first()
        
        if price_rec:
            processed_stocks.append({
                "symbol": comp.symbol,
                "name": comp.full_name,
                "price": price_rec.close_price,
                "best_ask": price_rec.high_price,
                "best_bid": price_rec.low_price,
            })
    # 5. Render Response with NAV history for the chart
    # Fetch NAV history for the performance chart (last 30 records)
    nav_records = Simulation_NAV_History.objects.filter(
        sim=active_sim
    ).order_by('-record_date')[:30]
    nav_records = list(nav_records)[::-1]  # oldest first for chart

    nav_labels = [r.record_date.strftime('%m/%d') for r in nav_records]
    nav_values = [float(r.nav) for r in nav_records]

    context = {
        "sim": active_sim,
        "popular_stocks": processed_stocks,
        "industries": all_industries,               
        "current_industry": selected_industry_id,
        "nav_labels_json": json.dumps(nav_labels),
        "nav_values_json": json.dumps(nav_values),
    }
    
    return render(request, "stock/index.html", context)


@login_required
def current_sim(request):
    sim = Simulation.objects.filter(
        user=request.user,
        status='ACTIVE'
    ).order_by('-created_at').first()

    if not sim:
        return JsonResponse({"error": "No active simulation"}, status=404)

    return JsonResponse({
        "sim_id": sim.id
    })

def api_search_companies(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 1:
        return JsonResponse({'results': []})
    
    
    # Use select_related to join Industry table and reduce DB hits
    companies = AShareStock.objects.filter(
        Q(symbol__icontains=query) | Q(name__icontains=query)
    ).select_related('industry')[:6]
    
    results = []
    for c in companies:
        results.append({
            'symbol': c.symbol,
            'full_name': c.full_name,
            'industry': c.industry.name if c.industry else "N/A",
        })
    
    return JsonResponse({'results': results})

def api_search(request):
    """
    Fast search API synchronized with the GLOBAL virtual simulation date.
    Ensures all users see the same market prices regardless of their individual sim state.
    """
    term = request.GET.get('q', '').strip().upper()
    if len(term) < 1: 
        return JsonResponse([], safe=False)
    
    # 1. Get the GLOBAL simulation date (The Master Clock)
    global_state = GlobalSimulationState.objects.first()
    if global_state:
        reference_date = global_state.current_global_date
    else:
        # Fallback to a safe date if global state isn't initialized
        return JsonResponse({"error": "Global state missing"}, status=500)

    # 2. Find matching companies
    matches = AShareStock.objects.filter(
        Q(symbol__icontains=term) | Q(name__icontains=term)
    )[:SEARCH_LIMIT]
    
    results = []
    for m in matches:
        # 3. Fetch historical price based on the GLOBAL reference date
        price_rec = DailyPrice.objects.filter(
            symbol=m,
            trade_date__lt=reference_date 
        ).order_by('-trade_date').first()
        
        # If no price exists for this company at this point in time, skip it
        if not price_rec:
            continue 

        results.append({
            "symbol": m.symbol, 
            "name": m.full_name, 
            "price": str(price_rec.close_price),
            "pe": str(m.trailing_pe)
        })
        
    return JsonResponse({"results": results})



# ==========================================

# 4. TRADING CORE (ER: Transactions, Holdings)

# ==========================================
@csrf_exempt
@login_required
def process_transaction(request):
    """
    Refactored Transaction Handler for Peer-to-Peer Trading.
    Directly deducts assets (freezing) and creates a PENDING TradeOrder.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        # 1. Parse payload
        if request.content_type == 'application/json':
            payload = json.loads(request.body)
        else:
            payload = request.POST

        sim_id = payload.get('sim_id')
        symbol = payload.get('symbol')
        qty = int(payload.get('quantity', 0))
        side = payload.get('type', payload.get('side', '')).upper()
        order_price = Decimal(payload.get('price', '0.0000'))
        request_id = payload.get('request_id')

        # --- REPLACED START: Enhanced parameter validation for debugging ---
        error_fields = []
        if not sim_id: error_fields.append("sim_id")
        if side not in ['BUY', 'SELL']: error_fields.append(f"side (current: {side})")
        if qty <= 0: error_fields.append(f"quantity (current: {qty})")
        if order_price <= 0: error_fields.append(f"price (current: {order_price})")

        if error_fields:
            return JsonResponse({
                "success": False, 
                "error": f"Invalid parameters or price. Check fields: {', '.join(error_fields)}",
                "debug_payload": {
                    "sim_id": sim_id,
                    "symbol": symbol,
                    "qty": qty,
                    "side": side,
                    "price": str(order_price)
                }
            })
        # --- REPLACED END ---

        with transaction.atomic():
            # 2. Check Global Market State
            global_state = GlobalSimulationState.objects.select_for_update().first()
            if not global_state or not global_state.is_market_open:
                return JsonResponse({"success": False, "error": "Market is currently closed."})
            
            virtual_today = global_state.current_global_date

            # 3. Lock Simulation record
            sim = Simulation.objects.select_for_update().filter(
                id=sim_id, 
                user=request.user, 
                status='ACTIVE'
            ).first()

            if not sim:
                return JsonResponse({"success": False, "error": "Active simulation not found."})

            # 4. Idempotency Check
            if request_id and TradeOrder.objects.filter(id=request_id).exists():
                return JsonResponse({"success": True, "message": "Order already placed."})

            company = AShareStock.objects.get(symbol=symbol)

            # 5. God's Price Boundary Validation (Refined for P2P Visibility)
            # Use TODAY'S real market boundaries to ensure the order is physically possible.
            today_price_rec = DailyPrice.objects.filter(
                symbol=company, 
                trade_date=virtual_today  # Use the actual simulation date
            ).first()
            
            if not today_price_rec:
                return JsonResponse({"success": False, "error": "MARKET_DATA_MISSING"})
            
            # Rejection logic: The price must be within [Low, High]
            if not (today_price_rec.low_price <= order_price <= today_price_rec.high_price):
                return JsonResponse({
                    "success": False, 
                    "error": "UNTRADABLE_PRICE",
                    "message": f"Price {order_price} out of range [{today_price_rec.low_price} - {today_price_rec.high_price}]"
                })
            
            # 6. Asset Freezing (Deduction)
            subtotal = order_price * qty
            estimated_fee = quantize_4(subtotal * COMMISSION_RATE)
            avg_cost_at_order = ZERO

            if side == "BUY":
                total_required = subtotal + estimated_fee
                if sim.available_cash < total_required:
                    return JsonResponse({"success": False, "error": "Insufficient cash."})
                
                sim.available_cash -= total_required
                sim.save()

                # Sync Holding: Update quantity and recalculate average cost
                holding, created = Simulation_Holding.objects.get_or_create(
                    sim=sim, symbol=company, 
                    defaults={'quantity': 0, 'avg_cost': ZERO}
                )
                total_cost = (holding.quantity * holding.avg_cost) + subtotal + estimated_fee
                holding.quantity += qty
                holding.avg_cost = (total_cost / holding.quantity).quantize(Decimal('0.0001'))
                holding.save()

            elif side == "SELL":
                holding = Simulation_Holding.objects.filter(sim=sim, symbol=company).first()
                if not holding or holding.quantity < qty:
                    return JsonResponse({"success": False, "error": "Insufficient shares."})
                
                avg_cost_at_order = holding.avg_cost
                
                # Instant Liquidation: Add net proceeds to cash
                net_proceeds = subtotal - estimated_fee
                sim.available_cash += net_proceeds
                sim.save()

                holding.quantity -= qty
                if holding.quantity == 0:
                    holding.delete()
                else:
                    holding.save()

            # 7. Create the FILLED Order
            new_order = TradeOrder.objects.create(
                user=request.user,
                sim=sim,
                symbol=company,
                side=side,
                price=order_price,
                quantity=qty,
                filled_quantity=qty,
                status=TradeOrder.OrderStatus.FILLED,
                order_date=virtual_today,
                avg_cost_snapshot=avg_cost_at_order if side == "SELL" else ZERO
            )

            # 8. Log Cash Flow (Audit Trail for Entropy/Fees)
            # ------------------------------------------------------
            # First, determine the total cash impact to calculate before_balance correctly
            cash_impact = -total_required if side == 'BUY' else net_proceeds
            initial_balance_before_trade = sim.available_cash - cash_impact

            # A. Record the Trade Principal (The "Mass" of the trade)
            Simulation_Cash_Flow.objects.create(
                sim=sim,
                request_id=f"TRADE_{new_order.id}",
                change_type=side, # 'BUY' or 'SELL'
                before_balance=initial_balance_before_trade,
                amount=-subtotal if side == 'BUY' else subtotal,
                after_balance=initial_balance_before_trade + (-subtotal if side == 'BUY' else subtotal)
            )

            # B. Record the Fee Separately (This is the "Entropy" you are looking for)
            # This specific entry is what your views.py queries to show total_fees_sum
            current_temp_balance = initial_balance_before_trade + (-subtotal if side == 'BUY' else subtotal)
            Simulation_Cash_Flow.objects.create(
                sim=sim,
                request_id=f"FEE_{new_order.id}",
                change_type='FEE', # Must match the query in your views.py
                before_balance=current_temp_balance,
                amount=-estimated_fee, # Fees always decrease the system's available cash
                after_balance=sim.available_cash
            )

            # ---  9. Record Audit Trail for "Operation Logs" UI ---
            # This ensures the trade appears in transactions_view immediately.
            Simulation_Transaction.objects.create(
                sim=sim,
                symbol=company,
                daily_price=today_price_rec, # Use the record found in Step 5
                trade_date=virtual_today,
                type=side,                   # 'BUY' or 'SELL'
                quantity=qty,
                price=order_price,
                fees=estimated_fee,
                total_amount=subtotal + estimated_fee if side == 'BUY' else subtotal - estimated_fee,
                matched_order=new_order,
                realized_pnl=ZERO if side == 'BUY' else (order_price - avg_cost_at_order) * qty - estimated_fee
            )

            return JsonResponse({
                "success": True,
                "message": f"Successfully executed {side} for {symbol}.",
                "order_id": new_order.id,
                "status": "FILLED" # Let the frontend know it can update the portfolio immediately
            })

    except AShareStock.DoesNotExist:
        return JsonResponse({"success": False, "error": "Stock not found."}, status=404)
    except Exception as e:
        print(f"Error: {str(e)}")
        return JsonResponse({"success": False, "error": "Order failed."}, status=500)


@csrf_exempt
@login_required
def cancel_order(request):
    """
    Cancels a PENDING or PARTIAL trade order and releases REMAINING frozen assets.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        payload = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        order_id = payload.get('order_id')

        if not order_id:
            return JsonResponse({"success": False, "error": "Order ID is required."})

        with transaction.atomic():
            # 1. Lock the order and verify ownership. 
            # Crucial: Allow cancellation for both PENDING and PARTIAL.
            order = TradeOrder.objects.select_for_update().filter(
                id=order_id,
                user=request.user,
                status__in=[TradeOrder.OrderStatus.PENDING, TradeOrder.OrderStatus.PARTIAL]
            ).first()

            if not order:
                return JsonResponse({"success": False, "error": "Order not found or cannot be cancelled."})

            sim = order.sim
            # Calculate what is left to be returned
            remaining_qty = order.quantity - order.filled_quantity
            
            if remaining_qty <= 0:
                return JsonResponse({"success": False, "error": "Order is already fully filled."})

            # 2. Asset Release Logic (Only for the remaining portion)
            if order.side == 'BUY':
                # Refund only the part that hasn't been spent
                subtotal = order.price * remaining_qty
                estimated_fee = quantize_4(subtotal * COMMISSION_RATE)
                refund_amount = subtotal + estimated_fee
                
                sim.available_cash += refund_amount
                sim.save()

            elif order.side == 'SELL':
                # Return only the remaining shares to the Simulation_Holding
                holding, created = Simulation_Holding.objects.get_or_create(
                    sim=sim,
                    symbol=order.symbol,
                    defaults={'quantity': 0, 'avg_cost': order.price}
                )
                holding.quantity += remaining_qty
                holding.save()

            # 3. Update Order Status
            order.status = TradeOrder.OrderStatus.CANCELLED
            order.save()

            return JsonResponse({
                "success": True, 
                "message": f"Order {order_id} cancelled. {remaining_qty} shares released.",
                "available_cash": str(sim.available_cash)
            })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def internal_matching_engine(execution_date):
    """
    Simplified Engine: 
    Since process_transaction handles instant execution, 
    this now only serves as a safety cleanup for the day.
    """
    # Auto-cancel any lingering non-filled orders from previous days
    stale_orders = TradeOrder.objects.filter(
        status__in=[TradeOrder.OrderStatus.PENDING, TradeOrder.OrderStatus.PARTIAL],
        order_date__lt=execution_date
    )
    
    count = stale_orders.count()
    stale_orders.update(status=TradeOrder.OrderStatus.CANCELLED)
    
    # Return count to maintain compatibility with existing return type
    return count

def execute_settlement(b_order, s_order, qty, price, trade_date, price_rec):
    """
    Handles assets transfer. Supports both P2P (b_order & s_order) 
    and P2M (one of the orders is None).
    """
    with transaction.atomic():
        subtotal = price * qty
        
        # Using global constants and quantization
        buy_fee = quantize_4(subtotal * COMMISSION_RATE)
        sell_fee = quantize_4(subtotal * COMMISSION_RATE)

        # ==========================================
        # A & C. Buyer Side Logic (Only if b_order exists)
        # ==========================================
        if b_order:
            # A. Update Buyer's Portfolio (Only if not already processed)
            if b_order.status != TradeOrder.OrderStatus.FILLED:
                b_holding, created = Simulation_Holding.objects.get_or_create(
                    sim=b_order.sim,
                    symbol=b_order.symbol,
                    defaults={'quantity': 0, 'avg_cost': ZERO}
                )
                total_cost = (b_holding.quantity * b_holding.avg_cost) + subtotal
                b_holding.quantity += qty
                b_holding.avg_cost = quantize_4(total_cost / b_holding.quantity)
                b_holding.save()

           # C. Buyer Refund Logic (Only if not already processed)
            if b_order.status != TradeOrder.OrderStatus.FILLED:
                # Frozen: (limit_price * qty) + fee. Actual: (exec_price * qty) + fee.
                frozen_unit_price = b_order.price + quantize_4(b_order.price * COMMISSION_RATE)
                actual_unit_price = price + quantize_4(price * COMMISSION_RATE)
                refund = (frozen_unit_price - actual_unit_price) * qty
                
                if refund > 0:
                    b_order.sim.available_cash += refund
                    b_order.sim.save()
            
            
            
            # D1. Create Buyer Transaction Record
            Simulation_Transaction.objects.create(
                sim=b_order.sim,
                symbol=b_order.symbol,
                daily_price=price_rec,
                trade_date=trade_date,
                type='BUY',
                quantity=qty,
                price=price,
                total_amount=subtotal + buy_fee,
                fees=buy_fee,  
                voucher_no=f"B{uuid.uuid4().hex[:12].upper()}",
                matched_order=b_order,
                opponent_order=s_order,
                realized_pnl=ZERO
            )

            
            #cash_before_fee = b_order.sim.available_cash
            
            
            #b_order.sim.available_cash -= buy_fee
            #b_order.sim.save()

            # Cash Flow Ledger
            #Simulation_Cash_Flow.objects.create(
                #sim=b_order.sim,
                #change_type='FEE',
               # before_balance=cash_before_fee,      
               # amount=-buy_fee,                     
               # after_balance=b_order.sim.available_cash,  
               # request_id=f"FEE_B_{b_order.id}_{int(timezone.now().timestamp())}"
            #)
        # ==========================================
        # Seller Side Logic (Only if s_order exists)
        # ==========================================
        if s_order:
            # Update Seller's Cash (Only if not already processed)
            if s_order.status != TradeOrder.OrderStatus.FILLED:
                s_order.sim.available_cash += (subtotal - sell_fee)
                s_order.sim.save()

            cost_at_order_time = s_order.avg_cost_snapshot or ZERO
            
            # Realized PnL = (Current Execution Price - Original Cost) * Quantity - Fee
            realized_pnl = (price - cost_at_order_time) * qty - sell_fee
            print("DEBUG SELL >>>", price, cost_at_order_time, qty, realized_pnl)

            # D2. Create Seller Transaction Record
            Simulation_Transaction.objects.create(
                sim=s_order.sim,
                symbol=s_order.symbol,
                daily_price=price_rec,
                trade_date=trade_date,
                type='SELL',
                quantity=qty,
                price=price,
                total_amount=subtotal - sell_fee,
                fees=sell_fee, 
                voucher_no=f"S{uuid.uuid4().hex[:12].upper()}",
                matched_order=s_order,
                opponent_order=b_order,
                realized_pnl=realized_pnl
            )

            # D2-Fee. Record Seller's Commission (Only if not already processed)
            if s_order.status != TradeOrder.OrderStatus.FILLED:
                Simulation_Cash_Flow.objects.create(
                    sim=s_order.sim,
                    change_type='FEE',
                    before_balance=s_order.sim.available_cash + sell_fee,
                    amount=-sell_fee,
                    after_balance=s_order.sim.available_cash,
                    request_id=f"FEE_S_{s_order.id}_{int(timezone.now().timestamp())}"
                )

        # ==========================================
        # E. Update Orders Status (Support Partial Fills)
        # ==========================================
        for order in [b_order, s_order]:
            if order: # Skip if the order is None (Market side in P2M)
                order.filled_quantity += qty
                if order.filled_quantity >= order.quantity:
                    order.status = TradeOrder.OrderStatus.FILLED
                else:
                    order.status = TradeOrder.OrderStatus.PARTIAL
                order.save()

def is_superuser(user):
    return user.is_authenticated and user.is_superuser

@user_passes_test(is_superuser)
def advance_simulation_date(request, sim_id=None):
    """
    Global System Clock Controller.
    Advances the GlobalSimulationState and triggers the P2P matching engine.
    """
    from datetime import timedelta
    from django.db import transaction

    with transaction.atomic():
        # 1. Fetch and Lock the Global State
        global_state = GlobalSimulationState.objects.select_for_update().first()
        if not global_state:
            return JsonResponse({"success": False, "error": "Global state not initialized."})

        current_date = global_state.current_global_date
        target_next_date = current_date + timedelta(days=1)

        # 2. Find the next valid trading date (skip weekends/holidays)
        next_market_record = DailyPrice.objects.filter(
            trade_date__gte=target_next_date
        ).order_by('trade_date').first()

        if not next_market_record:
            # If no more data in DB, we cannot advance
            return JsonResponse({"success": False, "error": "End of historical data reached."})

        new_date = next_market_record.trade_date

        # 3. TRIGGER MATCHING ENGINE (Crucial Step)
        # We match orders based on the NEW date's market boundaries.
        # This simulates the market opening and processing the order queue.
        matches_executed = internal_matching_engine(new_date)

        # 4. Update Global State
        global_state.current_global_date = new_date
        global_state.save()

        # 5. POST-MARKET SETTLEMENT: Update NAV for ALL active simulations
        # We process simulations in chunks if you have many users to avoid memory timeout.
        active_simulations = Simulation.objects.filter(status=Simulation.Status.ACTIVE)
        
        for sim in active_simulations:
            # Calculate valuation based on the new closing prices
            new_nav, mkt_val = calculate_nav_optimized(sim, new_date)
            
            # Update simulation record
            sim.current_virtual_date = new_date
            sim.save()

            # 6. Record NAV History for UI Charts
            Simulation_NAV_History.objects.update_or_create(
                sim=sim, 
                record_date=new_date,
                defaults={
                    'nav': new_nav, 
                    'cash': sim.available_cash, 
                    'market_value': mkt_val
                }
            )

    # Return summary or redirect
    return HttpResponseRedirect(reverse("index"))
# ==========================================
# 5. ANALYSIS & REPORTING
# ==========================================

@login_required
def stock_financials(request, symbol):
    """Deep fundamental data extraction for analysis."""
    stock = AShareStock.objects.get(symbol=symbol)
    # Using ER Financials fields
    fin_list = Financials.objects.filter(symbol=stock).order_by('-report_date')
    
    reports = []
    for f in fin_list:
        # Calculate Margin on-the-fly (Industrial standard: avoid storing derived fields)
        net_margin = (f.net_income / f.total_revenue * 100) if f.total_revenue else 0
        reports.append({
            "date": f.report_date,
            "revenue": f.total_revenue,
            "income": f.net_income,
            "margin": round(net_margin, 2),
            "eps": f.basic_eps
        })

    return render(request, "stock/financials.html", {
        "stock": stock,
        "reports": reports
    })

@login_required
@login_required
def stock_detail(request, symbol):
    """
    Stock Detail View: Displays financial reports, historical price trends, 
    and the user's current holdings based on the GLOBAL simulation clock.
    """
    from django.shortcuts import get_object_or_404
    
    # 1. Fetch stock basic info
    company = get_object_or_404(AShareStock, symbol=symbol)
    
    # 2. Get the GLOBAL simulation date (The Master Clock)
    global_state = GlobalSimulationState.objects.first()
    if global_state:
        reference_date = global_state.current_global_date
        is_market_open = global_state.is_market_open
    else:
        # Fallback for safety
        reference_date = datetime.strptime("2026-03-02", "%Y-%m-%d").date()
        is_market_open = True
    
    # 3. Get the active simulation account for the current user
    active_sim = Simulation.objects.filter(user=request.user).order_by('-created_at').first()
    
    # 4. Fetch price history: ONLY records on or before the GLOBAL virtual today
    # Prevents data leaks in the historical table and charts.
   
    
    price_history_qs = DailyPrice.objects.filter(
        symbol=company,
        trade_date__lte=reference_date
    ).order_by('-trade_date')[:30]
    price_history = list(price_history_qs)[::-1]

    
    yesterday_price_rec = DailyPrice.objects.filter(
        symbol=company,
        trade_date__lt=reference_date  
    ).order_by('-trade_date').first()

    
    if yesterday_price_rec:
        current_sim_price = yesterday_price_rec.close_price
    elif price_history:
        current_sim_price = price_history[-1].close_price
    else:
        current_sim_price = company.current_price
    # -----------------------
    # 5. Fetch financial reports
    financial_reports = Financials.objects.filter(
        symbol=company,
        report_date__lte=reference_date
    ).order_by('-report_date')


    # We sort by date ascending for the chart (left to right)
    chart_qs = financial_reports.order_by('report_date')
    
    # Extract dates and ratios into lists
    report_dates = [f.report_date.strftime('%Y-%m') for f in chart_qs]
    debt_ratios = [float(f.debt_asset_ratio) for f in chart_qs]
    current_ratios = [float(f.current_ratio) for f in chart_qs]
    quick_ratios = [float(f.quick_ratio) for f in chart_qs]

    # Serialize to JSON strings for the template's JavaScript
    chart_dates_json = json.dumps(report_dates)
    debt_ratios_json = json.dumps(debt_ratios)
    current_ratios_json = json.dumps(current_ratios)
    quick_ratios_json = json.dumps(quick_ratios)
   

    # 6. (Optional New Feature) Fetch Pending Orders for this stock
    # This allows users to see the current "Market Depth"
    pending_orders = TradeOrder.objects.filter(
        symbol=company,
        status='PENDING'
    ).order_by('-price') # Show highest buy/sell prices
    yesterday_rec = DailyPrice.objects.filter(
        symbol=company,
        trade_date__lt=reference_date
    ).order_by('-trade_date').first()

    if yesterday_rec:
        current_sim_price = yesterday_rec.close_price
    elif price_history:

        current_sim_price = price_history[0].close_price
    else:

        current_sim_price = company.current_price


    print(f"DEBUG >>> GlobalDate: {reference_date} | FinalPrice: {current_sim_price}")
    # Check if the user currently holds this stock
    user_holding = None
    if active_sim:
        user_holding = Simulation_Holding.objects.filter(
            sim=active_sim, 
            symbol=company
        ).first()

    # -----------------------
    # 7. Dynamic Formula Support
    # Extract all numeric field names from the Financials model
    # This allows the frontend to show which variables are available for custom formulas
    all_financial_fields = [
        f.name for f in Financials._meta.get_fields() 
        if isinstance(f, (DecimalField, FloatField, IntegerField))
    ]
    
    # Define fields to exclude from calculation variables
    excluded_fields = ['id', 'symbol_id']
    calculable_fields = [f for f in all_financial_fields if f not in excluded_fields]

    return render(request, "stock/detail.html", {
        "company": company,
        "current_price": current_sim_price, 
        "financials": financial_reports,
        "history": price_history,
        "holding": user_holding,
        "sim": active_sim,
        "virtual_today": reference_date,
        "is_market_open": is_market_open,
        "pending_orders": pending_orders,
        "chart_dates_json": chart_dates_json,
        "debt_ratios_json": debt_ratios_json,
        "current_ratios_json": current_ratios_json,
        "quick_ratios_json": quick_ratios_json,
        "calculable_fields": calculable_fields,
    })

@login_required
def stock_history_full(request, symbol):
    """
    Dedicated view for historical price data.
    Provides a deep dive into price movements while enforcing the 
    simulation's virtual date boundary to prevent data leaks.
    """
    from django.shortcuts import get_object_or_404
    
    # 1. Fetch stock basic info (Returns 404 if symbol not found)
    company = get_object_or_404(AShareStock, symbol=symbol)
    
    # 2. Get the active simulation context for the current user
    active_sim = Simulation.objects.filter(user=request.user).order_by('-created_at').first()
    
    # 3. Determine the "Time Machine" boundary
    # If no simulation is active, default to current real-world date
    reference_date = active_sim.current_virtual_date if active_sim else timezone.now().date()
    
    # 4. Fetch extended price history (limited to 100 entries)
    # CRITICAL: Added trade_date__lte filter to hide "future" market data
    price_history = DailyPrice.objects.filter(
        symbol=company,
        trade_date__lte=reference_date
    ).order_by('-trade_date')[:100]
    
    # 5. Render the historical data page within the simulation context
    return render(request, "stock/history_page.html", {
        "company": company,
        "history": price_history,
        "sim": active_sim,
        "reference_date": reference_date
    })

@login_required
@login_required
def transactions_view(request):
    """
    View to display the full transaction history for the active simulation.
    Uses select_related to optimize database performance for joined tables.
    """
    active_sim = Simulation.objects.filter(user=request.user).order_by('-created_at').first()
    recent_actions = []
    
    if active_sim:
        # We use select_related('symbol') to pre-fetch company names 
        # and avoid the N+1 query problem in the template.
        recent_actions = Simulation_Transaction.objects.filter(
            sim=active_sim
        ).select_related('symbol').order_by('-trade_date', '-created_at')
    
    return render(request, "stock/transactions.html", {
        "transactions": recent_actions,
        "sim": active_sim
    })

# ==========================================
# 6. GLOBAL ERROR HANDLERS (Professional Redundancy)
# ==========================================

def custom_404(request, exception):
    """
    Handle Page Not Found (e.g., user types a wrong stock URL)
    """
    return render(request, "errors/404.html", status=404)

def custom_500(request):
    """
    Handle Internal Server Errors (e.g., database lock timeout)
    """
    return render(request, "errors/500.html", status=500)

@login_required
def api_calculate_custom_indicator(request):
    """
    API endpoint that calculates custom financial indicators based on user formulas.
    Returns JSON data suitable for Chart.js rendering.
    """
    # 1. Extract parameters from the AJAX request
    symbol = request.GET.get('symbol')
    formula = request.GET.get('formula', '').strip()
    
    if not symbol or not formula:
        return JsonResponse({"success": False, "error": "Please provide both a stock symbol and a formula."})

    try:
        # 2. Identify the stock and simulation context
        company = AShareStock.objects.get(symbol=symbol)
        active_sim = Simulation.objects.filter(user=request.user).order_by('-created_at').first()
        
        # Use simulation date to prevent data leaking from the "future"
        reference_date = active_sim.current_virtual_date if active_sim else timezone.now().date()

        # 3. Fetch historical financial records up to the simulation date
        # Ordered by date ascending for proper chart timeline (Left -> Right)
        financial_records = Financials.objects.filter(
            symbol=company,
            report_date__lte=reference_date
        ).order_by('report_date')

        if not financial_records.exists():
            return JsonResponse({"success": False, "error": "No historical financial data found for this stock."})

        chart_labels = []
        chart_values = []

        # 4. Iterate through each report and calculate the result using our safe engine
        for report in financial_records:
            context = {}
            # Automatically pull all numeric fields from DB
            for field in report._meta.fields:
                if isinstance(field, (models.DecimalField, models.FloatField, models.IntegerField, models.BigIntegerField)):
                    value = getattr(report, field.name)
                    context[field.name] = Decimal(str(value)) if value is not None else Decimal('0')

            # --- INSERT THIS PART START ---
            # 4.1 Inject derived financial variables not present in physical DB columns
            assets = context.get('total_assets', Decimal('0'))
            liabilities = context.get('total_liabilities', Decimal('0'))
            
            # Define total_equity so users can use it in formulas
            context['total_equity'] = assets - liabilities
            # --- INSERT THIS PART END ---

            # Calculate the result for this period
            result = safe_eval_formula(formula, context)
            
            chart_labels.append(report.report_date.strftime('%Y-%m'))
            chart_values.append(float(result))

        return JsonResponse({
            "success": True,
            "labels": chart_labels,
            "values": chart_values,
            "formula_used": formula
        })

    except Company.DoesNotExist:
        return JsonResponse({"success": False, "error": "Company not found."})
    except Exception as e:
        # Return the specific error message (e.g., "Variable not found" or "Syntax Error")
        return JsonResponse({"success": False, "error": str(e)})
    
def generate_transaction_pdf(request, transaction_id):
    try:
        tx = Simulation_Transaction.objects.get(id=transaction_id, sim__user=request.user)
    except Simulation_Transaction.DoesNotExist:
        return HttpResponse("凭证不存在", status=404)

    buffer = io.BytesIO()

    p = canvas.Canvas(buffer, pagesize=(595.27, 841.89))
    width, height = (595.27, 841.89)

    try:
        pdfmetrics.registerFont(TTFont('msyh', FONT_PATH))
        p.setFont('msyh', 12)
    except:
        p.setFont('Helvetica', 12)

   
    p.setFillColorRGB(0.1, 0.1, 0.1)
    p.rect(0, height - 60, width, 60, stroke=0, fill=1)


    p.setFillColorRGB(1, 1, 1)
    try: p.setFont('msyh', 16)
    except: p.setFont('Helvetica', 16)
    p.drawString(50, height - 38, f"交易电子凭证 | {tx.sim.name}")


    p.setFillColorRGB(0, 0, 0)
    y_position = height - 100
    line_height = 25


    data = [
        ("凭证编号", f"{tx.voucher_no or 'N/A'}"),
        ("交易日期", f"{tx.trade_date.strftime('%Y-%m-%d %H:%M') if hasattr(tx.trade_date, 'strftime') else tx.trade_date}"),
        ("证券信息", f"{tx.symbol.full_name} ({tx.symbol.symbol})"),
        ("交易方向", "买入 (BUY)" if tx.type == 'BUY' else "卖出 (SELL)"),
        ("成交价格", f"¥{tx.price:,.2f}"),
        ("成交数量", f"{tx.quantity:,} 股"),
        ("手续费", f"¥{tx.fees:,.2f}"),
        ("成交总额", f"¥{tx.total_amount:,.2f}"),
    ]
    
    if tx.type == 'SELL':
        data.append(("结算盈亏", f"¥{tx.realized_pnl:,.2f}"))


    for label, value in data:

        p.setStrokeColorRGB(0.9, 0.9, 0.9)
        p.line(50, y_position - 5, width - 50, y_position - 5)
        
        try: p.setFont('msyh', 10)
        except: p.setFont('Helvetica', 10)
        p.setFillColorRGB(0.4, 0.4, 0.4)
        p.drawString(60, y_position, label)
        
        p.setFillColorRGB(0, 0, 0)
        p.drawRightString(width - 60, y_position, value)
        
        y_position -= line_height

    p.setStrokeColorRGB(0.8, 0, 0)
    p.circle(width - 100, height - 250, 40, stroke=1, fill=0)
    p.setFillColorRGB(0.8, 0, 0)
    try: p.setFont('msyh', 10)
    except: p.setFont('Helvetica', 10)
    p.drawCentredString(width - 100, height - 245, "模拟交易")
    p.drawCentredString(width - 100, height - 260, "核算专用")

    
    p.setFillColorRGB(0.6, 0.6, 0.6)
    try: p.setFont('msyh', 8)
    except: p.setFont('Helvetica', 8)
    p.drawCentredString(width/2, 50, "注：本凭证仅供模拟实验使用，不具备法律效力。")

    p.showPage()
    p.save()
    
    buffer.seek(0)
    
    filename = f"Voucher_{tx.voucher_no}.pdf" if tx.voucher_no else "Transaction_Receipt.pdf"
    


    return HttpResponse(
        buffer, 
        content_type='application/pdf', 
        headers={'Content-Disposition': f'inline; filename="{filename}"'}
    )



@csrf_exempt
@login_required
def ai_chat_api(request):
    """
    AI 助手对话 API 接口（已集成 Agent Memory Hub 记忆管理）
    
    每次对话自动：
      1. 检索用户历史记忆 → 注入上下文
      2. 调用 AI 引擎推理
      3. 将本轮 Q&A 写入记忆
    """
    if request.method != "POST":
        return JsonResponse({"error": "仅支持 POST 请求"}, status=405)

    try:
        # 1. 解析前端传来的 JSON
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()

        if not user_message:
            return JsonResponse({"reply": "您想聊点什么呢？比如：帮我分析一下持仓风险。"})

        # 2. 检查 AI 引擎是否就绪（懒加载）
        brain = get_ada_brain()
        if not brain:
            return JsonResponse({"reply": "抱歉，AI 引擎暂时离线，请检查 DeepSeek API 配置。"})

        # ============ 🔑 Agent Memory Hub 集成 ============
        mm = get_memory_manager()
        user_id = str(request.user.id)

        # 2.5 检索用户历史记忆作为上下文
        past_context = mm.get_llm_context(user_id, query=user_message)

        # 把历史上下文拼到用户消息前面
        if past_context:
            enriched_message = (
                f"以下是用户之前的对话历史和相关信息，请参考：\n\n"
                f"{past_context}\n\n"
                f"---\n"
                f"用户当前问题: {user_message}"
            )
        else:
            enriched_message = user_message
        # ==================================================

        # 3. 让 Agent 思考
        print(f"--- [AI Request] 用户 {request.user.username} 提问: {user_message} ---")
        ai_reply = brain.think(request.user, enriched_message)

        # ============ 🔑 记住本轮对话 ============
        mm.remember(user_id, "default", "user", user_message)
        mm.remember(user_id, "default", "assistant", ai_reply)
        print(f"--- [MemoryHub] 已记住用户 {request.user.username} 的对话 ---")
        # =======================================

        return JsonResponse({
            "reply": ai_reply,
            "status": "success"
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"reply": f"我的大脑出了一点小状况: {str(e)}"}, status=500)