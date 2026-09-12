import sqlite3
import re
from datetime import datetime
import database

class FarmAIAssistant:
    """
    24/7 Intelligent Organic Farm Assistant ("Kisan AI").
    Provides contextual customer service, produce pricing, Telugu translations,
    order tracking, culinary recipes, health advice, and coupon/wallet guidance.
    """

    @staticmethod
    def get_db():
        conn = sqlite3.connect(database.DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def process_message(cls, message: str, user_id: int = None) -> dict:
        msg = (message or "").strip()
        if not msg:
            return {
                "reply": "Namaste! 🙏 How can I assist you with your farm-fresh vegetables today?",
                "suggestions": ["🥬 In-Stock Produce", "🚚 Track My Order", "🪙 Wallet Coins", "🍛 Recipe Ideas"],
                "intent": "empty"
            }

        msg_lower = msg.lower()
        conn = cls.get_db()

        try:
            # 1. Check for specific Order ID query (e.g. VOF-2026...)
            order_match = re.search(r'(vof-[0-9]{8}-[0-9]+)', msg_lower)
            if order_match:
                order_id = order_match.group(1).upper()
                return cls._handle_specific_order_tracking(conn, order_id)

            # 2. Problem / Complaint / Customer Support Intent (Priority)
            if any(k in msg_lower for k in ['problem', 'issue', 'complaint', 'late', 'delayed', 'damaged', 'rotten', 'spoiled', 'bad quality', 'refund', 'cancel', 'customer support', 'helpline', 'contact', 'call support']):
                return cls._handle_problem_complaint(conn, user_id)

            # 3. General Order Tracking Intent
            if any(k in msg_lower for k in ['track', 'where is my order', 'delivery status', 'order status', 'when will my order', 'when will my delivery', 'my order']):
                return cls._handle_order_tracking(conn, user_id)

            # 3b. Cash on Delivery & Payment Mode Intent
            if any(k in msg_lower for k in ['cod', 'cash on delivery', 'payment method', 'how to pay', 'payment mode', 'pay on delivery', 'upi on arrival']):
                return {
                    "reply": (
                        "### 💵 100% Cash on Delivery (COD) Only\n\n"
                        "At Vamsi Organic Farms, we proudly offer **exclusive Cash on Delivery** with zero convenience fees!\n\n"
                        "• **₹0 COD Fees**: No extra charges or surprise platform fees.\n"
                        "• **Doorstep Inspection**: Inspect your harvested vegetables before paying.\n"
                        "• **Cash or UPI on Arrival**: Pay cash or scan the delivery executive's UPI QR code right at your doorstep.\n\n"
                        "Add your favorite vegetables to your Farm Basket and proceed to express checkout!"
                    ),
                    "suggestions": ["🥬 Browse In-Stock Harvest", "🚚 Track My Order", "💬 WhatsApp Support (+91 76759 60440)"],
                    "intent": "payment_cod"
                }

            # 4. Wallet & Coins Intent
            if any(k in msg_lower for k in ['wallet', 'coin', 'coins', 'cashback', 'bonus', 'balance', 'redeem']):
                return cls._handle_wallet_inquiry(conn, user_id)

            # 5. Promo Coupons & Offers Intent
            if any(k in msg_lower for k in ['coupon', 'promo', 'discount', 'voucher', 'offer', 'deal', 'codes', 'farm50', 'vamsi10', 'organic25']):
                return cls._handle_coupon_inquiry(conn)

            # 6. Recipes & Cooking Intent
            if any(k in msg_lower for k in ['recipe', 'cook', 'curry', 'fry', 'pappu', 'sambar', 'rasam', 'how to make', 'dinner ideas', 'lunch ideas', 'what can i cook']):
                return cls._handle_recipe_inquiry(conn, msg_lower)

            # 7. Health, Diet & Nutrition Intent
            if any(k in msg_lower for k in ['health', 'diabetes', 'diabetic', 'weight loss', 'sugar', 'blood pressure', 'bp', 'iron', 'vitamin', 'nutrition', 'calories', 'immunity', 'healthy']):
                return cls._handle_health_inquiry(msg_lower)

            # 8. Organic Practices & Farm Certifications
            if any(k in msg_lower for k in ['organic', 'pesticide', 'chemical', 'certification', 'harvested', 'where do', 'how fresh', 'safe', 'natural']):
                return cls._handle_organic_inquiry()

            # 9. Vegetable Specific Inquiries (English or Telugu names)
            vegi_res = cls._match_vegetable_inquiry(conn, msg_lower)
            if vegi_res:
                return vegi_res

            # 10. Greetings & Identity
            if any(k in msg_lower for k in ['hi', 'hello', 'hey', 'namaste', 'good morning', 'good afternoon', 'good evening', 'who are you', 'help']):
                return cls._handle_greeting(user_id, conn)

            # Default Fallback: Intelligent Produce Search
            return cls._handle_general_fallback(conn, msg)

        finally:
            conn.close()

    @classmethod
    def _handle_specific_order_tracking(cls, conn, order_id: str) -> dict:
        items = conn.execute("""
            SELECT p.*, prod.name as product_name
            FROM purchases p
            JOIN products prod ON p.product_id = prod.id
            WHERE p.order_id = ?
        """, (order_id,)).fetchall()

        if not items:
            return {
                "reply": f"I couldn't find an order with Reference ID **#{order_id}**. Please double-check your Order ID from your Orders tab or receipt!",
                "suggestions": ["🚚 View My Recent Orders", "📞 Contact Farm Helpline", "🥬 Browse Fresh Produce"],
                "intent": "order_not_found"
            }

        first = items[0]
        status = first['status']
        items_summary = ", ".join([f"{it['product_name'].split('[')[0].strip()} (x{it['quantity']})" for it in items])
        total = sum(it['total_price'] for it in items)

        status_messages = {
            'Placed': '⏳ Confirmed & Queued. Our morning harvest team has scheduled your vegetables for fresh packing!',
            'Packed at Farm': '📦 Packed at Farm. Handpicked and packed into eco-friendly bags with zero preservatives.',
            'Out for Delivery': '🚚 Out for Doorstep Delivery! Our local express rider is navigating to your address now.',
            'Delivered': '🟢 Successfully Delivered! Fresh from the farm right to your kitchen.',
            'Cancelled': '🔴 Cancelled. If this was unexpected, please contact our helpline for assistance.'
        }
        status_text = status_messages.get(status, f'Status: {status}')

        reply = (
            f"### 📦 Order Status for **#{order_id}**\n\n"
            f"- **Current Status**: **{status}**\n"
            f"- **Timeline Update**: {status_text}\n"
            f"- **Scheduled Slot**: {first['delivery_date'] or 'Today'} • {first['delivery_slot'] or 'Morning'}\n"
            f"- **Destination**: {first['delivery_address']}\n"
            f"- **Vegetables ({len(items)} items)**: {items_summary}\n"
            f"- **Total Amount**: ₹{total:.2f}\n\n"
            f"Need any modifications or special delivery instructions? Let me know!"
        )

        return {
            "reply": reply,
            "suggestions": ["🚚 View All My Orders", "📞 Contact Delivery Rider", "🥬 Order More Vegetables"],
            "intent": "track_order"
        }

    @classmethod
    def _handle_order_tracking(cls, conn, user_id: int) -> dict:
        if not user_id:
            return {
                "reply": (
                    "To track your orders directly, please sign in with your mobile number! "
                    "Alternatively, you can type your Order ID (like `VOF-20260829-1003`) right here and I'll find it instantly."
                ),
                "suggestions": ["📱 Log In with Mobile", "🥬 Browse Daily Vegetables", "📞 Call Support"],
                "intent": "track_order_guest"
            }

        recent_order = conn.execute("""
            SELECT p.order_id, p.purchase_date, p.delivery_date, p.delivery_slot, p.delivery_address, p.status,
                   COUNT(p.id) as item_count, SUM(p.total_price) as total_amount
            FROM purchases p
            WHERE p.user_id = ?
            GROUP BY p.order_id
            ORDER BY p.purchase_date DESC
            LIMIT 1
        """, (user_id,)).fetchone()

        if not recent_order:
            return {
                "reply": "You haven't placed any vegetable orders yet! Explore today's 5:00 AM morning harvest catalog and get ₹100 Welcome Coins on your first purchase. 🥬",
                "suggestions": ["🥬 Explore Fresh Vegetables", "🪙 Check My Farm Coins", "🏷️ View Active Coupons"],
                "intent": "no_orders"
            }

        order_id = recent_order['order_id']
        status = recent_order['status']
        total = recent_order['total_amount']
        slot = recent_order['delivery_slot'] or 'Morning (8:00 AM - 11:00 AM)'

        status_emojis = {
            'Placed': '⏳',
            'Packed at Farm': '📦',
            'Out for Delivery': '🚚',
            'Delivered': '🟢',
            'Cancelled': '🔴'
        }
        emoji = status_emojis.get(status, '📦')

        reply = (
            f"Here is your latest harvest order status:\n\n"
            f"**Order ID**: `#{order_id}`\n"
            f"**Live Status**: {emoji} **{status}**\n"
            f"**Scheduled Delivery**: {recent_order['delivery_date'] or 'Today'} ({slot})\n"
            f"**Delivery Address**: {recent_order['delivery_address']}\n"
            f"**Total Amount**: ₹{total:.2f}\n\n"
            f"You can view complete itemized invoices anytime in the **My Orders** tab on your dashboard!"
        )

        return {
            "reply": reply,
            "suggestions": [f"Track #{order_id}", "🥬 Add More Vegetables", "🪙 My Farm Coins"],
            "intent": "track_order"
        }

    @classmethod
    def _handle_problem_complaint(cls, conn, user_id: int) -> dict:
        return {
            "reply": (
                "### 🛡️ 100% Farm Fresh Guarantee & Immediate Support\n\n"
                "We sincerely apologize for any problem with your order! At Vamsi Organic Farms, customer satisfaction is our top priority:\n\n"
                "1. **Instant Replacement or Refund**: If any vegetable arrived bruised, spoiled, or missing, we provide an immediate free replacement or credit full refund coins to your Farm Wallet.\n"
                "2. **📞 Customer Support & WhatsApp**: Call or chat with us at **`+91 7675960440`** (Helpline: `+91 9876543210`, 6:00 AM - 10:00 PM).\n"
                "3. **💬 WhatsApp Live Support**: Chat directly with our farm logistics coordinator on WhatsApp at **`+91 7675960440`**.\n"
                "4. **Need to Cancel?**: If your order is still in `Placed` status, you can cancel it with 1-click in the **My Orders** tab."
            ),
            "suggestions": ["📞 Call Helpline", "💬 Open WhatsApp Chat", "🚚 Check Order Status", "🪙 Check Wallet Balance"],
            "intent": "problem_support"
        }

    @classmethod
    def _handle_wallet_inquiry(cls, conn, user_id: int) -> dict:
        bal = 100.0
        if user_id:
            u = conn.execute("SELECT wallet_balance FROM users WHERE id = ?", (user_id,)).fetchone()
            if u and u['wallet_balance'] is not None:
                bal = float(u['wallet_balance'])

        reply = (
            f"### 🪙 Your Farm Wallet & Cashback\n\n"
            f"Your current balance is **₹{bal:.2f} Farm Coins**.\n\n"
            f"**How Farm Wallet works:**\n"
            f"- **Instant Welcome Reward**: Every registered buyer receives **₹100 Welcome Coins**.\n"
            f"- **5% Automatic Cashback**: Every time you complete an order, 5% of your bill is credited back as coins.\n"
            f"- **1-Click Redemption**: When placing an order in your **Farm Basket**, toggle **'Redeem Farm Wallet Coins'** to deduct coins directly from your bill!\n"
            f"- **1 Coin = ₹1 Rupee**: No complicated points — 100 coins equal ₹100 real discount."
        )

        return {
            "reply": reply,
            "suggestions": ["🧺 Go to Farm Basket", "🏷️ View Active Coupons", "🥬 Browse Daily Vegetables"],
            "intent": "wallet_inquiry"
        }

    @classmethod
    def _handle_coupon_inquiry(cls, conn) -> dict:
        coupons = conn.execute("SELECT * FROM coupons WHERE is_active = 1").fetchall()
        if not coupons:
            coupon_list = "- `FARM50`: Flat ₹50 OFF on orders above ₹199\n- `VAMSI10`: 10% OFF on all fresh harvest"
        else:
            coupon_list = "\n".join([
                f"- **`{c['code']}`**: {c['description']} (Min Order: ₹{c['min_order']:.0f})"
                for c in coupons
            ])

        reply = (
            f"### 🏷️ Active Promo Coupons & Discounts\n\n"
            f"Apply any of these verified promo codes at checkout in your Farm Basket:\n\n"
            f"{coupon_list}\n\n"
            f"💡 *Tip: You can combine promo coupons with your Farm Wallet coins for maximum savings!*"
        )

        return {
            "reply": reply,
            "suggestions": ["🧺 Open Farm Basket", "🪙 My Farm Coins", "🥬 Browse Produce Catalog"],
            "intent": "coupon_inquiry"
        }

    @classmethod
    def _handle_recipe_inquiry(cls, conn, msg_lower: str) -> dict:
        if 'palak' in msg_lower or 'spinach' in msg_lower:
            recipe = (
                "### 🍲 Recipe: Andhra Palakura Pappu (Spinach Dal)\n\n"
                "**Ingredients**: Fresh Organic Palak (పాలకూర), Toor Dal (కందిపప్పు), Tomatoes, Green Chillies, Garlic, Mustard & Cumin seeds.\n"
                "**Quick Steps**:\n"
                "1. Pressure cook 1 cup Toor Dal with chopped spinach, 2 tomatoes, green chillies, and a pinch of turmeric for 3 whistles.\n"
                "2. Mash gently and season with salt.\n"
                "3. In a small pan, heat ghee or cold-pressed oil, add crushed desi garlic, mustard seeds, cumin seeds, and dry red chillies (Tadka).\n"
                "4. Pour hot tadka over dal and serve with hot steamed rice and ghee! 🥗"
            )
        elif 'tomato' in msg_lower or 'tamata' in msg_lower or 'rasam' in msg_lower:
            recipe = (
                "### 🍅 Recipe: Traditional Country Tomato Rasam (చారు)\n\n"
                "**Ingredients**: Fresh Hybrid/Desi Tomatoes (టమోటా), crushed garlic, black pepper, cumin seeds, fresh coriander roots, curry leaves.\n"
                "**Quick Steps**:\n"
                "1. Boil 3 chopped ripe tomatoes in 2 cups water with salt and turmeric until soft.\n"
                "2. Crush garlic, cumin, and black pepper into a coarse paste.\n"
                "3. Add the spice paste to the boiling broth with fresh coriander leaves.\n"
                "4. Temper with mustard seeds, curry leaves, and a dash of asafoetida (hing). Heavenly aroma and great for immunity!"
            )
        elif 'bhindi' in msg_lower or 'okra' in msg_lower or 'bendakaya' in msg_lower:
            recipe = (
                "### 🥗 Recipe: Crispy Bendakaya Vepudu (Andhra Okra Fry)\n\n"
                "**Ingredients**: Tender Ladies Finger (బెండకాయ), crushed peanuts, curry leaves, red chilli powder, garlic.\n"
                "**Secret Tip**: Wash and dry the bhindi thoroughly before chopping to keep it non-slimy!\n"
                "**Steps**:\n"
                "1. Sauté chopped bhindi in 2 tbsp hot oil on medium flame until golden and crisp (10-12 mins).\n"
                "2. In a separate pan, roast peanuts, crushed garlic, and curry leaves.\n"
                "3. Toss together with salt and chilli powder. Delicious crunch with every bite!"
            )
        elif 'brinjal' in msg_lower or 'vankaya' in msg_lower:
            recipe = (
                "### 🍆 Recipe: Gutti Vankaya Kura (Stuffed Andhra Eggplant)\n\n"
                "**Ingredients**: Fresh Purple Brinjals (వంకాయ), roasted peanuts, sesame seeds (నువ్వులు), coriander seeds, desiccated coconut, onions.\n"
                "**Steps**:\n"
                "1. Slit small round brinjals into four quarters keeping the stem intact.\n"
                "2. Blend roasted peanuts, sesame, coconut, and spices into a thick masala paste.\n"
                "3. Stuff brinjals generously with the masala and cook slowly in oil on low flame with tamarind pulp until melt-in-mouth tender."
            )
        else:
            recipe = (
                "### 🍛 Farm-to-Table Andhra Kitchen Ideas\n\n"
                "Here are three delicious everyday home curries you can make with our harvest:\n"
                "1. **Aloo Methi Stir Fry**: Diced new crop potatoes gently roasted with earthy fresh fenugreek leaves (మెంతికూర).\n"
                "2. **Sorakaya Majjiga Pulusu**: Hydrating tender bottle gourd (సొరకాయ) simmered in spiced buttermilk curry with ginger and green chillies.\n"
                "3. **Mixed Farm Sambar**: Sweet carrots, drumstick, brinjal, and tomatoes simmered in tangy dal.\n\n"
                "Tell me which vegetables you have at home, and I will create an instant recipe for you!"
            )

        return {
            "reply": recipe,
            "suggestions": ["🥬 In-Stock Produce", "🍅 Buy Tomatoes & Palak", "🚚 Track Order"],
            "intent": "recipe_ideas"
        }

    @classmethod
    def _handle_health_inquiry(cls, msg_lower: str) -> dict:
        if 'diabet' in msg_lower or 'sugar' in msg_lower:
            advice = (
                "### 🩺 Best Produce for Blood Sugar & Diabetes Management\n\n"
                "- **Crisp Bitter Gourd (Karela / కాకరకాయ)**: Contains *Charantin* and *Polypeptide-p*, proven natural compounds that mimic insulin and help control blood glucose.\n"
                "- **Fresh Fenugreek Leaves (Methi / మెంతికూర)**: High in soluble fiber that slows carbohydrate absorption.\n"
                "- **Tender Ridge Gourd (Turai / బీరకాయ)**: Low glycemic index and rich in dietary cellulose.\n"
                "- **Spinach (Palak / పాలకూర)**: Zero simple sugars, packed with magnesium and antioxidants."
            )
        elif 'weight' in msg_lower or 'diet' in msg_lower or 'calorie' in msg_lower:
            advice = (
                "### ⚖️ Best Low-Calorie Vegetables for Weight Management\n\n"
                "- **Bottle Gourd (Lauki / సొరకాయ)**: 96% water content, only 14 calories per 100g, excellent for liver health and belly fat reduction.\n"
                "- **Green Cabbage (Patta Gobhi / క్యాబేజీ)**: High crunch and fiber keeps you full for hours.\n"
                "- **Fresh Spinach (Palak / పాలకూర)**: High protein-to-calorie ratio with zero bad fats.\n"
                "- **Ridge Gourd (Turai / బీరకాయ)**: High dietary fiber that aids natural detox."
            )
        elif 'iron' in msg_lower or 'blood' in msg_lower:
            advice = (
                "### 🩸 High-Iron Vegetables for Hemoglobin & Energy\n\n"
                "- **Fresh Spinach (Palak / పాలకూర)**: High dietary non-heme iron and folate.\n"
                "- **Fresh Fenugreek (Methi / మెంతికూర)**: Traditional Ayurvedic leafy green for boosting stamina.\n"
                "- **Fresh Coriander Leaves (Dhania / కొత్తిమీర)**: Rich in Vitamin C which enhances iron absorption in the body."
            )
        else:
            advice = (
                "### 🌿 Everyday Health & Immunity Powerhouses\n\n"
                "- **Desi Garlic (వెల్లుల్లి)**: Contains *Allicin* for cholesterol balance and immunity.\n"
                "- **Fresh Ginger (అల్లం)**: Superior anti-inflammatory gingerol for digestion and joint health.\n"
                "- **Hybrid Tomatoes (టమోటా)**: Rich in *Lycopene*, supporting heart health and UV skin protection.\n"
                "- **Green Capsicum (బెంగళూరు మిర్చి)**: Packed with Vitamin C, more than oranges per 100g!"
            )

        return {
            "reply": advice,
            "suggestions": ["🥬 View Leafy Greens", "🫒 View Gourds & Roots", "🧺 Farm Basket"],
            "intent": "health_advice"
        }

    @classmethod
    def _handle_organic_inquiry(cls) -> dict:
        reply = (
            "### 🌿 100% Certified Organic • Farm-to-Table Transparency\n\n"
            "- **5:00 AM Morning Harvest**: Every vegetable is harvested in the early dawn hours, cleaned with potable water, and sorted before sunrise.\n"
            "- **Zero Chemical Pesticides**: Grown strictly using Panchagavya, Jeevamrutham, and organic compost — never synthetic fertilizers.\n"
            "- **Standards Compliance**: Complies with **APEDA NPOP** and **PGS-India** organic farming standards.\n"
            "- **Zero Chemical Waxing**: Vegetables are delivered raw and unpolished, retaining natural skins and maximum vitamins.\n"
            "- **15–30 Min Doorstep Delivery**: Direct farm-to-consumer model ensures freshness is preserved without cold-storage degradation."
        )
        return {
            "reply": reply,
            "suggestions": ["🥬 Explore Today's Harvest", "🪙 My Welcome Coins", "🚚 Delivery Slots"],
            "intent": "organic_info"
        }

    @classmethod
    def _match_vegetable_inquiry(cls, conn, msg_lower: str) -> dict:
        vegetables = conn.execute("SELECT * FROM products").fetchall()
        matched = []

        keywords_map = {
            'tomato': ['tomato', 'tamatar', 'టమోటా', 'tamota', 'tamata'],
            'onion': ['onion', 'pyaz', 'ఉల్లిపాయ', 'ullipayalu', 'kanda'],
            'potato': ['potato', 'aloo', 'బంగాళాదుంప', 'bangaladumpa', 'batata'],
            'chilli': ['chilli', 'mirch', 'పచ్చిమిర్చి', 'pachi mirchi', 'chillies'],
            'ginger': ['ginger', 'adrak', 'అల్లం', 'allam'],
            'garlic': ['garlic', 'lahsun', 'వెల్లుల్లి', 'vellulli'],
            'coriander': ['coriander', 'dhania', 'కొత్తిమీర', 'kothimeera'],
            'mint': ['mint', 'pudina', 'పుదీనా'],
            'spinach': ['spinach', 'palak', 'పాలకూర', 'palakoora'],
            'methi': ['methi', 'fenugreek', 'మెంతికూర', 'menthikoora'],
            'bhindi': ['bhindi', 'okra', 'ladies finger', 'బెండకాయ', 'bendakaya'],
            'cauliflower': ['cauliflower', 'gobhi', 'క్యాలీఫ్లవర్'],
            'cabbage': ['cabbage', 'patta gobhi', 'క్యాబేజీ'],
            'peas': ['peas', 'matar', 'బఠానీలు', 'bataneelu'],
            'carrot': ['carrot', 'gajar', 'క్యారెట్'],
            'capsicum': ['capsicum', 'shimla mirch', 'బెంగళూరు మిర్చి'],
            'brinjal': ['brinjal', 'baingan', 'వంకాయ', 'vankaya', 'eggplant'],
            'bottle gourd': ['bottle gourd', 'lauki', 'సొరకాయ', 'ఆనపకాయ', 'sorakaya'],
            'bitter gourd': ['bitter gourd', 'karela', 'కాకరకాయ', 'kakarakaya'],
            'ridge gourd': ['ridge gourd', 'turai', 'బీరకాయ', 'beerakaya']
        }

        for p in vegetables:
            p_name_lower = p['name'].lower()
            p_tags_lower = (p['tags'] or '').lower()
            for key, aliases in keywords_map.items():
                if any(alias in msg_lower for alias in aliases):
                    if any(alias in p_name_lower or alias in p_tags_lower for alias in aliases):
                        if p not in matched:
                            matched.append(p)

        if matched:
            lines = []
            for it in matched[:4]:
                stock_label = f"🟢 In Stock ({it['stock']} {it['unit']} available)" if it['stock'] > 10 else f"⚡ Low Stock ({it['stock']} {it['unit']} left)"
                lines.append(
                    f"- {it['image_url']} **{it['name']}**\n"
                    f"  Price: **₹{it['price']:.2f}** per {it['unit']} • {stock_label}\n"
                    f"  *Category*: {it['category']}"
                )
            reply = (
                f"### 🥬 Fresh Produce Availability\n\n"
                f"Here are the items matching your inquiry harvested this morning:\n\n" +
                "\n\n".join(lines) +
                f"\n\nAll items are certified organic, handpicked today at 5 AM. Would you like to add any to your Farm Basket?"
            )
            return {
                "reply": reply,
                "suggestions": ["🧺 Open Farm Basket", "🍛 Recipe Ideas", "🪙 Use Wallet Coins"],
                "intent": "product_inquiry",
                "products": [dict(p) for p in matched[:4]]
            }

        return None

    @classmethod
    def _handle_greeting(cls, user_id: int, conn) -> dict:
        user_name = "there"
        if user_id:
            u = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
            if u:
                user_name = u['name']

        reply = (
            f"Namaste, {user_name}! 🙏 I am **Kisan AI**, your 24/7 personal farm assistant at Vamsi Organic Farms.\n\n"
            f"I can help you with:\n"
            f"- 🥬 **Checking vegetable availability & live mandi prices**\n"
            f"- 🚚 **Live tracking your harvest delivery status**\n"
            f"- 🍛 **Authentic Andhra recipe suggestions for today's vegetables**\n"
            f"- 🩺 **Nutritional advice & diabetes-friendly produce**\n"
            f"- 🪙 **Checking your Farm Wallet balance & active promo discounts**\n"
            f"- 🛡️ **Resolving any delivery or freshness concerns**\n\n"
            f"What would you like assistance with right now?"
        )
        return {
            "reply": reply,
            "suggestions": ["🥬 In-Stock Produce", "🚚 Track Latest Order", "🪙 Wallet Coins", "🍛 Recipe Ideas", "🏷️ Active Coupons"],
            "intent": "greeting"
        }

    @classmethod
    def _handle_general_fallback(cls, conn, query: str) -> dict:
        # Search products by query tokens
        prods = conn.execute("""
            SELECT * FROM products 
            WHERE name LIKE ? OR category LIKE ? OR tags LIKE ? 
            LIMIT 3
        """, (f"%{query}%", f"%{query}%", f"%{query}%")).fetchall()

        if prods:
            item_list = "\n".join([f"- {p['image_url']} **{p['name']}**: ₹{p['price']:.2f} per {p['unit']}" for p in prods])
            reply = (
                f"I found these organic produce items related to *'{query}'*:\n\n"
                f"{item_list}\n\n"
                f"Would you like recipe ideas for these or want to check current delivery slots?"
            )
            return {
                "reply": reply,
                "suggestions": ["🧺 Add to Basket", "🍛 Suggest Recipe", "🚚 Delivery Slots"],
                "intent": "search_result"
            }

        return {
            "reply": (
                f"I am here to help with all farm operations and vegetable queries! "
                f"You can ask me about **today's harvest prices**, **order tracking**, **traditional recipes**, "
                f"**Farm Wallet coins**, or **how to apply discount coupons**."
            ),
            "suggestions": ["🥬 What's in Stock Today?", "🚚 Track My Order", "🪙 Farm Wallet Balance", "📞 Customer Support"],
            "intent": "general_help"
        }
