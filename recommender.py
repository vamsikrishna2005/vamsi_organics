import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'market.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Helper: Parse tags into a clean list
def parse_tags(tags_str):
    return [t.strip().lower() for t in tags_str.split(',') if t.strip()]

def get_all_products():
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return products

def get_user_purchases(user_id):
    conn = get_db_connection()
    purchases = conn.execute("""
        SELECT p.*, prod.name, prod.category, prod.tags, prod.price
        FROM purchases p
        JOIN products prod ON p.product_id = prod.id
        WHERE p.user_id = ?
        ORDER BY p.purchase_date DESC
    """, (user_id,)).fetchall()
    conn.close()
    return purchases

def get_ai_recommendations(user_id, limit=5):
    """
    Generate hybrid AI recommendations for a user:
    1. Content-based: Match products to user tag interests.
    2. Co-occurrence (Collaborative): Find items frequently bought by others who bought what this user bought.
    """
    purchases = get_user_purchases(user_id)
    if not purchases:
        # Cold start: Return popular items (highest stock or arbitrary top items)
        conn = get_db_connection()
        products = conn.execute("SELECT * FROM products ORDER BY stock DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [{"product": dict(p), "reason": "Popular fresh choice"} for p in products]

    # Purchased product IDs and categories
    purchased_product_ids = set(p['product_id'] for p in purchases)
    
    # --- 1. Content-Based recommendations ---
    # Build user tag-interest profile
    user_tag_scores = {}
    total_qty = 0
    for p in purchases:
        tags = parse_tags(p['tags'])
        qty = p['quantity']
        total_qty += qty
        for tag in tags:
            user_tag_scores[tag] = user_tag_scores.get(tag, 0) + qty

    # Normalize tag scores
    if total_qty > 0:
        for tag in user_tag_scores:
            user_tag_scores[tag] /= total_qty

    all_products = get_all_products()
    content_scores = []
    
    for prod in all_products:
        prod_id = prod['id']
        # Prioritize items not purchased yet, but also allow rebuy suggestions with lower weight
        is_new = prod_id not in purchased_product_ids
        
        prod_tags = parse_tags(prod['tags'])
        # Calculate matching score (dot product)
        score = sum(user_tag_scores.get(tag, 0) for tag in prod_tags)
        
        # Boost score slightly if it's in a category they buy often
        category_purchases = sum(1 for p in purchases if p['category'] == prod['category'])
        category_boost = min(category_purchases * 0.1, 0.5)
        score += category_boost
        
        if score > 0:
            reason = ""
            if is_new:
                # Find matching tag with highest user interest
                best_match_tag = max(prod_tags, key=lambda t: user_tag_scores.get(t, 0), default="")
                if best_match_tag:
                    reason = f"Based on your interest in {best_match_tag} items"
                else:
                    reason = f"Similar to your past {prod['category']} purchases"
            else:
                reason = "Frequently bought by you"
                score *= 0.8  # Slight penalty for already bought to encourage discovery

            content_scores.append({
                "product": dict(prod),
                "score": score,
                "reason": reason,
                "is_new": is_new
            })

    # Sort content recommendations by score descending
    content_scores.sort(key=lambda x: x['score'], reverse=True)

    # --- 2. Co-occurrence (Collaborative filtering) ---
    # Find items bought by other users who bought same items as current user
    co_occurrence_scores = {}
    conn = get_db_connection()
    
    # Find all transactions of other users
    other_purchases = conn.execute("""
        SELECT user_id, product_id 
        FROM purchases 
        WHERE user_id != ?
    """, (user_id,)).fetchall()
    
    # Build user-to-product mapping for other users
    other_user_items = {}
    for op in other_purchases:
        ouid = op['user_id']
        opid = op['product_id']
        if ouid not in other_user_items:
            other_user_items[ouid] = set()
        other_user_items[ouid].add(opid)
    
    # Calculate overlap and co-occurrence counts
    for opid in purchased_product_ids:
        # Find who else bought opid
        for ouid, items in other_user_items.items():
            if opid in items:
                # Add co-occurrence score to other items this user bought
                for other_item_id in items:
                    if other_item_id not in purchased_product_ids:
                        co_occurrence_scores[other_item_id] = co_occurrence_scores.get(other_item_id, 0) + 1
    
    # Fetch co-occurring products details
    co_occur_recommendations = []
    if co_occurrence_scores:
        placeholders = ','.join('?' for _ in co_occurrence_scores)
        co_products = conn.execute(
            f"SELECT * FROM products WHERE id IN ({placeholders})", 
            list(co_occurrence_scores.keys())
        ).fetchall()
        
        for prod in co_products:
            prod_id = prod['id']
            # Find which purchased item triggered this co-occurrence
            # For simplicity, we just lookup co-occurrence weight
            weight = co_occurrence_scores[prod_id]
            co_occur_recommendations.append({
                "product": dict(prod),
                "score": weight * 1.5, # Weight multiplier
                "reason": "Customers who bought similar items also bought this",
                "is_new": True
            })
    
    conn.close()

    # --- 3. Hybrid Merger ---
    # Merge both recommendation sources, averaging scores if an item appears in both
    merged = {}
    for item in content_scores:
        pid = item['product']['id']
        merged[pid] = item

    for item in co_occur_recommendations:
        pid = item['product']['id']
        if pid in merged:
            merged[pid]['score'] += item['score']
            merged[pid]['reason'] = "Highly recommended for you"
        else:
            merged[pid] = item

    recommendations_list = list(merged.values())
    recommendations_list.sort(key=lambda x: x['score'], reverse=True)

    return recommendations_list[:limit]


def get_predictive_notifications(user_id):
    """
    AI Predictive Alerts: Determine if a user needs to replenish items based on past order dates
    and standard item consumption lifespans.
    """
    # Standard Indian kitchen replenishment cycles in days
    LIFESPANS = {
        'Daily Essentials': 5,      # Tomatoes, onions, chillies, potatoes replenished every 4-6 days
        'Leafy Greens': 6,          # Palak, methi, coriander, mint replenished weekly
        'Fresh Vegetables': 8,       # Bhindi, capsicum, carrots, beans replenished every 7-10 days
        'Gourds & Roots': 10,       # Lauki, karela, turai replenished every 9-12 days
        'Vegetables': 8,
        'Spices & Pantry': 30,
        'Honey & Ghee': 30
    }

    purchases = get_user_purchases(user_id)
    if not purchases:
        return []

    # Get the latest purchase date for each product
    latest_purchases = {}
    for p in purchases:
        pid = p['product_id']
        raw_date = str(p['purchase_date']).strip()
        try:
            if ' ' in raw_date:
                p_date = datetime.strptime(raw_date, '%Y-%m-%d %H:%M:%S')
            else:
                p_date = datetime.strptime(raw_date, '%Y-%m-%d')
        except Exception:
            p_date = datetime.now()
            
        if pid not in latest_purchases or p_date > latest_purchases[pid]['date']:
            latest_purchases[pid] = {
                'date': p_date,
                'name': p['name'],
                'category': p['category'],
                'quantity': p['quantity']
            }

    now = datetime.now()
    alerts = []
    
    for pid, info in latest_purchases.items():
        days_since = (now - info['date']).days
        lifespan = LIFESPANS.get(info['category'], 14) # Default 14 days
        
        # If the user is near the end of the item's lifespan (within 80% to 150% of the lifespan)
        if lifespan * 0.8 <= days_since <= lifespan * 1.5:
            # Check if this alert was already sent (simulated: not checking database logs for duplicate spam in mock environment,
            # but we can return it as an active suggestion)
            alerts.append({
                "product_id": pid,
                "product_name": info['name'],
                "days_since": days_since,
                "message": f"Based on your purchase history, you might be running out of {info['name']}. Would you like to restock? 🥬",
                "type": "prediction"
            })
            
    return alerts


def trigger_restock_notification(product_id):
    """
    Admin-driven notification trigger: Finds past buyers of a product and alerts them
    that the item is freshly restocked.
    """
    conn = get_db_connection()
    
    # Find product name and details
    product = conn.execute("SELECT name, category FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        conn.close()
        return 0

    product_name = product['name']
    
    # Find all users who have bought this product or similar category products in the last 60 days
    users_to_notify = conn.execute("""
        SELECT DISTINCT user_id 
        FROM purchases 
        WHERE product_id = ?
    """, (product_id,)).fetchall()
    
    user_ids = [u['user_id'] for u in users_to_notify]
    
    # If no one has bought it, fall back to notifying users who buy the same category
    if not user_ids:
        users_in_category = conn.execute("""
            SELECT DISTINCT user_id 
            FROM purchases p
            JOIN products prod ON p.product_id = prod.id
            WHERE prod.category = ?
        """, (product['category'],)).fetchall()
        user_ids = [u['user_id'] for u in users_in_category]
        
    # Send notifications
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    notifications_created = 0
    
    for uid in user_ids:
        msg = f"Fresh arrival! {product_name} is newly harvested and back in stock! 🌿 Grab it before it's gone!"
        
        # Check if identical unread notification exists to avoid duplicates
        exists = conn.execute("""
            SELECT 1 FROM notifications 
            WHERE user_id = ? AND message = ? AND is_read = 0
        """, (uid, msg)).fetchone()
        
        if not exists:
            conn.execute("""
                INSERT INTO notifications (user_id, message, type, timestamp)
                VALUES (?, ?, ?, ?)
            """, (uid, msg, 'restock', now_str))
            notifications_created += 1
            
    conn.commit()
    conn.close()
    return notifications_created
