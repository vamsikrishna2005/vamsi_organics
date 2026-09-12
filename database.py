import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'market.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Drop tables if they exist to ensure clean slate
    cursor.execute("DROP TABLE IF EXISTS wallet_transactions")
    cursor.execute("DROP TABLE IF EXISTS reviews")
    cursor.execute("DROP TABLE IF EXISTS user_addresses")
    cursor.execute("DROP TABLE IF EXISTS notifications")
    cursor.execute("DROP TABLE IF EXISTS purchases")
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("DROP TABLE IF EXISTS products")

    # Create Products Table
    cursor.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            unit TEXT NOT NULL,
            image_url TEXT,
            tags TEXT NOT NULL,
            stock INTEGER NOT NULL,
            description TEXT,
            rating REAL DEFAULT 4.8,
            review_count INTEGER DEFAULT 28,
            nutrition_info TEXT DEFAULT ''
        )
    """)

    # Create Users Table with Farm Wallet Balance & OAuth 2.0 Provider
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE,
            role TEXT DEFAULT 'customer',
            password TEXT,
            wallet_balance REAL DEFAULT 100.0,
            auth_provider TEXT DEFAULT 'local',
            profile_picture TEXT DEFAULT ''
        )
    """)

    # Create Reviews Table
    cursor.execute("""
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating REAL NOT NULL,
            comment TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Create Wallet Transactions Table
    cursor.execute("""
        CREATE TABLE wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Create User Addresses Table (Allows saving multiple addresses with default selection)
    cursor.execute("""
        CREATE TABLE user_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            label TEXT DEFAULT 'Home', -- 'Home', 'Work', 'Other'
            address TEXT NOT NULL,
            is_default INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Create Purchases Table with Order Tracking & Invoicing
    cursor.execute("""
        CREATE TABLE purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            total_price REAL NOT NULL,
            purchase_date TEXT NOT NULL,
            delivery_date TEXT,
            delivery_slot TEXT,
            delivery_address TEXT DEFAULT 'Door #12, Green Avenue, Hyderabad',
            status TEXT DEFAULT 'Placed', -- 'Placed', 'Packed at Farm', 'Out for Delivery', 'Delivered', 'Cancelled'
            coupon_code TEXT DEFAULT '',
            discount_amount REAL DEFAULT 0.0,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    """)

    # Create User Cart Table for unique per-user persistent basket storage
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, product_id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_cart_uid ON user_cart(user_id)")

    # Create Indexes for lightning fast queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchases_user ON purchases(user_id, purchase_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchases_order ON purchases(order_id)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower ON users(LOWER(email))")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_addresses ON user_addresses(user_id, is_default)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_user_addresses_unique ON user_addresses(user_id, LOWER(TRIM(address)))")

    # Create Notifications Table
    cursor.execute("""
        CREATE TABLE notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            type TEXT NOT NULL, -- 'recommendation', 'restock', 'alert'
            is_read INTEGER DEFAULT 0, -- 0 for false, 1 for true
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # 1. Seed Top 20 Daily Indian Available Vegetables with Telugu Names
    products = [
        # Daily Essentials (1 to 6)
        ("Hybrid Tomatoes (Tamatar) [టమోటా]", "Daily Essentials", 35.00, "1 kg", "🍅", "cooking-essential, red, fresh, tamatar, tomato, tamota, టమోటా, gravy, essential", 80, "Farm-fresh juicy red tomatoes, rich in Lycopene and essential for daily Indian gravies and curries."),
        ("Desi Red Onions (Nashik Pyaz) [ఉల్లిపాయలు]", "Daily Essentials", 38.00, "1 kg", "🧅", "cooking-essential, all-season, fresh, pyaz, onion, kanda, ullipayalu, ఉల్లిపాయలు, essential", 95, "Crisp, pungent Nashik red onions. The backbone of every Indian tadka, gravy, and salad."),
        ("New Crop Potatoes (Aloo) [బంగాళాదుంప]", "Daily Essentials", 30.00, "1 kg", "🥔", "cooking-essential, root, starch, aloo, potato, batata, bangaladumpa, బంగాళాదుంప, essential", 120, "Freshly harvested golden potatoes, thin-skinned and perfect for curries, fries, and parathas."),
        ("Teekhi Green Chillies (Hari Mirch) [పచ్చిమిర్చి]", "Daily Essentials", 15.00, "100g", "🌶️", "spicy, fresh, essential, mirchi, pachi mirchi, పచ్చిమిర్చి, tadka, green", 50, "Spicy and aromatic fresh green chillies handpicked for bold Indian seasoning and tadka."),
        ("Fresh Ginger (Adrak) [అల్లం]", "Daily Essentials", 25.00, "250g", "🫚", "root, aromatic, tea-essential, adrak, ginger, allam, అల్లం, immunity, cooking-essential", 40, "Strong aromatic fresh ginger rhizomes, great for morning chai, curries, and digestive health."),
        ("Desi Garlic Bulbs (Lahsun) [వెల్లుల్లి]", "Daily Essentials", 45.00, "250g", "🧄", "aromatic, immunity, essential, lahsun, garlic, vellulli, వెల్లుల్లి, tadka, cooking-essential", 45, "Pungent white garlic cloves, rich in allicin for superior flavor and daily wellness."),

        # Leafy Greens (7 to 10)
        ("Fresh Coriander Leaves (Hara Dhania) [కొత్తిమీర]", "Leafy Greens", 15.00, "1 Bunch (100g)", "🌿", "leafy, herb, aromatic, dhania, coriander, kothimeera, కొత్తిమీర, garnish, green, fresh", 60, "Crisp, aromatic coriander leaves with roots, ideal for refreshing chutneys and everyday garnishing."),
        ("Fresh Mint Leaves (Pudina) [పుదీనా]", "Leafy Greens", 15.00, "1 Bunch (100g)", "🍃", "leafy, herb, cooling, pudina, mint, పుదీనా, chutney, aromatic, green", 50, "Fragrant spearmint leaves, excellent for biryani, cooling raitas, and summer beverages."),
        ("Fresh Spinach (Palak) [పాలకూర]", "Leafy Greens", 25.00, "1 Bunch (250g)", "🥬", "leafy, green, iron-rich, palak, spinach, palakoora, పాలకూర, curry, healthy, organic", 40, "Tender organic spinach leaves packed with dietary iron, vitamins A & C. Great for Palak Paneer."),
        ("Fresh Fenugreek Leaves (Methi) [మెంతికూర]", "Leafy Greens", 25.00, "1 Bunch (250g)", "🌱", "leafy, green, traditional, methi, menthikoora, మెంతికూర, paratha, healthy", 35, "Earthy, mildly bitter fresh methi leaves, perfect for wholesome Aloo Methi and hot Theplas."),

        # Fresh Vegetables (11 to 17)
        ("Tender Ladies Finger (Bhindi) [బెండకాయ]", "Fresh Vegetables", 35.00, "500g", "🥗", "green, stir-fry, popular, bhindi, okra, bendakaya, బెండకాయ, vegetable, fresh", 45, "Crisp, slim and tender bhindi without hard seeds, perfect for crunchy Kurkuri Bhindi and stir fries."),
        ("Fresh Cauliflower (Phool Gobhi) [క్యాలీఫ్లవర్]", "Fresh Vegetables", 35.00, "1 pc (500g)", "🥦", "cruciferous, fresh, gobhi, cauliflower, క్యాలీఫ్లవర్, curry, vegetable", 30, "Snow-white tight cauliflower florets, ideal for Aloo Gobhi, Gobi Manchurian, and stuffed parathas."),
        ("Green Cabbage (Patta Gobhi) [క్యాబేజీ]", "Fresh Vegetables", 28.00, "1 pc (500g)", "🥬", "cruciferous, crunchy, salad, patta gobhi, cabbage, క్యాబేజీ, vegetable", 35, "Crunchy, layered farm-fresh green cabbage for stir-fries, momos, and traditional salads."),
        ("Sweet Green Peas (Taza Matar) [బఠానీలు]", "Fresh Vegetables", 55.00, "500g", "🫛", "sweet, fresh, seasonal, matar, peas, bataneelu, బఠానీలు, paneer, vegetable", 40, "Naturally sweet, tender green pea pods, perfect for Matar Paneer, Pulao, and Aloo Matar."),
        ("Orange Sweet Carrots (Gajar) [క్యారెట్]", "Fresh Vegetables", 40.00, "500g", "🥕", "root, crunchy, vitamin-a, gajar, carrot, క్యారెట్, salad, vegetable", 50, "Sweet and crunchy carrots full of beta-carotene, great for salads, mixed veg, and Gajar Halwa."),
        ("Green Capsicum (Shimla Mirch) [బెంగళూరు మిర్చి]", "Fresh Vegetables", 45.00, "500g", "🫑", "crunchy, bell-pepper, capsicum, shimla mirch, బెంగళూరు మిర్చి, curry, vegetable", 35, "Thick-walled, glossy green bell peppers with crisp texture for Kadai paneer, noodles, and curries."),
        ("Purple Brinjal (Baingan) [వంకాయ]", "Fresh Vegetables", 35.00, "500g", "🍆", "eggplant, brinjal, vankaya, వంకాయ, traditional, curry, baingan, bharta, vegetable", 40, "Glossy deep-purple round eggplants, perfect for smoky Baingan Bharta and Gutti Vankaya."),

        # Gourds & Roots (18 to 20)
        ("Fresh Bottle Gourd (Lauki) [సొరకాయ / ఆనపకాయ]", "Gourds & Roots", 30.00, "1 pc (500g)", "🥒", "gourd, light, healthy, lauki, doodhi, sorakaya, anapakaya, సొరకాయ, ఆనపకాయ, vegetable", 30, "Tender and hydrating green bottle gourd, light on stomach and rich in dietary fiber."),
        ("Crisp Bitter Gourd (Karela) [కాకరకాయ]", "Gourds & Roots", 40.00, "500g", "🫒", "gourd, bitter, health, karela, kakarakaya, కాకరకాయ, diabetic-care, vegetable", 25, "Fresh dark-green bumpy karela, revered for blood sugar control and crispy masala fry."),
        ("Tender Ridge Gourd (Turai) [బీరకాయ]", "Gourds & Roots", 38.00, "500g", "🎋", "gourd, fiber-rich, light, turai, beerakaya, బీరకాయ, vegetable", 30, "Sweet-fleshed ridged gourd, ideal for gentle dal curries, chutneys, and low-calorie diets.")
    ]
    cursor.executemany("""
        INSERT INTO products (name, category, price, unit, image_url, tags, stock, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, products)

    # 2. Seed Users & Admin (Admin password hashed with werkzeug)
    admin_hashed_pw = generate_password_hash("admin123")
    users = [
        ("Vamsi Vegi", "vamsi@example.com", "8888888888", "customer", None),
        ("Pranav Ghee", "pranav@example.com", "7777777777", "customer", None),
        ("Sita Sweet", "sita@example.com", "6666666666", "customer", None),
        ("General Shopper", "shopper@example.com", "5555555555", "customer", None),
        ("Store Manager (Admin)", "admin@vamsiorganicfarms.com", "7675960440", "admin", admin_hashed_pw)
    ]
    cursor.executemany("""
        INSERT INTO users (name, email, phone, role, password)
        VALUES (?, ?, ?, ?, ?)
    """, users)

    # Commit users first to get their IDs
    conn.commit()

    # 3. Seed Purchases (Simulate history with Order IDs, address, and live status)
    now = datetime.now()
    
    # User 1 (Vamsi Vegi): Loves greens and cooking essentials.
    # Product IDs: 9 (Spinach ₹25), 7 (Coriander ₹15), 1 (Tomatoes ₹35)
    purchases_user1 = [
        ('VOF-20260826-1001', 1, 9, 2, 50.00, (now - timedelta(days=6)).strftime('%Y-%m-%d %H:%M:%S'), '2026-08-27', 'Morning (8:00 AM - 11:00 AM)', 'Flat 301, Sri Sai Residency, Madhapur, Hyderabad', 'Delivered'),
        ('VOF-20260827-1002', 1, 7, 1, 15.00, (now - timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S'), '2026-08-28', 'Morning (8:00 AM - 11:00 AM)', 'Flat 301, Sri Sai Residency, Madhapur, Hyderabad', 'Delivered'),
        ('VOF-20260829-1003', 1, 1, 3, 105.00, (now - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'), '2026-08-30', 'Morning (8:00 AM - 11:00 AM)', 'Flat 301, Sri Sai Residency, Madhapur, Hyderabad', 'Out for Delivery')
    ]

    # User 2 (Pranav Ghee): Buys Carrots (15 ₹40), Potatoes (3 ₹30), Spinach (9 ₹25)
    purchases_user2 = [
        ('VOF-20260805-1004', 2, 15, 1, 40.00, (now - timedelta(days=28)).strftime('%Y-%m-%d %H:%M:%S'), '2026-08-06', 'Evening (5:00 PM - 8:00 PM)', 'House #45, Jubilee Hills, Hyderabad', 'Delivered'),
        ('VOF-20260823-1005', 2, 3, 2, 60.00, (now - timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S'), '2026-08-24', 'Evening (5:00 PM - 8:00 PM)', 'House #45, Jubilee Hills, Hyderabad', 'Delivered'),
        ('VOF-20260813-1006', 2, 9, 1, 25.00, (now - timedelta(days=20)).strftime('%Y-%m-%d %H:%M:%S'), '2026-08-14', 'Evening (5:00 PM - 8:00 PM)', 'House #45, Jubilee Hills, Hyderabad', 'Delivered')
    ]

    # User 3 (Sita Sweet): Buys Mint (8 ₹15), Tomatoes (1 ₹35), Onions (2 ₹38)
    purchases_user3 = [
        ('VOF-20260821-1007', 3, 8, 2, 30.00, (now - timedelta(days=12)).strftime('%Y-%m-%d %H:%M:%S'), '2026-08-22', 'Afternoon (12:00 PM - 3:00 PM)', 'Plot 12, Amaravathi Road, Guntur', 'Delivered'),
        ('VOF-20260808-1008', 3, 1, 1, 35.00, (now - timedelta(days=25)).strftime('%Y-%m-%d %H:%M:%S'), '2026-08-09', 'Afternoon (12:00 PM - 3:00 PM)', 'Plot 12, Amaravathi Road, Guntur', 'Delivered'),
        ('VOF-20260819-1009', 3, 2, 1, 38.00, (now - timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S'), '2026-08-20', 'Afternoon (12:00 PM - 3:00 PM)', 'Plot 12, Amaravathi Road, Guntur', 'Delivered')
    ]

    # User 4 (General Shopper): Buys Onions (2 ₹38), Potatoes (3 ₹30), Tomatoes (1 ₹35)
    purchases_user4 = [
        ('VOF-20260825-1010', 4, 2, 2, 76.00, (now - timedelta(days=8)).strftime('%Y-%m-%d %H:%M:%S'), '2026-08-26', 'Morning (8:00 AM - 11:00 AM)', 'Door 8-2, MVP Colony, Visakhapatnam', 'Delivered'),
        ('VOF-20260825-1010', 4, 3, 2, 60.00, (now - timedelta(days=8)).strftime('%Y-%m-%d %H:%M:%S'), '2026-08-26', 'Morning (8:00 AM - 11:00 AM)', 'Door 8-2, MVP Colony, Visakhapatnam', 'Delivered'),
        ('VOF-20260825-1010', 4, 1, 1, 35.00, (now - timedelta(days=8)).strftime('%Y-%m-%d %H:%M:%S'), '2026-08-26', 'Morning (8:00 AM - 11:00 AM)', 'Door 8-2, MVP Colony, Visakhapatnam', 'Delivered')
    ]

    all_purchases = purchases_user1 + purchases_user2 + purchases_user3 + purchases_user4
    cursor.executemany("""
        INSERT INTO purchases (order_id, user_id, product_id, quantity, total_price, purchase_date, delivery_date, delivery_slot, delivery_address, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, all_purchases)

    # 4. Seed Saved Addresses (Pre-populate default address for customers)
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    addresses = [
        (1, 'Home', 'Flat 301, Sri Sai Residency, Madhapur, Hyderabad - 500081', 1, now_str),
        (1, 'Office', 'Cyber Towers, 4th Floor, Hitech City, Hyderabad - 500081', 0, now_str),
        (2, 'Home', 'House #45, Road No 10, Jubilee Hills, Hyderabad - 500033', 1, now_str),
        (3, 'Home', 'Plot 12, Amaravathi Road, Guntur - 522002', 1, now_str),
        (4, 'Home', 'Door 8-2, Sector 4, MVP Colony, Visakhapatnam - 530017', 1, now_str)
    ]
    cursor.executemany("""
        INSERT INTO user_addresses (user_id, label, address, is_default, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, addresses)

    # 5. Seed Notifications (Pre-populate a couple of alerts)
    notifications = [
        (1, "Fresh organic Coriander is freshly harvested and back in stock! 🌿", "restock", (now - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')),
        (2, "We noticed you bought Orange Sweet Carrots last month. Would you like to restock for your kitchen? 🥕", "recommendation", (now - timedelta(hours=4)).strftime('%Y-%m-%d %H:%M:%S'))
    ]
    cursor.executemany("""
        INSERT INTO notifications (user_id, message, type, timestamp)
        VALUES (?, ?, ?, ?)
    """, notifications)

    conn.commit()
    conn.close()
    check_and_migrate_db()
    print("Database initialized and seeded successfully!")

def check_and_migrate_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Purchases table migrations
    pragma_purchases = cursor.execute("PRAGMA table_info(purchases)").fetchall()
    purchases_cols = [col['name'] for col in pragma_purchases]
    if 'coupon_code' not in purchases_cols:
        cursor.execute("ALTER TABLE purchases ADD COLUMN coupon_code TEXT DEFAULT ''")
    if 'discount_amount' not in purchases_cols:
        cursor.execute("ALTER TABLE purchases ADD COLUMN discount_amount REAL DEFAULT 0.0")
        
    # 2. Users table migrations (Wallet Balance & OAuth 2.0)
    pragma_users = cursor.execute("PRAGMA table_info(users)").fetchall()
    users_cols = [col['name'] for col in pragma_users]
    if 'wallet_balance' not in users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN wallet_balance REAL DEFAULT 100.0")
        cursor.execute("UPDATE users SET wallet_balance = 100.0 WHERE wallet_balance IS NULL")
    if 'auth_provider' not in users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT 'local'")
    if 'profile_picture' not in users_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN profile_picture TEXT DEFAULT ''")
        
    # 3. Products table migrations (Ratings, Reviews, Nutrition)
    pragma_products = cursor.execute("PRAGMA table_info(products)").fetchall()
    products_cols = [col['name'] for col in pragma_products]
    if 'rating' not in products_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN rating REAL DEFAULT 4.8")
    if 'review_count' not in products_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN review_count INTEGER DEFAULT 28")
    if 'nutrition_info' not in products_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN nutrition_info TEXT DEFAULT ''")

    # 4. Create Reviews Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id)")

    # 5. Create Wallet Transactions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL, -- 'credit', 'debit'
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wallet_user ON wallet_transactions(user_id)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower ON users(LOWER(email))")

    # 6. Populate default nutrition info for all 20 vegetables if missing
    NUTRITION_MAP = {
        1: '{"calories": "22 kcal / 100g", "vitamins": "Vitamin C, Lycopene, Potassium", "benefits": "Powerful antioxidant protection, heart health & natural skin glow.", "culinary_pairing": "Ideal for Telugu Tamata Pappu, Rasam, and rich gravies."}',
        2: '{"calories": "40 kcal / 100g", "vitamins": "Quercetin, Vitamin B6, Sulfur", "benefits": "Aids blood sugar regulation and natural anti-inflammatory defense.", "culinary_pairing": "The backbone of daily Indian tadka, sambar, and fresh salads."}',
        3: '{"calories": "77 kcal / 100g", "vitamins": "Potassium, Vitamin C, Dietary Fiber", "benefits": "Sustained clean energy, gut-friendly starch, and electrolyte balance.", "culinary_pairing": "Crispy aloo fry, curries, and stuffed parathas."}',
        4: '{"calories": "40 kcal / 100g", "vitamins": "Capsaicin, Vitamin C, Vitamin A", "benefits": "Boosts metabolic rate, natural pain relief, and immune support.", "culinary_pairing": "Essential for spicy seasoning, tadka, and pachadis."}',
        5: '{"calories": "80 kcal / 100g", "vitamins": "Gingerol, Zinc, Magnesium", "benefits": "Soothes digestion, relieves morning nausea, and anti-cold defense.", "culinary_pairing": "Morning herbal chai, ginger rasam, and daily curries."}',
        6: '{"calories": "149 kcal / 100g", "vitamins": "Allicin, Manganese, Vitamin B6", "benefits": "Promotes cardiovascular health, regulates BP, and natural antibiotic.", "culinary_pairing": "Daily garlic tadka, vellulli karam, and rasam."}',
        7: '{"calories": "23 kcal / 100g", "vitamins": "Vitamin A, C, K, Iron", "benefits": "Natural heavy metal detoxification and liver wellness support.", "culinary_pairing": "Refreshing kothimeera pachadi, garnishing, and gravies."}',
        8: '{"calories": "44 kcal / 100g", "vitamins": "Menthol, Rosmarinic Acid, Vitamin A", "benefits": "Cooling digestive relief, breath freshening, and respiratory clarity.", "culinary_pairing": "Hyderabadi biryani, pudina chutney, and cooling raita."}',
        9: '{"calories": "23 kcal / 100g", "vitamins": "Dietary Iron, Folate, Vitamin K, A", "benefits": "Strengthens hemoglobin, bone density, and eye vision.", "culinary_pairing": "Classic Palak Paneer, Palakoora Pappu, and dal."}',
        10: '{"calories": "49 kcal / 100g", "vitamins": "Saponins, Fiber, Iron", "benefits": "Helps manage blood glucose levels and cholesterol absorption.", "culinary_pairing": "Methi Thepla, Menthikura Pappu, and vegetable stir fry."}',
        11: '{"calories": "25 kcal / 100g", "vitamins": "Choline, Vitamin C, Sulforaphane", "benefits": "Cellular detox, brain health, and healthy weight management.", "culinary_pairing": "Gobi Masala, Aloo Gobi, and vegetable biryani."}',
        12: '{"calories": "25 kcal / 100g", "vitamins": "Glutamine, Vitamin K, Fiber", "benefits": "Soothes stomach lining and supports digestive tract health.", "culinary_pairing": "South Indian Cabbage Poriyal, Kootu, and salads."}',
        13: '{"calories": "31 kcal / 100g", "vitamins": "Silicon, Folate, Vitamin K", "benefits": "Bone mineral density support and cardiovascular health.", "culinary_pairing": "Beans Usili, coconut stir-fry, and mixed vegetable kurma."}',
        14: '{"calories": "33 kcal / 100g", "vitamins": "Soluble Mucilage, Vitamin C, Folate", "benefits": "Lowers blood sugar spikes and aids gut lubrication.", "culinary_pairing": "Bendakaya Fry, Pulusu, and Crispy Kurkuri Bhindi."}',
        15: '{"calories": "41 kcal / 100g", "vitamins": "Beta-Carotene, Lutein, Vitamin A", "benefits": "Sharp eyesight, skin radiance, and cellular longevity.", "culinary_pairing": "Carrot Poriyal, Gajar Halwa, and fresh salads."}',
        16: '{"calories": "20 kcal / 100g", "vitamins": "Vitamin C, Bioflavonoids, Vitamin E", "benefits": "High collagen synthesis for skin elasticity and joint mobility.", "culinary_pairing": "Capsicum Besan Curry, Paneer Jalfrezi, and stir fries."}',
        17: '{"calories": "25 kcal / 100g", "vitamins": "Nasunin, Dietary Fiber, Potassium", "benefits": "Protects brain cell membranes and aids cholesterol management.", "culinary_pairing": "Signature Gutti Vankaya Kura, Baingan Bharta, and sambar."}',
        18: '{"calories": "14 kcal / 100g", "vitamins": "96% Hydration, Zinc, Thiamine", "benefits": "Ultimate cooling hydration, weight loss, and liver cleansing.", "culinary_pairing": "Sorakaya Pappu, Lauki Chana Dal, and morning juice."}',
        19: '{"calories": "17 kcal / 100g", "vitamins": "Charantin, Polypeptide-p, Vitamin C", "benefits": "Renowned clinical blood sugar regulator and blood purifier.", "culinary_pairing": "Karela Chips, Kakarakaya Vepudu, and sweet-tangy pulusu."}',
        20: '{"calories": "18 kcal / 100g", "vitamins": "Cellulose, Vitamin C, Peptides", "benefits": "Light on stomach, relieves acidity, and low glycemic index.", "culinary_pairing": "Beerakaya Paalu Kura, Ridge Gourd Pachadi, and dal."}'
    }

    for pid, n_info in NUTRITION_MAP.items():
        cursor.execute("""
            UPDATE products 
            SET nutrition_info = ? 
            WHERE id = ? AND (nutrition_info IS NULL OR nutrition_info = '')
        """, (n_info, pid))

    # 7. Seed sample reviews if empty
    review_count = cursor.execute("SELECT COUNT(*) as cnt FROM reviews").fetchone()['cnt']
    if review_count == 0:
        sample_reviews = [
            (1, 1, 5, "Extraordinarily juicy tomatoes! Cooked them into my Andhra Rasam and the flavor was farm-fresh.", "2026-09-08 14:20:00"),
            (1, 2, 5, "Very fresh and firm tomatoes, no bruises. Highly recommended for daily cooking.", "2026-09-07 10:15:00"),
            (9, 1, 5, "Crisp spinach with vibrant green leaves. Made Palak Paneer and everyone loved it!", "2026-09-08 18:30:00"),
            (2, 3, 5, "Authentic Nashik red onions. Crisp, pungent, and long shelf life.", "2026-09-06 16:45:00"),
            (7, 4, 5, "Incredible fresh coriander aroma! The roots were moist and stayed fresh for a week.", "2026-09-08 09:10:00"),
            (17, 2, 5, "Perfect tender brinjals for Gutti Vankaya curry. Zero seeds, delicious taste!", "2026-09-05 11:20:00")
        ]
        cursor.executemany("""
            INSERT INTO reviews (product_id, user_id, rating, comment, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, sample_reviews)

    # 8. Seed sample wallet welcome bonus if empty
    tx_count = cursor.execute("SELECT COUNT(*) as cnt FROM wallet_transactions").fetchone()['cnt']
    if tx_count == 0:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        wallet_seeds = [
            (1, 100.0, 'credit', '🎁 Welcome Farm Bonus Coins credited to your wallet!', now_str),
            (2, 100.0, 'credit', '🎁 Welcome Farm Bonus Coins credited to your wallet!', now_str),
            (3, 100.0, 'credit', '🎁 Welcome Farm Bonus Coins credited to your wallet!', now_str),
            (4, 100.0, 'credit', '🎁 Welcome Farm Bonus Coins credited to your wallet!', now_str)
        ]
        cursor.executemany("""
            INSERT INTO wallet_transactions (user_id, amount, type, description, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, wallet_seeds)

    # 9. Create and seed Coupons Table if missing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            min_order REAL DEFAULT 0.0,
            type TEXT DEFAULT 'flat',
            value REAL NOT NULL,
            max_discount REAL DEFAULT 0.0,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)
    coupon_count = cursor.execute("SELECT COUNT(*) as cnt FROM coupons").fetchone()['cnt']
    if coupon_count == 0:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        default_coupons = [
            ('FARM50', 199.0, 'flat', 50.0, 50.0, 'Flat ₹50 OFF on orders above ₹199', 1, now_str),
            ('VAMSI10', 99.0, 'percent', 10.0, 150.0, '10% OFF on fresh organic harvest (up to ₹150)', 1, now_str),
            ('FIRSTFARM', 150.0, 'percent', 15.0, 200.0, '15% Welcome Discount on your first farm order', 1, now_str),
            ('ORGANIC25', 299.0, 'percent', 25.0, 250.0, '25% Weekend Harvest Mega Saver (up to ₹250)', 1, now_str)
        ]
        cursor.executemany("""
            INSERT INTO coupons (code, min_order, type, value, max_discount, description, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, default_coupons)

    # 10. Create User Cart Table if missing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, product_id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_cart_uid ON user_cart(user_id)")
    
    # 11. Ensure user_addresses has unique constraint per user and trimmed address
    cursor.execute("""
        DELETE FROM user_addresses 
        WHERE id NOT IN (
            SELECT MIN(id) 
            FROM user_addresses 
            GROUP BY user_id, LOWER(TRIM(address))
        )
    """)
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_user_addresses_unique ON user_addresses(user_id, LOWER(TRIM(address)))")

    # 12. Ensure Store Manager phone is set to 7675960440
    cursor.execute("""
        UPDATE users 
        SET phone = '7675960440' 
        WHERE role = 'admin'
    """)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
